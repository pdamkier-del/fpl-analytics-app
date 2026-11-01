# Hvor kommer FPL-appens data fra — og hvilke muligheder er relevante?

Undersøgt 25. oktober 2026. Dette er en gennemgang af repositoryets indsamlingskode, eksisterende kildekvitteringer og leverandørernes offentlige produktsider. Ingen modelændring, ny dataintegration, konto, betaling eller leverandørhenvendelse. Kommercielle API'er er ikke afprøvet med nøgle. Annonceret dækning er ikke en uafhængig certificering af hver kamp, spiller eller statistik.

## De kilder, vi faktisk har

| Kilde | Indhold og anvendelse | Vigtig afgrænsning |
|---|---|---|
| Officiel Fantasy Premier League API | Aktuelle spiller-/hold-ID'er, FPL-positioner og priser, deadlines, PL-kampprogram, officielle point/minutter og tilgængelighedsnyheder. Bruges af den aktuelle indsamlingskode og dashboardet. | FPL's chance for at spille er ikke i sig selv P(start). Data omfatter ikke spillerens fulde internationale/CL/pokalbelastning. Publikt endpoint er ikke det samme som en aftalt stabil integrationsservice. |
| FotMob | Kampoversigter og detaljer: bekræftede opstillinger, formationer, minutter, ratings og tilgængelige xG/xA-/skud-/målmands-/eventstatistikker. Indsamlingen søger PL, CL, EL, Conference inkl. kvalifikation, FA Cup og EFL Cup. Bruges til aktuelle modelinputs og særskilt spillerkortkontekst. | Adgang går gennem webappens endpoints, ikke en dokumenteret kommerciel API-aftale i projektet. Udvalgte turneringer betyder ikke komplet målt dækning. Ukendte felter/identiteter skal forblive ukendte. |
| `olbauday/FPL-Core-Insights` | Historiske kamp-/spillerstatistikker og rolle-/opstillingsmateriale, indlæst i vores Core og historiske forskningsdata. | Et community-arkiv, ikke vores direkte leverandøraftale. Kendte fejl med datefrie cup/Europe-nøgler har krævet karantæne og gendannelse. |
| `vaastav/Fantasy-Premier-League` og `Randdalf/fplcache` | Historiske FPL-spillerkampe/registre og arkiverede bootstrap-snapshots. Vaastav-indsamlingen beholder også Understat-materiale. | Historiske slutværdier er ikke automatisk de oplysninger, der var til rådighed før en bestemt deadline. Understat-filer i arkivet betyder ikke et aktivt Understat-feed i B. |
| Officielle klub-/PL-sider | Dokumenterede skader, udlån, spillerprofiler og kamptrupper, bl.a. målmandsgennemgangen. | Afgrænsede kildekvitteringer og kontrol; generel struktureret indlæsning af trænerudtalelser er ikke implementeret. |
| Football-Data.co.uk | Historiske resultater og odds er hentet til markedsforsøget. | Forskningskilde, ikke aktivt oddsfeed. De hentede filer har ikke tilstrækkeligt dokumenterede observationstidspunkter til at kaldes præcise FPL-deadlineodds. |

Kode: `scripts/collect_current_locked_inputs.py`, `scripts/collect_dashboard_news.py`, `scripts/collect_player_match_context.py`, `scripts/v1_1_download_fpl_core_role_data.py`, `scripts/collect_2024_25_historical_layer.py`. Filhashes findes i `repository-evidence.json`.

## Hvad modellen bruger er ikke det samme som hvad appen viser

B-provenancen i `scripts/build_current_b_inputs.py` skelner eksplicit mellem:

- **Belastning og seneste start: PL alene.** Det er en aktiv begrænsning, selv om råarkivet indeholder midtugekampe.
- **Detaljerede taktiske roller: verificerede starter på tværs af turneringer.** Rollen udledes af eksisterende klassifikation. Formationsgeometri er ikke det samme som observerede gennemsnitspositioner; navnlig historisk 2024/25 har denne begrænsning.
- **Strukturerede trænerudtalelser: ikke implementeret generelt.** Afgrænset officiel målmandsevidens er ikke et generelt interviewfeed.

Spillerkortets midtugekontekst er et særskilt datasæt og beviser ikke, at alle disse statistikker påvirker P(start), xM eller xP. Det tidligere all-competition-belastningsforsøg er et inaktivt forsøg, ikke en skjult aktivering. Se den eksisterende `competition-context-20261025/README.md`.

