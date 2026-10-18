import pandas as pd
from diagnose_goalkeeper_minutes import diagnose

def test_only_available_keeper_is_flagged_not_forced():
    frame=pd.DataFrame([
      dict(name='Mike Penders',pos='GK',fixture_uuid='f1',team_id=1,p=.9,q=.1,s=90.,c=15.,x=81.15,news_state='AVAILABLE'),
      dict(name='Other keeper',pos='GK',fixture_uuid='f1',team_id=1,p=0.,q=0.,s=90.,c=15.,x=0.,news_state='OUT'),
    ])
    out=diagnose(frame)[0]
    assert out['not_hard_out_goalkeepers']==1
    assert out['review']=='ONLY_NON_HARD_OUT_GK_CHECK_START_ROLE'
    assert out['mm_p_start']==.9
    assert out['pm_expected_minutes']<out['mm_xm']
