import copy
import gzip
import json
import math
from pathlib import Path
import pytest
from fixtures import fixture,NOW
from labels import normalize,ZERO_FIELDS
from evaluate import score,baseline,component_probabilities
from metrics import bernoulli,crps,block_intervals,calibration,law_summary


def evaluate(data,history=True):
    f,m,b,fx,p,ids,h=data
    labels=normalize(f,b,fx,p,ids,h if history else None)
    return score(f,m,b,fx,labels,evidence_class='synthetic_infrastructure_only'),labels


def test_proper_scores_have_hand_derived_values():
    assert bernoulli(.5,1)==dict(brier=.25,log_loss=math.log(2))
    assert crps([0,2],1)==.5 and crps([2,2],2)==0
    assert math.isfinite(bernoulli(0,1)['log_loss'])
    for p in [float('nan'),1.1,-.1]:
        with pytest.raises(ValueError):bernoulli(p,1)


def test_complete_original_targets_and_baselines():
    result,_=evaluate(fixture())
    assert result['status']=='complete' and len(result['fixture_rows'])==len(result['point_rows'])==15
    assert result['summary']['mm']['minutes']['mae']==0
    assert result['summary']['pm']['crps']==result['summary']['pm']['points']['mse']==0
    assert result['summary']['pm']['ep_next']['mse']==0
    assert result['summary']['mm']['baseline_start_paired_rows']==15
    assert all(r['baseline_start']==.75 for r in result['fixture_rows'])
    assert result['summary']['pm']['intervals']['0.8']['forecast_mass']==1
    assert sum(result['pit_bins'])==15 and not result['formal_inference']


def test_unfinished_results_are_not_scored_or_live_fetched(monkeypatch):
    import labels
    data=fixture();data[4]['official_event']['data_checked']=False
    normalized=normalize(data[0],data[2],data[3],data[4],data[5])
    assert normalized['status']=='awaiting_results' and normalized['scored_rows']==0
    calls=[]
    def get(path):
        calls.append(path)
        assert path=='bootstrap-static/'
        return {'events':[dict(id=12,finished=False,data_checked=False)]}
    monkeypatch.setattr(labels,'get_official',get)
    assert labels.fetch_final(data[0])['status']=='awaiting_results'
    assert calls==['bootstrap-static/']


def test_double_gw_starts_are_not_inferred_from_90_minutes():
    data=fixture(double=True)
    partial,labels=evaluate(data,history=False)
    assert labels['mm_start_unknown']==30 and partial['status']=='partial_data'
    assert partial['summary']['mm']['known_starts']==0
    full,labels=evaluate(data,history=True)
    assert full['status']=='complete'and len(full['fixture_rows'])==30 and len(full['point_rows'])==15
    assert full['summary']['pm']['points']['mse']==full['summary']['pm']['gw_minute_crps']==0


def test_explicit_blank_zero_is_not_a_missing_fixture():
    result,labels=evaluate(fixture(blank=True))
    assert result['status']=='complete'and labels['blank_player_ids']==list(range(1,16))
    assert result['fixture_rows']==[] and len(result['point_rows'])==15
    assert result['summary']['pm']['crps']==0


@pytest.mark.parametrize('kind',['missing_player','identity','fixture','changed_points'])
def test_missing_or_changed_labels_are_not_zero(kind):
    data=fixture()
    if kind=='missing_player':data[4]['official_player_live'].pop()
    if kind=='identity':data[5][0]['code']+=1
    if kind=='fixture':data[4]['official_fixtures'][0]['event']=13
    if kind=='changed_points':data[4]['official_player_live'][0]['stats']['total_points']=9
    result,labels=evaluate(data)
    assert result['status']=='partial_data'and labels['missing']


def test_explicit_official_dnp_is_supported_but_not_absence():
    data=fixture();p=data[4]['official_player_live'][0]
    p['stats']={k:0 for k in ZERO_FIELDS};p['explain']=[];data[6].pop((1,120))
    result,labels=evaluate(data)
    assert result['status']=='complete'and result['summary']['mm']['minutes']['mae']==6
    assert result['fixture_rows'][0]['started']==0 and result['point_rows'][0]['points']==0


