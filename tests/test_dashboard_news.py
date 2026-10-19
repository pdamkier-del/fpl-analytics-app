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
