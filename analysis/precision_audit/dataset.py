"""Reconstruct the existing B structure; no live outputs or model writes."""
import argparse,copy,gzip,hashlib,json,sqlite3,zipfile
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np
import pandas as pd
from test_separated_goal_head import decode,prepare_tasks
from test_joint_role_candidate import histories
from build_current_b_inputs import historical_B_training
from gk_joint_bridge import observations,DurationHistory,prepare,UNKNOWN
from gk_solo_role import SoloRolePolicy,verified_squads
from joint_role_bridge import apply_assignment
from b_chain_contract import prepare_match
from fpl_v1_1_model.experimental_joint_role_assignment import RoleLineup
from precision_audit.oracles import reconcile_timeline
ROOT=Path(__file__).resolve().parents[2]

def dump(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True);b=json.dumps(obj,default=asdict,allow_nan=False,sort_keys=True).encode();Path(path).write_bytes(gzip.compress(b,mtime=0))
def load(path):
    records=json.loads(gzip.decompress(Path(path).read_bytes()))
    for r in records:r['dist']={int(k):[RoleLineup(**v)for v in vs]for k,vs in r['dist'].items()}
    return records

def historical(out,cache=None):
    if cache:tasks=json.loads(gzip.open(cache,'rt').read())
    else:tasks,_=prepare_tasks(json.loads((ROOT/'analysis/results/nonpenalty-goal-head-20261023/final-v2/model.json').read_text()),out)
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:
        core=pd.read_sql_query("SELECT o.*,p.canonical_name FROM player_fixture_observations o JOIN players p USING(player_uuid) WHERE is_final=1 AND season IN ('2024-25','2025-26')",db)
        teams=pd.read_sql_query("SELECT * FROM team_fixture_observations WHERE source_name='football_data_co_uk' AND season IN ('2024-25','2025-26')",db)
    from b_physical_workload import historical_ledger,features
    raw=historical_B_training();physical,physical_coverage=historical_ledger(ROOT);raw=features(raw,physical);prediction=pd.read_csv(ROOT/'analysis/results/integrated-repair-20261031/workload/predictions.csv.gz');prediction=prediction[prediction.arm.eq('all_comp_workload')]
    role=histories(core);obs=observations(ROOT);squads=verified_squads(ROOT);duration={};policies={};records=[];coverage=[]
    for season,fx,seed,data,_,factors,_ in tasks:
        g=raw[raw.season.eq(season)&raw.fixture_uuid.eq(fx)].copy();n=prediction[prediction.season.eq(season)&prediction.fixture_uuid.eq(fx)].set_index('player_uuid');cut=str(g.cutoff.iloc[0]);cut_ts=pd.Timestamp(cut)
        for c in ['p','q','s','c','x']:g[c]=g.player_uuid.map(n[c])
        if cut not in duration:duration[cut]=DurationHistory(obs,cut)
        if cut not in policies:
            past=raw[pd.to_datetime(raw.known_at,utc=True).lt(cut_ts)]
            policies[cut]=SoloRolePolicy(past,squads)
        inp=decode(copy.deepcopy(data));inp=replace(inp,players=tuple(p for p in inp.players if not p.player_id.startswith(UNKNOWN)))
        by=g.set_index('player_uuid');inp=replace(inp,players=tuple(replace(p,p_start=float(by.loc[p.player_id,'p']),p_cameo_given_bench=float(by.loc[p.player_id,'q']),start_minutes_mean=float(by.loc[p.player_id,'s']),cameo_minutes_mean=float(by.loc[p.player_id,'c']))for p in inp.players))
        inp,_,_=prepare(inp,g,duration[cut],role_policy=policies[cut],season=season)
        assigned,dist,_=apply_assignment(g,role[season],strength=.5);by=assigned.set_index('player_uuid');inp=replace(inp,players=tuple(p if p.is_keeper else replace(p,p_start=float(by.loc[p.player_id,'p']),p_cameo_given_bench=float(by.loc[p.player_id,'q']))for p in inp.players));inp=prepare_match(inp)
        inp=replace(inp,experimental_conditional_penalties=True,players=tuple(replace(p,goal_weight=float(factors[p.player_id]),penalty_fallback_weight=p.goal_weight)if p.player_id in factors else p for p in inp.players))
        truth=core[core.season.eq(season)&core.fixture_uuid.eq(fx)].copy();actual={str(r.player_uuid):{k:(None if pd.isna(v)else v)for k,v in r._asdict().items()if k!='Index'}for r in truth.itertuples()}
        for p in inp.players:
            if p.player_id.startswith(UNKNOWN):actual[p.player_id]=dict(minutes=0,started=0,total_points=0)
        goalrows=teams[teams.season.eq(season)&teams.fixture_uuid.eq(fx)].set_index('team_id');goals={team:int(goalrows.loc[int(team),'gf'])for team in [inp.home_team,inp.away_team]}
        try:
            if truth.fpl_red_cards.fillna(0).sum()>0:raise ValueError('Actual red-card removal outside normal timeline')
            reconcile_timeline(inp,actual,True);reconcile_timeline(inp,actual,False);valid=True;reason=None
        except ValueError as e:valid=False;reason=str(e)
        meta={}
        for r in g.itertuples():
            meta[str(r.player_uuid)]=dict(position=r.pos,team_id=int(r.team_id),gw=int(r.gw),prior_type=str(r.prior_type),news_state=str(r.news_state),return_active=bool(r.return_active),minutes_7d=float(r.minutes_7d),cutoff=cut)
        records.append(dict(season=season,fixture_uuid=fx,seed=int(seed),gw=int(g.gw.iloc[0]),cutoff=cut,input=asdict(inp),dist=dist,actual=actual,goals=goals,meta=meta,oracle_eligible=valid,oracle_exclusion=reason,gk_training_latest=policies[cut].last_training_label.isoformat(),parameter_scope='2024-25 retrospective conditional: NP coefficients fit 2025-26'if season=='2024-25'else'2025-26 reused research: fixed selected heads; no pristine holdout'))
        coverage.append(dict(season=season,fixture_uuid=fx,oracle_eligible=valid,reason=reason))
        if len(records)%25==0:print('Audit inputs',len(records),flush=True)
    dump(out/'historical-inputs.json.gz',records);pd.DataFrame(coverage).to_csv(out/'oracle-coverage.csv',index=False)
    return records

