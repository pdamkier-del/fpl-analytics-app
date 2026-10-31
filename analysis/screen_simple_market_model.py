"""Offline analytic MM/PM ablation. Never imported by app or production.

Market timing is unknown: these scores cannot authorize live promotion.
"""
import gzip, hashlib, json, sqlite3
from pathlib import Path
from dataclasses import replace
import numpy as np
import pandas as pd
from scipy.optimize import least_squares, brentq
from scipy.special import expit, logit
from scipy.stats import poisson, skellam, nbinom
from b_chain_contract import field_marginals
from gk_joint_bridge import marginals
from test_separated_goal_head import decode, UNKNOWN

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/simple-market-model-20261025'
ALIASES={'Man Utd':'Man United','Spurs':'Tottenham','Manchester City':'Man City','Manchester Utd':'Man United','Manchester United':'Man United',
 'Newcastle United':'Newcastle','Newcastle Utd':'Newcastle','Nottingham Forest':"Nott'm Forest",
 "Nott'm Forest":"Nott'm Forest",'Nott\u2019m Forest':"Nott'm Forest",'Tottenham Hotspur':'Tottenham',
 'Wolverhampton Wanderers':'Wolves','Brighton & Hove Albion':'Brighton','Leicester City':'Leicester',
 'Ipswich Town':'Ipswich','Leeds United':'Leeds','West Ham United':'West Ham','Sheffield Utd':'Sheffield United'}


def fair(odds):
    x=np.asarray(odds,float)
    if not np.isfinite(x).all() or (x<=1).any():raise ValueError('Invalid odds')
    p=1/x
    return p/p.sum()


def implied_means(odds):
    p=fair(odds[:3]);over=fair(odds[3:])[0]
    def residual(x):
        h,a=x
        return np.r_[skellam.sf(0,h,a)-p[0],skellam.pmf(0,h,a)-p[1],poisson.sf(2,h+a)-over]
    fit=least_squares(residual,[1.5,1.2],bounds=(.02,7),xtol=1e-10,ftol=1e-10,gtol=1e-10)
    if not fit.success:raise ValueError('Market inversion failed')
    return fit.x,float(np.linalg.norm(fit.fun))


def project(raw,total):
    raw=np.clip(np.asarray(raw,float),1e-6,1-1e-6)
    if len(raw)<total:raise ValueError('Insufficient candidate players')
    if len(raw)==total:return np.ones(len(raw))
    z=logit(raw)
    b=brentq(lambda s:expit(z+s).sum()-total,-50,50)
    return expit(z+b)


def simple_players(inp,history):
    updated=[]
    for p in inp.players:
        h=history.get(p.player_id,pd.DataFrame()).tail(8)
        if len(h):
            w=.8**np.arange(len(h)-1,-1,-1)
            start=(float(w@h.started)+2*p.p_start)/(w.sum()+2)
            b=h[h.started.eq(0)];q=(float(b.minutes.gt(0).sum())+2*p.p_cameo_given_bench)/(len(b)+2)
            s=h[h.started.eq(1)].minutes;c=h[h.started.eq(0)&h.minutes.gt(0)].minutes
            sm=(float(s.sum())+3*78)/(len(s)+3);cm=(float(c.sum())+3*15)/(len(c)+3)
        else:start,q,sm,cm=p.p_start,p.p_cameo_given_bench,78.,15.
        # Explicit unavailable/locked start probabilities remain locked.
        if p.p_start==0:start=0
        if p.p_start==1:start=1
        updated.append(replace(p,p_start=float(start),p_cameo_given_bench=float(q),start_minutes_mean=float(sm),cameo_minutes_mean=float(cm)))
    for team in (inp.home_team,inp.away_team):
        for keeper,total in [(False,10),(True,1)]:
            ids=[i for i,p in enumerate(updated) if p.team==team and p.is_keeper==keeper]
            locked=[i for i in ids if updated[i].p_start==1];free=[i for i in ids if 0<updated[i].p_start<1]
            remaining=total-len(locked)
            if remaining<0:raise ValueError('Too many locked starters')
            if free:
                values=np.zeros(len(free)) if remaining==0 else project([updated[i].p_start for i in free],remaining)
                for i,v in zip(free,values):updated[i]=replace(updated[i],p_start=float(v))
            elif remaining:raise ValueError('Insufficient eligible starters')
    return replace(inp,players=tuple(updated))