Vi har allerede xG, xA, skud- og enkelte shotmap-data. En ny leverandør af de samme tal er derfor ikke automatisk en ny informationskilde. Konkrete resterende huller omfatter komplette spiller- og trupobservationer på tværs af turneringer, sikre publiceringstidspunkter, historiske revisionsversioner, fremtidige ændringer i kampprogrammet, nogle rå BPS-/defensive komponenter samt struktureret fraværs-/trænerevidens. Det eksisterende workload-arkiv erklærer selv ufuldstændig dækning og manglende FA Cup i den pågældende historiske kilde; det er ikke en påstand om at den aktuelle indsamling aldrig søger FA Cup.

## Opta: konkret adgangsstatus

Jeg fandt ingen direkte Stats Perform/Opta-feedintegration i den gennemgåede indsamlingskode og ingen dokumenteret licens/adgang i det gennemgåede materiale. Det udelukker ikke, at ejeren har en ekstern aftale, som ikke er registreret her. Opta/FPL-ID'er i vores mapping er **identitetsnøgler, ikke API-adgang**. FotMob-endpoints og Opta-relaterede feltnavne dokumenterer heller ikke vores ret til Optas underliggende feed eller leverandøren bag hver statistik.

Stats Performs egne sider beskriver Opta-feeds til realtids- og historiske data og en salgs-/ekspertkontakt. Den gennemgåede side giver ikke en offentlig selvbetjeningspris, vi kan anvende som konkret tilbud. En relevant forespørgsel skal specificere PL + relevante europæiske og engelske cupturneringer, spilleropstillinger/udskiftninger, eventdata/xG/xA, skader/trupper, historik, publiceringstidspunkter og tilladt brug til modeltræning og appvisning. Ingen henvendelse er sendt.

## Andre realistiske muligheder

| Mulighed | Potentiel værdi for os | Adgang og begrænsning |
|---|---|---|
| **Sportmonks Football API** | Samlet kalender, opstillinger, events, minutter, trupper, skader/suspensioner; mulige xG- og forventet-opstilling-tilvalg. Relevant til at afløse skrøbelig indsamling og kontrollere tværturneringsdækning. | Officiel side annoncerer Starter fra **€29/md. ved månedlig betaling**, fem valgte ligaer. xG/Expected Lineups og visse historiske data er tilvalg. PL plus europæiske turneringer, kvalifikation og cups kan overstige fem turneringer. Pris og feltdækning skal verificeres for netop den pakke. |
| **API-Football (API-Sports)** | Bred kalender-/event-/opstillings-/skadesdækning; mulig supplerende leverandør til minutter og tilgængelighed. | Side annoncerer gratis **100 kald/dag** med begrænsede sæsoner og Pro fra **$19/md.** Dækning af statistik/lineups varierer pr. turnering/sæson. Vi har ikke verificeret komplet spiller-xG/xA eller historiske fraværsversioner. |
| **Stats Perform / Opta** | Direkte strukturerede event- og historiske data; mulighed for en mere konsistent kildekæde. | Kommerciel kontakt/aftale. Præcis turnerings-, felt-, historik- og anvendelsesret skal fastlægges. Ingen dokumenteret direkte adgang i appen. |
| **Hudl Statsbomb / Wyscout Data** | Rigere event-/positions- og analysegrundlag, afhængigt af produkt og aftale. Relevant hvis vi vil bygge modeller med reel shot-/chancekontekst. | Kommercielle produkter. Et Wyscout-videoabonnement må ikke antages at indeholde en data-API. StatsBomb Open Data er en anden, begrænset mulighed: den kontrollerede åbne konkurrencefil har PL **2003/04 og 2015/16**, ikke et aktuelt PL-feed. |
| **The Odds API** | Tidsstemplet ekstern målestok for holdmål, kampudfald og udvalgte spillermarkeder, hvor bookmakere tilbyder dem. | Historiske snapshots er betalte; dokumentationen beskriver femminutters intervaller fra september 2022, og ekstra markeder fra maj 2023. Det garanterer ikke en bestemt spillers marked/dækning. Odds skal korrigeres for margin og afstemmes med FPL-deadline. |
| **Understat** | Ekstra skud-/xG-kilde til krydskontrol og analyse af chancekvalitet. | Webstedet er tilgængeligt, og materiale er allerede gemt historisk via Vaastav. Der er ikke etableret en understøttet API/licens i projektet. Ikke en samlet løsning på skader, trupvalg og alle turneringer. xG-definitioner må ikke blandes ukritisk mellem leverandører. |
| **football-data.org** | Enkel API til kalender/resultater og en uafhængig kontrol af kampoversigter. Den offentlige dækning omfatter bl.a. PL og CL. | Gratis grunddækning med betalte udvidelser; erstatter ikke detaljerede spiller-xG/xA, trup- og skadeshistorikker. **Et andet produkt end Football-Data.co.uk.** |
| **Officielle klub-, PL- og UEFA-kilder** | Stærkeste kilde til konkrete udlån, trupberettigelse, kampprogram og offentligt bekræftede fravær. | Nyheder og pressekonferencer er uensartede. Citater skal tidsstemples og skelne fakta fra fortolkning; ros er ikke en startgaranti. |

