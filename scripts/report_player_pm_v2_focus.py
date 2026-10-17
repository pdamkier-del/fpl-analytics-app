#!/usr/bin/env python3
"""Frozen public PM v2 diagnostics; selected profiles, original MM, no tuning."""
import argparse,copy,json,sys
from pathlib import Path
from dataclasses import replace
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from research_player_pm_v2 import data,Factory,save,LIMITS
from fpl_v1_1_model.experimental_player_pm import historical_opponent_offsets,shadow_player_intensity,expected_exposure,lineup_rates
from replay_pm_conversion import simulate_observed
from run_vfinal_integrated import make_vfinal_input
from experiment_mm_pm import POINT_COMPONENTS
from audit_capture_io import write_frame


def uncertainty(inp,spec,seed=20261015,n=1000):
    rng=np.random.default_rng(seed);exposure={p.player_id:expected_exposure(p) for p in inp.players};by={}
    drawspec=copy.deepcopy(spec)
    for _ in range(n):
        for pid,pr in spec['profiles'].items():
            for field in ['xg90','xa90','finishing']:
                z=pr[field];drawspec['profiles'][pid][field]['mean']=float(rng.gamma(z['shape'],1/z['rate'])) if z['shape']>0 else 0.
        rates,_=lineup_rates(inp,drawspec,exposure)
        for team,r in rates.items():by.setdefault(team,[]).append([r['xg'],r['total']])
    return {team:dict(xg_interval95=np.quantile(v,[.025,.975],axis=0)[:,0].tolist(),goal_mean_interval95=np.quantile(v,[.025,.975],axis=0)[:,1].tolist(),note='Conditional independent-profile EB uncertainty at fixed expected MM exposure; not full posterior or future score interval') for team,v in by.items()}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='analysis/results/player-pm-v2-20261015');ap.add_argument('--repeats',type=int,default=8);ap.add_argument('--draws',type=int,default=400);ap.add_argument('--workers',type=int,default=1);a=ap.parse_args();out=Path(a.out);selection=json.loads((out/'selection.json').read_text())
    base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1';full=pd.read_csv(base/'vfinal_live_full_simulator_input.csv.gz',low_memory=False);h=pd.read_csv(base/'player_fixture_observations.csv.gz');h['known']=pd.to_datetime(h.available_at,utc=True);cut=pd.to_datetime(full.cutoff,utc=True).min()
    if pd.to_datetime(full.cutoff,utc=True).nunique()!=1 or not h.known.lt(cut).all():raise ValueError('Mixed/late source cutoff')
    obs,_,_,_=data(ROOT/'work/core.sqlite3');h=h.merge(historical_opponent_offsets(h),on=['season','fixture_uuid','team_id'],validate='many_to_one');obs=pd.concat([obs,h],ignore_index=True);factory=Factory(obs,'2026-27')
    focus=full[full.fpl_element.isin([411,12,165,154]) & full.target_gw.eq(full.target_gw.min())];fixtures=sorted(focus.fixture_uuid.unique());offsets={fx:i for i,fx in enumerate(sorted(full.fixture_uuid.unique()))};ref=pd.read_csv(base/'live_vfinal_fixture_xp.csv.gz').set_index(['fixture_uuid','player_uuid']).xpts_fixture
    profiles=[];rows=[];teamrows=[];uncertainties=[]
    for fx in fixtures:
        g=full[full.fixture_uuid.eq(fx)];inp,_=make_vfinal_input(g.copy());inp=replace(inp,bps_rules='2026-27');inputs={'original':(inp,None)}
        for mode,cfg in selection['selected'].items():
            c,spec=factory.build(inp,cut,cfg);inputs[mode]=(c,spec)
            for p in inp.players:
                name=g[g.player_uuid.eq(p.player_id)].iloc[0]
                if int(name.fpl_element) not in [411,12,165,154]:continue
                profiles.append(dict(player=name.player,element=int(name.fpl_element),mode=mode,team=str(p.team),profile=spec['profiles'][p.player_id]))
            uncertainties.append(dict(fixture=fx,mode=mode,teams=uncertainty(c,spec)))
        for repeat in range(a.repeats):
            seed=93000000+offsets[fx]+repeat*100000
            for mode,(candidate,spec) in inputs.items():
                d={}
                if spec is None:sim=simulate_observed(candidate,seed,draws=a.draws)
                else:
                    with shadow_player_intensity(spec,d):sim=simulate_observed(candidate,seed,draws=a.draws)
                if mode=='original' and repeat==0 and a.draws==400:
                    if any(v['xPts']!=float(ref.loc[(fx,pid)]) for pid,v in sim.items()):raise ValueError('Frozen current reference differs')
                for team,anchor in [(inp.home_team,inp.lambda_home_goals),(inp.away_team,inp.lambda_away_goals)]:
                    z=d.get(str(team));teamrows.append(dict(fixture=fx,team=int(team),mode=mode,repeat=repeat,xg=z['xg_sum']/z['draws'] if z else anchor,goal_mean=z['goal_mean_sum']/z['draws'] if z else anchor))
                for r in focus[focus.fixture_uuid.eq(fx)].itertuples():
                    v=sim[str(r.player_uuid)]
                    if not np.isclose(sum(v[k] for k in POINT_COMPONENTS),v['xPts'],atol=1e-10):raise ValueError('Component sum')
                    rows.append(dict(player=r.player,element=int(r.fpl_element),mode=mode,repeat=repeat,xp=v['xPts'],goals=v['goal_mean'],assists=v['assist_mean'],minutes=v['expected_minutes'],p10=v['p10'],p90=v['p90'],**{k:v[k] for k in POINT_COMPONENTS}))
            print('Focus completed',fx,repeat,flush=True)
    f=pd.DataFrame(rows);summary={}
    for (player,mode),g in f.groupby(['player','mode']):
        baseline=f[f.player.eq(player)&f['mode'].eq('original')].set_index('repeat').xp;delta=g.set_index('repeat').xp-baseline
        summary.setdefault(player,{})[mode]=dict(xp=float(g.xp.mean()),goals=float(g.goals.mean()),assists=float(g.assists.mean()),minutes=float(g.minutes.mean()),paired_xp_delta=float(delta.mean()),paired_seed_delta_sd=float(delta.std(ddof=1)),components={k:float(g[k].mean()) for k in POINT_COMPONENTS},mean_conditional_point_p10=float(g.p10.mean()),mean_conditional_point_p90=float(g.p90.mean()))
    t=pd.DataFrame(teamrows);team=t.groupby(['team','mode'],as_index=False)[['xg','goal_mean']].mean().to_dict('records');write_frame(out/'current_player_predictions.csv.gz',f)
    report=dict(classification='FROZEN_2026_10_12_PLAYER_PM_V2_NOT_LIVE',cutoff=str(cut),draws=a.draws,repeats=a.repeats,first_seed_original_exact=a.draws==400,players=summary,teams=team,profiles=profiles,uncertainty=uncertainties,selected=selection['selected'],limitations=LIMITS+['Public current GW6 source includes provisional Chelsea result; no new source certification'],locked_model_active=False,promotion_allowed=False)
    save(out/'current_player_report.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
