# Beslutningsrapport — opfølgning på PR #41

22. november 2026. Separat branch, baseret på `d28bfe3c`. **Ingen ændring af MM B, PM vFinal, TS v3, substitutionsforsøget eller den publicerede app.** Ingen ny modeloptimering eller kampsimulation.

## 1. PR #41: væsentlig rettelse, men samme præcisionstal

**Fundet og reproduceret:** `changed_model_code_between_gws` blev bygget fra et uordnet set. To kørsler med forskellige `PYTHONHASHSEED` gav forskellige JSON-/resultathashes, selv om de parsede resultater var identiske. Det er en reel fejl i den lovede byte-reproducerbarhed. Rettet med stabil nøglerækkefølge og canonical JSON. Runneren kontrollerer nu også resultathashes efter genberegning; tidligere kontrollerede den kun inputhashes.

De oprindelige point-/minutmetrics og sammenligningen med FPL `ep_next` er uændrede. Der er ikke påvist en væsentlig numerisk fejl i disse scores. Derimod er der klare evalueringsgrænser: tre allerede sete GW, skiftende modelversioner, post-outcome oracles og ufuldstændig TS-horisont. De er ikke nye holdouts eller dokumentation for en deployerbar komponentrettelse. En lokalt korrekt hashkæde er heller ikke uafhængig tidsattestation.

## 2. Substitutionsforsøget: fuldstændigt bevaret

Fit- og kernelhash er kontrolleret mod den eksisterende præregistrering og matcher præcist. Ingen ændring af model, fit, protokol, mindste stikprøve, sourcehook eller drift.

Senest hentede ledgerkvittering er fra **21. november kl. 17.22 dansk tid**: **0/8 afsluttede nye GW og 0/80 afsluttede kampe**. GW11 er optaget tidligere før deadline, men afventer endelige resultater. Der mangler GW11's afslutning samt mindst syv yderligere nye, gyldigt optagne og afsluttede runder. Tidligst GW11–18, hvis alle otte er gyldige og omfatter mindst 80 kampe; ellers senere. GW12–18 er ikke erklæret optaget på forhånd. De gamle 20 testkampe tæller ikke med. En efter-deadline capture blev korrekt sprunget over; det ændrer ikke den tidligere gyldige GW11-optagelse.

## 3. PM: årsager skilt ad med eksisterende data

Data er de oprindelige 2.007 GW8–10-forecasts og officielle resultater fra PR #41; her tilføjes en ny fejl-dekomponering, ikke en gentaget overordnet audit.

| Led | Nyt fund | Mest sandsynlig forklaring / grænse |
| --- | --- | --- |
| Holdenes målproduktion | 86,63 forventede krediterede mål, 83,70 observeret skud-xG, 65 mål | 18,70 af forecast-minus-mål-gabet på 21,63 ligger mellem observeret xG og realiserede mål. Det taler imod at behandle hele gabet som for høje holdstyrker. Efterkampens xG er kun diagnose, ikke en ny prædeadline-feature. |
| Spillerfordeling | Selv med faktisk holdvolumen er mål-MSE 0,02481 mod 0,02947 oprindeligt; assist-MSE 0,02609 mod 0,02850 | Meget individuel usikkerhed er tilbage, inklusive hvem der realiserer en chance, rolle og minutter. Restleddet beviser ikke dårlige fordelingsvægte. Tidligere afviste generelle share-/stjernenedskaleringer genoptages ikke. |
| Assistproduktion versus fordeling | Af nettobias +22,46 assists kan +19,83 henføres algebraisk til holdenes målvolumen ved den frosne assist/mål-rate; +2,63 er restleddet i total assist-rate | Størstedelen af den samlede assistbias kan følge samme målvolumenafvigelse. Ikke bevis for at ændre individuelle assistvægte. Egenmål/FPL-assistdefinition begrænser en bogstavelig ratefortolkning. Fordelingsleddet summerer til nul, men kan stadig give stor individuel fejl. |
| Clean sheets | CS-pointfejl −127,75 = +5,55 fra 60+-kvalifikation og −133,30 fra CS givet kvalifikation | Underskuddet forklares ikke af for få forventede kvalifikationsminutter. Ud fra fælles keeperminutter kan hold-CS afgrænses på 57/60 holdrækker: forventet 23,57–24,24 %, faktisk 31,58 %. Det er identifikationsgrænser, ikke konfidensintervaller; 400 Monte Carlo-træk og den lille stikprøve giver yderligere usikkerhed. Ingen Poisson-antagelse indføres. Tre rækker har utilstrækkelig keeper-konservation og udelades fra dette mål. |
| BPS/bonus | Kun bonusmiddel og komponenter er arkiveret, ikke fuld per-draw baggrunds-BPS. CBI-regelændringen alene giver −285 BPS til forsvarere på de faktiske tællere | At skifte CBI-enhed blindt kan sænke DEF-bonus yderligere. GK-save-subtyper og manglende DC/BPS-kobling er plausible forklaringer, men deres individuelle effekt kan ikke identificeres af bonusmiddel alene. Regelscoringen er allerede korrekt. |

