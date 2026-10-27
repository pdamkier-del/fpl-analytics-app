# Historisk B-backtest · GW6–8, 2026/27

Den aktuelle B-model er kørt retrospektivt på før-deadline-inputpakker. Det er **genskabte prognoser**, ikke de oprindelige prognoser. Faste modelvalg er udvalgt senere; testen er diagnostisk og ikke en uafhængig holdout. Produktionsmodel, aktuelle forecastfiler og private hold ændres ikke.

## Dækning og begrænsning

- GW6: 667 spillere, input-cutoff 10. oktober 07:35:11 UTC; original kilde-/simulatorcheckpoint `live_inputs_20261010_v1` og `live_vfinal_20261010_v1`.
- GW7: 667 spillere, input-cutoff 17. oktober 06:55:48 UTC; checksum-verificeret release `diagnostic-39011647304-1`.
- GW8: 668 spillere, input-cutoff 23. oktober 13:24:39 UTC; checksum-verificeret release `diagnostic-39960797508-1`.
- **GW1–5 er ikke beregnet:** den uændrede redningsmodel kræver fem tidligere ligakampe pr. hold (`keeper_fit.json`, `selection_protocol.min_history_matches=5`). Den numeriske `keeper_saves_at_deadline` afviser fire kampe og accepterer fem i regressionstesten. Tidligere sæsoners data relabeles ikke som den aktuelle sæson. Trup-/skadearkiver findes for disse runder, men opfylder ikke denne modelkontrakt.

At få en fuld GW1–8-test kræver derfor en særskilt valideret sæsonstartspolitik. Det er ikke ærligt at kalde denne leverance en fuld otte-GW-test. Appen viser de fem ikke-understøttede runder med forklaring og uden opdigtede prognoser eller nul-fejl.

## Beregningskæde

Eksisterende PR4/PR8/PR9-inputproducer, `infer_B`, GK-rolle-/varighedsmodel, fælles rollefordeling, særskilt NP-/straffemodel og den fysiske normal-kamptidslinje genbruges. Samme 400 simulationer pr. kamp og seed-offsets fra hele seks-GW-kalenderen bevares; kun origin-GW scores.

MM og PM har samme analytiske minutforventning. Samtlige 60 hold/kamp-sider overholder 90 målmandsminutter, 900 fysiske markspillerminutter og højst fem udskiftninger/tre vinduer for normale kampe. Modellen håndterer fortsat ikke alle bortvisnings-/concussion-undtagelser eller en kalibreret omregning fra fysisk tid til FPLs registrerede minutter.

Numeriske afrundinger ved sandsynlighedsgrænsen normaliseres kun inden for 1e-12; større fejl afvises. Det ændrer ingen modelmatematik. Gamle nul-sandsynligheder kunne ligge omkring −1e-15 efter summering. Arkiverne dokumenterer eventuelle eksportreparationer.

Kildedata og træningslabels skal være kendt før input-cutoff; direkte target-outcomes i PM-/MM-inputs afvises. Der bruges ingen falsk systemdato eller deaktivering af live-forecastets freshness-/deadlinekontroller. Historiske efterkampstider anvender dokumenterede +3/+4-timers estimater, og senere providerrettelser kan ikke fuldt udelukkes. Enkelte historiske rolle-rekonstruktioner blev bygget senere og er derfor ikke certificeret som præcise historiske publikationer.

## Resultater

2.002 spillerkampe, inklusive registrerede ikke-spillende spillere. Modellen er ikke optimeret mod disse runder.

| GW | Spillere | Minut-MAE | xP-MAE |
|---|---:|---:|---:|
| 6 | 667 | 11,65288 | 1,09745 |
| 7 | 667 | 11,67810 | 1,12719 |
| 8 | 668 | 12,56190 | 1,09586 |
| Samlet | 2.002 | 11,96459 | 1,10683 |

Samlet start-Brier 0,081515; minutbias +0,23850; xP-bias +0,00817. Tællinger omfatter også nuller og er ikke en særskilt vurdering af aktive fantasy-valg. Forskellige datotider og spillerkohorter betyder, at tal fra andre modelserier ikke er en parret effektmåling.

## Arkiv og genkørsel

`manifest.json` binder de tre forecast-/auditarkiver og de to oprindelige release-manifester med SHA256. Kilderne kan gendannes via `prepare_season_backtest_capsule.py`; selve replayet køres i `locked_numerical_runtime.py` med `backtest_current_season_b.py`. Disse værktøjer anvender isolerede mapper under work/scratch og overskriver ikke den aktuelle data-/modelkæde. Den oprindelige rolle-træningscache og historiske Core-checkpoints kræves som ved den eksisterende pipeline.

Eksempel for GW7:

```sh
PYTHONPATH=src:scripts:analysis python scripts/locked_numerical_runtime.py scripts/prepare_season_backtest_capsule.py --gw 7 --out /tmp/backtest-gw7 --release-manifest analysis/results/current-season-b-backtest-20261027/gw7-source-release.json
PYTHONPATH=src:scripts:analysis python scripts/locked_numerical_runtime.py scripts/backtest_current_season_b.py --inputs /tmp/backtest-gw7/inputs --source /tmp/backtest-gw7/source --out /tmp/backtest-gw7/output
```

Den publicerede numeriske serie bruger også det foregående rekonstruktionsledgers normale roller (GW6 → GW7 → GW8); brug `--ledger` til dette ved en fuld genkørsel.

## App

Sæsonrapporten får en særskilt backtesttabel og en tredje modelserie på spillerens sæsonoversigt. Før-deadline B, oprindelig MM/PM og genskabt B-backtest holdes adskilt. Faktiske stats fra alle otte runder bevares, og manglende prognoser bliver ikke til nul.
