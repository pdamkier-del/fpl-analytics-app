"""Freeze completed diagnostic replays and explicit unsupported origins."""
import argparse,gzip,hashlib,json
from pathlib import Path
import pandas as pd
from backtest_current_season_b import ROOT,BASE,warmup_status,digest,probability

def freeze(work,out):
    work,out=Path(work),Path(out);out.mkdir(parents=True,exist_ok=True)
    fit=ROOT/'analysis/results/joint-team-keeper-recovery-v1/keeper_fit.json';minimum=json.loads(fit.read_text())['selection_protocol']['min_history_matches']
    weeks=[warmup_status(gw,minimum)for gw in range(1,minimum+1)]
    for row in weeks:
        p=ROOT/'work/live-final-model/predeadline_2026_archives'/f"gw{row['gw']}.json";archive=json.loads(p.read_text());row.update(roster_snapshot=archive['evidence']['snapshot_at_utc'],archived_players=len(archive['players']),roster_source_sha256=archive['evidence']['source_sha256'],roster_source_url=archive['evidence'].get('source_url'))
    for gw in [6,7,8]:
        case=work/f'gw{gw}';doc=json.loads((case/'output/forecast.json').read_text());bootstrap=json.loads((case/'inputs/bootstrap.json').read_text());official={p['id']:p for p in bootstrap['elements']}
        doc['season']='2026-27'
        # Enrich only stable identity metadata from the same retained bootstrap.
        # This does not alter any simulated quantity or source/creation clock.
        for r in doc['players']:
            code=official[r['player_id']]['code']
            if r.get('fpl_code',code)!=code:raise ValueError('Stable code annotation conflicts')
            r['fpl_code']=code
        repaired=[]
        for r in doc['players']:
            for field in ['p_start','p_play','p60','p90']:
                original=r[field];r[field]=probability(original)
                if original!=r[field]:repaired.append(dict(player_id=r['player_id'],field=field,absolute_difference=abs(original-r[field])))
        doc['probability_roundoff_export']={'tolerance':1e-12,'repaired_values':len(repaired),'maximum_absolute_difference':max((r['absolute_difference']for r in repaired),default=0.)}
        for r in doc['players']:
            if abs(r['expected_minutes']-r['pm_expected_minutes'])>1e-8:raise ValueError('Backtest MM/PM mean mismatch')
        audit=json.loads((case/'output/audit.json').read_text())
        if len(audit)!=20 or not all(abs(t['analytic_gk_minutes']-90)<1e-8 for t in audit):raise ValueError('GK90 coverage failed')
        if not all(pd.Timestamp(t['last_label_known_at'])<pd.Timestamp(doc['cutoff'])for t in audit):raise ValueError('Future duration history')
        for t in audit:
            p=t['physical_timeline']
            if p['max_substitutions']>5:raise ValueError('Substitution limit failed')
        raw=gzip.compress((json.dumps(doc,sort_keys=True,allow_nan=False)+'\n').encode(),mtime=0);name=f'gw{gw}.json.gz';(out/name).write_bytes(raw)
        auditname=f'gw{gw}-audit.json.gz';(out/auditname).write_bytes(gzip.compress(json.dumps(audit,sort_keys=True,allow_nan=False).encode(),mtime=0))
        weeks.append(dict(gw=gw,status='replayed',file=name,sha256=hashlib.sha256(raw).hexdigest(),audit_file=auditname,audit_sha256=digest(out/auditname),cutoff=doc['cutoff'],generated_at=doc['generated_at'],registered_players=len(doc['players']),source_hashes=doc['source_hashes']))
        witness=case/'release-witness.json'
        if witness.exists():
            witness_name=f'gw{gw}-source-release.json';(out/witness_name).write_bytes(witness.read_bytes());weeks[-1].update(release_witness=witness_name,release_witness_sha256=digest(out/witness_name))
    manifest=dict(schema='B-current-season-backtest-index-v1',season='2026-27',scope='Retrospective fixed B policy; later-selected model, reused diagnostic, not original forecasts or independent holdout.',model_source='03d5c4d4777b44bc1d37884a1cf4dde106b45cab',minimum_prior_team_matches=minimum,minimum_history_source_sha256=digest(fit),warmup_guard='fpl_v1_1_model.deadline_keeper.keeper_saves_at_deadline enforces selected protocol min_history_matches',weeks=weeks,notes=['No future match is used as warm-up for GW1–5.','Predeadline input packs verified for GW6–8; fixed B MM, NP/penalty head, joint roles and physical normal-match timeline reused.','Every actual input cutoff is displayed. Verified later predeadline release capsules are used where available; there is no invented deadline timestamp.','History availability uses kickoff+3/4h proxies. Some historical role reconstructions were built later; retrospective provider revisions cannot be fully excluded.','Per-player analytic MM and PM minute expectations agree; realized FPL-minute totals are not forced to physical budgets.','Production, private teams and prospective accuracy series are unchanged.'])
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();freeze(a.work,a.out)
