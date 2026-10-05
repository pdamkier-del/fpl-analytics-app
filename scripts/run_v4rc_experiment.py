#!/usr/bin/env python3
"""v4RC: role-competition residual correction on frozen v4 P(start).

Protocol
--------
* Reproduce v4 workload_start P(start) exactly with the existing feature/model code.
* Build only cutoff-safe, within-team/fixture role-competition features from q/H,
  recent starts/minutes/workload and the frozen v4 baseline probability.
* Fit a residual logit correction with coefficient 1 fixed on logit(v4):
      logit(p_rc_raw) = logit(p_v4) + beta' X_rc
  then re-apply the inherited exact-11 team constraint.
* Select RC-A vs RC-B and L2 strength ONLY on GW16-21 after fitting on GW6-15.
* Refit the selected correction on GW6-21 and report GW22-38 only as a reused
  diagnostic, never as independent OOS evidence.
* Conditional starter/cameo duration and cameo probability remain unchanged.
"""
from __future__ import annotations
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fpl_v1_1_model.workload import WORKLOAD_FEATURES
from build_reproducible_role_benchmark import BASE_FEATURES, ROLE_FEATURES, normalize_eleven
from benchmark_squad_minutes import serialize

SOURCE = ROOT / "analysis/results/workload-recovered-v4/all_features.csv.gz"
V4_RESULTS = ROOT / "analysis/results/workload-recovered-minutes-v4"
OUT = ROOT / "analysis/results/v4rc-20261005-v1"
EPS = 1e-7

RC_A = [
    "rc_known_role",
    "rc_h_gap_slow", "rc_qh_gap_slow", "rc_rank_qh_slow",
    "rc_n_candidates_slow", "rc_entropy_slow",
    "rc_h_gap_fast", "rc_qh_gap_fast", "rc_rank_qh_fast",
    "rc_n_candidates_fast", "rc_entropy_fast",
]
RC_B = RC_A + [
    "rc_v4_logit_gap",
    "rc_started_last_gap",
    "rc_work_starts_7d_gap",
    "rc_work_starts_14d_gap",
    "rc_work_minutes_7d_gap",
    "rc_work_minutes_14d_gap",
    "rc_rest_days_gap",
]
FAMILIES = {"rc_a": RC_A, "rc_b": RC_B}
L2_VALUES = [0.5, 2.0, 10.0]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_gzip_csv(frame: pd.DataFrame, path: Path):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as txt:
                frame.to_csv(txt, index=False)
        raw.flush(); os.fsync(raw.fileno())
    os.replace(tmp, path)


def metric_block(y, minutes, p, xm):
    y = np.asarray(y, float); minutes = np.asarray(minutes, float)
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    xm = np.asarray(xm, float); err = xm - minutes
    return {
        "n": int(len(y)),
        "brier": float(np.mean((p-y)**2)),
        "log_loss": float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p))),
        "xmins_mae": float(np.mean(np.abs(err))),
        "xmins_rmse": float(np.sqrt(np.mean(err**2))),
        "xmins_bias": float(np.mean(err)),
    }


def fit_v4_start(frame: pd.DataFrame, train: np.ndarray) -> tuple[np.ndarray, dict]:
    cols = BASE_FEATURES + ROLE_FEATURES + WORKLOAD_FEATURES
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=2000, random_state=0))
    model.fit(frame.loc[train, cols], frame.loc[train, "y"])
    raw = model.predict_proba(frame[cols])[:, 1]
    p = normalize_eleven(frame, raw)
    return p, serialize(model, cols)


def xmins_from_p(frame: pd.DataFrame, p: np.ndarray) -> np.ndarray:
    s = frame.start_minutes_mean.to_numpy(float)
    q = frame.p_cameo_given_bench.to_numpy(float)
    c = frame.cameo_minutes_mean.to_numpy(float)
    return p*s + (1-p)*q*c


