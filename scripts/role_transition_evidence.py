"""Prior-only diagnostic role-transition evidence. No active caller imports it.

An unused player is not inferred injured/rested. Competition is a soft-role
and prior co-selection proxy, not proof of a coach's preferred hierarchy.
"""
import numpy as np
import pandas as pd

KEY=['season','fixture_uuid','player_uuid']
FEATURES=['transition_streak3','transition_contested3','transition_opportunity3','transition_return_pressure']


def available(row):
    """Known pre-match availability only; unknown remains None."""
    if row is None or pd.isna(row.get('news_eligible')) or row.get('news_eligible')!=True:return None
    clock=row.get('news_effective_at')
    if pd.isna(clock):return None
    clock=pd.Timestamp(clock);cut=pd.Timestamp(row['cutoff'])
    if clock.tzinfo is None or cut.tzinfo is None or clock>=cut:
        raise ValueError('Invalid pre-match availability clock')
    state=row.get('news_state')
    if state in ['OUT','SUSPENDED']:return 0.
    if state in ['AVAILABLE','RETURNED_AVAILABLE']:return 1.
    chance=row.get('news_chance')
    return float(chance)/100 if pd.notna(chance) and 0<=float(chance)<=100 else None


def build_evidence(target,observations,news,role_columns):
    if {'y','minutes','started','actual_start','actual_minutes'}&set(target):
        raise ValueError('Target outcomes forbidden')
    if target.duplicated(KEY).any()or observations.duplicated(KEY).any()or news.duplicated(KEY).any():
        raise ValueError('Duplicate player fixture')
    t=target.copy();o=observations.copy()
    for frame,cols in [(t,['cutoff']),(o,['kickoff_at','known_at'])]:
        for c in cols:
            if any(pd.Timestamp(v).tzinfo is None for v in frame[c]):raise ValueError('Timezone required')
            frame[c]=pd.to_datetime(frame[c],utc=True,format='mixed')
    if (o.known_at<o.kickoff_at).any():raise ValueError('Observation before kickoff')
    if not o.started.isin([0,1]).all():raise ValueError('Unknown historical start label')
    bynews={(r['season'],r['fixture_uuid'],r['player_uuid']):r for r in news.to_dict('records')}
    teams={}
    for key,g in o.groupby(['season','team_id'],sort=False):
        games=[]
        for fx,v in g.groupby('fixture_uuid',sort=False):
            if v.kickoff_at.nunique()!=1:raise ValueError('Conflicting kickoff')
            games.append(dict(fixture=fx,known=v.known_at.max(),kick=v.kickoff_at.iloc[0],
                starts=dict(zip(v.player_uuid,v.started)),minutes=dict(zip(v.player_uuid,v.minutes))))
        teams[key]=sorted(games,key=lambda x:(x['kick'],x['fixture']))
    result=[]
    for (season,team,cut,fixture),g in t.groupby(['season','team_id','cutoff','fixture_uuid'],sort=False):
        past=[v for v in teams.get((season,team),[])if v['known']<cut and v['kick']<cut and v['fixture']!=fixture]
        last=past[-3:];prior=past[-9:-3];look=past[-6:]
        uids=g.player_uuid.tolist();roles=g[role_columns].to_numpy(float)
        if not np.isfinite(roles).all()or (roles<0).any():raise ValueError('Invalid prior role probabilities')
        norm=np.linalg.norm(roles,axis=1);q=np.divide(roles,norm[:,None],out=np.zeros_like(roles),where=norm[:,None]>0)
        similarity=q@q.T
        source=g.set_index('player_uuid').to_dict('index')
        for j,row in enumerate(g.to_dict('records')):
            uid=row['player_uuid'];rival=None;best=0.;prior_n=0;prior_share=np.nan
            own=[v['starts'][uid]for v in prior if uid in v['starts']]
            if len(own)>=3:prior_share=float(np.mean(own));prior_n=len(own)
            for k,other in enumerate(uids):
                if k==j or (row['pos']in ['GK','GKP'])!=(source[other]['pos']in ['GK','GKP']):continue
                values=[v['starts'][other]for v in prior if other in v['starts']]
                if len(values)<3 or np.mean(values)<.5 or similarity[j,k]<.5:continue
                both=[v for v in prior if uid in v['starts']and other in v['starts']]
                starts=sum(v['starts'][uid]for v in both)
                overlap=sum(v['starts'][uid]*v['starts'][other]for v in both)/starts if starts else 0.
                score=float(similarity[j,k]*np.mean(values)*(1-overlap))
                if score>best or (score==best and score>0 and (rival is None or other<rival)):
                    best=score;rival=other
            streak=0
            for v in reversed(look):
                if v['starts'].get(uid)!=1:break
                streak+=1
            recent=[v['starts'][uid]for v in last if uid in v['starts']]
            contested=0;opportunity=0;known=0;injury=0
            for v in last:
                if rival is None:continue
                n=bynews.get((season,v['fixture'],rival));av=available(n)
                # Played minutes establish past availability, not an absence reason.
                if av is None and v['minutes'].get(rival,0)>0:av=1.
                if av is None:continue
                known+=1
                if v['starts'].get(uid)!=1:continue
                if av==0:
                    opportunity+=1
                    injury+=int(n is not None and n.get('news_state')=='OUT')
                elif av==1:contested+=1
            current=available(source.get(rival))if rival else None
            v={k:row[k]for k in KEY}
            v.update(transition_streak3=min(streak,3)/3 if past else np.nan,
                transition_contested3=contested/3 if known else np.nan,
                transition_opportunity3=opportunity/3 if known else np.nan,
                transition_return_pressure=(opportunity/3)*current if current is not None and known else np.nan,
                prior_share6=prior_share,prior_games=prior_n,recent_share3=float(np.mean(recent))if len(recent)==3 else np.nan,
                streak_games=streak,rival_uuid=rival,rival_score=best,rival_current_availability=current,
                rival_known_games3=known,confirmed_injury_opportunities3=injury,
                transition_max_known_at=max((x['known']for x in past),default=pd.NaT),
                team_history_games=len(past),availability_reason_inferred=False)
            result.append(v)
    return pd.DataFrame(result)
