from datetime import datetime,timedelta,timezone
import copy,json
import pytest
from collect_dashboard_news import build,seal
from dashboard_news_publication import checked,retain_latest


def raw():
    now=datetime.now(timezone.utc)
    return dict(events=[dict(id=8,is_next=True,deadline_time=(now+timedelta(days=2)).isoformat())],teams=[dict(id=1,name='City')],elements=[dict(id=1,web_name='Haaland',team=1,element_type=4,now_cost=156,status='d',news='Unspecified injury',news_added=(now-timedelta(hours=2)).isoformat(),chance_of_playing_next_round=75,chance_of_playing_this_round=None)])


def test_official_doubt_preserves_actual_time_and_probability():
    source=raw();n=build(source)
    assert n['players'][0]['status']=='d'
    assert n['players'][0]['chance_of_playing_next_round']==75
    assert n['players'][0]['news_added']==source['elements'][0]['news_added']
    assert seal(n)==n
    assert 'squad'not in n and 'manager'not in n


def test_unknown_update_time_stays_unknown():
    source=raw();source['elements'][0]['news_added']=None
    assert build(source)['players'][0]['news_added'] is None


@pytest.mark.parametrize('key,value',[('status','unknown'),('chance_of_playing_next_round',130),('news_added','2999-01-01T00:00:00Z')])
def test_invalid_official_data_cannot_be_published(key,value):
    source=raw();source['elements'][0][key]=value
    with pytest.raises(ValueError):build(source)


def test_tampered_feed_is_rejected():
    n=build(raw());n['players'][0]['status']='a'
    with pytest.raises(ValueError):checked(json.dumps(n))


def test_model_publication_keeps_more_recent_news(tmp_path,monkeypatch):
    from urllib.error import URLError
    import dashboard_news_publication as publication
    monkeypatch.setattr(publication,'urlopen',lambda *a,**k:(_ for _ in ()).throw(URLError('offline')))
    older=build(raw());newer=copy.deepcopy(older);newer['observed_at']=(datetime.fromisoformat(older['observed_at'])+timedelta(seconds=1)).isoformat();newer['players'][0]['news']='Further assessment';newer=seal(newer)
    source=tmp_path/'incoming';previous=tmp_path/'deployed'
    for path,value in [(source,older),(previous,newer)]:
        (path/'news').mkdir(parents=True);(path/'news/availability.json').write_text(json.dumps(value))
    retain_latest(source,previous)
    assert json.loads((source/'news/availability.json').read_text())==newer


def fixture(now,player=1,**kw):
    return dict(id=73,event=8,team_h=1,team_a=2,kickoff_time=(now-timedelta(days=1)).isoformat(),finished=False,stats=[dict(identifier='red_cards',h=[dict(value=1,element=player)],a=[])],**kw)


def test_red_card_does_not_require_updated_availability_or_imply_ban():
    source=raw();source['elements'][0].update(status='a',news='',red_cards=1);source['teams'].append(dict(id=2,name='Opponent'));now=datetime.now(timezone.utc)
    value=build(source,now.isoformat(),[fixture(now)])
    p=value['players'][0]
    assert p['status']=='a'and p['news']==''
    assert p['recent_red_cards'][0]['fixture_id']==73 and p['recent_red_cards'][0]['provisional']
    assert 'suspension_matches'not in p and value['discipline_checked']
    assert seal(value)==value


def test_season_red_card_total_is_not_a_current_event():
    source=raw();source['elements'][0]['red_cards']=1
    assert build(source,fixtures=[])['players'][0]['recent_red_cards']==[]


def test_old_and_future_red_cards_do_not_become_current_alerts():
    source=raw();source['teams'].append(dict(id=2,name='Opponent'));now=datetime.now(timezone.utc)
    for days in [15,-1]:
        f=fixture(now);f['kickoff_time']=(now-timedelta(days=days)).isoformat()
        assert build(source,now.isoformat(),[f])['players'][0]['recent_red_cards']==[]


def test_both_sides_and_player_identity_stay_distinct():
    source=raw();source['teams'].append(dict(id=2,name='Opponent'));source['elements'].append({**source['elements'][0],'id':2,'team':2,'web_name':'Other Palmer'})
    now=datetime.now(timezone.utc);f=fixture(now,2);f['stats'][0]['a']=f['stats'][0].pop('h');f['stats'][0]['h']=[]
    value=build(source,now.isoformat(),[f]);assert not value['players'][0]['recent_red_cards'];assert value['players'][1]['recent_red_cards'][0]['team_id']==2


def test_duplicate_and_unmapped_card_evidence_rejected():
    source=raw();source['teams'].append(dict(id=2,name='Opponent'));now=datetime.now(timezone.utc);f=fixture(now)
    with pytest.raises(ValueError,match='Duplicate'):build(source,now.isoformat(),[f,f])
    with pytest.raises(ValueError,match='Unmapped'):build(source,now.isoformat(),[fixture(now,999)])


def test_reviewed_ban_scope_is_attached_to_exact_event_without_changing_availability():
    source=raw();source['elements'][0]['status']='a';source['teams'].append(dict(id=2,name='Opponent'));now=datetime.now(timezone.utc);f=fixture(now)
    resolution=dict(player_id=1,fixture_id=73,kickoff=f['kickoff_time'],human_reviewed=True,source_url='https://www.premierleague.com/en/news/4425344',source_observed_at=(now-timedelta(minutes=5)).isoformat(),description='Afsones i EFL Cup.',premier_league_matches_missed=0)
    value=build(source,now.isoformat(),[f],[resolution]);assert value['players'][0]['status']=='a';assert value['players'][0]['recent_red_cards'][0]['resolution']['premier_league_matches_missed']==0
    # A reused fixture/player ID in another season/day must not inherit the ban.
    other={**resolution,'kickoff':(now-timedelta(days=2)).isoformat()};assert 'resolution'not in build(source,now.isoformat(),[f],[other])['players'][0]['recent_red_cards'][0]


def test_future_ban_review_is_not_backdated():
    source=raw();source['teams'].append(dict(id=2,name='Opponent'));now=datetime.now(timezone.utc);f=fixture(now)
    resolution=dict(player_id=1,fixture_id=73,kickoff=f['kickoff_time'],human_reviewed=True,source_url='https://www.premierleague.com/en/news/4425344',source_observed_at=(now+timedelta(minutes=5)).isoformat())
    with pytest.raises(ValueError,match='Unverified'):build(source,now.isoformat(),[f],[resolution])
