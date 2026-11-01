"""B-only dated return probabilities fitted to prior observed return episodes.

First recorded FPL appearance is an observable return proxy, not medical
clearance. A date estimate is never a certain availability switch.
"""
from pathlib import Path
import re,sqlite3
import numpy as np
import pandas as pd
VERSION='B-dated-return-survival-v1'
MONTHS={name:i for i,name in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'],1)}

def parse_date(text,observed_at,news_added=None):
    seen=pd.Timestamp(observed_at)
    if seen.tzinfo is None:raise ValueError('Dated news requires timezone')
    ref=pd.Timestamp(news_added)if news_added and pd.notna(news_added)else seen
    if ref.tzinfo is None or ref>seen:raise ValueError('Dated news timestamp after receipt')
    m=re.search(r'Expected back\s+(\d{1,2})\s+([A-Za-z]{3,9})(?:\s+(20\d{2}))?\b',str(text),re.I)
    if not m:return None
    month=MONTHS.get(m[2][:3].lower())
    if month is None:return None
    candidates=[]
    for year in ([int(m[3])]if m[3]else[ref.year-1,ref.year,ref.year+1]):
        try:day=pd.Timestamp(year=year,month=month,day=int(m[1]),tz='Europe/London').tz_convert('UTC')
        except ValueError:continue
        if m[3]or ref-pd.Timedelta(days=31)<=day<=ref+pd.Timedelta(days=183):candidates.append(day)
    return min(candidates,key=lambda d:abs((d-ref).total_seconds()))if candidates else None

def episodes(root,cutoff=None):
    from fpl_v1_1_model.team_news_history import read_split_gzip_jsonl
    root=Path(root);reports=pd.concat([read_split_gzip_jsonl(root/'work/mm-integration-source/news-2024','predeadline_strict.jsonl.gz'),read_split_gzip_jsonl(root/'data_v1_1/derived/team_news_audit/2025-26-v2','predeadline_strict.jsonl.gz')],ignore_index=True)
    reports=reports[reports.strict_eligible.eq(True)&reports.timing_verified.eq(True)&reports.raw_status.eq('i')].copy()
    reports['clock']=pd.to_datetime(reports.effective_at,utc=True,format='mixed');
    if cutoff is not None:reports=reports[reports.clock.lt(pd.Timestamp(cutoff))]
    reports=reports.sort_values('clock').drop_duplicates(['season','player_uuid','team_id','raw_news','news_added'])
    with sqlite3.connect(f'file:{root/"work/core.sqlite3"}?mode=ro',uri=True)as db:h=pd.read_sql_query('SELECT season,player_uuid,team_id,kickoff_at,minutes FROM player_fixture_observations WHERE is_final=1',db)
    h['kick']=pd.to_datetime(h.kickoff_at,utc=True);h['known']=h.kick+pd.to_timedelta(np.where(h.season.eq('2025-26'),3,4),unit='h');
    if cutoff is not None:h=h[h.known.lt(pd.Timestamp(cutoff))]
    history={(s,p,int(t)):g.sort_values('kick')for(s,p,t),g in h.groupby(['season','player_uuid','team_id'])};rows=[]
    for r in reports.itertuples():
        try:expected=parse_date(r.raw_news,r.clock,r.news_added)
        except ValueError:continue
        if expected is None:continue
        g=history.get((r.season,r.player_uuid,int(r.team_id)))
        if g is None:continue
        future=g[g.kick.gt(r.clock)]
        if future.empty:continue
        returned=future[future.minutes.gt(0)]
        end=returned.iloc[0]if len(returned)else future.iloc[-1]
        rows.append(dict(season=r.season,player_uuid=r.player_uuid,team_id=int(r.team_id),report_known_at=r.clock,expected_at=expected,event=bool(len(returned)),end_at=end.kick,outcome_known_at=end.known,residual_days=(end.kick-expected).total_seconds()/86400,source_id=r.source_id))
    f=pd.DataFrame(rows)
    if f.empty:raise ValueError('No dated medical episodes')
    # Repeated weekly snapshots/date updates cannot multiply one return outcome.
    f=f.sort_values('report_known_at').drop_duplicates(['season','player_uuid','team_id','end_at'])
    return f

def probability(training,cutoff,expected,target,min_risk=20):
    cut=pd.Timestamp(cutoff);expected=pd.Timestamp(expected);target=pd.Timestamp(target)
    if target<cut:raise ValueError('Return target precedes cutoff')
    h=training[pd.to_datetime(training.outcome_known_at,utc=True).lt(cut)&pd.to_datetime(training.report_known_at,utc=True).lt(cut)]
    now=(cut-expected).total_seconds()/86400;future=(target-expected).total_seconds()/86400
    h=h[h.residual_days.gt(now)] # Conditional on still unavailable at this receipt.
    if len(h)<min_risk:return None,dict(status='Not Available',reason='insufficient prior comparable return risk set',risk_set=len(h))
    survival=1.;risk=len(h)
    for time,g in h.sort_values('residual_days').groupby('residual_days'):
        if time>future:break
        deaths=int(g.event.sum());survival*=1-deaths/risk;risk-=len(g)
    # Jeffreys smoothing reflects finite-sample uncertainty at empirical tails.
    p=((1-survival)*len(h)+.5)/(len(h)+1)
    return float(p),dict(status='fitted',risk_set=len(h),last_training_outcome=str(pd.to_datetime(h.outcome_known_at,utc=True).max()),label='first subsequent recorded PL appearance, not medical clearance',model=VERSION)

def annotate(frame,bootstrap,observed_at,training):
    out=frame.copy();official={p['id']:p for p in bootstrap['elements']};caps=[];statuses=[];dates=[]
    for r in out.itertuples():
        p=official[int(r.fpl_element)];cap=1.;status='not_applicable';date=None
        if p['status']in ['i','d']and not r.news_eligible:
            expected=parse_date(p.get('news'),observed_at,p.get('news_added'))
            if expected is not None:
                date=expected.isoformat();prob,receipt=probability(training,r.cutoff,expected,r.target_kickoff)
                status=receipt['status']
                if prob is not None:cap=prob
            else:status='Not Available: no unambiguous source-known date'
        caps.append(cap);statuses.append(status);dates.append(date)
    out['medical_return_cap']=caps;out['medical_return_status']=statuses;out['medical_expected_at']=dates
    return out
