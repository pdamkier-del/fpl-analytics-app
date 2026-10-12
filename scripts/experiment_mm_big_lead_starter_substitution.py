#!/usr/bin/env python3
"""MM experiment: is an established PL starter's short appearance in a rout
a censored minutes observation rather than evidence of diminished fitness?

Fetch archived FotMob PL matchDetails only for public 2025/26 fixtures.
Original score AT substitution comes directly from confirmed event.homeScore,
event.awayScore, not final result. Outgoing player ID: event.swap[1].id.
Historic 11-man lineups from matchDetails.content.lineup.

Build chronological, cutoff-safe historical starter-duration features.
Select method on GW6-21; evaluate GW22-38 AFTER method choice.
THIS IS A SEPARATE starter-duration experiment, NOT frozen full-MM replay.
"""
from __future__ import annotations
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json,time
import numpy as np,pandas as pd,requests
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data_v1_1/raw/all-competitions-2025-26'
OUT=ROOT/'work/live-final-model'
API='https://www.fotmob.com/api/data/matchDetails'
NTHREADS=6
def fixtures():
    all=[]
    for path in sorted(RAW.glob('GW*/matches.csv')):
        x=pd.read_csv(path,low_memory=False)
        x=x[x.match_id.astype(str).str.contains('25-26-prem-') & x.finished.astype(str).str.lower().eq('true')]
        for v in x.itertuples(index=False):
            if not np.isfinite(v.fotmob_id):continue
            all.append(dict(id=int(v.fotmob_id),match_id=str(v.match_id),
                            gw=int(v.gameweek),kickoff=str(v.kickoff_time),
                            home=int(v.home_score),away=int(v.away_score)))
    unique={v['id']:v for v in all}
    assert len(unique)==380,(len(unique),len(all))
    return list(unique.values())
def extract(f):
    last=None
    for attempt in range(3):
        try:
            q=requests.get(API,params={'matchId':f['id']},
                headers={'User-Agent':'Mozilla/5.0 (FPL Analytics model research; historical public matches)', 'Accept':'application/json'},
                timeout=25)
            if q.status_code==429:
                time.sleep((attempt+1)*2.0)
                last='HTTP 429';continue
            if q.status_code!=200:return None,f'HTTP {q.status_code}'
            z=q.json()
            if not z.get('general',{}).get('finished'):return None,'not finished'
            hh=z['header']['teams']
            got=[int(hh[0]['score']),int(hh[1]['score'])]
            if got!=[f['home'],f['away']]:return None,f'final score mismatch {got} vs {f["home"],f["away"]}'
            content=z.get('content') or {}
            lu=content.get('lineup') or {}
            ev=((content.get('matchFacts') or {}).get('events') or {}).get('events') or []
            stars=[]
            for side,key in [('home','homeTeam'),('away','awayTeam')]:
                team=lu.get(key) or {}
                lineup=team.get('starters') or []
                if len(lineup)!=11:return None,f'{side}: incomplete starter list {len(lineup)}'
                tid=int(team['id'])
                for index,p in enumerate(lineup):
                    if p.get('id') is None:return None,'missing starter id'
                    stars.append(dict(id=int(p['id']),name=str(p.get('name')),
                           teamid=tid,side=side,goalkeeper=index==0))
            outgoing={}
            scores=[]
            for e in ev:
                if e.get('type')!='Substitution':continue
                swap=e.get('swap') or []
                if len(swap)!=2 or swap[1].get('id') is None:continue
                out=int(swap[1]['id'])
                if out in outgoing:return None,'double outgoing player'
                tm=float(e.get('time') or 0)
                hs=e.get('homeScore');a=e.get('awayScore')
                if hs is None or a is None:return None,'substitution without running score'
                margin=(int(hs)-int(a))*(1 if e.get('isHome') else -1)
                outgoing[out]=dict(minute=min(90.,tm),margin=margin,
                     injury=bool(e.get('injuredPlayerOut',False)),score=[int(hs),int(a)])
            # Integrity: outgoing starter entries should have matching team side,
            # no future event outcomes or scores used for prospective features.
            row=[]
            for p in stars:
                sub=outgoing.get(p['id'])
                row.append(dict(player_id=p['id'],name=p['name'],teamid=p['teamid'],
                    goalkeeper=p['goalkeeper'],gw=f['gw'],kickoff=f['kickoff'],
                    match_id=f['match_id'],minutes=90. if sub is None else sub['minute'],
                    substituted=sub is not None,
                    lead_at_sub=None if sub is None else int(sub['margin']),
                    injured_sub=False if sub is None else sub['injury'],
                    score_at_sub=None if sub is None else sub['score'],
                    home=p['side']=='home'))
            if len(row)!=22:return None,'wrong number of starters'
            if any(x['minutes']<1 or x['minutes']>90 for x in row):
                return None,'invalid substitution minutes'
            # Red-card matches: cannot safely treat non-substituted red-carded
            # starters as 90-minute players. Exclude from BOTH arms.
            status=z.get('header',{}).get('status') or {}
            if int(status.get('numberOfHomeRedCards') or 0)+int(status.get('numberOfAwayRedCards') or 0)>0:
                return dict(discard='red_card',rows=[]),None
            return dict(discard=None,rows=row),None
        except Exception as exc:
            last=str(exc)[:220];time.sleep(.25*(attempt+1))
    return None,last
