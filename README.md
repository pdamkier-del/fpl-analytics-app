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