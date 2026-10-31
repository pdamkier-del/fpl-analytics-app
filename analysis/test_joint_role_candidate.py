"""Paired, prior-only role transport gate; never publishes or edits B defaults."""
import argparse
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from research_europe_rotation import source_frames
from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
from fpl_v1_1_model.experimental_joint_role_assignment import fractional_assignment,role_scores
from fpl_v1_1_model.experimental_role_importance import importance
from fpl_v1_1_model.role_classifier import template,canonical
from run_2024_25_conditional_mm import jsonl_gz,team_name_map,norm

ROOT=Path(__file__).resolve().parents[1]


def histories(core):
    measured=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv')
    measured['season']='2025-26'
    measured['competition']='prem';measured['round_name']=measured.gw
    measured=measured.merge(core[['season','fixture_uuid','player_uuid','minutes']],
                            on=['season','fixture_uuid','player_uuid'],validate='one_to_one')
    derived=ROOT/'data_v1_1/derived/season_2024_25_v1'
    tmap=team_name_map(jsonl_gz(derived/'deadline_player_candidates.jsonl.gz'))
    observed={(str(r['match_id']),str(r['player_uuid'])):r for r in jsonl_gz(derived/'all_competition_player_observations.jsonl.gz') if r.get('player_uuid')}
    matches={str(r['match_id']):r for r in jsonl_gz(derived/'all_competition_match_actuals.jsonl.gz')}
    raw=pd.DataFrame(jsonl_gz(derived/'raw_role_inputs.jsonl.gz'))
    raw['team_id']=raw.team.map(lambda v:tmap.get(norm(v)))
    rows=[]
    for (match,team,form),g in raw.dropna(subset=['team_id']).groupby(['match_id','team_id','formation']):
        g=g.sort_values('lineup_slot');patterns=template(form)
        if not patterns:continue
        roles=['GK']+[canonical(r)for line in patterns for r in line]
        if len(g)!=11 or len(roles)!=11:continue
        observations=[observed.get((str(match),str(r.player_uuid)),{})for r in g.itertuples()]
        if any(not o.get('kickoff') or o.get('started') is not True for o in observations):continue
        for r,role,o in zip(g.itertuples(),roles,observations):
            rows.append(dict(season='2024-25',fixture_uuid=str(match),team_id=int(team),
                player_uuid=str(r.player_uuid),kickoff=o['kickoff'],known_at=r.available_at_proxy,
                formation=form,final_role=role,minutes=o.get('minutes'),
                competition=matches[str(match)]['competition'],round_name=matches[str(match)]['round']))
    return {'2024-25':AssignmentHistory(pd.DataFrame(rows),clock_hours=4),
            '2025-26':AssignmentHistory(measured)}


