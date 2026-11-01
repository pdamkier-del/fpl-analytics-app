"""Frozen 2024/25 shot models on the available later provider shot sample."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from audit_capture_io import write_frame
from research_shot_finishing import gamma_predict, loss, metrics
from fpl_v1_1_model.experimental_shot_finishing import fit_shots

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(__doc__)
    ap.add_argument('--root',default='analysis/results/shot-finishing-20261020')
    ap.add_argument('--capture',default='data_v1_1/raw/live-captures/20261018T190738Z/fotmob/details')
    args=ap.parse_args();out=Path(args.root);selected=json.loads((out/'selection.json').read_text())['selected']
    train=pd.read_csv(out/'native_nonpenalty_shots.csv.gz')
    train['known']=pd.to_datetime(train.known,utc=True)
    train=train[~train.quarantined_credit_dispute]
    cut=pd.Timestamp('2026-08-01T00:00:00Z')
    identity={}
    source=ROOT/'data_v1_1/derived/season_2024_25_v1/all_competition_player_observations.jsonl.gz'
    with gzip.open(source,'rt') as stream:
        for line in stream:
            row=json.loads(line)
            if row.get('identity_status')=='mapped' and row.get('fpl_fixture_id') is not None:
                pid=str(row['provider_player_id']);canonical=row['player_uuid']
                if pid in identity and identity[pid]!=canonical:raise ValueError('Ambiguous provider player')
                identity[pid]=canonical
    rows=[];hashes={};match_ids=set()
    for path in sorted(Path(args.capture).glob('*.json')):
        raw=path.read_bytes();doc=json.loads(raw);g=doc.get('general',{})
        if g.get('leagueName')!='Premier League':continue
        if pd.Timestamp(g['matchTimeUTCDate'])<=cut:raise ValueError('Later evaluation must follow frozen fit')
        mid=str(g['matchId'])
        if mid in match_ids:raise ValueError('Duplicate later match')
        match_ids.add(mid);hashes[path.name]=hashlib.sha256(raw).hexdigest()
        for s in doc['content']['shotmap']['shots']:
            if s.get('isOwnGoal') or s.get('situation')=='Penalty':continue
            x=s.get('expectedGoals')
            if x is None or not np.isfinite(x) or not 0<=x<=1:raise ValueError('Missing later pre-shot xG')
            pid=str(s['playerId'])
            rows.append(dict(shot_id=str(s['id']),fixture_uuid=mid,player_uuid=identity.get(pid,'cold-provider-'+pid),
                             known_player=pid in identity,xg=x,goal=int(s['eventType']=='Goal'),shot_type=s['shotType']))
    target=pd.DataFrame(rows)
    if target.shot_id.duplicated().any():raise ValueError('Duplicate later shot')
    shared={h:fit_shots(train,cut,half_life=h) for h in {c['half'] for c in selected.values()}}
    c=selected['aggregate'];p=selected['player']
    model=fit_shots(train,cut,ridge=p['ridge'],half_life=p['half'])
    values=dict(native_xg=target.xg.to_numpy(),
                calibration=shared[selected['calibration']['half']].predict(target.xg,target.player_uuid),
                aggregate=gamma_predict(train,target,shared[c['half']],cut,c['half'],c['tau']),
                shot_player=model.predict(target.xg,target.player_uuid))
    frames=[]
    for mode,probability in values.items():
        b=target.copy();b['mode']=mode;b['probability']=probability;frames.append(b)
    pred=pd.concat(frames,ignore_index=True);write_frame(out/'later_predictions.csv.gz',pred)
    results={m:metrics(g) for m,g in pred.groupby('mode')};paired={};rng=np.random.default_rng(20261020)
    for reference in ('native_xg','calibration'):
        paired[reference]={}
        for mode,probability in values.items():
            d=loss(target.goal.to_numpy(),probability)-loss(target.goal.to_numpy(),values[reference])
            blocks=pd.DataFrame(dict(fixture=target.fixture_uuid,delta=d)).groupby('fixture').delta.agg(['sum','size']).to_numpy()
            draws=blocks[rng.integers(len(blocks),size=(3000,len(blocks)))].sum(1)
            paired[reference][mode]=dict(log_loss_delta=float(d.mean()),ci95=np.quantile(draws[:,0]/draws[:,1],[.025,.975]).tolist())
    report=dict(classification='FROZEN_SHOT_MODEL_LATER_PARTIAL_SEASON_CONDITIONAL_CHECK',
                training='2024/25 non-penalty shots only; no 2025/26 shot season available',
                model_frozen_before=str(cut),source_capture=args.capture,matches=len(match_ids),
                shots=len(target),identity_bridge_shots=int(target.known_player.sum()),
                trained_player_shots=int(target.player_uuid.isin(train.player_uuid).sum()),selected=selected,
                metrics=results,paired=paired,source_sha256=hashes,
                prediction_sha256=hashlib.sha256((out/'later_predictions.csv.gz').read_bytes()).hexdigest(),
                input_sha256={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ('selection.json','native_nonpenalty_shots.csv.gz')},
                code_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in (
                    'scripts/check_shot_finishing_later.py','src/fpl_v1_1_model/experimental_shot_finishing.py')},
                limitations=['Partial later-season coverage, not the entire current season',
                             'Old player estimates; intervening shot season unavailable',
                             'Provider IDs bridge known players; unseen players have neutral offsets',
                             'Conditional on observed pre-shot xG; not pre-match xP',
                             'No hyperparameters selected on later sample; not pristine whole-model validation'],
                production_changed=False,promotion_allowed=False)
    (out/'later_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(matches=len(match_ids),shots=len(target),metrics=results,paired=paired),indent=2))


if __name__=='__main__':main()