Alle priser er sidernes annoncerede udgangspriser observeret 25. oktober 2026, ikke et indhentet tilbud eller en samlet pris på vores nødvendige dækning. Offentlig adgang til et websted er ikke i sig selv en aftale om systematisk indsamling, lagring, modeltræning eller videredistribution. Dette er konkrete valgkriterier, ikke en påstand om en allerede udført juridisk vurdering.

## Min anbefaling

1. **Behold FPL som facit for FPL-priser, regler og officielle point.** Ingen generisk statistikleverandør skal erstatte FPL-assist-/bonusdefinitioner.
2. **Prioritér komplet og stabil kalender-, opstillings-, minut- og fraværsdækning.** Sammenlign Sportmonks og API-Football på identiske konkrete kampe med PL, midtuge, cups, transfers og skader. Det er en mere målrettet første undersøgelse end at købe endnu et xG-tal.
3. Kræv i den sammenligning eksplicitte klub-/spiller-ID'er, faktisk nul versus manglende minutter, starter/ind- og udskiftningstidspunkter, kampslutstatus, ekstra tid, ændringer i kampprogram og tidsstempler. Gem både kampens tidspunkt og vores modtagelsestid; en nuværende skadepost rekonstruerer ikke, hvad man vidste sidste uge.
4. **Opta/Hudl er et muligt næste niveau**, hvis en overkommelig standard-API ikke kan udfylde de dokumenterede huller. Bed om prøveudtræk og specifik dækningsoversigt før køb, ikke blot en generel salgsliste.
5. **Tidsstemplede odds er en separat kandidat til validering.** Vi har allerede lavet et markedsforsøg med gratis historiske filer; et bedre feed ville især tilføje bedre deadline-vintage, ikke dokumentere en modelgevinst på forhånd.

Et rigtigt leverandørforsøg kræver en tilgængelig API-nøgle/autoriseret konto og eventuel betalingsbeslutning. Denne gennemgang omfatter kun offentligt dokumenteret adgang og vores eksisterende filer. Ingen nøgle er efterspurgt eller eksponeret, og ingen konto eller betaling er oprettet.

## Kontrollerede primære kilder

- FPL-endpoints: https://fantasy.premierleague.com/api/bootstrap-static/ og https://fantasy.premierleague.com/api/fixtures/ (eksisterende indsamlingskode og kvitteringer).
- Community-arkiver: https://github.com/olbauday/FPL-Core-Insights · https://github.com/vaastav/Fantasy-Premier-League · https://github.com/Randdalf/fplcache (repoets pinnede historiske indsamling).
- https://www.statsperform.com/products/opta-data/ · https://www.statsperform.com/products/opta-data-feeds/
- https://www.sportmonks.com/football-api/ · https://www.sportmonks.com/football-api/plans-pricing/
- https://www.api-football.com/ · https://www.api-football.com/coverage
- https://github.com/statsbomb/open-data · https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json
- https://www.hudl.com/products/wyscout
- https://the-odds-api.com/historical-odds-data/
- https://football-data.co.uk/data.php · https://www.football-data.org/coverage
- https://understat.com/ · https://www.fotmob.com/aboutUs/company

`external-source-receipts.json` indeholder URL, faktisk hentet URL, HTTP-status, UTC-hentetid og SHA-256 for de 14 kontrollerede eksterne dokumenter. Alle gav HTTP 200. Det er dokumentationskontrol, ikke succesfulde API-integrationsprøver. `repository-evidence.json` binder de centrale interne konklusioner til gennemgåede kildefiler. Ingen beregningskode er ændret, så modeltests/deploy er ikke genkørt for denne dokumentationsleverance.
