# Research log · 28 November 2026

1. The requested branch did not exist remotely. Created it from the observed `main` tip. Reviewed archive evidence on main and the frozen full-pool branch for suitability.
2. Scoped the exact TS v3 comparison to missing original-vintage coverage. Implemented a separate lagged public-data replay and market panel. Recorded 2022–23 as development and 2023–24 and 2024–25 as chronological evaluation seasons. The analysis is exploratory and was not externally preregistered. These already-public seasons are not prospective evidence.
3. Initial run stopped before analysis because the 2022–23 GW7 postponement left an empty initial snapshot. Shifted the common start to GW8 across seasons and arms before reading result tables. Kept the same model coefficients and strategy weights.
4. Tested selling prices, banking, hit rules, captain/vice, formation constraints and time filtering. Retained aggregate data checks, score and price tables, and charts.
5. Repeated market estimation independently and matched the aggregate CSV and source digests byte for byte. Completed 4,185 weekly ledger rows, verified unique season/horizon/seed/arm/GW keys, nonnegative bank and hit support, and retained per-season market robustness estimates.
