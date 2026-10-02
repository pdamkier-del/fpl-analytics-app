# FPL Analytics Desktop Web App

A Python-based desktop web application for Fantasy Premier League analytics and data management.

## Overview

This is the FPL Analytics v1.6 desktop application, providing tools for analyzing FPL data and managing player statistics. The application uses a web interface served locally for an intuitive user experience.

## Architecture

The application consists of several key components:

- **app/**: Web application frontend and backend
- **model/**: Data models and FPL analytics engine
- **start_app.py**: Application entry point
- **updater.py**: Handles application and data updates

## Local Data

**Important**: User-specific data and configurations are stored locally on your machine and are **not** tracked in this repository. The following directories are ignored:

- `user/`: Local user profiles, preferences, and settings
- `model/runs/`: Local model training runs and experiments
- `runtime/`: Local runtime environment

See `.gitignore` for the complete list of ignored paths.

## Official Model Versions

The `model/versions/v0.1-baseline.json` file is included as the official baseline model. Future personal Model Lab versions should remain local unless deliberately promoted to an official model version.

## Getting Started

Run the application using:

```bash
python start_app.py
```

Or use the Windows launcher script:

```bash
Start FPL App.bat
```

## Updates

## Advanced standing model checkpoint

The recovered standing model is in `src/fpl_v1_1_model/` and `scripts/`.
The original checkpoint is preserved byte-for-byte under
`model/checkpoints/role_aware_standing_v2/`; its manifest remains authoritative.
`model/checkpoints/provenance.json` records the source archive hashes. The
existing desktop bridge remains the active app engine until model validation
and integration are complete.

Historical Core from the existing Phase 5E checkpoint is preserved as
`model/checkpoints/phase5e_core/fpl_v1_1.sqlite3.gz`. Decompress it into a working
directory before running database scripts; never overwrite the frozen copy.
Detailed lineup/formation/average-position source CSVs are under
`data_v1_1/raw/fpl-core-2025-26/`.

Run the recovered model checks with `python scripts/run_model_checks.py`.
Dependencies are Python 3, NumPy, pandas, SciPy and scikit-learn; pytest is
optional for these assertion tests. See `docs/checkpoints/2026-10-01-integration.md`
for reproducible benchmark commands and remaining validation blockers.

The reproducible formation-first role classifier, cutoff-gated q/H and frozen
GW22–38 benchmark now run with:

```bash
python scripts/build_reproducible_role_benchmark.py --db work/core.sqlite3
```

See `docs/checkpoints/2026-10-02-reproducible-role-foundation.md` for the 1,052
disagreement audit, exact rules, OOS results, historical cutoff limitations and
the unresolved high-impact-role sanity check. All feature predictions and
input/code/output checksums are versioned under
`analysis/results/reproducible-role-v1/`. The app engine is not switched to this
experimental model.

The application supports two types of updates:

- **App Code Updates**: Core application improvements and features
- **FPL Data Updates**: Latest Fantasy Premier League data and statistics
