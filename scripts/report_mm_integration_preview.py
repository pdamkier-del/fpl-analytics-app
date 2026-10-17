#!/usr/bin/env python3
"""Read-only renderer and paired uncertainty postprocessing; no model tuning."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/results/mm-integration-preview-20261017'
def table(f):
    return f.to_markdown(index=False,floatfmt='.6f')
def block_ci(frame,col):
    rng=np.random.default_rng(17012026);draws=[]
    periods=[]
    for season,g in frame.groupby('season'):
        lo=22 if season=='2024-25' else 6
        h=g.groupby('gw')[col].agg(['sum','count']).reindex(range(lo,39),fill_value=0)
        periods.append(h.to_numpy(float))
    for _ in range(1000):
        total=0.;n=0
        for a in periods:
            starts=rng.integers(0,len(a),size=int(np.ceil(len(a)/4)))
            ix=np.concatenate([(np.arange(s,s+4)%len(a)) for s in starts])[:len(a)]
            total+=a[ix,0].sum();n+=a[ix,1].sum()
        draws.append(total/n)
    return [float(x) for x in np.quantile(draws,[.025,.975])]

def main():
    d=json.loads((OUT/'decision.json').read_text());r=json.loads((OUT/'runtime_parity.json').read_text())
    m=pd.read_csv(OUT/'metrics.csv');u=pd.read_csv(OUT/'uncertainty_summary.csv');x=pd.read_csv(OUT/'xi_comparison.csv')
    raw=pd.read_csv(OUT/'uncertainty_rows.csv.gz')
    old=pd.read_csv(ROOT/'analysis/results/mm-predictive-distribution-20261017/distributions.csv.gz');old=old[old['mode']=='role_dependent']
    paired=raw.merge(old[['season','fixture_uuid','player_uuid','crps','logloss']],on=['season','fixture_uuid','player_uuid'],validate='one_to_one',suffixes=('','_old'))
    paired['delta_crps']=paired.crps-paired.crps_old;paired['delta_logloss']=paired.logloss-paired.logloss_old
    contrasts={k:dict(mean=float(paired[k].mean()),interval95=block_ci(paired,k)) for k in ['delta_crps','delta_logloss']}
    paired['coverage_delta']=paired.shortest80_inside.astype(int)-paired.central80_inside.astype(int)
    contrasts['shortest_minus_central_coverage80']=dict(mean=float(paired.coverage_delta.mean()),interval95=block_ci(paired,'coverage_delta'))
    xp=x.pivot(index=['season','gw','fixture_uuid','team_id'],columns='mode',values='correct').reset_index()
    for label,values in [('correct',xp.combined-xp.B),('exact11',xp.combined.eq(11).astype(int)-xp.B.eq(11).astype(int)),('atleast10',xp.combined.ge(10).astype(int)-xp.B.ge(10).astype(int))]:
        xp['difference']=values
        contrasts['xi_combined_minus_B_'+label]=dict(mean=float(values.mean()),interval95=block_ci(xp,'difference'))
    assignments=pd.read_csv(OUT/'xi_assignments.csv.gz')
    ledger=pd.read_csv(ROOT/'analysis/results/reproducible-role-v1/classified_starters.csv',usecols=['fixture_uuid','team_id','player_uuid','final_role'])
    assigned=assignments.merge(ledger,on=['fixture_uuid','team_id','player_uuid'],how='left',validate='many_to_one')
    assigned['actual_starter']=assigned.final_role.notna();assigned['correct_role']=assigned.slot.eq(assigned.final_role)
    role_scores=assigned.groupby('slot').agg(predicted=('player_uuid','size'),starter_hits=('actual_starter','sum'),exact_role_hits=('correct_role','sum'),starter_accuracy=('actual_starter','mean'),exact_role_accuracy=('correct_role','mean')).reset_index()
    role_scores.to_csv(OUT/'position_role_errors.csv',index=False)
    (OUT/'probabilistic_paired_intervals.json').write_text(json.dumps(contrasts,indent=2)+'\n')
    pooled=m.query("season=='ALL' and club=='ALL' and group=='ALL'")
    groups=m.query("season=='ALL' and club=='ALL' and mode=='combined' and group!='ALL'")
    clubs=m.query("season!='ALL' and club!='ALL'").pivot(index=['season','club'],columns='mode',values='mae').reset_index()
    clubs['B_gain_vs_original']=clubs['original']-clubs['combined']
    clubs=clubs.sort_values(['season','combined'],ascending=[True,False])
    roles=pd.read_csv(ROOT/'analysis/results/individual-mm-refinement-20261016/group_metrics.csv.gz')
    prior_risks=pd.read_csv(ROOT/'docs/research/data/2026-10-16-mm-refinement-decision.csv')
    xi_summary=x.groupby('mode').correct.agg(n='count',average_correct='mean').reset_index()
    xi_summary['exact11_pct']=xi_summary['mode'].map(x.groupby('mode').correct.apply(lambda a:100*a.eq(11).mean()))
    xi_summary['atleast10_pct']=xi_summary['mode'].map(x.groupby('mode').correct.apply(lambda a:100*a.ge(10).mean()))
    combined=x[x['mode']=='combined'];formation_accuracy=combined.formation_correct.dropna().astype(bool).mean()
    text=fr'''# Final individual MM integration — 2026-10-17

**PREVIEW READY – NOT YET CERTIFIED. No lock or production model activation.**

Draft PR #15. Preview: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/

## A. Architecture and verified reuse

PR #4 supplies historical individual MM identities/positions and role design; PR #8 supplies source caps, normal-role and existing return-duration protection. PR #9 supplies the selected B calibrator. PR #10/#12 supply error/cohort evidence; PR #11 supplies prior-only detailed roles and formation assignment. PR #13 supplies the fixed development-selected sigma30 PMF. PR #14 supplies the integration stop gates. None of these research PRs was merged into production.

`mm_candidate.py` is the shared preview contract/formation/PMF implementation. `mm_candidate_forecast.py` fits the original B calibrator using previous known labels only. `replay_mm_candidate_calibration.py` refitted this real inference entry point at every evaluation origin: **{r['evaluation_rows']:,} forecasts, maximum absolute difference {r['max_abs_error']:.12g}** across p/q/s/c/x against PR #9. The bug caught during integration was temporary q-capping being carried across both projection passes; the final runtime correctly retains PR9's projected p and reuses the original upstream q on its final pass.

No PM, FPL scoring, TS or chips executed. All production `src`, `service`, `model` and frozen B inputs are checked unchanged against `56d637a` in CI. This branch stacks narrowly on #14; a future production change must selectively port reviewed dependencies rather than merge the whole research stack.

## B. Mathematics and contract

$$xM=p\,s+(1-p)\,q\,c.$$

p is marginal P(start), q is P(substitution on | no start), s and c are conditional mean durations. B uses the exact PR9 design, StandardScaler plus logistic regression C=0.1 (alpha10), then existing source/cap and exact 1GK+10 marginal projection. Training occurs chronologically using only known_at < cutoff. Hard valid OUT/SUSPENDED sources keep p=q=xM=0, even when historical outcomes contradict those sources. We do not invent expiry or clearance.

The formation selector retains PR11's last12-game formation mass (half-life5 observed games), 70-day role decay and Hungarian assignment score `logit(p) + .5*log(.02 + .78*exact_role_share + .20*role_family_share)`. It now **forbids** incompatible GK/outfield assignments and p=0 players, instead of merely assigning a soft 1e-4 penalty. It chooses the highest-frequency feasible historical formation, trying known alternatives only if needed. Fewer than3 prior complete XIs or no feasible assignment yields **Not Available**. Unknown detailed outfield roles stay unknown; a selected slot is a model assignment, not a newly verified primary role. Primary/secondary role probabilities are historical evidence; competing players share observed role support.

The XI is a deterministic constrained point choice, not a calibrated distribution over joint XIs or a claim to have identified the most probable joint XI. B's marginal start probabilities are never nudged. `FormationHistory`, `RoleHistory` and the existing classifier/template were audited; no second production role calculation was introduced. The selector intentionally preserves PR11's evaluated formation weights rather than silently adding FormationHistory's separate smoothing settings.

PR13 conditional duration shapes are bounded exponential-tilted Gaussian-shaped discrete masses, start0..90/cameo1..90, sigma30 selected only on 2024/25GW14–21. The mixture is `p*startPMF + (1-p)*q*cameoPMF + (1-p)*(1-q)*delta0`. Numerical endpoint/mean repair gives **max |E[PMF]−xM|={d['mean_max_abs_residual']:.3g} minutes**, checked at absolute tolerance1e−6, no relative tolerance. Mixture masses at0 /1–15 /16–60 /61–90 sum to1. Exact support endpoints imply point masses, not artificial probability floors.

Version `{d['model_version']}`, contract `{d['contract']}`. Each output contains identity/club/fixture/GW/cutoff/data-at, normal/position roles, selected formation/slot, p/q/s/c/xM, all91 minute masses, four bins, interval, availability, version and uncertainty status. Independent certification is false. Forecast cutoffs are historical information origins; they are not fabricated historical calculation-publication timestamps. Snapshot data-at denotes the cutoff-bound replay input, with actual history/news clocks preserved in source manifests. Outcomes in the public **historical replay** are explicitly evaluation labels; prospective targets reject outcome fields.

## C. Identical-cohort historical comparison

39,264 identical player-fixtures, all40 club-seasons. 2024/25GW22–38 and2025/26GW6–38. Six requested arms actually executed through the common output pipeline; added XI/PMF arms intentionally retain B p/q/s/c/xM exactly, so their point-minute metrics are equal by construction and verified against the generated contract.

{table(pooled[['mode','n','mae','rmse','start_brier','start_logloss','bias','over60']])}

Reused PR9 combined paired4-GW bootstrap: B−best MAE−0.113034 [−0.148345,−0.074534]; Brier−.0012885 [−.0016937,−.0008726]. Separate season intervals are recomputed here in `paired_intervals.json`. No formation-nudge model is promoted: its previous RMSE/Brier/>60-tail failures remain valid stop reasons.

### Error distribution and tail contribution

{table(pooled[['mode','median','p90','p95','p99','top5_error_share','top10_error_share']])}

Shares above are fractions, not percentages. Per-arm 0–5/5–15/15–30/30–60/>60 counts and error contributions are in `error_bands.csv`. Top100 concrete errors for original/best/B are retained with canonical IDs, actual/expected minutes, roles, source flags and cutoffs. There is no new causal explanation inferred from a bad outcome alone.

{table(groups[['group','n','mae','rmse','bias','start_brier','over60']])}

`limited_history` is an overlapping diagnostic group using weighted pre-cutoff history_n<3; it is not relabelled as a new verified tactical role. Rotations are evaluated by proper probability scores and calibration bins, not by calling a single correctly calibrated 50% forecast wrong. Existing PR9 matched role/rest/return paired intervals remain applicable because p/x are unchanged; all source medical and scheduled return1–3 flags remain in the per-row outputs. Unknown injury/training information remains unknown.

### All40 club-seasons, descending new MAE

{table(clubs[['season','club','original','best_existing','combined','B_gain_vs_original']])}

B vs best still improves31/40 point estimates and worsens9. Unadjusted club harm intervals previously flagged Everton2024/25, Newcastle2025/26 and Wolves2025/26. Common-pipeline equality is not evidence that these risks disappeared. No per-club switches or named-player boosts were fitted.

## D. XI and positions

{table(xi_summary)}

All compared XI observations are the same **660 2025/26 team-fixtures**. Original/best/B comparators are explicitly unconstrained raw top11 as in PR11, not claimed legal 1GK references. Combined hard-constrained assignments are stored in `xi_assignments.csv.gz`. Exact11 and >=10 match the previous15.303%/43.939% references; average correct9.148485 vs B9.119697. Equivalent detailed2024/25 classified role evidence is **Not Available**, so these XI rates are not reported for both seasons or all39,264 rows.

Formation agreement against the sufficient same-source post-match classified ledger: **{100*formation_accuracy:.3f}%**. This is source-relative formation agreement, not independently verified in-match tactical ground truth. Slot correctness is retained perfixture in `xi_comparison.csv`; the full11/10/9/… histogram is in `xi_hit_distribution.csv`. Truth labels never enter the pre-cutoff selector. Paired4-GW XI intervals are in the contrasts below; these small XI point gains are not automatically robust improvements.

{table(role_scores)}

## E. Probabilistic validation — gate not passed

{table(u.query("season=='ALL'")[['role','n','crps','logloss','p0','observed0','central50_inside','central80_inside','central90_inside','shortest50_inside','shortest80_inside','shortest90_inside']])}

Full widths and nominal contained **model mass** for both interval methods are in `uncertainty_summary.csv`, separately perseason/role. Four-band probability calibration is in `minute_band_calibration.csv`.

Prior central80 coverage90.5588% is reproduced. Shortest contiguous intervals, defined only from the PMF and without outcome fitting, cover87.6706% and average15.5789 minutes wide, vs25.2131 central. This is closer to80%, **not** proof of calibrated80% intervals. Many players have a large atom at0, making deterministic equal-tail intervals necessarily conservative. For example, average shortest80 contained model mass92.3095%, not exactly80%; reporting nominal confidence alone would hide this discreteness.

The numerical exact-mean repair has CRPS delta **{contrasts['delta_crps']['mean']:.9f}** and minute-logloss delta **{contrasts['delta_logloss']['mean']:.9f}** vs PR13. Paired4-GW intervals:

```json
{json.dumps(contrasts,indent=2)}
```

Thus the requested “improve calibration without worse CRPS/logloss” promotion gate is **not passed**. We do not hide the small loss increase: correcting endpoint means removes some tiny artificial tail mass. The PMF and intervals stay a separate labelled experimental preview component. Minute logloss uses explicit1e−12 clipping; contradictory hard-zero outcomes still imply infinite theoretical logloss. Predicted zero fraction63.4261% vs observed61.3183% indicates excess predicted zeros overall; all35 source-hard-zero appearances remain in evaluation.

## F. Holdout audit, source and live integration gates

Available frozen evaluation seasons are exactly the already repeatedly researched2024/25 and2025/26 periods. Current-season GW1–6 data have been repeatedly used in earlier app/Haaland/Chelsea/JoãoPedro diagnostics and are not documented untouched evaluation data. No later completed, preregistered B period is available in this evidence set. **No independent holdout validation is claimed.** Historic outcome/role publication uses inherited kickoff+3/4h proxies, not verified actual publication timestamps. Complete cup/Europe workload, clinical/training clearance and fixture-scoped suspension expiry remain missing.

`mm_candidate_forecast.py` provides a separate prospective inference/immutable local preregistration interface. It requires PR8 upstream tuples plus the exact prior-only B feature contract and source clocks; it rejects current/future labels, unknown training clocks, overlapping target fixtures, late registration and overwrites. Model/code identities accompany each record. This is preparation for prospective collection, **not a claim that independent future forecasts have already been registered**. A CI artifact is not itself durable third-party timestamp certification.

The existing live inference script produces a different legacy/vNext feature matrix; it cannot safely be relabelled B. The current B adapter therefore fails closed and the preview shows **current forecast Not Available**. No oldGW7 or historicalGW38 snapshot is presented as current. No current PM/xP/TS outputs were fabricated or recomputed with an unapproved MM.

## G. App, deployment, activation and rollback

The separate `mm-preview/` app displays real historical replay snapshots, clubs/GWs, expected formation/XI and alternatives, role competition, p/q/s/c/xM, minute bins and experimental intervals, Pitch/List sorting and player detail. Compressed payload SHA256 is verified in-browser. Failures show retry and hide results. No manager-state/localStorage/cookie/token code is touched.

The CI workflow refits B, runs the full pipeline, focused regressions, immutable production/frozen-input checks and preserves public evidence. Publication reuses the latest successful production Pages artifact and overlays **only** `mm-preview/`; every other production file must remain byte-identical. It persists only this new public research path to the live branch, for later forecast builds. No production MM switch or model merge. Deployment/browsing evidence is recorded in the completion checkpoint after verification.

Activation is **not permitted yet**. Necessary next gates: independently/prospectively recorded evaluation; review the three club risks and35 source conflicts; probabilistic non-inferiority/calibration; a verified current-season PR8→B feature/provenance bridge; audited current role identity/formation coverage; downstream PM effects evaluated under fixed PM after MM approval. Keep `locked_model_active=false`. Do not change PM/TS weights or the2125 benchmark.

Rollback: remove/revert only the `app/mm-preview/` public-path commit and rerun normal Pages publication, or republish the recorded previous production artifact under the existing publication lock. Production model files require no rollback because they were not changed. Leave the immutable historical evidence/draft PR intact.

## Reproduction

```bash
python -m pip install -r requirements-model-checkpoint.txt -r requirements-model-tests.txt requests tabulate
PYTHONPATH=src:scripts OPENBLAS_NUM_THREADS=1 python scripts/replay_mm_candidate_calibration.py
PYTHONPATH=src:scripts OPENBLAS_NUM_THREADS=1 python scripts/build_mm_integration_preview.py
PYTHONPATH=src:scripts OPENBLAS_NUM_THREADS=1 python scripts/report_mm_integration_preview.py
PYTHONPATH=src:scripts python -m pytest -q tests/test_mm_candidate.py tests/test_individual_mm_refinement.py
```

All actual model inputs and output hashes are in `manifest.json`. Gzip container content, decoded arrays and numerical differences must be distinguished. The completion checkpoint records clean-CI reproduction rather than assuming it.
'''
    dest=ROOT/'docs/research/2026-10-17-mm-integrated-preview.md';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
    manifest=json.loads((OUT/'manifest.json').read_text())
    manifest['outputs']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print('Report',dest)
if __name__=='__main__':main()
