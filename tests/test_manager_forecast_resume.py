"""Exercise the actual browser manager state machine, without remote jobs."""
from pathlib import Path
import subprocess


def test_waiting_manager_resumes_without_reconfirmation():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', 'tests/test_manager_forecast_resume.js'], cwd=root, check=True)


def test_changed_official_news_has_a_distinct_waiting_reason():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', 'tests/test_dashboard_team_news.js'], cwd=root, check=True)
