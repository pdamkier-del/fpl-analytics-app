"""Frozen-original evaluation only. No model calls or minute-to-PM refitting."""
import importlib.util
import math
from pathlib import Path
import statistics
from metrics import bernoulli,calibration,crps,error_summary,law_summary,probability
from labels import COMP

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('existing_pm_contracts',ROOT/'research/pm_defs/code/contracts.py')
contracts=importlib.util.module_from_spec(spec);spec.loader.exec_module(contracts)


def mean(values):
    values=[v for v in values if v is not None]
    return statistics.mean(values)if values else None


def baseline(player,bootstrap,fixtures,cutoff,fixture_count):
    from datetime import datetime
    parse=lambda x:datetime.fromisoformat(x.replace('Z','+00:00'))
    source=next((r for r in bootstrap['elements']if r['id']==player['id']),None)
    if source is None:return dict(start=None,minutes=None,points=None,ep_next=None)
    n=sum(1 for r in fixtures if r.get('finished')is True and r.get('kickoff_time')and parse(r['kickoff_time'])<parse(cutoff)
          and player['team_id']in[r['team_h'],r['team_a']])
    def finite(v):
        try:x=float(v)
        except(TypeError,ValueError):return None
        return x if math.isfinite(x)else None
    starts=finite(source.get('starts'));minutes=finite(source.get('minutes'));points=finite(source.get('total_points'))
    ongoing=any(r.get('kickoff_time')and parse(r['kickoff_time'])<parse(cutoff)and r.get('finished')is not True
                and player['team_id']in[r['team_h'],r['team_a']]for r in fixtures)
    valid=n>0 and not ongoing and starts is not None and 0<=starts<=n and minutes is not None and 0<=minutes<=90*n
    return dict(start=(starts+1)/(n+2)if valid else None,minutes=minutes/n if valid else None,
                points=points/n*fixture_count if valid and points is not None else None,
                ep_next=finite(source.get('ep_next')),denominator=n)


def component_probabilities(predicted,actual,position):
    out={}
    factor=4 if position in (1,2)else 1 if position==3 else None
    if factor:
        p=probability(predicted['cs_points']/factor);y=actual['cs_points']/factor
        if y not in (0,1):raise ValueError('Official CSaward is not binary')
        out['qualified_cs']=dict(p=p,y=y,**bernoulli(p,y))
    if position!=1:
        p=probability(predicted['dc_points']/2);y=actual['dc_points']/2
        if y not in (0,1):raise ValueError('Official DCaward is not binary')
        out['dc_award']=dict(p=p,y=y,**bernoulli(p,y))
    return out


