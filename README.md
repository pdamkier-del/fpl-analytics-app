# FPL Analytics — project entry point

**Season 2026/27: observation and validation phase.** Read [STATUS.md](STATUS.md) before changing any model or deployment. The original desktop application instructions are retained below.

- [Current B transfer app](https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html)
- [Isolated team/transfers preview](https://pdamkier-del.github.io/fpl-analytics-app/previews/team-transfers-20261126/app/transfers-classic.html) (PR #60; not the same release)
- [Permanent public forecast releases](https://github.com/pdamkier-del/fpl-analytics-app/releases)
- [Workflow runs](https://github.com/pdamkier-del/fpl-analytics-app/actions)
- [Agent rules](AGENTS.md)

The default branch is not necessarily the numerical runtime or UI checkout used by a deployed preview. Inspect the publication receipt, workflow source pins and service health before changing code. Do not merge research stacks or change frozen parameters to repair operations.

---

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

The application supports two types of updates:

- **App Code Updates**: Core application improvements and features
- **FPL Data Updates**: Latest Fantasy Premier League data and statistics