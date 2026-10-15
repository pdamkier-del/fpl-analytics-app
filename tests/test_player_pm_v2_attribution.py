import numpy as np
import pytest
from postprocess_player_pm_v2 import error_attribution


def test_error_attribution_is_symmetric_and_sums_despite_cancellation():
    # Only the first two components matter; one corrects and one worsens bias.
    d=np.zeros((4,10));d[:,0]=-1;d[:,1]=.5
    r=error_attribution(np.ones(4),d)
    assert r['delta']==pytest.approx(-.5)
    assert sum(r['components'].values())==pytest.approx(-.5)
    assert list(r['components'].values())[2:]==pytest.approx([0]*8)
