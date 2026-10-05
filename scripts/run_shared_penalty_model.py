#!/usr/bin/env python3
"""Shared penalty model experiment.

Builds a coherent penalty process from cutoff-safe history:
1) team penalty award probability blends team's own awarded rate and opponent's
   conceded-penalty rate, both shrunk to league;
2) penalty taker is allocated from recency-weighted prior attempts;
3) conversion uses taker history shrunk to league conversion;
4) if missed, a keeper-save branch uses the historical FPL penalty-save share
   among misses, so taker -2 and keeper +5 arise from the SAME event.

Scored penalties are reported separately from miss/save events. They must be
integrated with the team-goal process by replacing equivalent expected open-play
goal mass, not by adding goals on top of the existing team lambda.

Development/selection: GW6-21. Reused diagnostic: GW22-38.
"""
from __future__ import annotations
import gzip,io,json,math,sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from run_v4rc_experiment import write_json,sha

OUT=ROOT/'analysis/results/shared-penalty-model-20261005-v1'
TAUS=[2.,5.,10.,20.]
HALVES=[6.,12.,24.]


def logloss(y,p):
    y=np.asarray(y,float);p=np.clip(np.asarray(p,float),1e-9,1-1e-9)
    return float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p)))


def brier(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float)
    return float(np.mean((p-y)**2))


def load_pl_penalties():
    rows=[]
    for gw in range(1,39):
        p=ROOT/f'data_v1_1/raw/all-competitions-2025-26/GW{gw}/playermatchstats.csv'
        z=pd.read_csv(p,usecols=['player_id','match_id','minutes_played','penalties_scored','penalties_missed'])
        z=z[z.match_id.astype(str).str.contains('-prem-')].copy()
        z['attempts']=z.penalties_scored.fillna(0)+z.penalties_missed.fillna(0)
        if not z.empty:
            rows.append(z.assign(gw=gw))
    players=pd.concat(rows,ignore_index=True)
    # team identity from lineups (provider team_code)
    maps=[]
    for gw in range(1,39):
        p=ROOT/f'data_v1_1/raw/all-competitions-2025-26/GW{gw}/lineups.csv'
        z=pd.read_csv(p,usecols=['match_id','team_code','player_id','player_name'])
        z=z[z.match_id.astype(str).str.contains('-prem-')]
        z['player_id']=pd.to_numeric(z.player_id,errors='coerce')
        maps.append(z[['match_id','team_code','player_id']].dropna().drop_duplicates())
    mp=pd.concat(maps,ignore_index=True).drop_duplicates(['match_id','player_id'])
    players['player_id']=pd.to_numeric(players.player_id,errors='coerce')
    players=players.merge(mp,on=['match_id','player_id'],how='left',validate='many_to_one')
    pen=players[players.attempts>0].copy()
    if pen.team_code.isna().any():
        raise ValueError('Penalty taker team mapping incomplete')
    pen.team_code=pen.team_code.astype(int)

    fixtures=[]
    for gw in range(1,39):
        p=ROOT/f'data_v1_1/raw/fpl-core-2025-26/GW{gw}/fixtures.csv'
        z=pd.read_csv(p,usecols=['gameweek','match_id','home_team','away_team','tournament'])
        z=z[(z.gameweek==gw)&z.tournament.astype(str).str.lower().eq('prem')]
        for r in z.itertuples(index=False):
            fixtures.append(dict(gw=gw,match_id=r.match_id,team_code=int(r.home_team),opp_code=int(r.away_team),home=1))
            fixtures.append(dict(gw=gw,match_id=r.match_id,team_code=int(r.away_team),opp_code=int(r.home_team),home=0))
    sides=pd.DataFrame(fixtures)
    agg=pen.groupby(['gw','match_id','team_code'],as_index=False).agg(
        attempts=('attempts','sum'),scored=('penalties_scored','sum'),missed=('penalties_missed','sum'))
    sides=sides.merge(agg,on=['gw','match_id','team_code'],how='left')
    for c in ['attempts','scored','missed']:sides[c]=sides[c].fillna(0.)
    return sides,pen


def reconstruct_merged_gw():
    folder=ROOT/'analysis/results/legacy-season-technical-replay-v1'
    parts=sorted(folder.glob('merged_gw.csv.gz.part-*'))
    raw=gzip.decompress(b''.join(p.read_bytes() for p in parts))
    return pd.read_csv(io.BytesIO(raw))


