"""Score truly pre-deadline archived predictions only after official final labels.

Never fits a correction, backdates captures, or uses an in-progress match as
truth. Empty/pending cohorts remain pending rather than reported as perfect.
"""
import argparse,gzip,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from archive_prospective_player_forecast import utc


def score(manifest,records,outcomes,*,asof):
    now=utc(asof);captured=utc(manifest['recorded_at']);deadline=utc(manifest['origin_deadline']);data_at=utc(manifest['data_asof'])
    if manifest['schema']!='B-prospective-player-ledger-v1':raise ValueError('Unknown ledger schema')
    if len(records)!=manifest['records']:raise ValueError('Ledger row count mismatch')
    if outcomes.duplicated(['season','fixture_uuid','player_uuid']).any():raise ValueError('Duplicate final label')
    required={'season','fixture_uuid','player_uuid','team_id','is_final','known_at','kickoff','started','minutes','total_points'}
    if required-set(outcomes):raise ValueError('Incomplete final result contract')
    available={}
    for r in outcomes.itertuples():
        if str(r.is_final).lower()not in ('true','1'):continue
        known,kick=utc(r.known_at),utc(r.kickoff)
        if known>now or known<kick:continue
        if not math.isfinite(float(r.minutes))or not 0<=r.minutes<=90 or r.started not in (0,1,True,False) or not math.isfinite(float(r.total_points)):
            raise ValueError('Invalid official final values')
        available[(r.season,r.fixture_uuid,r.player_uuid)]=r
    seen=set();joined=[];pending=0;excluded=0
    for p in records:
        key=(manifest['season'],p['fixture_uuid'],p['player_uuid'])
        if key in seen:raise ValueError('Duplicate archived prediction')
        seen.add(key)
        eligible=p['eligible_for_pre_match_validation'] and data_at<=captured<deadline and captured<utc(p['kickoff']) and captured<=now and p.get('fpl_code')is not None
        if not eligible:excluded+=1;continue
        actual=available.get(key)
        if actual is None:pending+=1;continue
        if actual.team_id!=p['team_id']or utc(actual.kickoff)!=utc(p['kickoff']):raise ValueError('Prediction/result identity mismatch')
        for name in ['p_start','p_play','p60','p90']:
            if not math.isfinite(p[name])or not 0<=p[name]<=1:raise ValueError('Invalid archived probability')
        if not p['p90']<=p['p60']<=p['p_play']+1e-10:raise ValueError('Inconsistent minute probabilities')
        if not math.isfinite(p['expected_minutes'])or not 0<=p['expected_minutes']<=90 or not math.isfinite(p['xp']):raise ValueError('Invalid archived expectation')
        joined.append(dict(fixture=p['fixture_uuid'],position=p['position'],p_start=p['p_start'],p0=1-p['p_play'],p60=p['p60'],p90=p['p90'],ystart=int(actual.started),y0=int(actual.minutes==0),y60=int(actual.minutes>=60),y90=int(actual.minutes==90),minute_error=p['expected_minutes']-actual.minutes,xp_error=p['xp']-actual.total_points))
    f=pd.DataFrame(joined);metrics=[];bins=[]
    if len(f):
        for name,pcol,ycol in [('start','p_start','ystart'),('0','p0','y0'),('60','p60','y60'),('90','p90','y90')]:
            p=f[pcol].to_numpy();y=f[ycol].to_numpy();q=np.clip(p,1e-12,1-1e-12)
            metrics.append(dict(event=name,rows=len(f),brier=float(((p-y)**2).mean()),bias=float((p-y).mean()),log_loss=float(-(y*np.log(q)+(1-y)*np.log1p(-q)).mean())))
            bucket=np.minimum((10*p).astype(int),9)
            for i in range(10):
                m=bucket==i
                if m.any():bins.append(dict(event=name,bin=i,rows=int(m.sum()),predicted=float(p[m].mean()),observed=float(y[m].mean())))
    return dict(version='B-prospective-calibration-v1',forecast_sha256=manifest['forecast_sha256'],recorded_at=manifest['recorded_at'],scored_at=now.isoformat(),status='scored'if len(f)else'pending_final_matches'if pending else'no_eligible_predictions',scored_rows=len(f),pending_rows=pending,excluded_rows=excluded,metrics=metrics,reliability=bins,minute_mae=float(abs(f.minute_error).mean())if len(f)else None,minute_bias=float(f.minute_error.mean())if len(f)else None,xp_mae=float(abs(f.xp_error).mean())if len(f)else None,xp_bias=float(f.xp_error.mean())if len(f)else None,model_recalibrated=False,production_changed=False,full_model_certification=False)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ledger',type=Path,required=True);ap.add_argument('--outcomes',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    manifest=json.loads((args.ledger/'prospective-ledger-manifest.json').read_text());path=args.ledger/manifest['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256']:raise ValueError('Ledger checksum mismatch')
    records=[json.loads(l)for l in gzip.open(path,'rt')];outcomes=pd.read_csv(args.outcomes)
    result=score(manifest,records,outcomes,asof=datetime.now(timezone.utc).isoformat());result['outcomes_sha256']=hashlib.sha256(args.outcomes.read_bytes()).hexdigest();result['scorer_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ('metrics','reliability')}))

if __name__=='__main__':main()
