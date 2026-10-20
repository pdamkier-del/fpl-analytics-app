"""Provider-internal shot-level feasibility and temporal conversion test."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from audit_capture_io import write_frame
from research_pm_conversion import deadlines
from fpl_v1_1_model.experimental_shot_finishing import fit_shots

ROOT = Path(__file__).resolve().parents[1]
HALVES = (None, 90., 365.)


def extract(db):
    mapping, fixture_ids = {}, {}
    source = ROOT/'data_v1_1/derived/season_2024_25_v1/all_competition_player_observations.jsonl.gz'
    with gzip.open(source, 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('fpl_fixture_id') is not None and row.get('identity_status') == 'mapped':
                key = str(row['provider_match_id']), str(row['provider_player_id'])
                if key in mapping and mapping[key] != row['player_uuid']:
                    raise ValueError('Ambiguous player identity')
                mapping[key] = row['player_uuid']
                fixture_ids[key[0]] = int(row['fpl_fixture_id'])
    with sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro', uri=True) as con:
        fixtures = pd.read_sql_query("SELECT * FROM fixtures WHERE season='2024-25'", con)
        times = pd.read_sql_query("SELECT fixture_uuid, MIN(gw) gw, COUNT(DISTINCT gw) ngw, MIN(kickoff_at) kickoff, COUNT(DISTINCT kickoff_at) nkick FROM player_fixture_observations WHERE season='2024-25' AND is_final=1 GROUP BY fixture_uuid", con)
    if times.ngw.ne(1).any() or times.nkick.ne(1).any():
        raise ValueError('Ambiguous match chronology')
    fixture_map = fixtures.merge(times, on='fixture_uuid', validate='one_to_one').set_index('fpl_fixture_id')
    counts, hashes, rows, types, events = Counter(), {}, [], Counter(), Counter()
    for path in sorted((ROOT/'data_v1_1/raw/season_2024_25_v1/fotmob/details').glob('*.json')):
        raw = path.read_bytes()
        doc = json.loads(raw)
        general = doc.get('general', {})
        if general.get('leagueName') != 'Premier League':
            continue
        counts['matches'] += 1
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
        mid = str(general['matchId'])
        fixture = fixture_map.loc[fixture_ids[mid]]
        for shot in doc['content']['shotmap']['shots']:
            counts['all_shots'] += 1
            types[shot.get('shotType')] += 1
            events[shot.get('eventType')] += 1
            if shot.get('expectedGoals') is None:
                counts['missing_xg_all'] += 1
            if shot.get('isOwnGoal'):
                counts['own_goals_excluded'] += 1
                continue
            if shot.get('situation') == 'Penalty':
                counts['penalties_excluded'] += 1
                continue
            pid = mapping.get((mid, str(shot.get('playerId'))))
            xg = shot.get('expectedGoals')
            if pid is None or xg is None or not np.isfinite(xg) or not 0 <= xg <= 1:
                raise ValueError('Unmapped/incomplete native non-penalty shot')
            kickoff = pd.Timestamp(fixture.kickoff)
            rows.append(dict(shot_id=str(shot['id']), provider_match_id=mid,
                             fixture_uuid=fixture.fixture_uuid, player_uuid=pid,
                             player_name=shot.get('playerName'), gw=int(fixture.gw),
                             kickoff=kickoff, known=kickoff+pd.Timedelta(hours=4),
                             xg=float(xg), goal=int(shot['eventType']=='Goal'),
                             shot_type=shot['shotType'], situation=shot['situation']))
    frame = pd.DataFrame(rows)
    if frame.duplicated(['provider_match_id', 'shot_id']).any() or counts['matches'] != 380:
        raise ValueError('Incomplete/duplicate shot coverage')
    dispute = json.loads((ROOT/'analysis/results/pm-research-20261015/raw_nonpenalty_source_audit.json').read_text())['credit_discrepancies']
    bad = {(d['fixture_uuid'], d['player_uuid']) for d in dispute}
    frame['quarantined_credit_dispute'] = [(a,b) in bad for a,b in zip(frame.fixture_uuid, frame.player_uuid)]
    audit = dict(counts=counts, shot_types=types, outcomes=events,
                 nonpenalty_shots=len(frame), nonpenalty_goals=int(frame.goal.sum()),
                 quarantine_rows=int(frame.quarantined_credit_dispute.sum()),
                 players=int(frame.player_uuid.nunique()),
                 source_files=hashes, mapping_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                 excluded_predictors=['expectedGoalsOnTarget','isOnTarget','goalCrossedY','goalCrossedZ','eventType'],
                 predictors=['expectedGoals','canonical_player_uuid'])
    return frame, audit


def weights(frame, cutoff, half):
    return np.ones(len(frame)) if half is None else np.exp2(
        -(cutoff-frame.known).dt.total_seconds().to_numpy()/86400/half)


def gamma_predict(train, target, fit, cutoff, half, tau):
    w = weights(train, cutoff, half)
    state = pd.DataFrame(dict(player_uuid=train.player_uuid,
                              goals=w*train.goal.to_numpy(),
                              exposure=w*fit.predict(train.xg,train.player_uuid))).groupby('player_uuid').sum()
    factor = (state.goals+tau)/(state.exposure+tau)
    return np.clip(fit.predict(target.xg,target.player_uuid)*target.player_uuid.map(factor).fillna(1.).to_numpy(),1e-9,1-1e-9)


def loss(y,p):
    p = np.clip(np.asarray(p),1e-9,1-1e-9)
    return -(y*np.log(p)+(1-y)*np.log1p(-p))


def metrics(frame):
    y = frame.goal.to_numpy()
    p = frame.probability.to_numpy()
    return dict(shots=len(frame),goals=int(y.sum()),log_loss=float(loss(y,p).mean()),
                brier=float(np.mean((p-y)**2)),expected_goals=float(p.sum()),
                bias_per_shot=float(np.mean(p-y)))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--db', default='work/core.sqlite3')
    parser.add_argument('--mm-root', required=True)
    parser.add_argument('--out', default='analysis/results/shot-finishing-20261020')
    parser.add_argument('--include-disputed', action='store_true')
    parser.add_argument('--frozen-selection')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    frame,audit = extract(args.db)
    write_frame(out/'native_nonpenalty_shots.csv.gz',frame)
    if not args.include_disputed:
        frame = frame[~frame.quarantined_credit_dispute].copy()
    cuts = deadlines(Path(args.mm_root))['2024-25']
    for gw in range(16,39):
        if frame.loc[frame.gw.eq(gw),'kickoff'].lt(cuts[gw]).any():
            raise ValueError('Target match precedes original forecast cutoff')
    candidates = ([dict(family='calibration',half=h) for h in HALVES]
                  +[dict(family='aggregate',half=h,tau=t) for h in HALVES for t in (5.,20.,80.)]
                  +[dict(family='player',half=h,ridge=r) for h in HALVES for r in (1.,5.,20.,80.)])
    if args.frozen_selection:
        selected=json.loads(Path(args.frozen_selection).read_text())['selected']
        selection=dict(selected=selected,frozen_source_sha256=hashlib.sha256(Path(args.frozen_selection).read_bytes()).hexdigest())
    else:
        development=[]
        for gw in range(16,22):
            cut = cuts[gw]
            train,target = frame[frame.known.lt(cut)],frame[frame.gw.eq(gw)]
            shared = {h:fit_shots(train,cut,half_life=h) for h in HALVES}
            for i,cfg in enumerate(candidates):
                fit = shared[cfg['half']]
                if cfg['family']=='calibration': p = fit.predict(target.xg,target.player_uuid)
                elif cfg['family']=='aggregate': p = gamma_predict(train,target,fit,cut,cfg['half'],cfg['tau'])
                else: p = fit_shots(train,cut,ridge=cfg['ridge'],half_life=cfg['half']).predict(target.xg,target.player_uuid)
                development.append(dict(gw=gw,config=i,shots=len(target),nll_sum=float(loss(target.goal.to_numpy(),p).sum())))
            print('development GW',gw,'completed',flush=True)
        dev=pd.DataFrame(development).groupby('config')[['shots','nll_sum']].sum()
        score=dev.nll_sum/dev.shots
        selected={family:candidates[min((i for i,c in enumerate(candidates) if c['family']==family),key=lambda i:score.loc[i])]
                  for family in ('calibration','aggregate','player')}
        selection=dict(selected=selected,development='2024/25 GW16-21; pre-cutoff training only',
                       grid=[dict(**cfg,log_loss=float(score.loc[i])) for i,cfg in enumerate(candidates)])
    (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    predictions=[]
    for gw in range(22,39):
        cut=cuts[gw]
        train,target=frame[frame.known.lt(cut)],frame[frame.gw.eq(gw)]
        fits={h:fit_shots(train,cut,half_life=h) for h in {c['half'] for c in selected.values()}}
        cfg=selected['aggregate']
        fitted_player=fit_shots(train,cut,ridge=selected['player']['ridge'],half_life=selected['player']['half'])
        values=dict(native_xg=target.xg.to_numpy(),calibration=fits[selected['calibration']['half']].predict(target.xg,target.player_uuid),
                    aggregate=gamma_predict(train,target,fits[cfg['half']],cut,cfg['half'],cfg['tau']),
                    shot_player=fitted_player.predict(target.xg,target.player_uuid),
                    aggregate_matched_calibration=fits[cfg['half']].predict(target.xg,target.player_uuid),
                    player_matched_calibration=fits[selected['player']['half']].predict(target.xg,target.player_uuid))
        for mode,p in values.items():
            block=target.copy();block['mode']=mode;block['probability']=p;block['cutoff']=str(cut)
            predictions.append(block)
        print('evaluation GW',gw,'completed',flush=True)
    predicted=pd.concat(predictions,ignore_index=True)
    write_frame(out/'test_predictions.csv.gz',predicted)
    results={mode:metrics(g) for mode,g in predicted.groupby('mode')}
    paired={};rng=np.random.default_rng(20261020)
    for reference in ('native_xg','calibration','player_matched_calibration'):
        baseline=predicted[predicted['mode'].eq(reference)][['shot_id','probability']]
        for mode,g in predicted.groupby('mode'):
            pair=g.merge(baseline,on='shot_id',validate='one_to_one',suffixes=('','_base'))
            for metric,d in [('log_loss',loss(pair.goal,pair.probability)-loss(pair.goal,pair.probability_base)),
                             ('brier',(pair.probability-pair.goal)**2-(pair.probability_base-pair.goal)**2)]:
                blocks=pd.DataFrame(dict(fixture=pair.fixture_uuid,delta=d)).groupby('fixture').delta.agg(['sum','size']).to_numpy()
                draw=blocks[rng.integers(len(blocks),size=(3000,len(blocks)))].sum(1)
                paired[f'{mode}_vs_{reference}_{metric}']=dict(delta=float(np.mean(d)),ci95=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist())
    calibration={}
    for mode,g in predicted.groupby('mode'):
        bins=pd.cut(g.probability,[-np.inf,.05,.1,.2,.4,.6,.8,np.inf])
        calibration[mode]=[dict(bin=str(k),shots=len(v),predicted=float(v.probability.mean()),actual=float(v.goal.mean()))
                           for k,v in g.groupby(bins,observed=True)]
    report=dict(classification='CONDITIONAL_SHOT_CONVERSION_NOT_PREMATCH_XP',source_audit=audit,
                quarantine_credit_dispute=not args.include_disputed,
                selected=selected,evaluation='2024/25 GW22-38 rolling refit; hyperparameters fixed from GW16-21',
                metrics=results,paired=paired,calibration=calibration,
                by_shot_type={mode:{t:metrics(v) for t,v in g.groupby('shot_type')} for mode,g in predicted.groupby('mode')},
                source_hashes={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ('selection.json','native_nonpenalty_shots.csv.gz','test_predictions.csv.gz')},
                code_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in (
                    'scripts/research_shot_finishing.py','src/fpl_v1_1_model/experimental_shot_finishing.py')},
                limitations=['One season; no multi-season stable finishing certification','Reused historical research period, not pristine validation',
                             'Target pre-shot xG is conditioned on, not a known pre-match input','No failed-shot creator links',
                             'Kickoff+4h availability proxy; actual historical release clocks not verified',
                             'Player effects can absorb omitted context/source biases','Goal-credit discrepancy flagged; no FPL-point equivalence claimed'],
                production_changed=False,promotion_allowed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(selected=selected,metrics=results),indent=2))


if __name__=='__main__':main()
