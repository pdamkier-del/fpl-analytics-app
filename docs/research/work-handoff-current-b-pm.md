# Work handoff — current B → locked PM integration

Branch: `research-mm-pmf-sampler-bridge-20261017` (PR #17).
Production must remain unchanged until CI and live data gates pass.

## Already wired

- `capture_mm_prospective.py` archives official FPL bootstrap, fixtures and a verified `official-roster.json`.
- `assemble_current_b_roster.py` joins the official fixture/player set to canonical IDs and an **authentic** B feature table, rejecting mismatches.
- `run_current_mm_pm_once.py` runs the existing B calibration + locked vFinal PM six-GW preview. No personal manager state and no TS recommendations.
- The default PM minute sampler is unchanged. Do not use the PR17 alternative sampler for production.

## Data Work still must obtain/build

Place data privately under `work/` and use one single forecast cutoff before the official next deadline.

1. A timestamped official source directory containing `bootstrap.json`, `fixtures.json`, `receipt.json`, `official-roster.json`; refresh as necessary.
2. `identity.csv`: bijective official `fpl_element,player_uuid` mapping consistent with existing canonical identities, including transfers/new signings.
3. `features.csv`: one authentic current PR8 `role_chance_return_duration` row for **every** roster fixture-player, containing `NUM` plus p/q/s/c/x, team/position/gw/cutoff and known-at news/return/physical features. Use existing research code and historical minute records; never substitute legacy/vNext numbers without refit and disclosure.
4. `history.csv`: previously known, pre-cutoff labels/calibration rows for the original PR9 B model, with `known_at < cutoff`.
5. `roles.csv`: genuine formation/prior constraints, consistent with full XI.
6. `pm.csv`: complete current vFinal fixture rows, matching every official player/fixture and immutable rate controls, with penalty, goals, defence, BPS and availability features.
7. `bps-audit.json`: validated contemporary scoring rules and inputs.
8. `B-feature-provenance.json` **inside source directory**: includes `upstream_variant: role_chance_return_duration`, `features` matching the exact `research_individual_mm_refinement.NUM` array, `source_manifest_sha256` from authentic source manifest and verifiable source timing. Never create a fake manifest.

## Execute

```bash
PYTHONPATH=src:scripts:. python -m pytest -q tests/test_current_mm_roster.py tests/test_assemble_current_b_roster.py tests/test_mm_locked_bridge.py
PYTHONPATH=src:scripts:. python scripts/run_current_mm_pm_once.py \
  --source work/official-source --identity work/identity.csv \
  --features work/features.csv --history work/history.csv \
  --roles work/roles.csv --pm-input work/pm.csv \
  --bps-audit work/bps-audit.json --out work/current-mm-pm-preview
```

Run one fixture first if the full batch fails; diagnose exact required column and source. Once a genuine six-GW current forecast succeeds, wire existing public preview exporter and only then feed TS with verified private manager state. Validate all point sums, deadlines, fixture counts, hard absences and no leaked historical outcomes. Do not call synthetic or historical output a live forecast. Do not deploy unverified code.
