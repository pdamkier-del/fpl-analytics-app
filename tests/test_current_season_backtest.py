import hashlib,json
import pandas as pd
import pytest
from backtest_current_season_b import verify_origin,BASE,warmup_status

def fixture(tmp_path):
    inputs=tmp_path/'inputs';source=tmp_path/'source';inputs.mkdir();(source/BASE).mkdir(parents=True)
    boot=dict(events=[dict(id=6,deadline_time='2026-10-10T10:00:00Z')],elements=[dict(id=1,team=10,element_type=1)])
    fx=[dict(id=51,event=6,team_h=10,team_a=20,kickoff_time='2026-10-10T12:00:00Z',started=False)]
    prov=dict(data_at='2026-10-10T09:00:00Z',origin_deadline='2026-10-10T10:00:00Z')
    for name,obj in [('bootstrap',boot),('fixtures',fx)]:
        (inputs/(name+'.json')).write_text(json.dumps(obj));prov[name+'_sha256']=hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();prov[name+'_observed_at']='2026-10-10T08:00:00Z'
    (inputs/'provenance.json').write_text(json.dumps(prov))
    pd.DataFrame([dict(gw=6,cutoff=prov['data_at'],fixture_uuid='live-2026-27-fpl-51',team_id=10,fpl_element=1)]).to_csv(inputs/'pm.csv.gz',index=False)
    for name in ['player_fixture_observations','verified_penalty_attempts','verified_penalty_team_sides']:
        pd.DataFrame([dict(available_at='2026-10-09T20:00:00Z')]).to_csv(source/BASE/(name+'.csv.gz'),index=False)
    return inputs,source

def test_original_past_capsule_accepted_without_live_clock_bypass(tmp_path):
    i,s=fixture(tmp_path);assert verify_origin(i,s)[3]==6

@pytest.mark.parametrize('col',['y','minutes','started','actual_start','actual_minutes','total_points'])
def test_target_truth_fields_rejected_even_if_finite(tmp_path,col):
    i,s=fixture(tmp_path);f=pd.read_csv(i/'pm.csv.gz');f[col]=0;f.to_csv(i/'pm.csv.gz',index=False)
    with pytest.raises(ValueError,match='Target outcomes'):verify_origin(i,s)

def test_unpopulated_legacy_target_columns_are_not_labels(tmp_path):
    i,s=fixture(tmp_path);f=pd.read_csv(i/'pm.csv.gz');f['actual_minutes']=float('nan');f.to_csv(i/'pm.csv.gz',index=False)
    assert verify_origin(i,s)[3]==6

@pytest.mark.parametrize('change',['cutoff','past_labels','roster','source_hash','source_time','started_fixture'])
def test_no_future_or_unverified_source_can_enter_replay(tmp_path,change):
    i,s=fixture(tmp_path)
    if change in ['cutoff','source_hash','source_time']:
        p=json.loads((i/'provenance.json').read_text())
        if change=='cutoff':p['data_at']=p['origin_deadline']
        elif change=='source_hash':p['bootstrap_sha256']='wrong'
        else:p['bootstrap_observed_at']=p['data_at']
        (i/'provenance.json').write_text(json.dumps(p))
    elif change=='past_labels':pd.DataFrame([dict(available_at='2026-10-10T09:00:00Z')]).to_csv(s/BASE/'player_fixture_observations.csv.gz',index=False)
    elif change=='roster':
        f=pd.read_csv(i/'pm.csv.gz');f['fpl_element']=2;f.to_csv(i/'pm.csv.gz',index=False)
    else:
        fs=json.loads((i/'fixtures.json').read_text());fs[0]['started']=True;(i/'fixtures.json').write_text(json.dumps(fs))
        p=json.loads((i/'provenance.json').read_text());p['fixtures_sha256']=hashlib.sha256(json.dumps(fs,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();(i/'provenance.json').write_text(json.dumps(p))
    with pytest.raises(ValueError):verify_origin(i,s)

def test_model_warmup_is_reported_not_backfilled_with_future_matches():
    for gw in range(1,6):
        r=warmup_status(gw,5);assert r['status']=='unsupported_model_warmup' and r['maximum_prior_league_matches_per_team']<r['minimum_prior_team_matches']
    assert warmup_status(6,5)['status']=='pending_backtest'

def test_real_frozen_keeper_kernel_requires_five_prior_matches():
    from fpl_v1_1_model.deadline_keeper import keeper_saves_at_deadline
    from backtest_current_season_b import ROOT
    fit=json.loads((ROOT/'analysis/results/joint-team-keeper-recovery-v1/keeper_fit.json').read_text())
    sides=pd.DataFrame([dict(fixture_uuid='target',team_id=10,opponent_team_id=20,was_home=True)])
    def history(n):
        return pd.DataFrame([dict(season='2026-27',fixture_uuid=f'past-{g}',team_id=t,opponent_team_id=20 if t==10 else 10,kickoff_at=f'2026-09-{g:02d}T12:00:00Z',available_at=f'2026-09-{g:02d}T16:00:00Z',shots_on_target=4,shots_on_target_conceded=3)for g in range(1,n+1)for t in [10,20]])
    with pytest.raises(ValueError,match='Insufficient source-definition SOT history'):
        keeper_saves_at_deadline(history(4),sides,'2026-10-01T00:00:00Z',fit,season='2026-27')
    out=keeper_saves_at_deadline(history(5),sides,'2026-10-01T00:00:00Z',fit,season='2026-27')
    assert len(out)==1 and out.lambda_saves.gt(0).all()

def test_probability_export_repairs_only_float_roundoff():
    from backtest_current_season_b import probability
    assert probability(-8.88e-16)==0 and probability(1+8.88e-16)==1
    assert probability(.83)==.83
    with pytest.raises(ValueError):probability(-.001)
    with pytest.raises(ValueError):probability(1.001)

@pytest.mark.parametrize('bad',['hash','member','origin','url'])
def test_original_release_integrity_is_required_before_restoring(tmp_path,bad):
    import zipfile,io
    from prepare_season_backtest_capsule import prepare
    raw=b'source';name='../escaped.json'if bad=='member'else'work/live-final-model/bootstrap.json'
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w')as z:z.writestr(name,raw)
    payload=stream.getvalue();manifest=dict(origin_gw=8 if bad=='origin'else 7,archive_url='https://untrusted.invalid/release.zip'if bad=='url'else'https://github.com/pdamkier-del/fpl-analytics-app/releases/download/test/diagnostic-snapshot.zip',archive_sha256='bad'if bad=='hash'else hashlib.sha256(payload).hexdigest(),files={name:hashlib.sha256(raw).hexdigest()})
    path=tmp_path/'source.json';path.write_text(json.dumps(manifest));path.with_suffix('.zip').write_bytes(payload)
    with pytest.raises(ValueError):prepare(7,tmp_path/'isolated',release_manifest=path)
    assert not (tmp_path/'isolated/escaped.json').exists()
