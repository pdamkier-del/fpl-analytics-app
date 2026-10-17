#!/usr/bin/env python3
"""Chelsea/Haaland/Saka diagnostics; not tuning targets or a current live release."""
import argparse,copy,json,sys,sqlite3
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import gamma
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import research_pm_conversion as research
from audit_capture_io import checked_records,write_frame
from audit_correctness_historical import decode
from replay_pm_conversion import simulate_observed
from experiment_mm_pm import POINT_COMPONENTS
from fpl_v1_1_model.experimental_pm_conversion import event_weights,shadow_joint_assists
from fpl_v1_1_model.experimental_survival_sampler import shadow_survival_sampler
from contextlib import ExitStack


def early_team_conversion(db):
    with sqlite3.connect(db) as c:
        xg=pd.read_sql_query("SELECT season,fixture_uuid,team_id,kickoff_at,xg FROM team_fixture_observations WHERE source_name='vaastav_historical_core' AND season IN ('2023-24','2024-25','2025-26')",c)
        gf=pd.read_sql_query("SELECT season,fixture_uuid,team_id,gf FROM team_fixture_observations WHERE source_name='football_data_co_uk'",c)
    f=xg.merge(gf,on=['season','fixture_uuid','team_id'],validate='one_to_one');rows=[]
    for (season,team),g in f.groupby(['season','team_id']):
        g=g.sort_values(['kickoff_at','fixture_uuid']);early=g.head(6);later=g.iloc[6:12]
        if len(early)!=6 or len(later)!=6 or early.xg.sum()<=0 or later.xg.sum()<=0:continue
        rows.append(dict(season=season,team_id=int(team),early_goals=float(early.gf.sum()),early_xg=float(early.xg.sum()),early_ratio=float(early.gf.sum()/early.xg.sum()),next6_goals=float(later.gf.sum()),next6_xg=float(later.xg.sum()),next6_ratio=float(later.gf.sum()/later.xg.sum())))
    # Threshold is descriptive, not fitted or used in a forecast candidate.
    return dict(classification='DESCRIPTIVE_REALIZED_CONVERSION_NOT_PREMATCH_XG_FORECAST',all_teams=rows,early_overperformers=[r for r in rows if r['early_ratio']>=1.5],warning='Next-six realized xG is used only to describe conversion persistence, never forecast inputs or parameter selection')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--out',default='analysis/results/pm-research-20261015');ap.add_argument('--db',default='work/core.sqlite3');a=ap.parse_args();out=Path(a.out)
    selection=json.loads((out/'selection.json').read_text())['selected'];base=ROOT/'data_v1_1/derived/live_locked_inputs/2026-27-v1';full=pd.read_csv(base/'vfinal_live_full_simulator_input.csv.gz',low_memory=False);current=pd.read_csv(base/'player_fixture_observations.csv.gz')
    current['known']=pd.to_datetime(current.available_at,utc=True);cut=pd.to_datetime(full.cutoff,utc=True).min()
    if not (current.known<cut).all():raise ValueError('Current history after cutoff')
    obs,_,_,audit=research.observations(a.db);obs=pd.concat([obs,current],ignore_index=True);rows=[];factors=[];teamchecks=[]
    for record in checked_records(a.inputs):
        inp=decode(copy.deepcopy(record['inputs']['original']));gf={};af={}
        for family,cfg in selection.items():
            state=research.weighted_states(obs,cut,'2026-27',cfg['half']);g,a1=research.factors(inp,state,cfg['tau'],hierarchical=family=='hierarchy',team_tau=cfg['team_tau'])
            gf[family]=g;af[family]=a1
            for p in inp.players:
                named=full[full.player_uuid.eq(p.player_id)].iloc[0]
                if int(named.fpl_element) not in [411,12,165,109]:continue
                evidence=state[0].loc[p.player_id] if p.player_id in state[0].index else None
                factors.append(dict(player=named.player,id=int(named.fpl_element),family=family,goal_factor=g[p.player_id],assist_factor=a1[p.player_id],weighted_history=evidence.to_dict() if evidence is not None else None))
        inputs=dict(original=inp,finishing=event_weights(inp,gf['goal']),assist_conversion=event_weights(inp,assist_factor=af['assist']),hierarchy=event_weights(inp,gf['hierarchy'],af['hierarchy']),combined=event_weights(inp,gf['goal'],af['assist']),team_finishing=event_weights(inp,gf['goal'],change_total=True),joint_hierarchy=event_weights(inp,gf['hierarchy'],af['hierarchy']))
        mm=decode(copy.deepcopy(record['inputs']['combined_mean']));inputs.update(mm_original=mm,mm_combined=event_weights(mm,gf['goal'],af['assist']))
        for mode,data in inputs.items():
            teamchecks.append(dict(fixture=record['fixture'],mode=mode,home=data.home_team,away=data.away_team,lambda_home=data.lambda_home_goals,lambda_away=data.lambda_away_goals))
        offsets={fx:i for i,fx in enumerate(sorted(full.fixture_uuid.unique()))};fixture=record['fixture'];fixture_players=full[full.fixture_uuid.eq(fixture)]
        for repeat in range(8):
            seed=93000000+offsets[fixture]+repeat*100000
            for mode,data in inputs.items():
                with ExitStack() as stack:
                    if mode=='joint_hierarchy':stack.enter_context(shadow_joint_assists())
                    if mode.startswith('mm_'):stack.enter_context(shadow_survival_sampler(record['starter_hazards']))
                    sim=simulate_observed(data,seed)
                if mode=='original' and repeat==0:
                    ref=pd.read_csv(base/'live_vfinal_fixture_xp.csv.gz');ref=ref[ref.fixture_uuid.eq(fixture)].set_index('player_uuid').xpts_fixture
                    if any(v['xPts']!=float(ref.loc[pid]) for pid,v in sim.items()):raise ValueError('Current original reference not exact')
                for r in fixture_players[fixture_players.fpl_element.isin([411,12,165,109])].itertuples():
                    value=sim[str(r.player_uuid)];rows.append(dict(player=r.player,player_uuid=r.player_uuid,team=int(r.team_id),mode=mode,repeat=repeat,xp=value['xPts'],goal_mu=value['goal_mean'],assist_mu=value['assist_mean'],minutes=value['expected_minutes'],**{k:value[k] for k in POINT_COMPONENTS}))
        print('Current PM focus completed',fixture,flush=True)
    f=pd.DataFrame(rows);summary={}
    for (player,mode),g in f.groupby(['player','mode']):
        ref=f[f.player.eq(player)&f['mode'].eq('mm_original' if mode.startswith('mm_') else 'original')].set_index('repeat');delta=g.set_index('repeat').xp-ref.xp
        summary.setdefault(player,{})[mode]=dict(xp=float(g.xp.mean()),goals=float(g.goal_mu.mean()),assists=float(g.assist_mu.mean()),minutes=float(g.minutes.mean()),seed_xp_sd=float(g.xp.std(ddof=1)),paired_seed_delta=float(delta.mean()),paired_seed_delta_sd=float(delta.std(ddof=1)),components={k:float(g[k].mean()) for k in POINT_COMPONENTS})
    chelsea=current[current.team_id.eq(6)];by=chelsea.groupby('player_uuid')[['goals','xg','fpl_assists','xa']].sum();names=full.drop_duplicates('player_uuid').set_index('player_uuid').player;by['player']=by.index.map(names);by['goal_minus_xg']=by.goals-by.xg
    report=dict(classification='FROZEN_12_OCTOBER_PM_CONVERSION_SHADOW_NOT_LIVE',cutoff=str(cut),results=summary,selected=selection,draws=400,repeats=8,original_first_seed_exact=True,conversion_factors=factors,team_checks=teamchecks,chelsea=dict(actual_goals=float(chelsea.goals.sum()),xg=float(chelsea.xg.sum()),fpl_assists=float(chelsea.fpl_assists.sum()),xa=float(chelsea.xa.sum()),players=by.sort_values('goal_minus_xg',ascending=False).reset_index().to_dict('records')),historical_team_comparison=early_team_conversion(a.db),locked_model_active=False,promotion_allowed=False,limitations=['Same frozen snapshot as preceding MM audit, not a new forecast','All-xG/FPL-assist conversion includes penalty and teammate/source effects','No actual future outcomes or personal TS/chip calculation'])
    write_frame(out/'current_conversion_focus.csv.gz',f);(out/'current_conversion_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(classification=report['classification'],cutoff=report['cutoff'],results=summary,chelsea=report['chelsea'],team_checks=teamchecks),indent=2))
if __name__=='__main__':main()
