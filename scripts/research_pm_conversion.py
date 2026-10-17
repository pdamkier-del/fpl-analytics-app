#!/usr/bin/env python3
"""Cutoff-only conversion screen on ORIGINAL forecast inputs, not realized target xG."""
import argparse,copy,hashlib,json,sqlite3,sys
from pathlib import Path
from dataclasses import replace,asdict
import numpy as np,pandas as pd
from scipy.special import gammaln
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from audit_capture_io import checked_records,write_records,write_frame
from audit_correctness_historical import decode
from fpl_v1_1_model.experimental_pm_conversion import gamma_mean,event_weights,poisson_deviance

HALVES=[90.,365.,None];TAUS=[5.,20.,80.]

def observations(db):
    with sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True) as c:
        f=pd.read_sql_query('SELECT * FROM player_fixture_observations WHERE is_final=1',c)
        teams=pd.read_sql_query("SELECT * FROM team_fixture_observations WHERE source_name='football_data_co_uk'",c)
        names=pd.read_sql_query('SELECT player_uuid,canonical_name FROM players',c)
    if f.duplicated(['season','fixture_uuid','player_uuid']).any():raise ValueError('Duplicate outcomes')
    for col in ['xg','xa','goals','fpl_assists','minutes']:
        if not np.isfinite(f[col]).all() or f[col].lt(0).any():raise ValueError('Invalid/missing conversion history')
    f['known']=pd.to_datetime(f.kickoff_at,utc=True)+pd.to_timedelta(np.where(f.season.eq('2025-26'),3,4),unit='h')
    # FPL expected stats did not exist early in this archived 2022/23 series.
    excluded=f.season.eq('2022-23')&f.gw.lt(16)
    audit=dict(rows_by_season=f.groupby('season').size().to_dict(),excluded_2022_early_placeholder_rows=int(excluded.sum()),missing_fields={col:int(f[col].isna().sum()) for col in ['npxg','shots','shots_on_target','big_chances_created']},source_publication_certified=False,availability='kickoff+4h; 2025/26 +3h, matching archived MM/PM adapter proxies',team_identity='(season, team_id), never team_id alone across seasons')
    return f[~excluded].copy(),teams,names,audit


def weighted_states(obs,cut,season,half):
    past=obs[obs.known<cut].copy()
    if past.empty:raise ValueError('No verified prior conversion history')
    age=(cut-past.known).dt.total_seconds().to_numpy()/86400
    w=np.ones(len(past)) if half is None else np.exp2(-age/half)
    cols=['goals','xg','fpl_assists','xa','minutes'];v=past[cols].mul(w,axis=0);v['player_uuid']=past.player_uuid
    players=v.groupby('player_uuid')[cols].sum()
    current=v[past.season.eq(season)].copy();current['team_id']=past.loc[current.index,'team_id'];current['pos']=past.loc[current.index,'fpl_position'].replace({'GKP':'GK'})
    team=current.groupby('team_id')[cols].sum();position=current.groupby('pos')[cols].sum();league=current[cols].sum()
    if league.xg<=0 or league.xa<=0:league=v[cols].sum()
    league_g=float(league.goals/league.xg);league_a=float(league.fpl_assists/league.xa)
    return players,team,position,league_g,league_a,len(past),str(past.known.max())


def factors(inp,state,tau,hierarchical=False,team_tau=80.):
    players,teams,pos,lg,la,_,_=state;gf={};af={}
    for p in inp.players:
        pid=p.player_id;row=players.loc[pid] if pid in players.index else pd.Series(dict(goals=0.,xg=0.,fpl_assists=0.,xa=0.,minutes=0.))
        team=teams.loc[int(p.team)] if int(p.team) in teams.index else None
        pg=float(gamma_mean(team.goals,team.xg,team_tau,lg)) if hierarchical and team is not None else (lg if hierarchical else 1.)
        pa=float(gamma_mean(team.fpl_assists,team.xa,team_tau,la)) if hierarchical and team is not None else (la if hierarchical else 1.)
        gf[pid]=float(gamma_mean(row.goals,row.xg,tau,pg));af[pid]=float(gamma_mean(row.fpl_assists,row.xa,tau,pa))
    return gf,af


