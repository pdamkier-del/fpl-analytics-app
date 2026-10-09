# FH + WC — LOCKED (approved 2026-10-09)

Frozen selection policy:
- Source: `src/fpl_xpts/simple_chip_thresholds.py`
- `LOCKED_LAMBDA_FH = 10.0` xP; `LOCKED_LAMBDA_WC = 20.0` xP.
- FH marginal gain is measured ONLY for the current GW against the normal post-transfer TS lineup. FH squad is temporary; original bank, owned squad and free-transfer balance are restored.
- WC marginal gain is the current six-GW weighted WC-as-TS first-action candidate objective compared with locked normal TS. WC offers unlimited free transfers, and a new permanent roster.
- Holding threshold for each chip: `lambda * (period_end_gw - gw)/(period_end_gw - period_start_gw)`. Periods GW1–19 and GW20–38. The largest positive adjusted opportunity wins; tie preserves chips; at most one chip per GW.
- 2025/26 in-sample 2,209 actual points (FH GW3/25; WC GW6/26) vs no-chip TS 2,125. The 2024/25 GW6–38 conditional comparison also preferred (10,20) among tested pairs. Calibration is not a cutoff-certified estimate of true expected uplift.
- Receding six-GW TS, locked MM, locked PM/vFinal, and locked TC must NOT be modified to implement BB. BB must be layered separately.
- Historical 2025/26 six-GW forecast was partially synthetic from deadline-available data; 2024/25 roster metadata capture provenance remains conditional. Keep caveats without silently retuning policy.

Freeze mechanism: release checkpoint branch `chip-fh-wc-locked-20261009` preserves this code/history. BB research continues on `audit-role-minutes-20261001` and must preserve identical FH/WC choices when BB is unavailable.
