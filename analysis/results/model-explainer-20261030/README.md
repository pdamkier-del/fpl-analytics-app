# Readable model explainer in the existing B app

Five-step Data → MM → PM → TS → Chips navigation, five native MathML equations (fractions, summations, indices), plain-language reading instructions and variable definitions. No external math renderer/CDN or change to the model. Existing October9 model-tree documentation remains in a closed, explicitly historical archive, not presented as the active B implementation.

Actual sealed player/GW examples show start chance, MM expected minutes, PM expected minutes, zero/60+/90-minute probabilities and exported xP components. Changing player or GW reuses forecast data only. Missing/unusable forecast status is labelled; no fabricated conditional inputs or point channels. Penalty goal/miss subsets are explicitly not double-counted.

Checked against source: minutes by conditional expectation; probabilities by minute mass; xP as sample mean and sum of exported channels; TS objective discounts future scores but does not discount deterministic hits/buffer (PlannerConfig.discount_transfer_costs=False in existing config). Physical90 GK/900 outfield coverage is distinguished from reported FPL clock; timeline omissions for red-card removals/concussion extras remain explicit. Restricted/heuristic transfer search is not described as a proven global optimum.

Local desktop/mobile browser checks cover native equations, responsive header/step navigation, real player and six-GW selection, channel values, archive labelling, same existing navigation, unchanged local squad/plan and no computation requests or JavaScript errors/overflow. Screenshots use public forecast players only, no personal manager data.