def score(f,mm,bootstrap,fixtures,normalized,*,evidence_class='prospective'):
    if normalized['status']=='awaiting_results':
        return dict(status='awaiting_results',evidence_class=evidence_class,scored_rows=0)
    gw=f['gws'][0];actual={(r['id'],r['fixture']):r for r in normalized['rows']}
    original_mm={(r['player_id'],r['fixture_id']):r for r in mm['players']}
    fixture_rows=[];point_rows=[];warnings=[]
    next_events=[e['id']for e in bootstrap['events']if e.get('is_next')]
    ep_ok=next_events==[gw]
    rank=sorted(f['players'],key=lambda p:(-next(w for w in p['weeks']if w['gw']==gw)['xpts'],p['id']))[:50]
    top={p['id']for p in rank};missing={r['id']for r in normalized['missing']}
    for p in f['players']:
        if p['id']in missing:continue
        w=next(w for w in p['weeks']if w['gw']==gw)
        ref=baseline(p,bootstrap,fixtures,f['data_asof'],len(w['fixtures']))
        local=[]
        for item in w['fixtures']:
            fixture=int(item['fixture_uuid'].rsplit('-',1)[1]);a=actual.get((p['id'],fixture))
            if a is None:raise ValueError('Normalized fixture coverage disappeared')
            m=original_mm[p['player_uuid'],item['fixture_uuid']]
            pred={('bonus_points'if k=='expected_bonus'else k):v for k,v in item['components'].items()}
            if abs(contracts.canonical_total(pred)-item['xpts'])>1e-7:raise ValueError('Original component mean mismatch')
            if abs(contracts.canonical_total(a['components'])-a['points'])>1e-7:raise ValueError('Official component total mismatch')
            if a['dc_count']is not None and p['position']!=1:
                award=contracts.dc_award({1:'GK',2:'DEF',3:'MID',4:'FWD'}[p['position']],a['dc_count'],f['season'])
                if award!=a['components']['dc_points']:raise ValueError('Official DCcount/award disagreement')
            ps=probability(item['p_start']);pp=probability(m['p_play']);p60=probability(item['p_60_plus']);p90=probability(item['p_90'])
            participation=int(a['minutes']>0);b=bernoulli(pp,participation)
            row=dict(gw=gw,id=p['id'],fixture=fixture,position=p['position'],club=p['team_id'],role=m.get('normal_role','unknown'),
                     availability=m.get('availability','unknown'),rotation='low_start'if ps<.2 else'rotation'if ps<.8 else'high_start',
                     active=pp>=.2,top50=p['id']in top,p_start=ps,started=a['starts'],p_play=pp,played=participation,
                     xmins=item['xmins'],minutes=a['minutes'],start=None if a['starts']is None else bernoulli(ps,a['starts']),
                     appearance=b,p60=dict(p=p60,y=int(a['minutes']>=60),**bernoulli(p60,int(a['minutes']>=60))),
                     p90=dict(p=p90,y=int(a['minutes']==90),**bernoulli(p90,int(a['minutes']==90))),
                     q_sub=probability(item['q_sub']),bench_probability=(1-ps)*probability(item['q_sub']),
                     start_minutes=m.get('start_minutes'),sub_minutes=m.get('sub_minutes'),
                     predicted_components=pred,actual_components=a['components'],
                     predicted_goals=pred['goal_points']/{1:10,2:6,3:5,4:4}[p['position']],goals=a['goals'],
                     predicted_assists=pred['assist_points']/3,assists=a['assists'],
                     component_probabilities=component_probabilities(pred,a['components'],p['position']),
                     baseline_start=ref['start'],baseline_minutes=ref['minutes'],card_only=a['official_card_only'])
            row['start_log_loss_delta']=row['start']['log_loss']-bernoulli(ref['start'],a['starts'])['log_loss']if row['start']is not None and ref['start']is not None else None
            bins=item['distribution']['minute_bins'];category=0 if a['minutes']==0 else 1 if a['minutes']<60 else 2 if a['minutes']<90 else 3
            if len(bins)!=4 or abs(sum(bins)-1)>1e-7:raise ValueError('Invalid coarse minute law')
            row['minute_bin_brier']=sum((probability(v)-int(i==category))**2 for i,v in enumerate(bins))
            # p_zero is minutes==0; explicitly never interpreted as zero points.
            row['pm_sample_zero_minute_brier']=bernoulli(item['distribution']['p_zero'],int(a['minutes']==0))['brier']
            row['bench_brier']=None if a['starts']is None else bernoulli(row['bench_probability'],int(not a['starts']and participation))['brier']
            row['conditional_cameo_brier']=bernoulli(row['q_sub'],participation)['brier']if a['starts']==0 else None
            fixture_rows.append(row);local.append(a)
        actual_points=sum(a['points']for a in local);actual_minutes=sum(a['minutes']for a in local)
        samples=w['scenarios']['points'];mins=w['scenarios']['minutes']
        if abs(mean(samples)-w['xpts'])>1e-7:raise ValueError('Original xP/scenario mismatch')
        law=law_summary(samples,actual_points,f'{gw}:{p["id"]}')
        ep=ref['ep_next']if ep_ok else None
        point_rows.append(dict(gw=gw,id=p['id'],position=p['position'],club=p['team_id'],
            role=fixture_rows[-1]['role']if local else'blank',top50=p['id']in top,
            xp=w['xpts'],points=actual_points,crps=law['crps'],law=law,
            minute_total_crps=crps(mins,actual_minutes),ep_next=ep,season_points_mean=ref['points'],
            squared_error=(w['xpts']-actual_points)**2,
            ep_mse_delta=(w['xpts']-actual_points)**2-(ep-actual_points)**2 if ep is not None else None))
    def summarize(fr,pr):
        starts=[r for r in fr if r['start']is not None]
        mm_out=dict(fixture_rows=len(fr),known_starts=len(starts),start_log_loss=mean([r['start']['log_loss']for r in starts]),
            start_brier=mean([r['start']['brier']for r in starts]),appearance_brier=mean([r['appearance']['brier']for r in fr]),
            appearance_log_loss=mean([r['appearance']['log_loss']for r in fr]),
            minutes=error_summary([(r['xmins'],r['minutes'])for r in fr]),
            baseline_minutes=error_summary([(r['baseline_minutes'],r['minutes'])for r in fr if r['baseline_minutes']is not None]),
            p60_brier=mean([r['p60']['brier']for r in fr]),p90_brier=mean([r['p90']['brier']for r in fr]),
            p60_log_loss=mean([r['p60']['log_loss']for r in fr]),p90_log_loss=mean([r['p90']['log_loss']for r in fr]),
            coarse_minute_brier=mean([r['minute_bin_brier']for r in fr]),bench_brier=mean([r['bench_brier']for r in fr]),
            pm_sample_zero_minute_brier=mean([r['pm_sample_zero_minute_brier']for r in fr]),
            conditional_cameo_brier=mean([r['conditional_cameo_brier']for r in fr]),
            start_log_loss_delta=mean([r['start_log_loss_delta']for r in fr]),
            baseline_start_paired_rows=sum(r['start_log_loss_delta']is not None for r in fr),card_only_rows=sum(r['card_only']for r in fr),
            duration_if_started=error_summary([(r['start_minutes'],r['minutes'])for r in fr if r['started']==1 and r['start_minutes']is not None]),
            duration_if_bench_appeared=error_summary([(r['sub_minutes'],r['minutes'])for r in fr if r['started']==0 and r['played']and r['sub_minutes']is not None]))
        pm_out=dict(player_gw_rows=len(pr),points=error_summary([(r['xp'],r['points'])for r in pr]),
            crps=mean([r['crps']for r in pr]),gw_minute_crps=mean([r['minute_total_crps']for r in pr]),
            ep_next=error_summary([(r['ep_next'],r['points'])for r in pr if r['ep_next']is not None]),
            season_mean=error_summary([(r['season_points_mean'],r['points'])for r in pr if r['season_points_mean']is not None]),
            ep_mse_delta=mean([r['ep_mse_delta']for r in pr]),ep_paired_rows=sum(r['ep_mse_delta']is not None for r in pr))
        pm_out['goal_counts']=error_summary([(r['predicted_goals'],r['goals'])for r in fr])
        pm_out['assist_counts']=error_summary([(r['predicted_assists'],r['assists'])for r in fr])
        pm_out['intervals']={k:dict(coverage=mean([int(r['law']['intervals'][k]['covered'])for r in pr]),
            forecast_mass=mean([r['law']['intervals'][k]['forecast_mass']for r in pr]),
            width=mean([r['law']['intervals'][k]['width']for r in pr]))for k in ['0.5','0.8','0.95']}
        for name in ['qualified_cs','dc_award']:
            vals=[r['component_probabilities'][name]for r in fr if name in r['component_probabilities']]
            pm_out[name]=dict(n=len(vals),brier=mean([r['brier']for r in vals]),log_loss=mean([r['log_loss']for r in vals]))
        pm_out['haul_brier']={k:mean([r['law']['haul'][k]['brier']for r in pr])for k in ['2','5','10']}
        return dict(mm=mm_out,pm=pm_out)
    overall=summarize(fixture_rows,point_rows);groups=[]
    for dimension in ['position','club','role','rotation','availability','active','top50']:
        for key in sorted({str(r[dimension])for r in fixture_rows}):
            selected=[r for r in fixture_rows if str(r[dimension])==key];ids={r['id']for r in selected}
            groups.append(dict(dimension=dimension,group=key,**summarize(selected,[r for r in point_rows if r['id']in ids])))
    cal={name:calibration([(r[name]['p'],r[name]['y'])for r in fixture_rows])for name in ['p60','p90']}
    cal['start']=calibration([(r['p_start'],r['started'])for r in fixture_rows if r['started']is not None])
    cal['appearance']=calibration([(r['p_play'],r['played'])for r in fixture_rows])
    components=[]
    for comp in COMP:
        for cohort in ['all','active','top50']:
            rows=fixture_rows if cohort=='all'else[r for r in fixture_rows if r[cohort]]
            components.append(dict(component=comp,cohort=cohort,**error_summary([(r['predicted_components'][comp],r['actual_components'][comp])for r in rows]),
                observed_nonzero=sum(r['actual_components'][comp]!=0 for r in rows)))
    for name in ['qualified_cs','dc_award']:
        vals=[r['component_probabilities'][name]for r in fixture_rows if name in r['component_probabilities']]
        cal[name]=calibration([(r['p'],r['y'])for r in vals])
    for threshold in ['2','5','10']:
        cal['points_ge'+threshold]=calibration([(r['law']['haul'][threshold]['p'],r['law']['haul'][threshold]['y'])for r in point_rows])
    pit=[0]*10
    for r in point_rows:pit[min(9,int(r['law']['randomized_pit']*10))]+=1
    exposure=[]
    for lo,hi in [(0,0),(1,59),(60,89),(90,90)]:
        rows=[r for r in fixture_rows if lo<=r['minutes']<=hi]
        exposure.append(dict(actual_minute_range=[lo,hi],n=len(rows),
            minute_bias=mean([r['xmins']-r['minutes']for r in rows]),
            point_bias=mean([sum(r['predicted_components'].values())-sum(r['actual_components'].values())for r in rows]),
            interpretation='Outcome-conditioned descriptive association; not causal attribution or a deployable correction'))
    priority=sorted([r for r in components if r['cohort']=='top50'and r['n']],key=lambda r:(-abs(r['bias']),-r['mae'],r['component']))
    complete=normalized['status']=='complete'and normalized['mm_start_unknown']==0
    return dict(schema='fpl-frozen-mm-pm-evaluation/v1',gw=gw,season=f['season'],status='complete'if complete else'partial_data',
        evidence_class=evidence_class,forecast_sha256=f['forecast_sha256'],summary=overall,groups=groups,calibration=cal,
        components=components,priority=priority,fixture_rows=fixture_rows,point_rows=point_rows,pit_bins=pit,exposure_profiles=exposure,
        coverage={k:normalized[k]for k in ['missing','expected_players','scored_players','mm_start_unknown','fixtures']},
        identified_limitations=['No forecast background-BPS law','No per-fixture full minute PMF in DGW','No save-count law from save buckets',
            'No verified injury-return episode cohort','Minute/point residual association is not causal decomposition'],
        model_refitted=False,model_changed=False,formal_inference=False)