def _role_value_cols(frame, role, speed):
    qcol = f"q_{role}_{speed}"
    hcol = f"H_{role}_{speed}"
    if qcol not in frame or hcol not in frame:
        return None
    return qcol, hcol


def add_role_competition_features(frame: pd.DataFrame, p_v4: np.ndarray) -> pd.DataFrame:
    f = frame.copy()
    for name in set(RC_B):
        f[name] = 0.0
    base_logit = logit(np.clip(np.asarray(p_v4, float), EPS, 1-EPS))
    f["_rc_base_logit"] = base_logit

    keys = ["fixture_uuid", "team_id"]
    for _, idx in f.groupby(keys, sort=False).indices.items():
        ii = np.asarray(idx, dtype=int)
        g = f.iloc[ii]
        roles = g.expected_role.fillna("UNKNOWN").astype(str).to_numpy()
        for local_i, global_i in enumerate(ii):
            role = roles[local_i]
            if role == "UNKNOWN":
                continue
            f.at[f.index[global_i], "rc_known_role"] = 1.0
            # Slow and fast role competition.
            top_comp_local = None
            for speed in ("slow", "fast"):
                cols = _role_value_cols(g, role, speed)
                if cols is None:
                    continue
                q = g[cols[0]].to_numpy(float)
                h = g[cols[1]].to_numpy(float)
                qh = q*h
                own_h = h[local_i]; own_qh = qh[local_i]
                others = np.ones(len(g), dtype=bool); others[local_i] = False
                if others.any():
                    max_h = float(np.max(h[others]))
                    max_qh = float(np.max(qh[others]))
                    comp_candidates = np.flatnonzero(others)
                    j = int(comp_candidates[np.argmax(qh[others])])
                else:
                    max_h = max_qh = 0.0; j = local_i
                positive = qh[qh > 0.005]
                if len(positive):
                    w = positive / positive.sum()
                    entropy = float(-(w*np.log(w)).sum() / np.log(len(w))) if len(w) > 1 else 0.0
                else:
                    entropy = 0.0
                rank = 1.0 + float(np.sum(qh > own_qh + 1e-12))
                f.at[f.index[global_i], f"rc_h_gap_{speed}"] = own_h - max_h
                f.at[f.index[global_i], f"rc_qh_gap_{speed}"] = own_qh - max_qh
                f.at[f.index[global_i], f"rc_rank_qh_{speed}"] = rank
                f.at[f.index[global_i], f"rc_n_candidates_{speed}"] = float(len(positive))
                f.at[f.index[global_i], f"rc_entropy_{speed}"] = entropy
                if speed == "slow":
                    top_comp_local = j

            if top_comp_local is None:
                continue
            comp_global = ii[top_comp_local]
            own = f.iloc[global_i]; comp = f.iloc[comp_global]
            f.at[f.index[global_i], "rc_v4_logit_gap"] = float(base_logit[global_i] - base_logit[comp_global])
            for src, outcol in [
                ("role_started_last_gw", "rc_started_last_gap"),
                ("work_starts_7d", "rc_work_starts_7d_gap"),
                ("work_starts_14d", "rc_work_starts_14d_gap"),
                ("work_minutes_7d", "rc_work_minutes_7d_gap"),
                ("work_minutes_14d", "rc_work_minutes_14d_gap"),
                ("work_player_rest_days", "rc_rest_days_gap"),
            ]:
                if src in f:
                    a = float(own[src]) if pd.notna(own[src]) else 0.0
                    b = float(comp[src]) if pd.notna(comp[src]) else 0.0
                    f.at[f.index[global_i], outcol] = a-b
    f.drop(columns=["_rc_base_logit"], inplace=True)
    assert np.isfinite(f[RC_B].to_numpy(float)).all()
    return f


