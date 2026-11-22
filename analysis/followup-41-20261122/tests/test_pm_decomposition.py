from pathlib import Path
import json
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1]
def test_allocation_identity_and_zero_sum():
 d=pd.read_csv(R/'results/pm-volume-allocation-rows.csv');s=d[d.supported];assert np.allclose(s.error,s.volume_error+s.allocation_error)
 assert np.allclose(s.groupby(['target','gw','fixture','team']).allocation_error.sum(),0,atol=1e-10)

def test_squared_decomposition_keeps_cross_term():
 d=pd.read_csv(R/'results/pm-volume-allocation-summary.csv');assert np.allclose(d.mean_squared_error,d.volume_mean_square+d.allocation_mean_square+d.cross_term)

def test_clean_sheet_bounds_and_eligibility_are_not_poisson_proxy():
 d=pd.read_csv(R/'results/pm-team-cs-bounds.csv');d=d[d.identified];assert len(d)==57;assert d.cs_probability_low.between(0,1).all();assert d.cs_probability_high.between(0,1).all();assert (d.cs_probability_high>=d.cs_probability_low).all();assert (d.brier_high>=d.brier_low).all()
 c=pd.read_csv(R/'results/pm-clean-sheet-decomposition.csv');c=c[c.supported];assert np.allclose(c.predicted_points-c.actual_points,c.eligibility_error+c.conditional_cs_error)

def test_pr41_fix_preserves_parsed_statistics():
 j=json.loads((R/'results/pr41-reproducibility.json').read_text());assert j['parsed_content_equal']and not j['byte_equal'];assert j['fixed_byte_equal_across_hashseeds']and j['numerical_values_unchanged']

def test_assist_three_stage_identity_does_not_attribute_all_bias_to_shares():
 d=pd.read_csv(R/'results/pm-assist-three-stage-rows.csv');s=d[d.supported];assert np.allclose(s.error,s.goal_volume+s.assist_eligibility_rate+s.player_allocation)
 assert np.allclose(s.groupby(['gw','fixture','team']).player_allocation.sum(),0,atol=1e-10)