def pmfs(inp):
    m={p.player_id:field_marginals(p) for p in inp.players if not p.is_keeper}
    for team in (inp.home_team,inp.away_team):m.update(marginals([p for p in inp.players if p.team==team and p.is_keeper]))
    return m


def expected_points(inp,masses,means,bonus):
    minutes=np.arange(91);exposure={k:float(v@minutes)/90 for k,v in masses.items()};result={}
    for team,lam,opp,pen in [(inp.home_team,means[0],means[1],inp.lambda_home_penalties),(inp.away_team,means[1],means[0],inp.lambda_away_penalties)]:
        players=[p for p in inp.players if p.team==team]
        def shares(attr):
            v=np.array([max(0,getattr(p,attr))*exposure[p.player_id] for p in players]);return v/v.sum() if v.sum() else np.zeros(len(v))
        gs,ass,ps=shares('goal_weight'),shares('assist_weight'),shares('penalty_weight')
        conversion=sum(ps[i]*p.penalty_conversion for i,p in enumerate(players));ordinary=max(0,lam-pen*conversion)
        for i,p in enumerate(players):
            mass=masses[p.player_id];e=exposure[p.player_id];play=1-mass[0];p60=mass[60:].sum()
            goals=ordinary*gs[i]+pen*ps[i]*p.penalty_conversion
            gp=10 if p.is_keeper else 6 if p.position=='DEF' else 5 if p.position=='MID' else 4
            cp=4 if p.position in ('DEF','GK','GKP') else 1 if p.position=='MID' else 0
            # An explicit approximation: independent exposure-weighted recipient shares.
            assists=lam*inp.assist_probability_per_goal*ass[i]
            cs=float(mass[60:]@np.exp(-opp*minutes[60:]/90))
            score=play+p60+gp*goals+3*assists+cp*cs+bonus.get(p.player_id,0)*e
            score-=play*(p.discipline.yellow+3*p.discipline.red+2*p.p_own_goal)
            score-=2*pen*ps[i]*(1-p.penalty_conversion)
            if p.position in ('DEF','GK','GKP'):
                mu=opp*minutes/90
                score-=float(mass@((mu-(1-np.exp(-2*mu))/2)/2))
            if p.is_keeper:
                mu=p.lambda_saves*minutes/90
                buckets=sum(poisson.sf(3*k-1,mu) for k in range(1,40))
                score+=float(mass@buckets)
                otherpen=inp.lambda_away_penalties if team==inp.home_team else inp.lambda_home_penalties
                otherconv=inp.away_penalty_conversion if team==inp.home_team else inp.home_penalty_conversion
                score+=5*otherpen*(1-otherconv)*inp.p_penalty_save_given_miss*e
            elif inp.bps_rules!='2024-25':
                mu=p.dc_mu_90*minutes/90;t=10 if p.position=='DEF' else 12
                prob=nbinom.sf(t-1,1/p.dc_alpha,1/(1+p.dc_alpha*mu)) if p.dc_alpha>1e-12 else poisson.sf(t-1,mu)
                score+=2*float(mass@prob)
            result[p.player_id]=float(score)
    return result