def pure_xg_input(inp,obs,cut,season):
    h=obs[(obs.known<cut)&obs.season.eq(season)].sort_values(['known','fixture_uuid']);position=h.groupby('fpl_position')[['xg','xa','minutes']].sum();by={str(pid):g for pid,g in h.groupby('player_uuid')};ps=[]
    for p in inp.players:
        role='GKP' if 'GKP' in position.index and p.position=='GK' else p.position
        if role not in position.index or position.loc[role,'minutes']<=0:raise ValueError('Missing current-season position prior')
        pop=position.loc[role];g=by.get(p.player_id,h.iloc[:0]);values={}
        for kind,event,half,tau in [('goal','xg',14.301700060813651,340.37043955522125),('assist','xa',28.106996692019756,365.22361910394244)]:
            w=np.exp2(-np.arange(len(g)-1,-1,-1)/half);num=float(w@g[event]);den=float(w@g.minutes)
            values[kind]=(num+tau*float(pop[event]/pop.minutes))/(den+tau)
        ps.append(replace(p,goal_weight=values['goal'],assist_weight=values['assist']))
    return replace(inp,players=tuple(ps))


def proxy(inp):
    """Pre-match analytic screening proxy. Realized target minutes/xG never used."""
    out=[]
    for team,lam,pen,conv in [(inp.home_team,inp.lambda_home_goals,inp.lambda_home_penalties,inp.home_penalty_conversion),(inp.away_team,inp.lambda_away_goals,inp.lambda_away_penalties,inp.away_penalty_conversion)]:
        ps=[p for p in inp.players if p.team==team]
        e=np.array([p.p_start*p.start_minutes_mean+(1-p.p_start)*p.p_cameo_given_bench*p.cameo_minutes_mean for p in ps])/90.
        g=e*np.array([p.goal_weight for p in ps]);a=e*np.array([p.assist_weight for p in ps]);pk=e*np.array([p.penalty_weight for p in ps])
        g=g/g.sum() if g.sum()>0 else np.zeros(len(g));a=a/a.sum() if a.sum()>0 else np.zeros(len(a));pk=pk/pk.sum() if pk.sum()>0 else g
        for i,p in enumerate(ps):out.append(dict(player_uuid=p.player_id,team_id=int(team),goal_mu=max(1e-12,max(0.,lam-pen*conv)*g[i]+pen*p.penalty_conversion*pk[i]),assist_mu=max(1e-12,lam*inp.assist_probability_per_goal*a[i]),team_mu=lam))
    return pd.DataFrame(out)


def target_records(path,db,season):
    records=checked_records(path)
    if len(records)!=330:raise ValueError('Incomplete original seasonal inputs')
    with sqlite3.connect(db) as c:fx=pd.read_sql_query('SELECT * FROM fixtures WHERE season=?',c,params=[season])
    if fx.duplicated(['home_team_id','away_team_id']).any():raise ValueError('Ambiguous fixture sides')
    lookup={(int(r.home_team_id),int(r.away_team_id)):r.fixture_uuid for r in fx.itertuples()}
    for r in records:r['core_fixture']=lookup[r['home'],r['away']]
    return records


def config_list():
    return [dict(name=f'{family}_h{half}_t{tau}_team{team_tau}',family=family,half=half,tau=tau,team_tau=team_tau) for family in ['goal','assist','hierarchy'] for half in HALVES for tau in TAUS for team_tau in ([20.,80.,320.] if family=='hierarchy' else [80.])]


def propose(inp,cfg,state):
    g,a=factors(inp,state,cfg['tau'],hierarchical=cfg['family']=='hierarchy',team_tau=cfg['team_tau'])
    return event_weights(inp,g if cfg['family']!='assist' else {},a if cfg['family']!='goal' else {})


