"""Exercise the actual MM release CLI with frozen q/sub and recorded official news.

These are synthetic contract tests; they do NOT certify a 2026/27 live
locked MM forecast or the downstream PM/TS/chip chain.
"""
from __future__ import annotations
import json,subprocess,sys
from pathlib import Path
import pandas as pd
import pytest
from fpl_v1_1_model.live_availability_boundary import BOUNDARY_VERSION

ROOT=Path(__file__).resolve().parents[1]
LOCK=json.loads((ROOT/"config"/"fpl_locked_model.json").read_text())["version"]


def setup_rows(tmp_path, *,news_state="OUT", scoped_gw=6, observation="2026-10-10T08:20:00+00:00"):
    rows=[]
    for i in range(12):
        hard=i==11
        rows.append(dict(season="2026-27",gw=6,fixture_uuid="fixture-6",team_id=1,
            player_uuid=f"player-{i}",player=f"Player {i}",team="Example",
            pos="MID",cutoff="2026-10-10T09:00:00+00:00",
            p_start=0. if hard else 1.,xmins=4. if hard else 80.,
            start_minutes_mean=80.,mm_q_sub=.2,mm_sub_minutes=20.,
            team_news_state=news_state if hard else "AVAILABLE",
            team_news_availability_cap=0. if hard else 1.,
            expected_role="CM",xi_assigned_role="CM",xi_formation="4-3-3"))
    players=pd.DataFrame(rows)
    news=pd.DataFrame([dict(
        player_uuid=f"player-{i}",gw=scoped_gw,
        normalized_availability_state=rows[i]["team_news_state"],
        observed_at=observation,cutoff="2026-10-10T10:00:00+00:00",
        source="Official FPL bootstrap-static",
        source_id="bootstrap:2026-10-10T08:20:00Z",
        timing_verified=True) for i in range(12)])
    f=tmp_path/"raw.csv"
    nf=tmp_path/"official_news.csv"
    players.to_csv(f,index=False)
    news.to_csv(nf,index=False)
    return f,nf


def run_export(tmp_path,inp,news,*,gw=6,version=LOCK,live=True,season="2026-27"):
    out=tmp_path/"export"
    cmd=[sys.executable,str(ROOT/"scripts"/"export_mm_release.py"),
         "--input",str(inp),"--out",str(out),"--season",season,
         "--model-version",version]
    if live:
        cmd += ["--live-hard-availability","--origin-gw",str(gw),
                "--news-ledger",str(news)]
    result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    return result,out


@pytest.mark.parametrize("state",["OUT","SUSPENDED"])
def test_end_to_end_live_export_zeroes_ineligible_minutes_and_keeps_provenance(tmp_path,state):
    src,news=setup_rows(tmp_path,news_state=state)
    process,out=run_export(tmp_path,src,news)
    assert process.returncode==0,process.stderr
    data=pd.read_csv(out/"mm_forecasts.csv.gz")
    assert len(data)==12
    hard=data.loc[data.player_uuid=="player-11"].iloc[0]
    assert hard.xmins==0 and hard.p_start==0
    assert hard.mm_raw_xmins==4
    assert hard.live_effective_q_sub==0
    assert hard.mm_raw_q_sub==.2
    assert hard.live_eligibility_minutes_removed==4
    assert (data.loc[data.player_uuid!="player-11","xmins"]==80).all()
    meta=json.loads((out/"live_availability_policy.json").read_text())
    manifest=json.loads((out/"manifest.json").read_text())
    assert meta["availability_policy"]==BOUNDARY_VERSION
    assert meta["hard_unavailable_player_fixture_rows"]==1
    assert meta["raw_expected_minutes_removed"]==4
    assert meta["published_mm_sha256"]==manifest["sha256_csv_gz"]
    assert meta["full_final_chain_live_certified"] is False
    assert manifest["exact11_max_abs_error"]==0


def test_rejects_unscoped_news_and_later_gw_without_future_certification(tmp_path):
    src,news=setup_rows(tmp_path,scoped_gw=7)
    proc,out=run_export(tmp_path,src,news)
    assert proc.returncode!=0
    assert "origin GW" in proc.stderr
    assert not (out/"manifest.json").exists()


def test_rejects_news_captured_after_inference_cutoff(tmp_path):
    src,news=setup_rows(tmp_path,observation="2026-10-10T09:30:00+00:00")
    proc,out=run_export(tmp_path,src,news)
    assert proc.returncode!=0
    assert "Post-cutoff" in proc.stderr
    assert not (out/"manifest.json").exists()


def test_rejects_official_state_mismatch(tmp_path):
    src,news=setup_rows(tmp_path)
    ledger=pd.read_csv(news)
    ledger.loc[11,"normalized_availability_state"]="AVAILABLE"
    ledger.to_csv(news,index=False)
    proc,out=run_export(tmp_path,src,news)
    assert proc.returncode!=0
    assert "availability differs" in proc.stderr
    assert not (out/"manifest.json").exists()


def test_rejects_modified_raw_frozen_output(tmp_path):
    src,news=setup_rows(tmp_path)
    frame=pd.read_csv(src)
    frame.loc[11,"xmins"]=0
    frame.to_csv(src,index=False)
    proc,out=run_export(tmp_path,src,news)
    assert proc.returncode!=0
    assert "raw minutes do not match" in proc.stderr
    assert not (out/"manifest.json").exists()


def test_rejects_current_season_without_boundary(tmp_path):
    src,news=setup_rows(tmp_path)
    proc,out=run_export(tmp_path,src,news,live=False)
    assert proc.returncode!=0
    assert "Current-season" in proc.stderr
    assert not (out/"manifest.json").exists()


def test_rejects_mismatched_locked_model_version(tmp_path):
    src,news=setup_rows(tmp_path)
    proc,out=run_export(tmp_path,src,news,version="UNLOCKED")
    assert proc.returncode!=0
    assert "model-version differs" in proc.stderr
    assert not (out/"manifest.json").exists()


def test_rejects_missing_trained_cameo_probability(tmp_path):
    src,news=setup_rows(tmp_path)
    frame=pd.read_csv(src).drop(columns=["mm_q_sub"])
    frame.to_csv(src,index=False)
    proc,out=run_export(tmp_path,src,news)
    assert proc.returncode!=0
    assert "Missing genuine frozen MM output field" in proc.stderr
    assert not (out/"manifest.json").exists()


def test_historical_export_path_remains_unchanged(tmp_path):
    src,news=setup_rows(tmp_path)
    data=pd.read_csv(src).iloc[:11].copy()
    data["season"]="2025-26"
    data.to_csv(src,index=False)
    proc,out=run_export(tmp_path,src,news,live=False,season="2025-26")
    assert proc.returncode==0,proc.stderr
    assert (out/"manifest.json").exists()
    assert not (out/"live_availability_policy.json").exists()
