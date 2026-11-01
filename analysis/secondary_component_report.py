"""Summarize isolated secondary-component replay without parameter fitting."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from secondary_components import INPUT

BINARY={'p60','cs','save3','save6','save9','dc_hit','bonus1','bonus2','bonus3'}
COMPONENTS=['cs','cs_pts','saves','save3','save6','save9','save_pts','penalty_save_pts','dc_hit','dc_pts','bonus','bonus1','bonus2','bonus3','bps','gc_pts','negative_pts']


def intervals(g, error):
    """Separate fixture and player-cluster bootstraps; neither is an IID row CI."""
    result={}
    for key in ('fixture_uuid','player_uuid'):
        z=pd.DataFrame({'cluster':g[key].astype(str),'e':error}).groupby('cluster').e.agg(['sum','count'])
        if len(z)<2: continue
        rng=np.random.default_rng(20261101)
        ids=rng.integers(0,len(z),(1000,len(z)))
        means=z['sum'].to_numpy()[ids].sum(axis=1)/z['count'].to_numpy()[ids].sum(axis=1)
        lo,hi=np.quantile(means,[.025,.975]);result[key+'_bias_lo']=float(lo);result[key+'_bias_hi']=float(hi)
    return result


def metric(g,component,cluster=True):
    p=pd.to_numeric(g['p_'+component],errors='coerce');y=pd.to_numeric(g['y_'+component],errors='coerce')
    valid=np.isfinite(p)&np.isfinite(y);g=g.loc[valid];p=p[valid].to_numpy();y=y[valid].to_numpy()
    if not len(g):return None
    e=p-y
    out=dict(n=len(g),positive_labels=int((y>0).sum()),sparse=bool(g.fixture_uuid.nunique()<20 or (component in BINARY and (y>0).sum()<20)),fixtures=g.fixture_uuid.nunique(),players=g.player_uuid.nunique(),pred=float(p.mean()),actual=float(y.mean()),bias=float(e.mean()),mae=float(np.abs(e).mean()),rmse=float(np.sqrt(np.mean(e*e))))
    if cluster: out.update(intervals(g,e))
    if component in BINARY:
        q=np.clip(p,1e-6,1-1e-6);out.update(brier=float(np.mean(e*e)),log_loss=float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q))))
    return out


def allowed(g,component):
    if component in ['cs','cs_pts']:g=g[g.position.isin(['GK','GKP','DEF','MID'])]
    if component in ['saves','save3','save6','save9','save_pts','penalty_save_pts']:g=g[g.position.isin(['GK','GKP'])]
    if component in ['dc_hit','dc_pts']:g=g[g.position.isin(['DEF','MID','FWD'])]
    if component=='gc_pts':g=g[g.position.isin(['GK','GKP','DEF'])]
    return g


def summarize(frame,out):
    df=frame[~frame.player_uuid.str.startswith('__unlisted_goalkeeper__:')].copy()
    base=df[(df.rep==0)&(df.draws==2000)&df.position.ne('TEAM')].copy()
    value=base.position.map({'GK':4,'GKP':4,'DEF':4,'MID':1,'FWD':0})
    base['p_cs_pts']=base.p_cs*value; base['y_cs_pts']=base.y_cs*value
    df['p_cs_pts']=df.p_cs*df.position.map({'GK':4,'GKP':4,'DEF':4,'MID':1,'FWD':0,'TEAM':0})
    df['y_cs_pts']=df.y_cs*df.position.map({'GK':4,'GKP':4,'DEF':4,'MID':1,'FWD':0,'TEAM':0})
    base['xm_band']=pd.cut(base.p_minutes,[-1,30,60,80,91],labels=['0-30','30-60','60-80','80-90']).astype(str)
    base['p60_band']=pd.cut(base.p_p60,[-.01,.2,.5,.8,.95,1.01]).astype(str)
    base['actual_minute_band']=pd.cut(base.actual_minutes,[-1,0,59,89,91],labels=['DNP','1-59','60-89','90']).astype(str)
    base['lambda_decile']=base.groupby('season').lambda_opp.transform(lambda v:pd.qcut(v,10,labels=False,duplicates='drop'))
    summary=[];reliability=[];coverage=[]
    for component in COMPONENTS:
        pool=allowed(base,component)
        for keys in [('season','position'),('season','position','xm_band'),('season','position','p60_band'),('season','position','actual_minute_band'),('season','position','lambda_decile'),('season','position','prior_type'),('season','position','team'),('season','position','source')]:
            for values,g in pool.groupby(list(keys),dropna=False):
                labels=dict(zip(keys,values));m=metric(g,component)
                if m: summary.append(dict(component=component,group='|'.join(keys),**labels,**m))
        for (season,pos),g in pool.groupby(['season','position']):
            coverage.append(dict(component=component,season=season,position=pos,eligible=len(g),labels=int(g['y_'+component].notna().sum())))
            if component in BINARY:
                for band,b in g.groupby(pd.cut(g['p_'+component],np.linspace(0,1,11),include_lowest=True),observed=True):
                    m=metric(b,component)
                    if m:reliability.append(dict(component=component,season=season,position=pos,bin=str(band),**m))
    team=df[(df.rep==0)&(df.draws==2000)&df.position.eq('TEAM')]
    for season,g in team.groupby('season'):
        summary.append(dict(component='team_cs',group='season',season=season,position='TEAM',**metric(g,'cs')))
    pd.DataFrame(summary).to_csv(out/'metrics.csv',index=False)
    pd.DataFrame(reliability).to_csv(out/'reliability.csv',index=False)
    pd.DataFrame(coverage).to_csv(out/'label-coverage.csv',index=False)
    # Within-GW dependence: season-position bias intervals after clustering by GW.
    gw=[]
    for component in COMPONENTS:
        for (season,pos),g in allowed(base,component).groupby(['season','position']):
            g=g.dropna(subset=['p_'+component,'y_'+component]).copy()
            if not len(g):continue
            g['fixture_uuid']=g.gw
            m=metric(g,component)
            gw.append(dict(component=component,season=season,position=pos,n=len(g),gw_bias_lo=m.get('fixture_uuid_bias_lo'),gw_bias_hi=m.get('fixture_uuid_bias_hi')))
    pd.DataFrame(gw).to_csv(out/'gw-cluster-intervals.csv',index=False)
    # Paired nested-prefix convergence and independent-seed noise on fixed subset.
    mc=[]
    deep=df[df.draws==10000]
    for rep in (0,1):
        ref=deep[deep.rep==rep]
        for n in (400,2000):
            paired=df[(df.rep==rep)&(df.draws==n)].merge(ref,on=['season','fixture_uuid','player_uuid'],suffixes=('_small','_large'))
            for component in COMPONENTS:
                for pos,g in paired.groupby('position_small'):
                    d=g['p_'+component+'_small']-g['p_'+component+'_large']
                    mc.append(dict(comparison=f'{n}-10000',rep=rep,component=component,position=pos,n=len(g),mean_delta=d.mean(),rms_delta=np.sqrt((d*d).mean()),max_abs_delta=d.abs().max()))
    paired=deep[deep.rep==0].merge(deep[deep.rep==1],on=['season','fixture_uuid','player_uuid'],suffixes=('_small','_large'))
    for component in COMPONENTS:
        for pos,g in paired.groupby('position_small'):
            d=g['p_'+component+'_small']-g['p_'+component+'_large']
            mc.append(dict(comparison='10000-independent-seeds',rep=-1,component=component,position=pos,n=len(g),mean_delta=d.mean(),rms_delta=np.sqrt((d*d).mean()),max_abs_delta=d.abs().max()))
    pd.DataFrame(mc).to_csv(out/'mc-convergence.csv',index=False)
    score_rows=[]
    deep_cohort=df[df.fixture_uuid.isin(deep.fixture_uuid.unique()) & df.position.ne('TEAM')]
    for component in COMPONENTS:
        for keys,g in allowed(deep_cohort,component).groupby(['season','position','draws','rep']):
            m=metric(g,component,cluster=False)
            if m: score_rows.append(dict(component=component,season=keys[0],position=keys[1],draws=keys[2],rep=keys[3],**m))
    pd.DataFrame(score_rows).to_csv(out/'mc-score-metrics.csv',index=False)
    # Player-level diagnostic groups are descriptive, never automatic candidates.
    individuals=[]
    for component in COMPONENTS:
        for keys,g in allowed(base,component).groupby(['season','position','player_uuid']):
            valid=g.dropna(subset=['y_'+component]);
            if not len(valid):continue
            e=valid['p_'+component]-valid['y_'+component]
            individuals.append(dict(season=keys[0],position=keys[1],player_uuid=keys[2],component=component,n=len(valid),pred=valid['p_'+component].mean(),actual=valid['y_'+component].mean(),bias=e.mean(),mae=e.abs().mean()))
    pd.DataFrame(individuals).to_csv(out/'player-diagnostics.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    return base,team


def residuals(base,team,out):
    records=json.load(gzip.open(INPUT,'rt'));by={(r['season'],r['fixture_uuid']):r for r in records}
    rows=[];ties=[]
    from fpl_v1_1_model.bps import BPSComponents,bps_2024_25,bps_2025_26,allocate_bonus_points
    for (season,fx),g in base.groupby(['season','fixture_uuid']):
        r=by[season,fx];actual=r['actual'];scores={};bonus={}
        for row in g.itertuples():
            a=actual.get(row.player_uuid,{})
            if a.get('minutes',0)<=0:continue
            need=['bps','goals','fpl_assists','penalty_saves','saves','goals_conceded_on_pitch','penalty_misses','yellow_cards','fpl_red_cards','own_goals']
            if any(a.get(k) is None for k in need):continue
            scores[row.player_uuid]=int(a['bps']);bonus[row.player_uuid]=a.get('bonus')
            # 2024 goals have the same BPS value regardless of penalty origin.
            # 2025 scorers have only bounded residuals without a penalty split.
            exact=season=='2024-25' or a['goals']==0
            comp=BPSComponents(minutes=a['minutes'],position=row.position,non_penalty_goals=a['goals'],assists=a['fpl_assists'],clean_sheet=int(a['minutes']>=60 and a['goals_conceded_on_pitch']==0),penalty_saves=a['penalty_saves'],saves_total=a['saves'],saves_inside_box=a['penalty_saves'],goals_conceded=a['goals_conceded_on_pitch'],penalty_misses=a['penalty_misses'],yellow_cards=a['yellow_cards'],red_cards=a['fpl_red_cards'],own_goals=a['own_goals'])
            rule=bps_2024_25 if season=='2024-25' else bps_2025_26
            observed=a['bps']-rule(comp);expected=row.bg_rate*a['minutes']/90
            goal_bps={'GK':12,'GKP':12,'DEF':12,'MID':18,'FWD':24}[row.position]
            ambiguity=0 if exact else (goal_bps-12)*a['goals']
            rows.append(dict(season=season,fixture_uuid=fx,player_uuid=row.player_uuid,position=row.position,exact_event_partition=exact,goals=a['goals'],residual_lo=expected-observed-ambiguity,residual_hi=expected-observed,minutes=a['minutes'],assists=a['fpl_assists'],cs=comp.clean_sheet,red=a['fpl_red_cards'],team_score=r['goals'][str(row.team)],predicted_bg_sd=float(row.bg_sd or 0)*np.sqrt(a['minutes']/90),observed_partial_background=observed,expected_background=expected,residual=expected-observed))
        # Rank audit requires every actual participant to have a BPS label and
        # be represented in the forecast roster; otherwise skip the fixture.
        participants={pid for pid,a in actual.items() if a.get('minutes',0)>0}
        complete=participants==set(scores)
        if complete:
            allocated=allocate_bonus_points(scores)
            mismatch=sum(allocated[pid]!=bonus[pid] for pid in scores)
            top=sorted(scores.values(),reverse=True)
            t=team[(team.season==season)&(team.fixture_uuid==fx)].iloc[0]
            ties.append(dict(season=season,fixture_uuid=fx,complete=True,actual_top_tie=int(len(top)>1 and top[0]==top[1]),pred_top_tie=t.p_top_tie,actual_bonus_recipients=sum(v>0 for v in bonus.values()),pred_bonus_recipients=t.p_bonus_recipients,bonus_rank_mismatches=mismatch))
        else:ties.append(dict(season=season,fixture_uuid=fx,complete=False))
    d=pd.DataFrame(rows);d.to_csv(out/'bps-background-residuals.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    tables=[]
    d=d[d.exact_event_partition].copy()
    d['goal_band']=d.goals.clip(upper=2).astype(int).astype(str)
    d['minute_band']=pd.cut(d.minutes,[0,59,60,89,91]).astype(str)
    for keys in [('season','position'),('season','position','minute_band'),('season','position','team_score'),('season','position','cs'),('season','position','red'),('season','position','assists'),('season','position','goal_band')]:
        for values,g in d.groupby(list(keys)):
            e=g.residual.to_numpy()
            tables.append(dict(group='|'.join(keys),**dict(zip(keys,values)),n=len(g),residual_bias=e.mean(),observed_sd=g.observed_partial_background.std(),residual_sd=float(np.std(e,ddof=1)) if len(e)>1 else np.nan,predicted_rms_sd=float(np.sqrt(np.mean(g.predicted_bg_sd**2))),centered_variance_ratio=float(np.var(e,ddof=1)/np.mean(g.predicted_bg_sd**2)) if len(e)>1 and np.mean(g.predicted_bg_sd**2)>0 else np.nan,**intervals(g,e)))
    pd.DataFrame(tables).to_csv(out/'bps-background-groups.csv',index=False)
    pd.DataFrame(ties).to_csv(out/'bonus-rank-ties.csv',index=False)
    near=[]
    d=base[base.season.eq('2025-26')&base.position.isin(['DEF','MID','FWD'])].copy()
    d['threshold']=np.where(d.position.eq('DEF'),10,12);d['distance']=d.dc_count-d.threshold
    for (pos,dist),g in d[d.distance.between(-2,2)].groupby(['position','distance']):
        near.append(dict(position=pos,distance=dist,n=len(g),actual_hit=g.y_dc_hit.mean(),pred_hit=g.p_dc_hit.mean(),rule_mismatch=int(((g.dc_count>=g.threshold)!=(g.y_dc_hit>0)).sum())))
    pd.DataFrame(near).to_csv(out/'dc-threshold-boundaries.csv',index=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--predictions',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.predictions,low_memory=False);base,team=summarize(d,a.out);residuals(base,team,a.out)
    (a.out/'summary-scope.json').write_text(json.dumps(dict(fixtures=base[['season','fixture_uuid']].drop_duplicates().shape[0],player_fixture_rows=len(base),cs_label='RULE-DERIVED ONLY from actual FPL minutes and player goals_conceded_on_pitch; independent direct FPL CS label NOT AVAILABLE',dc_2024='Direct label NOT AVAILABLE; season-specific model DC is identically zero',bps_background='Partial event residual; exact generated-event partition for all 2024/25 rows and non-scorers in 2025/26. Scoring 2025/26 rows have bounds only because penalty-goal split NOT AVAILABLE. Unavailable Opta terms remain in background; 2025/26 brace variance not independently identified',log_loss_clip=1e-6,intervals='1000 deterministic percentile cluster bootstrap repetitions separately by fixture, player and GW; overlapping groups descriptive; no multiple-testing-adjusted candidate selection',acceptance='No parameter fitting on reused historical labels. Model change requires documented semantics defect or prospective/untouched improvement. No 2026/27 actual-label validation.'),indent=2)+'\n')
    paths=sorted(a.out.glob('*'));(a.out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in paths if p.is_file() and p.name!='SHA256SUMS'))

if __name__=='__main__':main()
