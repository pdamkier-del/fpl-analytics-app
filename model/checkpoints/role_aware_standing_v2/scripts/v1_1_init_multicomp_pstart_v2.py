#!/usr/bin/env python3
"""Create append-only tables for multi-competition P(start) v2 data."""
import argparse, sqlite3
DDL='''
CREATE TABLE IF NOT EXISTS club_matches_v2 (
  source_match_id TEXT PRIMARY KEY,
  season TEXT NOT NULL,
  kickoff_at TEXT NOT NULL,
  competition TEXT NOT NULL,
  competition_stage TEXT,
  round_strength REAL,
  home_team_name TEXT NOT NULL,
  away_team_name TEXT NOT NULL,
  home_team_external_id TEXT,
  away_team_external_id TEXT,
  source_name TEXT NOT NULL,
  payload_path TEXT,
  observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS player_match_roles_v2 (
  source_match_id TEXT NOT NULL,
  external_player_id TEXT NOT NULL,
  player_name TEXT NOT NULL,
  team_external_id TEXT,
  started INTEGER NOT NULL,
  minutes REAL NOT NULL,
  in_matchday_squad INTEGER,
  role TEXT,
  role_x REAL,
  role_y REAL,
  source_name TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  PRIMARY KEY(source_match_id, external_player_id),
  FOREIGN KEY(source_match_id) REFERENCES club_matches_v2(source_match_id)
);
CREATE INDEX IF NOT EXISTS idx_club_matches_v2_date ON club_matches_v2(kickoff_at);
CREATE INDEX IF NOT EXISTS idx_roles_v2_player ON player_match_roles_v2(external_player_id);
CREATE TABLE IF NOT EXISTS player_availability_v2 (
  external_player_id TEXT NOT NULL,
  team_external_id TEXT,
  observed_at TEXT NOT NULL,
  status TEXT NOT NULL,
  chance_of_playing REAL,
  reason TEXT,
  source_name TEXT NOT NULL,
  payload_path TEXT,
  PRIMARY KEY(external_player_id, observed_at, source_name)
);
CREATE INDEX IF NOT EXISTS idx_avail_v2_player_time ON player_availability_v2(external_player_id, observed_at);

CREATE TABLE IF NOT EXISTS player_registration_v2 (
  external_player_id TEXT NOT NULL,
  team_external_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  registration_status TEXT NOT NULL DEFAULT 'registered',
  source_name TEXT NOT NULL,
  payload_path TEXT,
  PRIMARY KEY(external_player_id, team_external_id, observed_at, source_name)
);
CREATE INDEX IF NOT EXISTS idx_registration_v2_team_time ON player_registration_v2(team_external_id, observed_at);
CREATE TABLE IF NOT EXISTS player_transfer_context_v2 (
  external_player_id TEXT NOT NULL,
  team_external_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  previous_team_external_id TEXT,
  transfer_fee_eur REAL,
  fee_percentile_within_club REAL,
  age REAL,
  previous_minutes_share REAL,
  previous_start_share REAL,
  expectation_signal REAL,
  source_name TEXT NOT NULL,
  payload_path TEXT,
  PRIMARY KEY(external_player_id, team_external_id, observed_at, source_name)
);
CREATE INDEX IF NOT EXISTS idx_transfer_context_v2_team_time ON player_transfer_context_v2(team_external_id, observed_at);
CREATE TABLE IF NOT EXISTS player_cold_start_role_prior_v2 (
  external_player_id TEXT NOT NULL,
  team_external_id TEXT NOT NULL,
  role TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  q_prior REAL NOT NULL,
  hierarchy_prior REAL NOT NULL,
  prior_equivalent_matches REAL NOT NULL,
  source_name TEXT NOT NULL,
  PRIMARY KEY(external_player_id, team_external_id, role, observed_at, source_name)
);
CREATE INDEX IF NOT EXISTS idx_cold_prior_v2_team_time ON player_cold_start_role_prior_v2(team_external_id, observed_at);

CREATE TABLE IF NOT EXISTS forecast_match_context_v2 (
  source_match_id TEXT PRIMARY KEY,
  deadline_at TEXT NOT NULL,
  competition TEXT NOT NULL,
  competition_stage TEXT,
  round_strength REAL,
  opponent_strength_home REAL,
  opponent_strength_away REAL,
  observed_at TEXT NOT NULL
);
'''
ap=argparse.ArgumentParser(); ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3'); a=ap.parse_args()
con=sqlite3.connect(a.db); con.executescript(DDL); con.commit(); print('initialized',a.db)
