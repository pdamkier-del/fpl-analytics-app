import pandas as pd
from fpl_v1_1_model.relative_future_match_importance import premier_table_before

def test_table_uses_only_matches_before_cutoff():
    s=pd.DataFrame([
      {"match_id":"m1","competition":"prem","kickoff":pd.Timestamp("2025-08-10T15:00:00Z"),
       "home_team_id":1,"away_team_id":2,"home_score":2,"away_score":0,"finished":True,"gameweek":1},
      {"match_id":"m1","competition":"prem","kickoff":pd.Timestamp("2025-08-10T15:00:00Z"),
       "home_team_id":1,"away_team_id":2,"home_score":2,"away_score":0,"finished":True,"gameweek":1},
      {"match_id":"m2","competition":"prem","kickoff":pd.Timestamp("2025-08-20T15:00:00Z"),
       "home_team_id":2,"away_team_id":1,"home_score":3,"away_score":0,"finished":True,"gameweek":2},
    ])
    t=premier_table_before(s,"2025-08-15T12:00:00Z").set_index("team_id")
    assert t.loc[1,"points"]==3
    assert t.loc[2,"points"]==0
    assert t.loc[1,"position"]==1
