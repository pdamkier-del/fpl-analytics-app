import copy,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from live_forecast_contract import validate_forecast_rows


def rows():
    return [{'id':pid,'weeks':[dict(gw=g,xpts=4.,xmins=65.,p_start=.7,q_sub=.3) for g in range(6,12)]} for pid in [1,2]]


def check(data):return validate_forecast_rows(data,[{'id':1},{'id':2}],6)


def test_full_coverage():assert check(rows())['gws']==list(range(6,12))


@pytest.mark.parametrize('change',['missing_player','duplicate_player','missing_gw','duplicate_gw','nan','missing_minutes','bad_probability'])
def test_reject_incomplete_or_invalid_final_data(change):
    data=rows()
    if change=='missing_player':data.pop()
    if change=='duplicate_player':data[1]['id']=1
    if change=='missing_gw':data[0]['weeks'].pop()
    if change=='duplicate_gw':data[0]['weeks'][0]['gw']=7
    if change=='nan':data[0]['weeks'][0]['xpts']=float('nan')
    if change=='missing_minutes':del data[0]['weeks'][0]['xmins']
    if change=='bad_probability':data[0]['weeks'][0]['p_start']=1.1
    with pytest.raises(RuntimeError):check(data)


def test_dgw_minutes_and_negative_points_are_valid_model_values():
    data=rows();data[0]['weeks'][0].update(xmins=170,xpts=-.1)
    check(data)