def main():
    protocol=json.loads((OUT/'protocol.json').read_text())
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--prepared-tasks',type=Path);args=ap.parse_args()
    if args.prepared_tasks:
        tasks=json.loads(gzip.open(args.prepared_tasks,'rt').read())
    else:
        from test_separated_goal_head import prepare_tasks
        fitted=json.loads((ROOT/'analysis/results/nonpenalty-goal-head-20261023/final-v2/model.json').read_text())
        tasks,_=prepare_tasks(fitted,OUT)
    baseline=pd.read_csv(ROOT/'analysis/results/physical-timeline-20261024/predictions.csv.gz');baseline=baseline[baseline.arm.eq('baseline')]
    with sqlite3.connect(f'file:{ROOT/"work/core.sqlite3"}?mode=ro',uri=True) as db:
        core=pd.read_sql_query("SELECT * FROM player_fixture_observations WHERE is_final=1 AND season IN ('2024-25','2025-26')",db)
    core['known']=pd.to_datetime(core.kickoff_at,utc=True)+pd.Timedelta(hours=4)
    if core.duplicated(['season','fixture_uuid','player_uuid']).any():raise ValueError('Duplicate actuals')
    byfixture=core.groupby(['season','fixture_uuid']);rows=[];markets=[];historycache={}
    maps={};odds={};records={}
    for season in ('2024-25','2025-26'):
        maps[season]={str(r.id):ALIASES.get(r['name'],r['name']) for _,r in pd.read_csv(OUT/f'raw/teams-{season}.csv').iterrows()}
        d=pd.read_csv(OUT/f'raw/{season}.csv');d['date']=pd.to_datetime(d.Date,dayfirst=True).dt.strftime('%Y-%m-%d')
        odds[season]=d.set_index(['date','HomeTeam','AwayTeam'],verify_integrity=True)
        for line in gzip.open(ROOT/f'analysis/results/general-conversion-20261020/{season}_prepared.jsonl.gz','rt'):
            r=json.loads(line);records[season,r['core_fixture']]=r
    for n,(season,fx,seed,data,dist,factors,conditional) in enumerate(tasks):
        inp=decode(data);inp=replace(inp,players=tuple(replace(p,goal_weight=factors[p.player_id]) for p in inp.players))
        rec=records[season,fx];cut=pd.Timestamp(rec['cutoff']);ck=(season,str(cut))
        if ck not in historycache:
            past=core[core.season.eq(season)&core.known.lt(cut)].sort_values('known')
            historycache[ck]={pid:g for pid,g in past.groupby('player_uuid')}
        hist=historycache[ck];bonus={pid:float(g.bonus.sum())*90/(g.minutes.sum()+450) for pid,g in hist.items()}
        label=byfixture.get_group((season,fx));date=str(label.kickoff_at.iloc[0])[:10]
        row=odds[season].loc[(date,maps[season][inp.home_team],maps[season][inp.away_team])]
        means,residual=implied_means(row[['AvgH','AvgD','AvgA','Avg>2.5','Avg<2.5']].values)
        actual=[int(label[label.team_id.eq(int(t))].goals.sum()) for t in (inp.home_team,inp.away_team)]
        markets.append(dict(season=season,fixture_uuid=fx,cutoff=str(cut),kickoff=str(label.kickoff_at.iloc[0]),market_clock_known=False,fit_residual=residual,home=means[0],away=means[1],baseline_home=inp.lambda_home_goals,baseline_away=inp.lambda_away_goals,actual_home=actual[0],actual_away=actual[1]))
        for mm,cur in [('frozen',inp),('simple',simple_players(inp,hist))]:
            mass=pmfs(cur)
            for source,lams in [('analytic',[inp.lambda_home_goals,inp.lambda_away_goals]),('market',means)]:
                xp=expected_points(cur,mass,lams,bonus)
                for p in cur.players:
                    if p.player_id.startswith(UNKNOWN):continue
                    m=mass[p.player_id]
                    rows.append(dict(season=season,fixture_uuid=fx,player_uuid=p.player_id,arm=f'{source}_PM_{mm}_MM',keeper=p.is_keeper,baseline_p_start=next(q.p_start for q in inp.players if q.player_id==p.player_id),p_start=p.p_start,xp=xp[p.player_id],xmins=float(m@np.arange(91)),p0=m[0],p60=m[60:].sum(),p90=m[90]))
        if (n+1)%50==0:print('Scored',n+1,flush=True)
    scored=pd.DataFrame(rows).merge(core[['season','fixture_uuid','player_uuid','minutes','started','total_points']],on=['season','fixture_uuid','player_uuid'],validate='many_to_one')
    baseline=baseline.merge(core[['season','fixture_uuid','player_uuid','started']],on=['season','fixture_uuid','player_uuid'],validate='one_to_one');baseline['p_start']=baseline.baseline_p_start;baseline['arm']='archived_B'
    allrows=pd.concat([baseline,scored],ignore_index=True)
    if len(scored)!=len(baseline)*4:raise ValueError('Cohort mismatch')
    # Frozen MM must reproduce the sealed baseline analytic marginals.
    frozen=scored[scored.arm.eq('analytic_PM_frozen_MM')].merge(baseline,on=['season','fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_b'))
    parity=max(float(abs(frozen[c]-frozen[c+'_b']).max()) for c in ['xmins','p0','p60','p90','p_start'])
    if parity>1e-7:raise ValueError(f'Frozen MM differs {parity}')
    metrics=[]
    for (season,arm),g in allrows.groupby(['season','arm']):
        for cohort,v in {'all':g,'played':g[g.minutes.gt(0)],'rotation':g[g.baseline_p_start.between(.2,.85)&~g.keeper],'keeper':g[g.keeper]}.items():
            metrics.append(dict(season=season,arm=arm,cohort=cohort,rows=len(v),minute_mae=float(abs(v.xmins-v.minutes).mean()),minute_bias=float((v.xmins-v.minutes).mean()),xp_mae=float(abs(v.xp-v.total_points).mean()),xp_bias=float((v.xp-v.total_points).mean()),start_brier=float(((v.p_start-v.started)**2).mean()),**{f'p{k}_brier':float(((v[f'p{k}']-(v.minutes.eq(0) if k==0 else v.minutes.ge(k)))**2).mean()) for k in [0,60,90]}))
    metric=pd.DataFrame(metrics);bootstrap=[];rng=np.random.default_rng(20261025)
    for season,g in allrows.groupby('season'):
        b=g[g.arm.eq('archived_B')]
        for arm,a in g[g.arm.ne('archived_B')].groupby('arm'):
            p=a.merge(b,on=['fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_b'))
            p['delta']=abs(p.xp-p.total_points)-abs(p.xp_b-p.total_points)
            agg=p.groupby('fixture_uuid').delta.agg(['sum','count']).to_numpy();idx=rng.integers(0,len(agg),(1000,len(agg)));res=agg[idx].sum(axis=1);boot=res[:,0]/res[:,1]
            bootstrap.append(dict(season=season,arm=arm,xp_mae_delta=float(p.delta.mean()),ci95=np.quantile(boot,[.025,.975]).tolist()))
    allrows.to_csv(OUT/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0});metric.to_csv(OUT/'metrics.csv',index=False);pd.DataFrame(markets).to_csv(OUT/'team-markets.csv',index=False)
    receipt=dict(research_only=True, minute_model='hybrid ablation retaining frozen B prior, not standalone', input_model_sha256=hashlib.sha256((ROOT/'analysis/results/nonpenalty-goal-head-20261023/final-v2/model.json').read_bytes()).hexdigest(), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), fixtures=len(tasks),players_per_arm=len(baseline),frozen_mm_max_error=parity,bootstrap=bootstrap,activation=False,production_changed=False,deadline_safe_market_test=False,protocol_sha256=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest(),sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/'raw').glob('*.csv'))})
    (OUT/'decision.json').write_text(json.dumps(receipt,indent=2)+'\n');print(metric[metric.cohort.eq('all')].to_string(index=False))

if __name__=='__main__':main()