def test_card_only_zero_minute_is_not_positive_minute_appearance_or_zero_points():
    data=fixture();p=data[4]['official_player_live'][0];data[6].pop((1,120))
    p['stats']={k:0 for k in ZERO_FIELDS};p['stats'].update(total_points=-1,yellow_cards=1)
    p['explain']=[dict(fixture=120,stats=[dict(identifier='yellow_cards',points=-1,value=1)])]
    result,_=evaluate(data)
    row=result['fixture_rows'][0]
    assert row['card_only']and row['played']==0 and result['point_rows'][0]['points']==-1
    assert row['pm_sample_zero_minute_brier']==1 # p_zero is minutes, not points.


def test_baseline_uses_only_original_prior_information():
    f,m,b,fx,*_=fixture();ref=baseline(f['players'][0],b,fx,f['data_asof'],1)
    assert ref['start']==.75 and ref['minutes']==90 and ref['points']==2
    b['elements'][0]['starts']=999
    assert baseline(f['players'][0],b,fx,f['data_asof'],1)['start']is None
    data=fixture();data[2]['events'][11]['is_next']=False
    result,_=evaluate(data)
    assert result['summary']['pm']['ep_paired_rows']==0


def test_identified_cs_dc_probabilities_only():
    pred=dict(cs_points=2.,dc_points=1.);actual=dict(cs_points=4.,dc_points=2.)
    result=component_probabilities(pred,actual,2)
    assert result['qualified_cs']['p']==.5 and result['dc_award']['brier']==.25
    assert 'qualified_cs'not in component_probabilities(dict(cs_points=0,dc_points=1),dict(cs_points=0,dc_points=0),4)


def test_no_inference_before_fixed_stop_or_minimum_independent_units():
    assert block_intervals([-.1]*11,120,locked=True)['status']=='not_inferential'
    assert block_intervals([-.1]*12,119,locked=True)['status']=='not_inferential'
    assert block_intervals([-.1]*12,120,locked=False)['status']=='not_inferential'
    a=block_intervals([-.1]*12,120,locked=True);b=block_intervals([-.1]*12,120,locked=True)
    assert a==b and a['blocks']['3']['family_ci97_5']==pytest.approx([-.1,-.1])
    gaps=block_intervals([-.1]*12+[None]*4,120,locked=True)
    assert gaps['gws']==12 and gaps['calendar_origins']==16 and gaps['mean']==pytest.approx(-.1)


def test_known_gw10_ledger_is_regression_not_new_efficacy():
    root=Path(__file__).resolve().parents[3]/'analysis/audits/2026-11-22/inputs/archive'
    live=json.loads(gzip.decompress((root/'gw10-live.json.gz').read_bytes()))
    # Reuse two already-seen official ledgers; do not rerun an old model audit.
    from labels import MAP,COMP
    from evaluate import contracts
    for p in live['elements'][:2]:
        comp={k:0. for k in COMP}
        for explanation in p['explain']:
            for item in explanation['stats']:comp[MAP[item['identifier']]]+=item['points']
        assert contracts.canonical_total(comp)==p['stats']['total_points']
    old_f=json.loads(gzip.decompress((root/'gw10-forecast.json.gz').read_bytes()))
    old_f['players']=old_f['players'][:2] # Contract check, not a repeated GWaccuracy audit.
    bootstrap=json.loads(gzip.decompress((root/'bootstrap.json.gz').read_bytes()))
    fixtures=json.loads(gzip.decompress((root/'fixtures.json.gz').read_bytes()))
    event=next(e for e in bootstrap['events']if e['id']==10)
    payload=dict(season=old_f['season'],gw=10,official_event=event,
                 official_fixtures=[r for r in fixtures if r.get('event')==10],official_player_live=live['elements'])
    normalized=normalize(old_f,bootstrap,fixtures,payload,[dict(id=p['id'],code=p['code'])for p in bootstrap['elements']])
    assert normalized['status']=='complete'and len(normalized['rows'])==2
