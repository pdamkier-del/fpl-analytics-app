"""One sealed MM→PM forecast for every B view and private TS client."""
import json
from pathlib import Path
from b_chain_contract import VERSION,validate_forecast
from mm_candidate_forecast import seal_document
from export_joint_gk_preview import dump


def publish(root,forecast,distribution):
    root=Path(root);base=root/'app/mm-preview';out=base/'current'
    validate_forecast(forecast)
    gate=json.loads((root/'analysis/results/unified-b-chain-20261021/validation.json').read_text())
    if not gate['accepted']:raise ValueError('Unified B validation rejected publication')
    index=json.loads((out/'index.json').read_text())
    mm=json.loads((out/'mm.json').read_text())
    moments={(p['fixture_id'],p['player_id']):p for p in distribution['players']}
    for r in mm['players']:
        q=moments[r['fixture_id'],r['player_id']]
        r.update({k:q[k]for k in ['p_start','p_sub_given_not_start','start_minutes','sub_minutes','xmins','p_play','p_60_plus','p_90']})
    mm.update(model_version=VERSION,data_at=forecast['data_asof'])
    mm=seal_document(mm)
    index.update(model=VERSION,minute_sampler=VERSION,forecast_sha256=forecast['forecast_sha256'],
        data_asof=forecast['data_asof'],chain_version=VERSION,
        forecast_file_sha256=dump(out/'forecast.json',forecast),mm_file_sha256=dump(out/'mm.json',mm))
    inputs=root/'work/current-B-inputs'
    from build_existing_b_app import source_data
    documents=source_data(json.loads((inputs/'bootstrap.json').read_text()),json.loads((inputs/'fixtures.json').read_text()),
        json.loads((inputs/'provenance.json').read_text()),forecast,mm)
    index['existing_app_data_sha256']=dump(out/'existing-app-data.json',dict(forecast_sha256=forecast['forecast_sha256'],documents=documents))
    index['chain_validation_file']='chain-validation.json'
    index['chain_validation_sha256']=dump(out/'chain-validation.json',gate)
    dump(out/'index.json',index)