def fit_offset_correction(frame, p0, train, features, l2):
    X = frame[features].to_numpy(float)
    mu = X[train].mean(axis=0)
    sd = X[train].std(axis=0)
    sd[sd < 1e-8] = 1.0
    Z = (X-mu)/sd
    y = frame.y.to_numpy(float)
    off = logit(np.clip(np.asarray(p0, float), EPS, 1-EPS))
    Xt = Z[train]; yt = y[train]; ot = off[train]

    def fun(beta):
        z = ot + Xt @ beta
        p = expit(z)
        loss = np.mean(np.logaddexp(0, z) - yt*z) + 0.5*l2*np.dot(beta,beta)/len(yt)
        grad = Xt.T @ (p-yt) / len(yt) + l2*beta/len(yt)
        return float(loss), grad

    res = minimize(lambda b: fun(b), np.zeros(len(features)), jac=True, method="L-BFGS-B",
                   options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-9})
    if not res.success:
        raise RuntimeError("RC optimization failed: " + res.message)
    raw = expit(off + Z @ res.x)
    corrected = normalize_eleven(frame, raw)
    model = {
        "features": features, "l2": float(l2), "coefficients": res.x.tolist(),
        "mean": mu.tolist(), "scale": sd.tolist(), "optimizer_success": True,
        "optimizer_fun": float(res.fun), "iterations": int(res.nit),
    }
    return corrected, model