Dekomponeringerne er præcise aritmetiske identiteter med krydsled bevaret — ikke kausale interventioner eller lovede gevinster. Clean-sheet-signal og målrealisering kan hænge sammen. Der er ikke fundet en ny “gratis” korrektionsfaktor.

## 4. Det konkrete næste arbejde

Omkostninger nedenfor er planlægningsestimater, ikke køb eller en bestilling af produktionsintegration.

| Forsøg / handling | Data og status | Forventet omkostning | Målbart succeskriterium |
| --- | --- | --- | --- |
| A. Eksisterende fælles substitutionsforsøg | Kører allerede; uændret | Eksisterende daglig kørsel; ingen ekstra simulation her | Præcis den eksisterende 8-GW/80-kamp-gate med CRPS, MSE- og subgroup-safeguards. |
| B. Privat TS-datagrundlag | Logger implementeret, privat tomt ledger initialiseret; ingen rigtige managerdata kopieret | Sekunder og omtrent et komprimeret forecast pr. beslutning; lille lokal lagringsomkostning. Automatisk hook kræver særskilt integration | Første nye datapunkt før deadline med fuld horisont, hashmatchet managerstate/plan, FT/bank/nomination/chips og hold-kontrol. 100 % dækning af disse felter; 0 private data i Git/CI. Afviste og manglende runder tæller ikke som resultater. |
| C. Kontrolleret PM-hypotese om assist-rate/goal-volume | De eksisterende to-sæsons input og budget-ablationer er tilgængelige. Definition og forsøgsdesign kan starte nu; ny forecastgevinst er ikke dokumenteret | Ca. 0,5–1 dag til target-/definitionstest og protocol; simulation først hvis en konkret uløst ablation kræver det | Samme holdmål/minutproces, kun assist-eligibility/rate ændres. Fast kronologisk train/dev, derefter ny prospective periode; lavere point-CRPS og ikke forværret point-MSE/positionsbias. Ingen tuning på GW8–10. |
| D. BPS-identifikation før ny kandidat | Eksisterende keeper-inside/xGOT og handlingsledger; per-draw baggrunds-BPS mangler i de offentlige snapshots | Ca. 1–2 dage til schema/target-kontrol; derefter en afgrænset privat forskningscapture, ikke fuld ny sæsonsimulation | Samme eventtræk/rolle/minutter kan rekonstrueres; eksplicitte bidrag afstemmer uden dobbeltregning. Først derefter et separat kandidatforsøg mod den aktive BPS-lov med total-point-CRPS og bonuskalibrering. |
| E. Kommerciel ekstern xP-sammenligning | Konkret protokol klar; ingen verificeret tilladt matched eksport fra FPL Review/LazyFPL | Ingen indkøb foretaget. Afhænger af eksportret/licens; minimal løbende scoreberegning efter adgang | Første optagelse ved deadline−60 min efter rettighedsgates. Første review efter 12 nye GW/120 kampe, parret GW-bootstrap og primært point-MSE. Ingen kommerciel score opfindes før data findes. |

**Kan starte nu:** uændret observationsindsamling i A; privat TS-capture i B så snart et nyt før-deadline-TS-output og en reel managerintention foreligger; mål-/assist-definitionstests i C og BPS-target-/schemaarbejde i D. **Kan ikke hævdes startet:** en automatisk produktionshook, en ægte GW11-efterregistrering, et nyt BPS-kandidatresultat eller et kommercielt benchmark uden datarettigheder.

Loggeren er en separat lokal sidecar, ikke en ændring af appen. Den eksisterende TS-bridge gemmer hold-kontrolscores for hele horisonten, men ikke alle seks kontrol-XI'er. Kildescenarierne bevares til korrekt senere reproduktion; manglende nomineringer erklæres ikke som observerede. Tidsbevis er foreløbig lokal systemklokke, ikke uafhængig notarisation. Se [privat logning](PRIVATE_TS_LOGGING.md).

Eksterne data starter kun ved dokumenteret eksport-/opbevarings-/analyse- og publikationsret. Et abonnement eller offentlig læseadgang er ikke en scrapinglicens. Se den konkrete [eksterne protokol](EXTERNAL_XP_PROTOCOL.md). Ingen kontakter, køb eller integrationer er udført.
