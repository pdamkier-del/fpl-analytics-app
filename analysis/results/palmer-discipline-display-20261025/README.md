# Palmer: vis rødt kort og den korrekte afsoning

## Faktisk status, kontrolleret 25. oktober 2026

Cole Palmer er **spiller 154 hos Chelsea (hold 6)**. Den anden Palmer i FPL-kataloget er en anden spiller og bruges ikke som identitet.

- Officielle FPL-kampdata til Chelsea–Spurs, fixture **73**, GW8, kickoff **24. oktober kl. 16.30 UTC**, registrerer **ét rødt kort**, 79 minutter og -1 FPL-point. Samme kort findes i fixture-events, GW8-live og element-summary. FPL markerer fortsat kampen som foreløbig i den indsamlede fixtureversion; den markering bevares.
- FPL-bootstrap angiver samtidig `status=a`, tomt nyhedsfelt og 100 % tilgængelighed til næste runde.
- [Premier Leagues officielle karantæneoversigt](https://www.premierleague.com/en/news/4425344) forklarer: udvisning for **to gule kort**, automatisk **én kamps karantæne**, afsoning mod **Liverpool i EFL Cup**, og **ingen mistede Premier League-kampe** som følge af denne udvisning.

Kort og PL-tilgængelighed kan altså begge være korrekte. Det var misvisende, at kortet manglede i visningen; det er ikke i sig selv bevis for, at Palmer skal have nul xM til næste PL-kamp. Korttypen kan heller ikke udledes af FPLs `yellow_cards=0` i kampstatistikken: den selvstændige officielle forklaring er nødvendig.

## Rettelsen

1. **Generisk kortkontrol for alle spillere.** Det eksisterende offentlige statusfeed henter nu også officielle fixture-events. Røde kort fra de seneste 14 dage kobles med præcise spiller- og kamp-ID'er. Sæsontotalen bruges ikke som en aktuel karantæne. Fremtidige/for gamle kampe, dubletter og ukendte spiller-ID'er bliver ikke omdannet til nye advarsler.
2. **Spillerkortet viser aktuel status tydeligt.** Det nye statusfelt står før kampoversigten og viser rødt kort, kamp/GW/dato, eventuel foreløbig markering, rå FPL-status og en separat forklaring på afsoningen. Standalone-spillersidens statusmærke viser også kortet. Historiktabellen har en kolonne for røde kort.
3. **Dashboardet viser kortet for det ejede hold.** En spiller med et registreret kort gemmes ikke under sammenfoldede tilgængelige spillere, blot fordi FPL-status er `a`. Statusflaget omskrives ikke til en opdigtet suspension.
4. **Kildebelagt afsoning.** `research/discipline_sources/reviewed-resolutions.json` indeholder den gennemgåede PL-oplysning om Palmer. Den er bundet til spiller-ID, fixture-ID **og absolut kickoff**, så genbrugte IDs i andre sæsoner ikke arver afgørelsen. Den beskriver fakta fra kilden, ikke en manuelt valgt startchance eller modelvægt. Uafklarede andre kort vises som uafklarede; én kendt sag giver ikke en generel afsoningsregel.
5. **Alder er synlig.** Statuskilden har hentetid. Hvis den er ældre end én time, kan registrerede kort stadig vises som senest kendte oplysninger, men tilgængelighed bekræftes ikke som aktuel. Planlægningens eksisterende strenge friskhedskrav er bevaret; `allowStale` gælder visning, ikke tilladelse til beregning.
6. **Fælles opdateringsvej.** B-publiceringen genhenter det udvidede feed, og den eksisterende nyhedsopdatering opdaterer både tilgængelighed og kortdata. Kuraterede rollefortolkninger er stadig manuelle og markeres særskilt; de må ikke forveksles med et komplet live-nyhedsfeed. GitHubs planlagte kørsler er ikke en garanti for øjeblikkelig opdatering.

Der er ingen ændring af MM-/PM-/TS-matematik eller en ny karantænekorrektion i prognosen. Palmer får især ikke fejlagtigt nul minutter i Premier League alene på grund af pokalafsoningen. Den allerede kørende numeriske B-opdatering genbruges, og produktionsmodellen og brugerens hold ændres ikke.

## Verifikation

- **1.025 Python-tests bestået**, 57,15 sekunder. Nye tests dækker red-event versus availability, sæsontotal versus kamp, datoafgrænsning, begge kampsider, ukendte/dobbelte events, præcis afsoningskobling og fremtidige kildevurderinger.
- JavaScript-tests består for kort med `status=a`, synlig kortadvarsel uden opdigtet PL-ban, uændrede beregningsfriskhedskrav og en kildebelagt pokalafsoning.
- Lokal browserkontrol består på desktop, mobil og den separate spillerside: kort og afsoning vises, historik viser én udvisning, de otte sandsynlighedskort bevares, ingen horisontal overflow, sidefejl eller privat POST, og ingen ændret holdlagring.
- Numeriske kildefiler matcher fortsat den gennemgåede B-kilde `03d5c4d4777b44bc1d37884a1cf4dde106b45cab`. Lokalt genereret visning ændrer ikke de numeriske forecastbytes.

```sh
PYTHONPATH=src:scripts:. /workspace/fpl-venv/bin/python scripts/collect_dashboard_news.py --out /tmp/current-news.json
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python -m pytest -q tests
node tests/test_dashboard_team_news.js
node tests/test_player_text_context.js
NODE_PATH=/workspace/scratch/normal-match-browser/node_modules DESKTOP_URL=http://127.0.0.1:18129/mm-preview/app/ node analysis/verify_player_discipline.cjs
```

Primærkilden og dens hentetid/hash er bevaret i `official-suspension-receipt.json`; den gennemgåede afsoning findes i registret. Den nye statusrecord og lokale browserkontroller er gemt her. Offentlig releasekontrol tilføjes efter deployment.
