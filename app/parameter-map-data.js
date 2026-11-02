/* Read-only explanatory metadata. Historical values are not asserted as live values. */
window.FPL_PARAMETER_MAP=[
  {
    "group": "Hold og kamp",
    "key": "lambda_home_goals",
    "name": "Hjemmeholdets mål",
    "desc": "Forventede mål mod den konkrete modstander",
    "type": "Dynamisk",
    "value": null,
    "source": "locked team-model → MatchSimInput"
  },
  {
    "group": "Hold og kamp",
    "key": "lambda_away_goals",
    "name": "Udeholdets mål",
    "desc": "Forventede mål mod den konkrete modstander",
    "type": "Dynamisk",
    "value": null,
    "source": "locked team-model → MatchSimInput"
  },
  {
    "group": "Hold og kamp",
    "key": "assist_probability_per_goal",
    "name": "Assist-hyppighed",
    "desc": "Andel almindelige mål med assist",
    "type": "Fallback",
    "value": "0,72 (standard, kan overskrives)",
    "source": "joint_simulator.py"
  },
  {
    "group": "Hold og kamp",
    "key": "lambda_pen",
    "name": "Straffesparksintensitet",
    "desc": "Holdets forventede straffespark",
    "type": "Dynamisk",
    "value": null,
    "source": "fixture_input.py → PM"
  },
  {
    "group": "Hold og kamp",
    "key": "team_pen_conversion",
    "name": "Straffesparkskonvertering",
    "desc": "Holdets konvertering af straffespark",
    "type": "Dynamisk",
    "value": null,
    "source": "fixture_input.py → PM"
  },
  {
    "group": "Rolle og spiller",
    "key": "pos",
    "name": "FPL-position",
    "desc": "Afgør FPL-scoringsregler og relevante priors",
    "type": "Regel",
    "value": null,
    "source": "FPL roster / fixture_input.py"
  },
  {
    "group": "Rolle og spiller",
    "key": "q_role_slow",
    "name": "Taktisk rollefordeling",
    "desc": "Fordeler rollen mellem historisk plausible positioner før deadline",
    "type": "Dynamisk",
    "value": null,
    "source": "role_classifier.py / role_event_priors.py"
  },
  {
    "group": "Rolle og spiller",
    "key": "goal_mu",
    "name": "Målpotentiale",
    "desc": "Spillerandel normaliseret til holdets målbudget",
    "type": "Afledt",
    "value": null,
    "source": "attack.py / fixture_input.py"
  },
  {
    "group": "Rolle og spiller",
    "key": "assist_mu",
    "name": "Assistpotentiale",
    "desc": "Spillerandel af forventede assists",
    "type": "Afledt",
    "value": null,
    "source": "attack.py / fixture_input.py"
  },
  {
    "group": "Rolle og spiller",
    "key": "goal_prior_tau",
    "name": "Målpriorstyrke",
    "desc": "Historisk kalibreret positions-shrinkage",
    "type": "Historisk",
    "value": "340,37 minutter (ikke bekræftet live)",
    "source": "joint-component-recovery-v1/player_attack_fit.json"
  },
  {
    "group": "Rolle og spiller",
    "key": "assist_prior_tau",
    "name": "Assistpriorstyrke",
    "desc": "Historisk kalibreret positions-shrinkage",
    "type": "Historisk",
    "value": "365,22 minutter (ikke bekræftet live)",
    "source": "joint-component-recovery-v1/player_attack_fit.json"
  },
  {
    "group": "Minutmodel MM",
    "key": "p_start",
    "name": "Startchance",
    "desc": "Sandsynlighed for at starte",
    "type": "Dynamisk",
    "value": null,
    "source": "locked MM → joint_simulator.py"
  },
  {
    "group": "Minutmodel MM",
    "key": "p_cameo_given_bench",
    "name": "Indskiftningschance",
    "desc": "Sandsynlighed for indskiftning givet bænk",
    "type": "Dynamisk",
    "value": null,
    "source": "locked MM → joint_simulator.py"
  },
  {
    "group": "Minutmodel MM",
    "key": "start_minutes_mean",
    "name": "Starterminutter",
    "desc": "Betinget forventet spilletid",
    "type": "Dynamisk",
    "value": null,
    "source": "locked MM → joint_simulator.py"
  },
  {
    "group": "Minutmodel MM",
    "key": "cameo_minutes_mean",
    "name": "Indskiftningsminutter",
    "desc": "Betinget forventet spilletid",
    "type": "Dynamisk",
    "value": null,
    "source": "locked MM → joint_simulator.py"
  },
  {
    "group": "Minutmodel MM",
    "key": "xmins",
    "name": "Forventede minutter",
    "desc": "Start- og indskiftningskomponenter kombineres",
    "type": "Afledt",
    "value": null,
    "source": "canonical_fixture_input.py"
  },
  {
    "group": "Defensive bidrag",
    "key": "mu_dc",
    "name": "DefCon-rate",
    "desc": "Forventet antal defensive aktioner",
    "type": "Dynamisk",
    "value": null,
    "source": "fixture_input.py"
  },
  {
    "group": "Defensive bidrag",
    "key": "dc_alpha",
    "name": "DefCon-spredning",
    "desc": "NB2 variansparameter; historisk delt pr. FPL-position",
    "type": "Kalibreret",
    "value": null,
    "source": "defcon.py / joint_simulator.py"
  },
  {
    "group": "Defensive bidrag",
    "key": "dc_threshold_DEF",
    "name": "Forsvarernes DefCon-grænse",
    "desc": "Giver to point ved opnået tærskel",
    "type": "Regel",
    "value": "10 aktioner",
    "source": "defcon.py"
  },
  {
    "group": "Defensive bidrag",
    "key": "dc_threshold_MID_FWD",
    "name": "MID/FWD DefCon-grænse",
    "desc": "Giver to point ved opnået tærskel",
    "type": "Regel",
    "value": "12 aktioner",
    "source": "defcon.py"
  },
  {
    "group": "Bonus og disciplin",
    "key": "bg_mean_rate90",
    "name": "BPS-baggrund",
    "desc": "Forventet baggrunds-BPS pr. 90 minutter",
    "type": "Dynamisk",
    "value": null,
    "source": "fixture_input.py → joint_simulator.py"
  },
  {
    "group": "Bonus og disciplin",
    "key": "bg_sd90",
    "name": "BPS-spredning",
    "desc": "Spredning i baggrunds-BPS",
    "type": "Kalibreret",
    "value": null,
    "source": "joint_simulator.py"
  },
  {
    "group": "Bonus og disciplin",
    "key": "bps_background_mean",
    "name": "Ældre BPS-gennemsnit",
    "desc": "Fallback kun hvis rate90 mangler",
    "type": "Fallback",
    "value": "0",
    "source": "joint_simulator.py"
  },
  {
    "group": "Bonus og disciplin",
    "key": "bps_background_sd",
    "name": "Ældre BPS-spredning",
    "desc": "Fallback kun hvis rate90 mangler",
    "type": "Fallback",
    "value": "0",
    "source": "joint_simulator.py"
  },
  {
    "group": "Bonus og disciplin",
    "key": "p_yellow",
    "name": "Gult kort",
    "desc": "Sandsynlighed for gult kort",
    "type": "Dynamisk",
    "value": null,
    "source": "fixture_input.py"
  },
  {
    "group": "Bonus og disciplin",
    "key": "p_red",
    "name": "Rødt kort",
    "desc": "Sandsynlighed for rødt kort",
    "type": "Dynamisk",
    "value": null,
    "source": "fixture_input.py"
  },
  {
    "group": "Målmænd og straffespark",
    "key": "lambda_saves",
    "name": "Redninger",
    "desc": "Forventet antal redninger",
    "type": "Dynamisk",
    "value": null,
    "source": "keeper.py / joint_simulator.py"
  },
  {
    "group": "Målmænd og straffespark",
    "key": "pen_weight",
    "name": "Straffesparksskytte",
    "desc": "Fordelingsvægt ved straffespark",
    "type": "Dynamisk",
    "value": null,
    "source": "fixture_input.py"
  },
  {
    "group": "Målmænd og straffespark",
    "key": "pen_conversion",
    "name": "Straffesparkskonvertering",
    "desc": "Skytterelateret sandsynlighed",
    "type": "Dynamisk",
    "value": null,
    "source": "fixture_input.py"
  },
  {
    "group": "Målmænd og straffespark",
    "key": "penalty_order",
    "name": "Rækkefølge for skytter",
    "desc": "Kun aktiv under hierarkisk penalty-model",
    "type": "Betinget",
    "value": null,
    "source": "joint_simulator.py"
  },
  {
    "group": "Strategi TS",
    "key": "six_gw_weights",
    "name": "Seks-GW-vægtning",
    "desc": "Fast diskontering i låst TS v3",
    "type": "Låst plan",
    "value": "1, 0,60, 0,36, 0,216, 0,1296, 0,07776",
    "source": "TS v3 locked contract; verify active release"
  },
  {
    "group": "Strategi TS",
    "key": "hit_buffer",
    "name": "Transfer hit-buffer",
    "desc": "Beslutningsbuffer ved transfers",
    "type": "Låst plan",
    "value": "1,0 point",
    "source": "TS v3 locked contract; verify active release"
  }
];