def current(out,archive,forecast_path):
    base=out/'current-origin'
    with zipfile.ZipFile(archive)as z:
        for name in z.namelist():
            p=Path(name)
            if p.is_absolute()or'..'in p.parts:raise ValueError('Invalid archive path')
        z.extractall(base)
    inputs=base/'work/current-B-inputs';h=pd.read_csv(inputs/'history.csv.gz',low_memory=False);t=pd.read_csv(inputs/'target.csv.gz',low_memory=False);prov=json.loads((inputs/'provenance.json').read_text());boot=json.loads((inputs/'bootstrap.json').read_text())
    from mm_candidate_forecast import infer_B
    from mm_locked_bridge import attach_mm
    from run_vfinal_integrated import make_vfinal_input
    from gk_solo_role import mark_horizon_absences
    from fpl_v1_1_model.experimental_role_assignment_history import AssignmentHistory
    pred,_=infer_B(h,t,prov);pred=mark_horizon_absences(pred,boot);frame=attach_mm(pd.read_csv(inputs/'pm.csv.gz',low_memory=False),pred)
    squads=pd.read_csv(base/'work/joint-gk-current/role-squad-evidence.csv.gz')
    for column in ['clock','kick']:squads[column]=pd.to_datetime(squads[column],utc=True,format='mixed')
    policy=SoloRolePolicy(h,squads);role=AssignmentHistory(pd.read_csv(inputs/'roles.csv.gz'))
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True)as db:
        ob=pd.read_sql_query("SELECT season,fixture_uuid,player_uuid,team_id,fpl_position,started,minutes,kickoff_at FROM player_fixture_observations WHERE is_final=1 AND fpl_position IN ('GK','GKP','G')",db)
    ob['known_at']=pd.to_datetime(ob.kickoff_at,utc=True)+pd.to_timedelta(np.where(ob.season.eq('2024-25'),4,3),unit='h')
    live=pd.read_csv(base/'data_v1_1/derived/live_locked_inputs/2026-27-v1/player_fixture_observations.csv.gz');live=live[live.fpl_position.isin(['GK','GKP','G'])].copy();live['known_at']=pd.to_datetime(live.available_at,utc=True)
    ob=pd.concat([ob,live[ob.columns]],ignore_index=True).drop_duplicates(['season','fixture_uuid','player_uuid'])
    factors=pd.read_csv(base/'work/joint-gk-current/nonpenalty-goal-head.csv.gz').set_index(['fixture_uuid','player_uuid']).ordinary_goal_weight
    evidence=json.loads((base/'work/gk-official-evidence/evidence.json').read_text());incomplete=(evidence['team_id'],) if evidence['unlisted_competitors'] else ()
    f=json.loads(Path(forecast_path).read_text());first=min(f['gws']);records=[];catalogue={p['id']:p for p in boot['elements']}
    for fx,g in frame[frame.gw.eq(first)].groupby('fixture_uuid',sort=True):
        mm=pred[pred.fixture_uuid.eq(fx)].copy();inp,_=make_vfinal_input(g);inp=replace(inp,bps_rules='2026-27');inp,_,_=prepare(inp,mm,DurationHistory(ob,g.cutoff.iloc[0]),incomplete_teams=incomplete,role_policy=policy,season='2026-27');adjusted,dist,_=apply_assignment(mm,role,strength=.5);by=adjusted.set_index('player_uuid');inp=replace(inp,players=tuple(p if p.is_keeper else replace(p,p_start=float(by.loc[p.player_id,'p']),p_cameo_given_bench=float(by.loc[p.player_id,'q']))for p in inp.players));cat={r.player_uuid:catalogue[int(r.fpl_element)]for r in g.itertuples()};inp=prepare_match(inp,cat);inp=replace(inp,experimental_conditional_penalties=True,players=tuple(replace(p,goal_weight=float(factors.loc[(fx,p.player_id)]),penalty_fallback_weight=p.goal_weight)if not p.player_id.startswith(UNKNOWN)else p for p in inp.players))
        names={r.player_uuid:catalogue[int(r.fpl_element)]['web_name']for r in g.itertuples()};meta={r.player_uuid:dict(id=int(r.fpl_element),name=names[r.player_uuid],position=r.pos,team_id=int(r.team_id),price_tenths=int(cat[r.player_uuid]['now_cost']))for r in g.itertuples()}
        records.append(dict(season='2026-27',fixture_uuid=fx,gw=first,cutoff=str(g.cutoff.iloc[0]),seed=93000000+list(sorted(frame.fixture_uuid.unique())).index(fx),input=asdict(inp),dist=dist,meta=meta,forecast_sha256=f['forecast_sha256'],parameter_scope='Prospective current B; no future outcomes'))
    dump(out/'current-inputs.json.gz',records);return records

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--tasks',type=Path);p.add_argument('--current-archive',type=Path);p.add_argument('--forecast',type=Path);p.add_argument('--current-only',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if not a.current_only:historical(a.out,a.tasks)
    if a.current_archive:current(a.out,a.current_archive,a.forecast)
if __name__=='__main__':main()
