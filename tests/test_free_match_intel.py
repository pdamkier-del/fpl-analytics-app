import copy
import json
from pathlib import Path
import pytest
from free_match_intel import parse_rotowire,discover_sportsmole,clock,build


def sample(kind='Predicted Lineup'):
    b={'teams':[{'id':1,'name':'Chelsea','short_name':'CHE'},{'id':2,'name':'Man Utd','short_name':'MUN'}],'elements':[]}
    for team in [1,2]:
        for i in range(11):b['elements'].append(dict(id=team*100+i,team=team,first_name='Player',second_name=f'{team} {i}',web_name=f'P{team}{i}',status='a',news=''))
    def side(team,side):
        players=''.join(f'<li class="lineup__player"><a title="Player {team} {i}" href="/soccer/player/{team}-{i}">P</a></li>'for i in range(11))
        return f'<ul class="lineup__list {side}"><li class="lineup__status">{kind}</li>{players}<li class="lineup__title">Injuries</li><li class="lineup__player"><a title="Other Player" href="/soccer/player/other">Other</a><span class="lineup__inj">QUES</span></li></ul>'
    html='<div class="lineup is-soccer"><div class="lineup__time"><b>October 31</b> 8:30 AM ET</div><div class="lineup__mteam is-home">Chelsea</div><div class="lineup__mteam is-visit">Manchester United</div>'+side(1,'is-home')+side(2,'is-visit')+'</div>'
    fixtures=[dict(id=84,event=9,team_h=1,team_a=2,kickoff_time='2026-10-31T12:30:00Z',started=False)]
    return html,b,fixtures


def test_future_prediction_is_attributed_not_probability_or_official():
    h,b,f=sample();r=parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')
    assert len(r['rows'])==2
    for row in r['rows']:
        assert row['eligible_editorial_xi']and row['complete_mapped_xi']
        assert len(row['players'])==11 and len(row['reported_absences'])==1
        assert row['reported_absences'][0]['player_id']is None
        assert not row['official_confirmation']and not row['model_input_enabled']
        assert row['source_published_at']is None and 'p_start'not in row


def test_injuries_cannot_fill_an_unknown_lineup():
    h,b,f=sample('Unknown Lineup')
    import re
    h=re.sub(r'<li class="lineup__player"><a title="Player.*?</li>','',h)
    rows=parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows']
    assert len(rows)==2 and all(not r['players']and not r['eligible_editorial_xi']for r in rows)
    assert all(len(r['reported_absences'])==1 for r in rows)


def test_provider_confirmation_does_not_become_official_evidence():
    h,b,f=sample('Confirmed Lineup');rows=parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows']
    assert all(r['source_kind']=='provider_reported_confirmed'and not r['eligible_editorial_xi']and not r['official_confirmation']for r in rows)


def test_after_kickoff_and_flagged_started_are_rejected():
    h,b,f=sample();assert not parse_rotowire(h,b,f,'2026-10-31T12:30:00Z')['rows']
    f[0]['started']=True;assert not parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows']


def test_exact_fixture_clock_and_opponent_required():
    h,b,f=sample();f[0]['kickoff_time']='2026-10-31T13:30:00Z'
    assert not parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows']
    f[0]['kickoff_time']='2026-10-31T12:30:00Z';f[0]['team_h']=2
    assert not parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows']


def test_unmapped_duplicate_and_wrong_club_players_reject_xi():
    h,b,f=sample();b['elements'][0]['team']=2
    r=parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows'][0]
    assert not r['eligible_editorial_xi']and r['players'][0]['player_id']is None
    h,b,f=sample();h=h.replace('Player 1 0','Player 1 1')
    assert not parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows'][0]['eligible_editorial_xi']


def test_unrecognized_status_is_not_assumed_prediction():
    h,b,f=sample('Premium Lineup');r=parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')
    assert not r['rows']and len(r['rejected'])==2


def test_discovery_never_verifies_fixture_or_follows_external_links():
    p='/football/chelsea/preview/chelsea-vs-man-united_123.html'
    r=discover_sportsmole(f'<a href="{p}">Preview</a><a href="https://evil.example{p}">Bad</a><a href="/football/preview/">Index</a>')
    assert len(r)==1 and not r[0]['fixture_verified']and not r[0]['model_input_enabled']


def test_naive_clock_rejected():
    with pytest.raises(ValueError,match='Timezone'):clock('2026-10-25T12:00:00')


def test_capture_checksum_required(tmp_path):
    (tmp_path/'receipts.json').write_text(json.dumps([dict(key='fpl',url='https://fantasy.premierleague.com/api/bootstrap-static/',status=200,sha256='bad',observed_at='2026-10-25T19:00:00Z')]))
    (tmp_path/'fpl.raw').write_text('{}')
    with pytest.raises(ValueError,match='checksum'):build(tmp_path)


def test_sportsmole_cup_preview_remains_unverified_for_pl():
    from free_match_intel import parse_sportsmole_article
    h='<script type="application/ld+json">{"datePublished":"2026-10-25T11:00:00Z","dateModified":"2026-10-25T12:00:00Z"}</script><h1>Fleetwood vs Arsenal</h1><p><strong>Arsenal possible starting lineup:</strong></p><p>Kepa; Timber, Salmon, Mosquera, Hincapie; Zubimendi, Lewis-Skelly; Dowman, Merino, Eze; Harriman-Annous</p>'
    receipt={'url':'https://www.sportsmole.co.uk/football/arsenal/league-cup/preview/fleetwood-vs-arsenal_123.html','observed_at':'2026-10-25T19:00:00Z'}
    r=parse_sportsmole_article(h,receipt)
    assert r['competition_url_hint']=='league-cup'and not r['fixture_verified']and not r['model_input_enabled']
    assert r['possible_lineups'][0]['eleven_names']and not r['possible_lineups'][0]['players_identity_verified']
    with pytest.raises(ValueError,match='publication clock'):
        parse_sportsmole_article(h.replace('2026-10-25T12:00:00Z','2026-10-26T12:00:00Z'),receipt)
    with pytest.raises(ValueError,match='publication clock'):
        parse_sportsmole_article(h.replace('datePublished','unavailable'),receipt)


def test_est_clock_after_us_dst_change():
    h,b,f=sample();h=h.replace('October 31','November 2').replace('8:30 AM ET','3:00 PM ET')
    f[0]['kickoff_time']='2026-11-02T20:00:00Z'
    assert len(parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows'])==2


def test_ambiguous_player_identity_is_not_resolved_by_order():
    h,b,f=sample();p=copy.deepcopy(b['elements'][0]);p['id']=999;b['elements'].append(p)
    r=parse_rotowire(h,b,f,'2026-10-25T19:00:00Z')['rows'][0]
    assert not r['complete_mapped_xi']and r['players'][0]['player_id']is None
