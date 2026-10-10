"""One-GW current-season locked-model readiness audit. Never substitutes an approximate forecast."""
import csv,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"app"

def main():
    people=json.loads((APP/"current-players.json").read_text())
    fixtures=json.loads((APP/"live-fixtures.json").read_text())
    gw=people.get("next_gw")
    target=[f for f in fixtures["fixtures"] if f.get("gw")==gw and not f.get("finished")]
    required={
      "current_2026_27_confirmed_tactical_lineups":ROOT/"data_v1_1/raw/fpl-core-2026-27",
      "current_2026_27_predeadline_news":ROOT/"data_v1_1/derived/team_news_audit/2026-27-v2",
      "current_2026_27_match_ratings":ROOT/"data_v1_1/derived/mm_v2_ratings/player_match_ratings_2026_27.csv.gz",
      "current_2026_27_mm_fixture_features":ROOT/"work/live-final-model/mm_features.csv.gz",
      "current_2026_27_pm_fixture_features":ROOT/"work/live-final-model/pm_features.csv.gz",
      "current_2026_27_licensed_inputs":ROOT/"work/live-final-model/manifest.json"}
    checks={k:p.exists() for k,p in required.items()}
    official_base_path=APP/"gw-source-features.json"
    source_base=json.loads(official_base_path.read_text()) if official_base_path.is_file() else {}
    source_ready=(source_base.get("observed_at")==people["fetched_at"] and source_base.get("gw")==gw and source_base.get("fixture_count")==len(target) and source_base.get("player_fixture_count",0)>=250)
    report={"gw":gw,"source_asof":people["fetched_at"],"fixture_count":len(target),
      "player_count":len(people["players"]),"official_fixture_feature_base_ready":source_ready,
      "official_fixture_feature_rows":source_base.get("player_fixture_count",0),"required_input_checks":checks,
      "locked_model_ready":all(checks.values()) and bool(target),
      "note":"Existence audit only, NOT validation of completeness, as-of timestamps or model inference.",
      "locked_mm_script":"scripts/run_locked_mm_gw6_38.py",
      "locked_pm_script":"scripts/run_rolling_vfinal_gw6_38.py",
      "locked_ts_script":"scripts/run_ts_v3_final_chain_gw6.py"}
    (APP/"one-gw-readiness.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("CURRENT ONE GW LOCKED MODEL PREFLIGHT:",json.dumps(report))
    if report["locked_model_ready"]:
        print("Inputs exist; verification and inference still required.")
    else:
        print("BLOCKED: not enough cutoff-safe current-season inputs to execute locked MM -> vFinal -> TS on GW",gw)
if __name__=="__main__":main()
