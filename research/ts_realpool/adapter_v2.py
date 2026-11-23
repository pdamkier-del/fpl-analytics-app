"""Identity adapter: validate original arrays; never reconstruct a forecast."""
import hashlib
import json
import math

TAG='fpl-forecast-2026-27-gw12-f54f651ea03ee099ef5be35c9cb36eddc3a8472470ead2aaac786b097c281633'
IDENTITY='4d1a2e3925d5da64bfdfa2f7f98a9b7a04ade220f3546f655e4bc4a7ca1051dd'
RAW='8f80f07829f3dff4dd5eeff70cde5d5ee1065fb7610aa108a14da83744f4eab7'

def adapt(f,mm,validate,*,original=True):
    if original and(f['forecast_sha256']!=IDENTITY or f['gws']!=list(range(12,18))):
        raise ValueError('Wrong original issue/horizon')
    validate(f)
    if original and(len(f['players'])<500 or f['scenario_contract']['draws']!=400):
        raise ValueError('Full original pool/scenario gate failed')
    if len({p['id']for p in f['players']})!=len(f['players']):raise ValueError('Duplicate player')
    native={(r['player_id'],r['fixture_id']):r for r in mm['players']}
    eligible=[]
    for p in sorted(f['players'],key=lambda p:p['id']):
        if p['position']not in(1,2,3,4)or type(p['price_tenths'])is not int or p['price_tenths']<=0 or type(p['team_id'])is not int:
            raise ValueError('Incomplete player metadata')
        w=next(w for w in p['weeks']if w['gw']==f['gws'][0])
        if not w['fixtures']:continue
        if len(w['fixtures'])==1:
            probability=native[p['player_uuid'],w['fixtures'][0]['fixture_uuid']]['p_play']
        else:
            probability=sum(x>0 for x in w['scenarios']['minutes'])/len(w['scenarios']['minutes'])
        if not math.isfinite(probability)or not -1e-12<=probability<=1+1e-12:raise ValueError('Invalid native participation')
        if probability>=.2:eligible.append(p['id'])
    # Identity, including native PM means, draws, draw order and every extra field.
    return f,eligible
