import pandas as pd
from fpl_xpts.vfinal_forecast import compose_current_forecast,composition_summary

def test_missing_vfinal_row_falls_back_not_zero():
    base=pd.DataFrame([
      {"id":1,"gw":22,"xpts_mean":4.2,"p_play":.95},
      {"id":2,"gw":22,"xpts_mean":3.1,"p_play":.80},
    ])
    vf=pd.DataFrame([
      {"id":1,"gw":22,"vfinal_xp":5.0,"vfinal_p_play":.90},
    ])
    out=compose_current_forecast(base,vf,22).set_index("id")
    assert out.loc[1,"xpts_mean"]==5.0
    assert out.loc[1,"forecast_source"]=="vfinal"
    assert out.loc[2,"xpts_mean"]==3.1
    assert out.loc[2,"forecast_source"]=="phase5q_fallback"
    assert composition_summary(out.reset_index())["complete"]

def test_composition_preserves_player_count():
    base=pd.DataFrame([{"id":1,"gw":22,"xpts_mean":2.0,"p_play":1.0}])
    vf=pd.DataFrame(columns=["id","gw","vfinal_xp","vfinal_p_play"])
    out=compose_current_forecast(base,vf,22)
    assert len(out)==1
    assert out.iloc[0].xpts_mean==2.0