def penalty_save_share():
    g=reconstruct_merged_gw()
    cols=set(g.columns)
    if 'penalties_saved' not in cols or 'penalties_missed' not in cols:
        return dict(p_save_given_miss=0.50,source='fallback_no_fpl_penalty_saved_column',penalty_saves=None,penalty_misses=None)
    saves=float(pd.to_numeric(g.penalties_saved,errors='coerce').fillna(0).sum())
    misses=float(pd.to_numeric(g.penalties_missed,errors='coerce').fillna(0).sum())
    # FPL penalty_missed belongs to takers, saved belongs to GKs. Both count events.
    rate=saves/misses if misses>0 else .5
    return dict(p_save_given_miss=float(np.clip(rate,.05,.95)),source='2025-26 FPL merged_gw',penalty_saves=saves,penalty_misses=misses)


def occurrence_predictions(sides,tau):
    team=defaultdict(lambda:[0.,0.]) # attempts, fixtures
    conceded=defaultdict(lambda:[0.,0.])
    league=[0.,0.]
    out=[]
    for gw in sorted(sides.gw.unique()):
        cur=sides[sides.gw==gw]
        for r in cur.itertuples(index=False):
            lg=league[0]/league[1] if league[1]>0 else .12
            a,n=team[int(r.team_code)];c,m=conceded[int(r.opp_code)]
            own=(a+tau*lg)/(n+tau) if n+tau>0 else lg
            opp=(c+tau*lg)/(m+tau) if m+tau>0 else lg
            lam=max(1e-6,.5*own+.5*opp)
            out.append(dict(gw=int(r.gw),match_id=r.match_id,team_code=int(r.team_code),
                opp_code=int(r.opp_code),actual=int(r.attempts>0),attempts=float(r.attempts),
                lambda_pen=lam,p_pen=1-math.exp(-lam)))
        # update after fixture block
        bymatch=cur.groupby('match_id')
        for _,g in bymatch:
            for r in g.itertuples(index=False):
                t=int(r.team_code);o=int(r.opp_code);att=float(r.attempts)
                team[t][0]+=att;team[t][1]+=1
                conceded[o][0]+=att;conceded[o][1]+=1
                league[0]+=att;league[1]+=1
    return pd.DataFrame(out)


def taker_predictions(pen,half):
    decay=2**(-1/half)
    state=defaultdict(lambda:defaultdict(float))
    hits=[];probs=[]
    for gw in sorted(pen.gw.unique()):
        cur=pen[pen.gw==gw]
        # decay all state once per GW
        for t in list(state):
            for p in list(state[t]):state[t][p]*=decay
        for r in cur.itertuples(index=False):
            t=int(r.team_code);pid=int(r.player_id)
            s=state[t];den=sum(s.values())
            p=(s.get(pid,0)+.05)/(den+.05*max(1,len(s)+1))
            probs.append(p);hits.append(int(max(s,key=s.get) == pid) if s else 0)
        for r in cur.itertuples(index=False):
            state[int(r.team_code)][int(r.player_id)]+=float(r.attempts)
    return dict(mean_true_taker_probability=float(np.mean(probs)) if probs else 0,
                primary_taker_hit_rate=float(np.mean(hits)) if hits else 0,n_events=len(probs))


def conversion_predictions(pen,tau):
    player=defaultdict(lambda:[0.,0.]);league=[0.,0.]
    ys=[];ps=[]
    for gw in sorted(pen.gw.unique()):
        cur=pen[pen.gw==gw]
        for r in cur.itertuples(index=False):
            pid=int(r.player_id);lg=league[0]/league[1] if league[1] else .78
            sc,at=player[pid];p=(sc+tau*lg)/(at+tau)
            # expand attempts; data are almost always 1 but handle counts
            n=int(round(float(r.attempts)));s=int(round(float(r.penalties_scored)))
            ys.extend([1]*s+[0]*max(0,n-s));ps.extend([p]*n)
        for r in cur.itertuples(index=False):
            pid=int(r.player_id);sc=float(r.penalties_scored);at=float(r.attempts)
            player[pid][0]+=sc;player[pid][1]+=at;league[0]+=sc;league[1]+=at
    return dict(log_loss=logloss(ys,ps),brier=brier(ys,ps),mean_pred=float(np.mean(ps)),
                actual_rate=float(np.mean(ys)),n=len(ys))


