"""Production-safe composition of integrated vFinal with an explicit fallback.

Integrated historical vFinal artifacts do not necessarily contain every active FPL
player. Missing rows must never be interpreted as zero expected points. This
module overlays vFinal where it exists and otherwise preserves the supplied
baseline forecast, while recording the source on every output row.
"""
from __future__ import annotations
import pandas as pd

def compose_current_forecast(base: pd.DataFrame, vfinal: pd.DataFrame, gw: int) -> pd.DataFrame:
    required_base={"id","gw","xpts_mean","p_play"}
    required_vf={"id","gw","vfinal_xp","vfinal_p_play"}
    mb=required_base-set(base.columns)
    mv=required_vf-set(vfinal.columns)
    if mb: raise ValueError(f"base forecast missing columns: {sorted(mb)}")
    if mv: raise ValueError(f"vFinal forecast missing columns: {sorted(mv)}")

    b=base[base.gw.astype(int).eq(int(gw))].copy()
    if b.id.duplicated().any():
        raise ValueError("base current forecast must have one row per FPL id")
    v=vfinal[vfinal.gw.astype(int).eq(int(gw))][list(required_vf)].copy()
    if v.id.duplicated().any():
        raise ValueError("vFinal current forecast must have one row per FPL id")

    out=b.merge(v,on=["id","gw"],how="left",validate="one_to_one")
    use=out.vfinal_xp.notna()
    out["forecast_source"]="phase5q_fallback"
    out.loc[use,"forecast_source"]="vfinal"
    out.loc[use,"xpts_mean"]=out.loc[use,"vfinal_xp"].astype(float)
    use_pp=use & out.vfinal_p_play.notna()
    out.loc[use_pp,"p_play"]=out.loc[use_pp,"vfinal_p_play"].astype(float)

    if out[["xpts_mean","p_play"]].isna().any().any():
        raise ValueError("composed forecast contains missing xP or p_play")
    if len(out)!=len(b):
        raise RuntimeError("forecast composition changed base player coverage")
    return out

def composition_summary(frame: pd.DataFrame) -> dict:
    if "forecast_source" not in frame:
        raise ValueError("forecast_source column is required")
    counts=frame.forecast_source.value_counts().to_dict()
    total=len(frame)
    return {
        "players":int(total),
        "vfinal":int(counts.get("vfinal",0)),
        "phase5q_fallback":int(counts.get("phase5q_fallback",0)),
        "vfinal_share":float(counts.get("vfinal",0)/total) if total else 0.0,
        "complete":bool(frame[["xpts_mean","p_play"]].notna().all().all()),
    }
