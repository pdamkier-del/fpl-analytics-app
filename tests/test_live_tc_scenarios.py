import sys
from pathlib import Path
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_live_tc_scenarios import samples


def test_tc_refuses_a_six_week_future_option_pool():
    with pytest.raises(ValueError,match='complete current chip half'):
        samples(pd.DataFrame({'target_gw':range(7,13)}),7)


def test_tc_refuses_a_past_fixture_even_with_full_half():
    rows=[dict(target_gw=gw,fixture_uuid=str(gw),player_uuid='p',cutoff='2026-10-10T14:00:00Z',target_kickoff='2026-10-09T12:00:00Z') for gw in range(7,20)]
    with pytest.raises(ValueError,match='not future'):
        samples(pd.DataFrame(rows),7)