def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    sides,pen=load_pl_penalties()
    save=penalty_save_share()

    occ=[]
    for tau in TAUS:
        p=occurrence_predictions(sides,tau)
        m=p.gw.between(6,21)
        occ.append(dict(tau=tau,log_loss=logloss(p.loc[m,'actual'],p.loc[m,'p_pen']),
                        brier=brier(p.loc[m,'actual'],p.loc[m,'p_pen']),
                        mean_pred=float(p.loc[m,'p_pen'].mean()),actual_rate=float(p.loc[m,'actual'].mean())))
    occ=pd.DataFrame(occ).sort_values(['log_loss','brier']);occ.to_csv(OUT/'occurrence_candidates.csv',index=False)
    tau=float(occ.iloc[0].tau)
    pred=occurrence_predictions(sides,tau)
    diag=pred.gw.between(22,38)
    occ_diag=dict(log_loss=logloss(pred.loc[diag,'actual'],pred.loc[diag,'p_pen']),
                  brier=brier(pred.loc[diag,'actual'],pred.loc[diag,'p_pen']),
                  mean_pred=float(pred.loc[diag,'p_pen'].mean()),actual_rate=float(pred.loc[diag,'actual'].mean()),
                  mean_lambda=float(pred.loc[diag,'lambda_pen'].mean()))

    takers=[dict(half_life=h,**taker_predictions(pen[pen.gw<=21],h)) for h in HALVES]
    tk=pd.DataFrame(takers).sort_values(['mean_true_taker_probability','primary_taker_hit_rate'],ascending=False)
    tk.to_csv(OUT/'taker_candidates.csv',index=False);half=float(tk.iloc[0].half_life)
    taker_diag=taker_predictions(pen[pen.gw>=22],half)

    convs=[dict(tau=t,**conversion_predictions(pen[pen.gw<=21],t)) for t in TAUS]
    cv=pd.DataFrame(convs).sort_values(['log_loss','brier']);cv.to_csv(OUT/'conversion_candidates.csv',index=False)
    conv_tau=float(cv.iloc[0].tau)
    conv_diag=conversion_predictions(pen[pen.gw>=22],conv_tau)

    result=dict(
      architecture={
        'occurrence':'EB blend 50/50 team penalties awarded + opponent penalties conceded, shrunk to league',
        'taker':'recency-weighted prior penalty attempts within team',
        'conversion':'player conversion shrunk to league conversion',
        'keeper_save':'single shared miss outcome; keeper save probability conditional on a miss',
        'scored_penalty_goal_integration':'subtract expected scored-penalty mass from team goal lambda, then simulate explicit penalty score; never add on top',
      },
      selected=dict(occurrence_tau=tau,taker_half_life=half,conversion_tau=conv_tau,
                    p_keeper_save_given_miss=save['p_save_given_miss']),
      development=dict(occurrence_best=occ.iloc[0].to_dict(),taker_best=tk.iloc[0].to_dict(),conversion_best=cv.iloc[0].to_dict()),
      reused_diagnostic=dict(occurrence=occ_diag,taker=taker_diag,conversion=conv_diag),
      penalty_save_source=save,
      event_counts=dict(total_attempts=float(pen.attempts.sum()),scored=float(pen.penalties_scored.sum()),
                        missed=float(pen.penalties_missed.sum()),fixtures_with_penalty=int((sides.attempts>0).sum())),
      promotion_allowed=False,
      next_integration='joint simulator shared penalty event with explicit taker miss -2, keeper save +5, scored penalty goal replacing equal expected team-goal mass')
    write_json(OUT/'model_summary.json',result)
    pred.to_csv(OUT/'occurrence_predictions.csv.gz',index=False,compression='gzip')
    write_json(OUT/'protocol.json',dict(development='GW6-21',reused_diagnostic='GW22-38',
        note='Penalty save/miss is one shared event, not independent player/GK forecasts'))
    outs=[p for p in sorted(OUT.iterdir()) if p.name!='manifest.json']
    write_json(OUT/'manifest.json',dict(sources=[dict(path='scripts/run_shared_penalty_model.py',sha256=sha(Path(__file__)))],
      outputs=[dict(path=p.name,sha256=sha(p)) for p in outs]))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
