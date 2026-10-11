# Classic app recovery checkpoint — 2026-10-11

Initial verified application code: `a4df4661fdb23439c7c924c063c52fd356f36898`, branch `free-github-static-20261010`.
Pages: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38161078504 — success.
Private service HTTP checks: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/38161078467 — success.

## Delivered flow

The original technical My Team and Player layouts are retained. Classic Transfers now calls the original private Python runtime directly, resumes private jobs, and displays the saved result without redirecting users into a different optimizer. Manager-state identity, forecast cutoff, deadline, official next GW, diagnostic status and validation-only rejection are checked before recommendations are shown. A requested computation waiting for a cutoff after the state observation resumes automatically when a valid new forecast is loaded; existing private jobs also resume. This transport-only behavior is regression-tested and does not change any decision rule.

The actual squad and purchase prices remain in browser storage. A real private manager computation was completed through the Classic button, and the input was compared with the existing private backup after UI tests: unchanged. No actual roster, purchase prices, manager hash, recommendations, private URLs or job capabilities are recorded in this repository.

My Team supports Pitch/List, metric selection, original player popup, full profiles, legal XI/bench swaps and separate manual C/VC. Saved manual lineups survive reload. Without a saved lineup, a valid original current-team result supplies a clearly labelled unsaved model default. Manual transfer previews show existing player forecast differences and legal budget/club checks; they neither run an alternative JS transfer strategy nor alter the actual squad or personal plan.

Profiles use the ID-keyed official team dictionary, official image codes, fixture IDs, original xP/minutes/start probabilities, point components, graphs and official season statistics. HTML navigation and JS/CSS references are versioned together to avoid old cached broken documents.

A private one-click opening file and the existing private backup were updated outside GitHub. Portable import finishes before the Classic page reads an initially empty store, and does not replace newer actual state.

## Verification

- 420 Python tests passed; all 10 JavaScript test files passed.
- Published desktop: all seven routes, player search/sort, fixture GW selection/details, unsupported horizon as Not Available, player comparison, model tree/formulas, actual 15-player rendering, C/VC, legal swaps, illegal formation rejection, captain-to-bench rejection, Pitch/List and reload.
- Published manual editor rejected an invalid purchase price without saving it. Manual preview rejected insufficient budget and a fourth club player.
- The original private Python service completed a genuine personal TS/chip calculation started directly from Classic. No GitHub token or official account sync is needed.
- Source changes since recovery HEAD do not touch `src`, `model`, `config`, `analysis` or `service`. Locked mathematics, search rules and parameters are unchanged; `locked_model_active=false`.
- Timeout, disconnect, stale forecast, price/state mismatch and synthetic result rejection are covered by regression tests.

## Concrete remaining limits

- A real mobile viewport/touch-drag session was not verified. The cloud browser offers no viewport control; its local-file mobile wrapper was rejected by URL policy, and no bypass was attempted. Responsive styles are present; the tested ⇄ interaction remains the fallback.
- Separate constrained one-transfer/paid-transfer optimized scenarios are Not Available when the original runtime has not returned them. No alternate model is invented.
- The full future chip calendar remains Not Available; original current chip decisions and manual TC policy are preserved.
- Main has the hourly UTC :17 forecast schedule, but a successful genuine scheduled original-chain run has not been verified. The public UI warns about missing/overdue runs. The existing forecast is checked for freshness/deadline/GW before use; Pages deployment alone is not a new model forecast.
- Full source certification remains blocked by the documented BPS/history/mapping/publication-time gaps. No certification is claimed.
- Ordinary user browser storage cannot be inspected from the separate cloud session. The private one-click file is the explicit one-time bridge; later manual updates and persistence use the same local storage keys.

Resume from latest HEAD; preserve any newer user edits. Do not publish private files or retest historical source versions without new evidence.