def metrics(g,p,q):
    x=p*g.s.to_numpy()+(1-p)*q*g.c.to_numpy()
    return dict(rows=len(g),fixtures=int(g.fixture_uuid.nunique()),
                start_brier=float(np.mean((p-g.y.to_numpy())**2)),
                minute_mae=float(np.mean(abs(x-g.minutes.to_numpy()))),
                minute_bias=float(np.mean(x-g.minutes.to_numpy())))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--fixed-strength',type=float);args=ap.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    strengths=[0.,.1,.25,.5]
    if args.fixed_strength is not None:
        if not 0<args.fixed_strength<=1:raise ValueError('Invalid fixed role strength')
        strengths=[0.,args.fixed_strength]
    protocol=dict(strengths=strengths,development='GW6-21 in each season; same global strength',
        validation='GW22-38; reused historical research periods, not independent holdout',
        selection='fixed previously selected strength; no retuning after competition-code correction'if args.fixed_strength is not None else'lowest mean development start-Brier, tie prefers zero',
        gate='start-Brier and minute-MAE improve each season; absolute minute bias does not worsen; then full paired PM gate required',
        historical_roles={'2024-25':'formation/layout proxy; archival clock proxies',
                          '2025-26':'classified measured/structural roles; kickoff+3h clock proxies'},
        importance='existing match_importance formula; explicit provider-code normalization, prior participation and known stage; neutral opponent=.5; no future calendar',
        missing_history='unchanged B, reported',production_changed=False)
    protocol['sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    f,core,_=source_frames();f=f.reset_index(drop=True);hist=histories(core)
    results={s:f.p.to_numpy().copy()for s in strengths};cameos={s:f.q.to_numpy().copy()for s in strengths};receipts=[]
    for i,((season,fx,team),g)in enumerate(f.groupby(['season','fixture_uuid','team_id'])):
        g=g[~g.pos.isin(['GK','GKP'])]
        if not len(g):continue
        if g.cutoff.nunique()!=1:raise ValueError('Mixed origin')
        evidence=hist[season].evidence(season,team,g.cutoff.iloc[0])
        if evidence is None:continue
        if abs(g.p.sum()-10)>1e-6:raise ValueError('Baseline does not supply ten outfield starts')
        caps=np.ones(len(g));known=g.news_eligible.to_numpy(bool);chance=pd.to_numeric(g.news_chance,errors='coerce').to_numpy(float)
        caps[known&np.isfinite(chance)]=chance[known&np.isfinite(chance)]/100
        caps[known&g.news_state.isin(['OUT','SUSPENDED']).to_numpy()]=0
        states=evidence['states'];players=[dict(player_uuid=str(r.player_uuid),**states.get(str(r.player_uuid),{}))for r in g.itertuples()]
        target_importance=importance('prem',int(g.gw.iloc[0]),pd.Timestamp(g.cutoff.iloc[0]).month,evidence['active_competitions'])
        matrices=[(w,role_scores(players,form,target_importance)[0])for form,w in evidence['formations'].items()]
        denominator=sum(w for w,_ in matrices)
        for strength in strengths[1:]:
            p=sum(w*fractional_assignment(g.p.to_numpy(),score,caps=caps,strength=strength).sum(axis=1)for w,score in matrices)/denominator
            if abs(p.sum()-10)>2e-6 or (p>caps+2e-7).any():raise ValueError('Broken role marginals')
            results[strength][g.index]=p
            q=np.minimum(g.q.to_numpy(),np.divide(np.maximum(caps-p,0),1-p,out=np.zeros(len(p)),where=p<1))
            cameos[strength][g.index]=q
        receipts.append(dict(season=season,fixture_uuid=fx,team_id=int(team),cutoff=str(g.cutoff.iloc[0]),
                             known_at=evidence['max_known_at'],games=evidence['games']))
        if i%100==0:print('Role team fixtures',i,flush=True)
    scores=[]
    for season in sorted(f.season.unique()):
        for period,mask in [('development',f.gw.between(6,21)),('validation',f.gw.between(22,38))]:
            g=f[f.season.eq(season)&mask]
            for strength in strengths:scores.append(dict(season=season,period=period,strength=strength,**metrics(g,results[strength][g.index],cameos[strength][g.index])))
    score=pd.DataFrame(scores);score.to_csv(out/'metrics.csv',index=False)
    dev=score[score.period.eq('development')].groupby('strength').start_brier.mean()
    selected=float(args.fixed_strength)if args.fixed_strength is not None else float(dev.idxmin());passed=selected>0
    for season in sorted(f.season.unique()):
        g=score[score.season.eq(season)&score.period.eq('validation')].set_index('strength');a=g.loc[selected];b=g.loc[0.]
        passed &= a.start_brier<b.start_brier and a.minute_mae<b.minute_mae and abs(a.minute_bias)<=abs(b.minute_bias)
    report=dict(selected_strength=selected,mm_gate_passed=bool(passed),pm_gate_passed=False,
                enabled=False,excluded_role_games={s:len(h.excluded)for s,h in hist.items()},
                team_fixture_receipts=len(receipts),protocol_sha256=protocol['sha256'])
    f['candidate_p']=results[selected];f['candidate_q']=cameos[selected];f['candidate_x']=f.candidate_p*f.s+(1-f.candidate_p)*f.candidate_q*f.c
    f.to_csv(out/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(receipts).to_csv(out/'role-receipts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    (out/'decision.json').write_text(json.dumps(report,indent=2)+'\n')
    print(score.to_string(index=False));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
