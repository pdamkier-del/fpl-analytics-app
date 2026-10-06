import pandas as pd
from fpl_v1_1_model.external_rating_ingest import extract_fotmob,resolve_player,resolve_match,map_rows


def test_exact_ids_win_and_conflicts_are_not_forced():
    row=dict(provider='fotmob',provider_player_id='1',provider_opta_id='2',match_id='m',team_id=3,player_name='Joe Smith')
    ids={('fotmob','1'):{'uuid-a'}};opta={'2':{'uuid-b'}}
    assert resolve_player(row,ids,opta,{})==('uuid-a','mapped','known_provider_id')
    ids[('fotmob','1')].add('uuid-b')
    assert resolve_player(row,ids,opta,{})[:2]==(None,'ambiguous')
    assert resolve_player(row,{}, {}, {('m',3,'joesmith'):{'uuid-a'}})[0]=='uuid-a'
    assert resolve_player({**row,'player_name':'J. Smith'}, {}, {}, {('m',3,'joesmith'):{'uuid-a'}})[0] is None


def test_known_match_id_requires_date_and_competition_agreement():
    row=dict(provider='fotmob',provider_match_id='7',season='2025/26',competition='prem',team_code=3,kickoff='2026-01-01T15:00:00Z')
    registry={('2025/26','prem','2026-01-01',3):{'right'}}
    assert resolve_match(row,registry,{('fotmob','7'):{'wrong'}})==(None,'unresolved')
    assert resolve_match(row,registry,{})==('right','mapped')
    registry[next(iter(registry))].add('other')
    assert resolve_match(row,registry,{})==(None,'ambiguous')


def test_extraction_preserves_rating_scale_and_post_match_proxy():
    event={'id':'7','status':{'utcTime':'2026-01-01T15:00:00Z'}}
    player={'id':8,'name':'Player','performance':{'rating':7.5}}
    detail={'general':{'matchId':'7','finished':True,'matchTimeUTCDate':event['status']['utcTime'],'homeTeam':{'id':9}},
        'header':{'status':{'finished':True}},'content':{'lineup':{'homeTeam':{'starters':[player]}},
        'playerStats':{'8':{'id':8,'teamId':9,'optaId':'10','stats':[{'stats':{'FotMob rating':{'stat':{'value':7.54321}}}}]}}}}
    r=extract_fotmob(detail,event,'2025/26','prem',{'9':{'team_id':1,'team_code':3,'team_name':'Arsenal'}})[0]
    assert r['rating']==7.54321
    assert pd.Timestamp(r['available_at'])==pd.Timestamp(event['status']['utcTime'])+pd.Timedelta(hours=6)


def test_mapping_retains_provider_rows_and_does_not_fuzzy_fill():
    rows=pd.DataFrame([dict(provider=p,provider_match_id='7',provider_player_id='8',provider_opta_id='10',
        season='2025/26',competition='prem',team_code=3,team_id=1,kickoff='2026-01-01T15:00:00Z',rating=7.2,player_name='Player')
        for p in ['fotmob','sofascore']])
    registry={('2025/26','prem','2026-01-01',3):{'m'}}
    mapped,audit=map_rows(rows,registry,{}, {}, {'10':{'uuid'}}, {}, {})
    assert len(mapped)==2 and set(mapped.provider)=={'fotmob','sofascore'}
    assert not mapped.duplicated(['provider','player_uuid','match_id']).any()


def test_provider_bootstrap_is_order_independent_and_conflicts_stay_ambiguous():
    base=dict(provider='fotmob',provider_player_id='8',provider_match_id='7',
        season='2025/26',competition='prem',team_code=3,team_id=1,
        kickoff='2026-01-01T15:00:00Z',rating=7.2,player_name='Player')
    raw=pd.DataFrame([{**base,'provider_opta_id':'10'}, {**base,'provider_opta_id':'11','provider_match_id':'9'}])
    registry={('2025/26','prem','2026-01-01',3):{'m'}}
    for rows in [raw,raw.iloc[::-1]]:
        mapped,audit=map_rows(rows,registry,{}, {}, {'10':{'uuid-a'},'11':{'uuid-b'}}, {}, {})
        assert mapped.empty
        assert set(audit.player_mapping_status)=={'ambiguous'}


def test_unfinished_matches_do_not_produce_ratings():
    detail={'general':{'matchId':'7','finished':False},'header':{'status':{'finished':False}}}
    assert extract_fotmob(detail,{'id':'7'},'2025/26','prem',{})==[]


def test_competition_phase_requires_exact_canonical_parent_id():
    from fpl_v1_1_model.external_rating_ingest import provider_competition_matches
    d={'general':{'leagueId':9999,'parentLeagueId':42}}
    assert provider_competition_matches(d,42)
    assert not provider_competition_matches(d,73)
    assert provider_competition_matches({'general':{'leagueId':47}},47)
    assert not provider_competition_matches({'general':{}},42)


def test_requested_season_does_not_accept_previous_fa_cup_fallback():
    from fpl_v1_1_model.external_rating_ingest import in_season
    assert in_season('2026-05-16T14:00:00Z','2025/2026')
    assert not in_season('2026-05-16T14:00:00Z','2026/2027')
    assert in_season('2026-07-01T00:00:00Z','2026/2027')
    assert not in_season('2027-07-01T00:00:00Z','2026/2027')
