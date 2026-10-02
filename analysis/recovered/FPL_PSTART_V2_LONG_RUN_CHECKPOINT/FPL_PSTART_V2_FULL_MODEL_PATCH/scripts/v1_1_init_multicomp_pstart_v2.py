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
'''
ap=argparse.ArgumentParser(); ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3'); a=ap.parse_args()
con=sqlite3.connect(a.db); con.executescript(DDL); con.commit(); print('initialized',a.db)
