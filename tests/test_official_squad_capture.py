import html
import hashlib
import io
import json

import pytest

from capture_gk_official_evidence import fetch_squad


def payload(position, team='mensteam'):
    value=json.dumps({'players':[dict(playerFirstName='Example',playerLastName='Keeper',
        playerPosition=position,teams=[team])]})
    return ('<div data-props="'+html.escape(value,quote=True)+'"></div>').encode()


def test_staff_only_response_is_retried_uncached_and_generic_keeper_is_accepted():
    requests=[]
    def opener(request, timeout):
        requests.append(request)
        return io.BytesIO(payload('Coach' if len(requests)==1 else 'Goalkeeper'))
    data,receipt=fetch_squad('https://example.com/squad',opener=opener)
    assert data==payload('Goalkeeper')
    assert receipt['retrieval_attempt']==2
    assert receipt['requested_url']==requests[1].full_url
    assert 'evidence_capture='in receipt['requested_url']
    assert receipt['rejected_responses'][0]['sha256']==hashlib.sha256(payload('Coach')).hexdigest()
    assert requests[0].get_header('Cache-control')=='no-cache'


def test_valid_first_response_does_not_require_a_named_player_or_extra_request():
    requests=[]
    def opener(request, timeout):
        requests.append(request)
        return io.BytesIO(payload('Goalkeeper'))
    _,receipt=fetch_squad('https://example.com/squad',opener=opener)
    assert len(requests)==receipt['retrieval_attempt']==1


@pytest.mark.parametrize('team',['mensteam','onLoan','under19s'])
def test_staff_or_non_first_team_keepers_never_become_complete_first_team_evidence(team):
    calls=[]
    def opener(request, timeout):
        calls.append(request.full_url)
        return io.BytesIO(payload('Coach'if team=='mensteam'else'Goalkeeper',team))
    with pytest.raises(ValueError,match='availability is unknown'):
        fetch_squad('https://example.com/squad',opener=opener)
    assert len(calls)==3