def slice_metrics(frame, p_base, p_rc, mask, label):
    y = frame.y.to_numpy(float); m = frame.minutes.to_numpy(float)
    xb = xmins_from_p(frame, p_base); xr = xmins_from_p(frame, p_rc)
    return [
        {"slice": label, "arm": "v4", **metric_block(y[mask], m[mask], p_base[mask], xb[mask])},
        {"slice": label, "arm": "v4rc", **metric_block(y[mask], m[mask], p_rc[mask], xr[mask])},
    ]


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    protocol = {
        "name": "v4RC role-competition residual correction",
        "source": str(SOURCE.relative_to(ROOT)),
        "v4_preserved": "conditional starter minutes, sub appearance probability and sub duration unchanged",
        "development_train": "GW6-15",
        "development_selection": "GW16-21",
        "final_train": "GW6-21",
        "reused_diagnostic": "GW22-38; previously inspected, not independent OOS",
        "families": FAMILIES,
        "l2_values": L2_VALUES,
        "selection_objective": "lowest development start log-loss; candidate must also not worsen xMins RMSE by >0.05 minutes vs v4; otherwise retain v4",
        "exact_11_constraint": True,
        "posthoc_slices_not_used_for_selection": ["actual starter", "actual substitute", "did not play"],
    }
    write_json(OUT/"protocol.json", protocol)

    frame = pd.read_csv(SOURCE)
    frame = frame.reset_index(drop=True)
    known = pd.to_datetime(frame.outcome_known_at, utc=True)

    dev_val = frame.gw.between(16, 21).to_numpy()
    dev_cut = pd.to_datetime(frame.loc[dev_val, "cutoff"], utc=True).min()
    dev_train = (frame.gw.between(6, 15) & (known < dev_cut)).to_numpy()
    p_dev, v4_dev_model = fit_v4_start(frame, dev_train)

    # Verify exact reproduction on the saved development validation rows.
    saved_dev = pd.read_csv(V4_RESULTS/"development_predictions.csv.gz")
    key = ["fixture_uuid", "player_uuid", "team_id", "gw"]
    chk = frame.loc[dev_val, key].copy()
    chk["p_rebuilt"] = p_dev[dev_val]
    chk = chk.merge(saved_dev[key+["workload_start_p_start"]], on=key, validate="one_to_one")
    max_dev_repro = float(np.max(np.abs(chk.p_rebuilt-chk.workload_start_p_start)))
    if max_dev_repro > 1e-10:
        raise AssertionError(f"development v4 reproduction mismatch {max_dev_repro}")

    feat_dev = add_role_competition_features(frame, p_dev)
    y = frame.y.to_numpy(float); mins = frame.minutes.to_numpy(float)
    xb_dev = xmins_from_p(frame, p_dev)
    base_dev = metric_block(y[dev_val], mins[dev_val], p_dev[dev_val], xb_dev[dev_val])

    candidates = []
    models_dev = {}
    preds_dev = {}
    for family, features in FAMILIES.items():
        for l2 in L2_VALUES:
            name = f"{family}_l2_{l2:g}"
            prc, model = fit_offset_correction(feat_dev, p_dev, dev_train, features, l2)
            xrc = xmins_from_p(frame, prc)
            met = metric_block(y[dev_val], mins[dev_val], prc[dev_val], xrc[dev_val])
            candidates.append({"candidate": name, "family": family, "l2": l2, **met,
                               "delta_log_loss": met["log_loss"]-base_dev["log_loss"],
                               "delta_brier": met["brier"]-base_dev["brier"],
                               "delta_xmins_rmse": met["xmins_rmse"]-base_dev["xmins_rmse"],
                               "delta_xmins_mae": met["xmins_mae"]-base_dev["xmins_mae"]})
            models_dev[name] = model
            preds_dev[name] = prc

    cand = pd.DataFrame(candidates).sort_values(["log_loss", "xmins_rmse", "candidate"])
    acceptable = cand[cand.delta_xmins_rmse <= 0.05]
    best = acceptable.iloc[0] if len(acceptable) else None
    if best is None or best.log_loss >= base_dev["log_loss"] - 1e-10:
        selected_name = "v4"
        selected_family = None
        selected_l2 = None
    else:
        selected_name = str(best.candidate)
        selected_family = str(best.family)
        selected_l2 = float(best.l2)

    cand.to_csv(OUT/"development_candidates.csv", index=False)
    selection = {
        "baseline": base_dev,
        "selected": selected_name,
        "selected_family": selected_family,
        "selected_l2": selected_l2,
        "development_v4_reproduction_max_abs_error": max_dev_repro,
        "rule": protocol["selection_objective"],
    }
    write_json(OUT/"selection.json", selection)
    write_json(OUT/"development_models.json", {"v4_start": v4_dev_model, "rc": models_dev})

    # Final fit: recreate frozen v4 on GW6-21, then fit only selected RC correction.
    test = frame.gw.between(22, 38).to_numpy()
    final_cut = pd.to_datetime(frame.loc[test, "cutoff"], utc=True).min()
    final_train = (frame.gw.between(6, 21) & (known < final_cut)).to_numpy()
    p_final, v4_final_model = fit_v4_start(frame, final_train)

    saved_test = pd.read_csv(V4_RESULTS/"reused_holdout_diagnostic_predictions.csv.gz")
    chk2 = frame.loc[test, key].copy()
    chk2["p_rebuilt"] = p_final[test]
    chk2 = chk2.merge(saved_test[key+["workload_start_p_start", "workload_start_xmins"]], on=key, validate="one_to_one")
    max_test_repro = float(np.max(np.abs(chk2.p_rebuilt-chk2.workload_start_p_start)))
    if max_test_repro > 1e-10:
        raise AssertionError(f"final v4 reproduction mismatch {max_test_repro}")

    feat_final = add_role_competition_features(frame, p_final)
    if selected_name == "v4":
        p_rc = p_final.copy()
        rc_final_model = None
    else:
        p_rc, rc_final_model = fit_offset_correction(
            feat_final, p_final, final_train, FAMILIES[selected_family], selected_l2
        )
    x_base = xmins_from_p(frame, p_final)
    x_rc = xmins_from_p(frame, p_rc)
    base_test = metric_block(y[test], mins[test], p_final[test], x_base[test])
    rc_test = metric_block(y[test], mins[test], p_rc[test], x_rc[test])

    # Cutoff-safe slices and explicitly posthoc descriptive appearance slices.
    rows = []
    pband = (p_final >= 0.20) & (p_final <= 0.80)
    rows += slice_metrics(frame, p_final, p_rc, test, "all")
    rows += slice_metrics(frame, p_final, p_rc, test & pband, "v4_pstart_0.20_to_0.80")
    known_role = feat_final.rc_known_role.to_numpy() > 0.5
    rows += slice_metrics(frame, p_final, p_rc, test & known_role, "known_role")
    actual_sub = (frame.y.to_numpy()==0) & (frame.minutes.to_numpy()>0)
    actual_start = frame.y.to_numpy()==1
    did_not_play = frame.minutes.to_numpy()==0
    rows += slice_metrics(frame, p_final, p_rc, test & actual_sub, "POSTHOC_actual_substitute")
    rows += slice_metrics(frame, p_final, p_rc, test & actual_start, "POSTHOC_actual_starter")
    rows += slice_metrics(frame, p_final, p_rc, test & did_not_play, "POSTHOC_did_not_play")
    pd.DataFrame(rows).to_csv(OUT/"diagnostic_slices.csv", index=False)

    # Per-GW stability.
    gwrows = []
    for gw in range(22, 39):
        mask = test & frame.gw.eq(gw).to_numpy()
        if not mask.any():
            continue
        for arm, p, x in [("v4", p_final, x_base), ("v4rc", p_rc, x_rc)]:
            gwrows.append({"gw": gw, "arm": arm, **metric_block(y[mask], mins[mask], p[mask], x[mask])})
    pd.DataFrame(gwrows).to_csv(OUT/"metrics_by_gw.csv", index=False)

    # Save only test predictions, enough to reproduce comparison.
    pred = frame.loc[test, key+["team","player","pos","expected_role","y","minutes"]].copy()
    pred["v4_p_start"] = p_final[test]
    pred["v4rc_p_start"] = p_rc[test]
    pred["v4_xmins"] = x_base[test]
    pred["v4rc_xmins"] = x_rc[test]
    for c in RC_B:
        pred[c] = feat_final.loc[test, c].to_numpy()
    write_gzip_csv(pred, OUT/"reused_diagnostic_predictions.csv.gz")

    result = {
        "classification": "development-selected candidate plus reused diagnostic; not independent OOS",
        "development_selection": selection,
        "reused_diagnostic": {
            "v4": base_test,
            "v4rc": rc_test,
            "delta_v4rc_minus_v4": {k: rc_test[k]-base_test[k] for k in ["brier","log_loss","xmins_mae","xmins_rmse","xmins_bias"]},
            "v4_reproduction_max_abs_start_error": max_test_repro,
        },
        "selected_candidate_promoted": False,
        "promotion_reason": "Independent OOS still required even if reused diagnostic improves.",
        "conditional_minutes_unchanged": True,
        "rows": int(test.sum()),
        "fixtures": int(frame.loc[test, "fixture_uuid"].nunique()),
    }
    write_json(OUT/"result.json", result)
    write_json(OUT/"frozen_models.json", {"v4_start": v4_final_model, "rc": rc_final_model})

    outputs = [p for p in sorted(OUT.iterdir()) if p.name != "manifest.json"]
    write_json(OUT/"manifest.json", {
        "sources": [
            {"path": str(SOURCE.relative_to(ROOT)), "sha256": sha(SOURCE)},
            {"path": str((V4_RESULTS/"development_predictions.csv.gz").relative_to(ROOT)), "sha256": sha(V4_RESULTS/"development_predictions.csv.gz")},
            {"path": str((V4_RESULTS/"reused_holdout_diagnostic_predictions.csv.gz").relative_to(ROOT)), "sha256": sha(V4_RESULTS/"reused_holdout_diagnostic_predictions.csv.gz")},
            {"path": "scripts/run_v4rc_experiment.py", "sha256": sha(Path(__file__))},
        ],
        "outputs": [{"path": p.name, "sha256": sha(p)} for p in outputs],
    })
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