def screen(records,obs,season,configs,dev_only=False):
    truth=obs[obs.season.eq(season)].set_index(['fixture_uuid','player_uuid']);states={};rows=[]
    for r in records:
        if dev_only and not 6<=r['origin']<=21:continue
        inp=decode(copy.deepcopy(r['input']));cut=pd.Timestamp(r['input']['players'][0].get('cutoff')) if 'cutoff' in r['input']['players'][0] else None
        # Forecast captures have no dates; bind cutoff to archived authoritative GW deadlines.
        if cut is None:cut=DEADLINES[season][int(r['origin'])]
        actual=truth.loc[r['core_fixture']]
        candidates={'original':inp,'xg_only':pure_xg_input(inp,obs,cut,season)}
        for cfg in configs:
            key=(int(r['origin']),cfg['half'])
            if key not in states:states[key]=weighted_states(obs,cut,season,cfg['half'])
            candidates[cfg['name']]=propose(inp,cfg,states[key])
        for mode,data in candidates.items():
            p=proxy(data);p=p[p.player_uuid.isin(r['reference'])]
            if not p.player_uuid.isin(actual.index).all():raise ValueError('Missing target outcomes for frozen reference roster')
            y=actual.loc[p.player_uuid]
            for target,col in [('goals','goal_mu'),('fpl_assists','assist_mu')]:
                yy=y[target].to_numpy();mu=p[col].to_numpy();nll=mu-yy*np.log(mu)+gammaln(yy+1)
                rows.append(dict(season=season,gw=r['origin'],fixture=r['core_fixture'],mode=mode,event=target,rows=len(p),nll_sum=float(nll.sum()),mae_sum=float(abs(mu-yy).sum()),rmse_sum=float(((mu-yy)**2).sum()),mean_pred_sum=float(mu.sum()),mean_actual_sum=float(yy.sum())))
    return pd.DataFrame(rows)


def screen_metrics(frame):
    rows=[]
    for (mode,event),g in frame.groupby(['mode','event']):
        n=int(g.rows.sum());rows.append(dict(mode=mode,event=event,rows=n,nll=float(g.nll_sum.sum()/n),mae=float(g.mae_sum.sum()/n),rmse=float(np.sqrt(g.rmse_sum.sum()/n)),mean_pred=float(g.mean_pred_sum.sum()/n),mean_actual=float(g.mean_actual_sum.sum()/n)))
    return rows


def deadlines(root):
    result={}
    for season in ['2024-25','2025-26']:
        # The MM artifact carries the exact same cutoffs used for original PM capture.
        f=pd.read_csv(root/f'{season}_features.csv.gz',usecols=['gw','cutoff']);counts=f.groupby('gw').cutoff.nunique()
        if counts.ne(1).any():raise ValueError('Mixed cutoff')
        result[season]={int(k):pd.Timestamp(v) for k,v in f.groupby('gw').cutoff.first().items()}
    return result


def main():
    global DEADLINES
    ap=argparse.ArgumentParser();ap.add_argument('--db',default='work/core.sqlite3');ap.add_argument('--inputs2024',required=True);ap.add_argument('--inputs2025',required=True);ap.add_argument('--mm-root',default='analysis/results/mm-research-20261014');ap.add_argument('--out',default='analysis/results/pm-research-20261015');a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    obs,teams,names,audit=observations(a.db);DEADLINES=deadlines(Path(a.mm_root));configs=config_list();r24=target_records(a.inputs2024,a.db,'2024-25')
    development=screen(r24,obs,'2024-25',configs,dev_only=True);metrics=screen_metrics(development);chosen={}
    for family,event in [('goal','goals'),('assist','fpl_assists')]:
        allowed={c['name']:c for c in configs if c['family']==family};m=min([m for m in metrics if m['mode'] in allowed and m['event']==event],key=lambda m:m['nll']);chosen[family]=allowed[m['mode']]
    allowed={c['name']:c for c in configs if c['family']=='hierarchy'};by={mode:sum(m['nll'] for m in metrics if m['mode']==mode) for mode in allowed};chosen['hierarchy']=allowed[min(by,key=by.get)]
    selection=dict(classification='PREKICKOFF_ANALYTIC_PROXY_SCREEN_NOT_FULL_SIMULATOR_ACCURACY',development='2024/25 GW6-21, actual target xG/minutes never inputs',selection='goal/assist Poisson NLL; hierarchy sum of both',selected=chosen,grid=metrics,availability=audit,locked_model_active=False,promotion_allowed=False)
    (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    # Selection persisted before loading later 2025 target forecast/outcome records.
    r25=target_records(a.inputs2025,a.db,'2025-26')
    keep=list(chosen.values());p24=screen(r24,obs,'2024-25',keep);p25=screen(r25,obs,'2025-26',keep);write_frame(out/'screen_scores.csv.gz',pd.concat([p24,p25]))
    report=dict(protocol=selection,results={'2024-25_GW22-38':screen_metrics(p24[p24.gw.ge(22)]),'2025-26_GW6-38':screen_metrics(p25)},limitations=['Analytic selection proxy differs from event-time normalization; full original PM replay required','All-xG includes penalties; no identified NPG finishing or pure creator effect','Actual historical source publication times unavailable','Reused development seasons, not pristine independent whole-model holdouts'],locked_model_active=False,promotion_allowed=False)
    (out/'screen_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