def scored(star,target,method):
    last3=star[-3:]
    ms=np.asarray([r['minutes'] for r in last3],float)
    ws=np.array([.55,.75,1.0])[-len(last3):]
    mask=np.array([r['substituted'] and not r['injured_sub'] and
         55<=r['minutes']<=83 and r['lead_at_sub'] is not None and
         r['lead_at_sub']>=3 for r in last3],dtype=bool)
    if method=='ignore':
        ws=ws*np.where(mask,0.,1.)
        if ws.sum()<.01:return float(np.mean(ms))
    elif method=='downweight25':
        ws=ws*np.where(mask,.25,1.)
    elif method=='downweight50':
        ws=ws*np.where(mask,.5,1.)
    elif method=='impute90':
        ms=np.where(mask,90.,ms)
    elif method=='impute85':
        ms=np.where(mask,np.maximum(ms,85.),ms)
    elif method!='original':raise ValueError(method)
    return float(np.sum(ms*ws)/sum(ws))
def metric(frame,col):
    if frame.empty:return None
    e=frame[col].to_numpy(float)-frame.actual_minutes.to_numpy(float)
    return dict(n=int(len(e)),mae=round(float(np.abs(e).mean()),5),
        rmse=round(float(np.sqrt(np.mean(e*e))),5),
        bias=round(float(e.mean()),4),
        predicted=round(float(frame[col].mean()),3),
        observed=round(float(frame.actual_minutes.mean()),3))
