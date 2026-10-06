# MM v2 rating data brief

Build a player-match rating ledger for 2025/26 official club matches involving Premier League clubs, and then extend it to 2026/27 to date.

Competitions: Premier League, Champions League, Europa League, Conference League, FA Cup, EFL/Carabao Cup.

Preferred providers: FotMob and SofaScore. Keep separate provider rows when both exist.

Required CSV columns:
- provider
- player_uuid
- match_id
- available_at
- rating

Preferred extra columns:
- provider_player_id
- player_name
- team_id
- team_name
- competition
- kickoff
- minutes
- role

Identity rules:
1. reuse existing internal player_uuid
2. exact provider/internal mapping if available
3. exact existing FPL/all-competitions mapping
4. exact normalized name + team + match
5. leave unresolved/ambiguous rows unresolved; never fuzzy-force

Data rules:
- ratings must stay on original 0-10 provider scale
- duplicate provider/player/match rows are invalid
- no target-match leakage
- available_at must be after the completed match; document any proxy used
- audit mapped, unresolved, ambiguous and missing-coverage rows

Suggested output:
`data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz`

Then run:
`PYTHONPATH=src python scripts/run_mm_v2_xi_rating_experiment.py --ratings data_v1_1/derived/mm_v2_ratings/player_match_ratings.csv.gz --out analysis/results/mm-v2-xi-rating-with-external-ratings-20261006-v1`

Compare against XI-only:
`analysis/results/mm-v2-xi-rating-20261006-v1/result.json`

Important slices: uncertain starters, multi-role players, close same-role competition, rating up/down trends, and GWs 30,22,31,36,32,38,37,29.

Do not promote from reused GW22-38 alone.
