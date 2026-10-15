"""Historical origin snapshots must not include later data from the same GW."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rolling_deadline_state import select_deadline_state


def test_same_gw_later_snapshot_is_excluded():
    cutoff = pd.Timestamp("2025-10-01T11:00:00Z")
    frame = pd.DataFrame([
        dict(player_uuid="a", gw=6, cutoff=cutoff, new_xmins=67),
        dict(player_uuid="a", gw=6, cutoff=cutoff + pd.Timedelta(hours=1), new_xmins=90),
        dict(player_uuid="b", gw=5, cutoff=cutoff - pd.Timedelta(days=7), new_xmins=82),
    ])
    chosen = select_deadline_state(frame, 6, cutoff).set_index("player_uuid")
    assert chosen.loc["a", "new_xmins"] == 67
    assert chosen.loc["b", "new_xmins"] == 82


def test_same_player_later_gw_with_earlier_timestamp_does_not_win():
    cutoff = pd.Timestamp("2025-10-01T11:00:00Z")
    frame = pd.DataFrame([
        dict(player_uuid="a", gw=5, cutoff=cutoff - pd.Timedelta(days=1), new_xmins=80),
        dict(player_uuid="a", gw=7, cutoff=cutoff - pd.Timedelta(days=2), new_xmins=0),
    ])
    assert select_deadline_state(frame, 6, cutoff).iloc[0]["new_xmins"] == 80


def test_missing_cutoff_is_not_assumed_to_be_safe():
    cutoff = pd.Timestamp("2025-10-01T11:00:00Z")
    frame = pd.DataFrame([
        dict(player_uuid="a", gw=6, cutoff=pd.NaT, new_xmins=90)
    ])
    with pytest.raises(ValueError, match="missing cutoff"):
        select_deadline_state(frame, 6, cutoff)


def test_no_pre_cutoff_player_state_rejected():
    cutoff = pd.Timestamp("2025-10-01T11:00:00Z")
    frame = pd.DataFrame([
        dict(player_uuid="a", gw=6, cutoff=cutoff + pd.Timedelta(hours=1), new_xmins=90)
    ])
    with pytest.raises(ValueError, match="No player state"):
        select_deadline_state(frame, 6, cutoff)