def main():
    ff=fixtures()
    outputs=[];failed={}
    with ThreadPoolExecutor(max_workers=NTHREADS) as pool:
        future={pool.submit(extract,f):f for f in ff}
        for k,fut in enumerate(as_completed(future),1):
            f=future[fut]
            res,error=fut.result()
            if error:
                failed[str(f['id'])]=error
            elif res.get('discard') is None:
                outputs+=res['rows']
            if k%80==0:
                print('GAMESTATE_FETCH',json.dumps({'completed':k,'total':len(ff),
                      'scored_fixture_sides':len(outputs)//11,'failed':len(failed)}),flush=True)
    if len(outputs)<380*22*.8:raise AssertionError('Unverified game-state source coverage '+str(len(outputs)//22))
    a=pd.DataFrame(outputs).sort_values(['kickoff','match_id','player_id'])
    a['kickoff']=pd.to_datetime(a.kickoff,utc=True)
    a['player_id']=a.player_id.astype(int)
    a['teamid']=a.teamid.astype(int)
    if a.duplicated(['match_id','player_id']).any():raise AssertionError('duplicate FotMob player match')
    bymatch={mid:grp for mid,grp in a.groupby('match_id')}
    teams=defaultdict(list)
    for mid,g in bymatch.items():
        for tid in g.teamid.unique():
            teams[int(tid)].append((g.kickoff.iloc[0],mid))
    for ti in teams:
        teams[ti].sort()
    players=defaultdict(list)
    records=[]
    for mid,grp in sorted(bymatch.items(),key=lambda z:z[1].kickoff.iloc[0]):
        ko=grp.kickoff.iloc[0]
        for r in grp.itertuples(index=False):
            if r.goalkeeper:continue
            pid=int(r.player_id);tid=int(r.teamid)
            # Sequence of preceding TEAM fixtures, not global GW subtraction.
            pastteam=[k for date,k in teams[tid] if date<ko][-5:]
            paststarts=[z for z in players[pid] if z['match_id'] in set(pastteam) and z['teamid']==tid]
            paststarts=sorted(paststarts,key=lambda z:z['kickoff'])
            # Define established automatic starter strictly using pre-match
            # last five club fixtures and documented prior 4+ starts.
            if len(pastteam)==5 and len(paststarts)>=4 and np.mean([p['minutes'] for p in paststarts])>=75:
                last3=paststarts[-3:]
                source_has_blowout=any(z['substituted'] and not z['injured_sub'] and
                        55<=z['minutes']<=83 and z['lead_at_sub'] is not None and
                        z['lead_at_sub']>=3 for z in last3)
                rec=dict(gw=int(r.gw),teamid=tid,pid=pid,name=str(r.name),
                    kickoff=str(ko),actual_minutes=float(r.minutes),
                    was_early_sub=bool(r.substituted and 55<=r.minutes<=83),
                    current_lead=None if pd.isna(r.lead_at_sub) else int(r.lead_at_sub),
                    previous_game_ended_by_lead_sub=bool(paststarts[-1]['substituted'] and
                           paststarts[-1]['lead_at_sub'] is not None and paststarts[-1]['lead_at_sub']>=3 and
                           55<=paststarts[-1]['minutes']<=83 and not paststarts[-1]['injured_sub']),
                    any_of_last3_blowout_sub=source_has_blowout,
                    prior_starts=len(paststarts),
                    prior_avg_minutes=round(float(np.mean([p['minutes'] for p in paststarts])),3))
                for method in ['original','ignore','downweight25','downweight50','impute90','impute85']:
                    rec[method]=scored(last3,r,method)
                records.append(rec)
        for r in grp.itertuples(index=False):
            if r.goalkeeper:continue
            players[int(r.player_id)].append(dict(match_id=str(r.match_id),teamid=int(r.teamid),
                kickoff=ko,minutes=float(r.minutes),substituted=bool(r.substituted),
                lead_at_sub=r.lead_at_sub,injured_sub=bool(r.injured_sub)))
    scored_all=pd.DataFrame(records)
    if len(scored_all)<1100:raise AssertionError('Too few prior-established PL starters '+str(len(scored_all)))
    cand=['ignore','downweight25','downweight50','impute90','impute85']
    dev=scored_all[scored_all.gw.between(6,21)]
    test=scored_all[scored_all.gw.between(22,38)]
    if len(dev)<400 or len(test)<600:raise AssertionError('Insufficient chronological splits')
    def comparison(frame):
        return {k:dict(overall=metric(frame,k),
                       prior_lead_sub=metric(frame[frame.any_of_last3_blowout_sub],k),
                       prev_game_lead_sub=metric(frame[frame.previous_game_ended_by_lead_sub],k),
                       unaffected=metric(frame[~frame.any_of_last3_blowout_sub],k))
                for k in ['original']+cand}
    dev_metrics=comparison(dev)
    eligible=[k for k in cand if
              dev_metrics[k]['overall']['mae']<=dev_metrics['original']['overall']['mae']+.015 and
              dev_metrics[k]['overall']['rmse']<=dev_metrics['original']['overall']['rmse']+.02 and
              dev_metrics[k]['prior_lead_sub'] is not None and
              dev_metrics[k]['prior_lead_sub']['n']>=15 and
              dev_metrics[k]['prior_lead_sub']['mae']<dev_metrics['original']['prior_lead_sub']['mae']-.1 and
              dev_metrics[k]['prior_lead_sub']['rmse']<dev_metrics['original']['prior_lead_sub']['rmse']]
    selected=min(eligible,key=lambda k:(dev_metrics[k]['prior_lead_sub']['rmse'],
                                         dev_metrics[k]['prior_lead_sub']['mae'])) if eligible else 'original'
    test_metrics=comparison(test)
    # Difference in expected duration does not prove the player was fit,
    # simply tests signal quality for next appearance.
    affected=scored_all[scored_all.previous_game_ended_by_lead_sub]
    examples=affected[['gw','name','actual_minutes','prior_avg_minutes','original','ignore','impute90','impute85']].tail(25).round(3).to_dict('records')
    observed_routs=a[(a.substituted) & (~a.injured_sub) & a.lead_at_sub.notna() &
                       a.minutes.between(55,83)].copy()
    stat={}
    for kind,frame in [('leading3plus',observed_routs[observed_routs.lead_at_sub>=3]),
                       ('leading1or2',observed_routs[observed_routs.lead_at_sub.between(1,2)]),
                       ('draw_or_behind',observed_routs[observed_routs.lead_at_sub<=0])]:
        stat[kind]=dict(player_substitutions=len(frame),
                  mean_out_minute=round(float(frame.minutes.mean()),3) if len(frame) else None,
                  different_players=frame.player_id.nunique())
    report=dict(classification='READ_ONLY_FOTMOB_SCORE_AT_SUBSTITUTION_ESTABLISHED_STARTER_BACKTEST',
       provider_audit=dict(total_archived_matches=len(ff),verified_used_matches=int(a.match_id.nunique()),
         fullscore_validated=True,failed_count=len(failed),failure_examples=dict(list(failed.items())[:12]),
         starter_rows=len(a),excluded_redcard_or_incomplete_fixtures=380-int(a.match_id.nunique())-len(failed)),
       lead_at_sub_distribution=stat,
       model_scope='Established starting outfield players prior >=4/5 team PL starts and >=75min average',
       development={'gws':'6-21','cases':len(dev),'scores':dev_metrics},
       selected_on_development_only=selected,
       diagnostic_reused={'gws':'22-38','cases':len(test),'scores':test_metrics},
       sample_previous_rout_starter_returns=examples,
       held_out_2026_27=False,promoted=False,
       caveats=['Observational: team leading by >=3 at the minute of substitution does not prove the coach substituted to protect the player',
                'Excludes matches with any red card; uses confirmed 11 starters and scored match-details event snapshots',
                'Only CONDITIONAL starter duration; no P(start), XI, PM, TS changes',
                'No statement about all future gameweeks or inevitable 90 minutes',
                'GW22-38 season reused in prior diagnostic; independent unseen-season replay still required'])
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'mm_big_lead_protected_starter_duration_ab.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('LEAD_SUB_AUDIT_COVERAGE',json.dumps(report['provider_audit']),flush=True)
    print('LEAD_SUB_AUDIT_SUBSTITUTIONS',json.dumps(stat),flush=True)
    print('LEAD_SUB_AUDIT_DEV',json.dumps({'n':len(dev),'selected':selected,'score':{k:dev_metrics[k] for k in ['original']+cand}}),flush=True)
    print('LEAD_SUB_AUDIT_DIAGNOSTIC',json.dumps({'n':len(test),'selected':selected,'baseline':test_metrics['original'],'selected_result':test_metrics[selected]}),flush=True)
    print('LEAD_SUB_AUDIT_EXAMPLES',json.dumps(examples[:10],ensure_ascii=False),flush=True)
if __name__=='__main__':main()
