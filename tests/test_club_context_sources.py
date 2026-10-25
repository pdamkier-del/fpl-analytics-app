import pytest
from club_context_sources import parse_team_news
B={'teams':[{'id':1,'name':'Arsenal','short_name':'ARS'},{'id':2,'name':'Aston Villa','short_name':'AVL'}]}
TEXT='The player may return but the manager has not promised a start in the next game.'
def card(code='ars',body=TEXT):return f'<li class="team-news-item" data-team-code="{code}"><h2>Arsenal</h2><p><strong>Latest News: </strong>{body}</p><em>Last Updated Fri 23rd Oct</em></li>'

def test_known_club_and_qualifications_preserved():
    r=parse_team_news(card(),B,'2026-10-25T19:00:00Z');v=r['clubs'][0]
    assert v['team_id']==1 and v['full_text']==TEXT
    assert v['source_updated_label']=='Last Updated Fri 23rd Oct'
    assert v['source_published_at']is None and v['fixture_id']is None
    assert not v['official_confirmation']and not v['model_input_enabled']
    assert r['coverage']['missing_club_ids']==[2]

def test_duplicate_club_rejected():
    with pytest.raises(ValueError,match='Duplicate'):parse_team_news(card()+card(),B,'2026-10-25T19:00:00Z')

def test_unknown_club_does_not_fill_missing_team():
    r=parse_team_news(card('xyz'),B,'2026-10-25T19:00:00Z')
    assert not r['clubs']and r['coverage']['missing_club_ids']==[1,2]

def test_no_body_or_duplicate_body_rejected():
    for s in [card(body=''),card().replace('</li>',f'<p>Latest News: {TEXT}</p></li>')]:
        r=parse_team_news(s,B,'2026-10-25T19:00:00Z');assert not r['clubs']and r['rejected']

def test_unrelated_heading_cannot_create_club_context():
    r=parse_team_news(f'<h2>Arsenal</h2><p>Latest News: {TEXT}</p>',B,'2026-10-25T19:00:00Z');assert not r['clubs']

def test_date_label_not_reconstructed_into_exact_timestamp():
    r=parse_team_news(card().replace('Last Updated Fri 23rd Oct','Last Updated unknown'),B,'2026-10-25T19:00:00Z')
    assert r['clubs'][0]['source_published_at']is None and r['clubs'][0]['next_gw_freshness']=='not_verified'

def test_naive_clock_and_ambiguous_club_registry_rejected():
    with pytest.raises(ValueError,match='Timezone'):parse_team_news(card(),B,'2026-10-25')
    with pytest.raises(ValueError,match='Ambiguous'):parse_team_news(card(),{'teams':[B['teams'][0],B['teams'][0]]},'2026-10-25T19:00:00Z')


def test_conflicting_heading_and_club_code_rejected():
    with pytest.raises(ValueError,match='Conflicting'):parse_team_news(card('avl'),B,'2026-10-25T19:00:00Z')
