from datetime import datetime,timedelta,timezone
from labels import COMP,ZERO_FIELDS

NOW=datetime.now(timezone.utc)


def fixture(*,double=False,blank=False):
    origin=12;positions=[1]*2+[2]*5+[3]*5+[4]*3
    games=[] if blank else[dict(id=120+i,event=origin,team_h=1,team_a=2,finished=True,kickoff_time=(NOW+timedelta(days=2)).isoformat())for i in range(2 if double else 1)]
    past=[dict(id=100+i,event=10+i,team_h=1,team_a=2,finished=True,kickoff_time=(NOW-timedelta(days=3-i)).isoformat())for i in range(2)]
    f=dict(season='2026-27',gws=list(range(12,18)),data_asof=(NOW-timedelta(hours=1)).isoformat(),forecast_sha256='a'*64,players=[])
    mm=dict(players=[]);live=[];elements=[];hist={}
    for pid,pos in enumerate(positions,1):
        person=dict(id=pid,name='Synthetic'+str(pid),player_uuid='p'+str(pid),team_id=1 if pid<=8 else 2,position=pos,weeks=[])
        for gw in f['gws']:
            xs=[]
            for game in games:
                if gw!=origin:continue
                pred={('expected_bonus'if c=='bonus_points'else c):0. for c in COMP};pred['appearance_points']=2.
                xs.append(dict(fixture_uuid='live-2026-27-fpl-'+str(game['id']),xpts=2.,xmins=90.,p_start=1.,p_60_plus=1.,p_90=1.,q_sub=0.,components=pred,
                    distribution=dict(minute_bins=[0,0,0,1],p_zero=0)))
                mm['players'].append(dict(player_id=person['player_uuid'],fixture_id=xs[-1]['fixture_uuid'],p_play=1.,normal_role='regular',availability='OK',start_minutes=90.,sub_minutes=10.))
                hist[pid,game['id']]=dict(starts=1,minutes=90,total_points=2,bps=10,defensive_contribution=0)
            person['weeks'].append(dict(gw=gw,fixtures=xs,xpts=2.*len(xs),xmins=90.*len(xs),scenarios=dict(points=[2.*len(xs)]*4,minutes=[90.*len(xs)]*4)))
        f['players'].append(person)
        stats={k:0 for k in ZERO_FIELDS};stats.update(minutes=90*len(games),starts=len(games),total_points=2*len(games),bps=10*len(games))
        live.append(dict(id=pid,stats=stats,explain=[dict(fixture=g['id'],stats=[dict(identifier='minutes',points=2,value=90,points_modification=0)])for g in games]))
        elements.append(dict(id=pid,code=1000+pid,team=person['team_id'],starts=2,minutes=180,total_points=4,ep_next=str(2*len(games))))
    bootstrap=dict(elements=elements,events=[dict(id=g,is_next=g==12,deadline_time=(NOW+timedelta(days=(g-12)*7+1)).isoformat())for g in range(1,39)])
    payload=dict(season='2026-27',gw=12,observed_at_utc=(NOW+timedelta(days=3)).isoformat(),official_event=dict(id=12,finished=True,data_checked=True),official_fixtures=games,official_player_live=live)
    return f,mm,bootstrap,past+[{**r,'finished':False}for r in games],payload,[dict(id=p['id'],code=p['code'])for p in elements],hist
