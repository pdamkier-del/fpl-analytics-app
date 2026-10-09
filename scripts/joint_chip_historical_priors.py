from __future__ import annotations
"""Read-only pre-2025 availability and WC marginal-value calibration."""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pandas as pd
from fpl_xpts.joint_chip_stopping import ScenarioParameters

def calibrated_assumptions(availability_json, wc_history_directory):
    info=json.loads(Path(availability_json).read_text())
    folder=Path(wc_history_directory)
    files=list(folder.rglob('wc_gw12.csv'))+list(folder.rglob('wc_gw20.csv'))
    if len(files)!=2:
        raise RuntimeError('Expected EXACTLY two pre-2025 WC xP-gain observations')
    values=[]
    for f in files:
        z=pd.read_csv(f)
        vals=pd.to_numeric(z.loc[z.wc.eq(True),'wc_gain'],errors='coerce').dropna()
        if len(vals)!=1:raise RuntimeError('Invalid historical WC sample: '+str(f))
        values.append(float(vals.iloc[0]))
    # Known limitation: n=2 historical WC origins; not enough to validate a
    # complete distribution. These ARE the same six-GW TS objective units as
    # current WC gains; do NOT mix in one-week FH raw gap reference.
    m=float(np.mean(values))
    p=ScenarioParameters(
        new_mild=float(info['p_one_or_two_unexpected_zero']),
        new_severe=float(info['p_three_plus_unexpected_zero']),
        mild_persistence=float(info['p_zero_minutes_persists_one_gw']),
        baseline_wc_gain=m)
    manifest=dict(historical_seasons=info['seasons'],
                  historical_lineup_draws=int(info['hypothetical_11_player_squad_draws']),
                  wc_reference_n=2,wc_reference_2024_25_values=values,
                  wc_baseline_xp=m,
                  classification='Availability proxy and 2 WC origins; provisional, not validated',
                  parameters=vars(p))
    return p,manifest
