# FPL Research Lab — staged dashboard product specification

Target: a separate read-only public `/research-lab/` area, potentially sharing the existing app navigation and design system. This document is a specification, not a built or deployed page.

## MVP screens

1. **Overview:** frozen baseline/model versions, final versus pending GWs, data coverage, MM/PM proper-score cards, links to source/result versions. No score is labelled “production validated” merely because it is displayed.
2. **GW evolution:** MM start-Brier/log loss, expected-minute RMSE/MAE; PM xP-MSE/MAE/CRPS; calibration and sample counts. Per-GW and cumulative scores are separate. Display code/version changes, excluded rounds, and CI methodology.
3. **Error atlas:** public FPL player/club/position/role and component drilldowns, raw error sign, finite sample support and target definitions. Sparse subgroups are visibly exploratory; do not rank alleged player bias from three observations.
4. **Components:** team goal volume, goal/assist share/eligibility, CS qualification and on-pitch CS, DC, save points, BPS versus bonus. Identification gaps and model-dependent assumptions are visible.
5. **Experiments:** searchable registry, hypothesis, baseline, time splits, dependencies, status, registered decisions, full reproduction and immutable evidence links. Rejected and uninformative trials remain visible.
6. **Versions/decisions:** original forecast vintages, model/fit/scoring-rule identities and append-only decision log. Show when a model changed; never silently compare unlike cohorts.

## Later screens

- **External comparison:** only lawful, properly timestamped matched xP; ep_next remains a named simple baseline. If no commercial data exists, show the gate rather than a fabricated league table.
- **Achievable accuracy:** learning curves, alternative-class and conditional-uncertainty diagnostics with information-set assumptions. No “percentage of optimal” gauge without an identified benchmark.
- **Private TS Lab:** owner-scoped capability/session, no-store, explicit recommendation/intention/execution, keep-control, FT/hits/chips and trajectory coverage. Static Pages never receives the underlying private state.
- **Parameter/experiment explorer:** original baseline immutable; each what-if gets a candidate ID, independent namespace, assumptions and compute budget. Interactive changes are never a live production configuration. Fits or expensive search require a registered execution plan in a later task.

## Acceptance tests before a Lab UI release

Dashboard values equal the versioned report contract on desktop/mobile; zero/pending/not-identified states remain distinct; source/time/model identity available in each drilldown; charts have target units and denominator/sample counts; missing GWs are gaps rather than interpolated fake scores. Filters do not change registered primary populations or retrospectively choose a winning model. Public bundle/artifact scans and access tests prove no managerstate or secrets are included. No dashboard action can mutate the approved production manifest.

MVP UI work follows completion of the report contract and one verified GW loop. The current deliverable remains the masterplan/registry/architecture, not implementation of these screens.
