import numpy as np
import pandas as pd
import pytest
from current_b_features import prior_features


def inputs():
    target=pd.DataFrame([dict(season='2026-27',fixture_uuid='future',player_uuid='a',team_id=1,
        cutoff='2026-10-17T16:00:00Z',p=.8,q=.2,s=85.,c=15.,x=68.6,
        normal_role_p=np.nan,p_role=.9,pos='FWD')])
    obs=pd.DataFrame([dict(season='2026-27',fixture_uuid='past'+str(i),player_uuid='a',team_id=1,
        known_at=f'2026-10-{i+1:02d}T15:00:00Z',kickoff_at=f'2026-10-{i+1:02d}T12:00:00Z',
        started=int(i!=6),minutes=0 if i==6 else 90,role_available=i!=6) for i in range(7)])
    return target,obs,pd.DataFrame()


def test_known_absence_does_not_weaken_normal_role_and_unknown_is_missing():
    t,h,old=inputs();f=prior_features(t,h,old)
    assert f.normal_p.iloc[0]==.9
    assert f.stable_p.iloc[0]>.9  # No negative role evidence from unavailable game.
    assert f.starter_mean.iloc[0]==90
    assert np.isnan(f.cameo_mean.iloc[0])
    assert f.last_started.iloc[0]==1


def test_future_and_current_labels_cannot_change_features():
    t,h,old=inputs();reference=prior_features(t,h,old)
    future=h.iloc[:1].copy();future['fixture_uuid']='later';future['known_at']='2026-10-18T15:00:00Z';future['minutes']=0
    pd.testing.assert_frame_equal(reference,prior_features(t,pd.concat([h,future]),old))
    for col in ['y','minutes','actual_formation']:
        with pytest.raises(ValueError,match='Target outcomes'):prior_features(t.assign(**{col:0}),h,old)
    h.loc[0,'fixture_uuid']='future'
    with pytest.raises(ValueError,match='Target fixture'):prior_features(t,h,old)


def test_physical_load_follows_identity_but_normal_role_does_not_follow_wrong_club():
    t,h,old=inputs();h.loc[:,'team_id']=2
    f=prior_features(t,h,old)
    assert f.history_n.iloc[0]==0 and np.isnan(f.starter_mean.iloc[0])
    assert pd.notna(f.physical_last_known_at.iloc[0])
    assert f.normal_p.iloc[0]==.9
