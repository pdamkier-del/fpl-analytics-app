# D. Data Gap Report

Det afgørende skel er mellem et felt, vi kan hente i dag, et felt i en original prædeadline-kilde og et felt, der faktisk indgår i produktionskæden. Dette er en feltaudit, ikke en juridisk erklæring om ubegrænset brug af offentlige sportsdata.

| Felt / signal | Eksisterende dækning | Faktisk brug i pinned kæde | Mangler / rettigheder / næste kontrol |
| --- | --- | --- | --- |
| Officielle minutter, starts, points, xG/xA og status | GW8–10 arkiver + længere historiske observationer | Rolle/minutter og mål-/assistpriors | Efterkampens xG/xA er outcomes, ikke gamle features. API-adgang giver ikke generel videredistributionslicens. |
| Holdmål / styrke / modstander | Eksisterende model og historiske xG-fits | Anvendes allerede; “tilføj xG” er ikke nyt | Eksakt team-goal PMF/CS-law mangler i de valgte gamle publiceringspakker; detaljerede mean-event-kvitteringer her først GW10. |
| XI og rolleblandinger | Arkiverede MM-/lineup-rækker, exact-11 | Fælles rolle/XI, workload og historik | Forventet XI fra en ekstra provider skal have versions-/cutoffbevis og må ikke være officiel start-XI udgivet efter FPL-deadline. |
| Cup-/Europa-minutter og kampkalender | Betydelig historisk recovery + workload-modul | Anvendes allerede i låst MM | Fuld dækning og oprindelig tilgængelighed for fremtidige kampe/udsættelser er ikke certificeret. Ukendt er ikke nul. |
| Skade/tvivl og trænernyheder | Arkiveret officiel status samt tekstevidenspiloter | Availability/caps; tekstvisning er ikke automatisk numerisk feature | Skadetype, comeback-dato, citatets publiceringstid/ændringer og entity-mapping mangler systematisk. Ingen bagudrettet slutning fra senere comeback. |
| Præcise substitutionshændelser | Rapporterede FPL-minutter | Bruges som proxy i forskningskandidaten | Faktiske sekunder, tillægstid, ud/ind-par, årsag, skade og kampstatus ved beslutningen mangler. FPL90 er ikke fysisk slutfløjt. |
| Defensive handlinger og BPS | CBI, tackles, recoveries og legacy baggrundsledger | Separat NB-DC + normal BPS-baggrund | Fælles inden-kamp-variation mangler; gamle CBI/dispossessed-proxyen transporteres over regelændring. Kræver ny targetkalibrering, ikke blind addition. |
| Redninger inde i feltet | Allerede gemte rådata: 70 PL-kampe, 141 mappede keeperrækker, alle inside-counts matcher shotmap | Almindelige redningssubtyper er ikke eksplicit input til B-event-BPS | 133 rækker består også total-shot-reconciliation; otte save-afvigelser holdes ude af strengt valideret feature. Providerrettigheder skal afklares før distribution/integration. |
| Ægte xGOT imod / goals prevented | 135 eksplicitte xGOT-rækker, 133 matcher skudsum inden 0,03 | Ikke i den gamle BPS-detaljefeatureliste | To uafklarede definitions-/afrundingsafvigelser. Manglende felter sættes ikke til nul. |
| Big-chance-save-flag | Intet eksplicit felt i den undersøgte rådata | BPS-feltet for ordinære big-chance saves forbliver uden separat generation | Må ikke konstrueres fra en vilkårlig xGOT-tærskel. Søg verificeret eventdefinition/licens. |
| Straffespark / taker / conversion | Eksplicit separat model og audited exposure-recovery | Delt forekomst/taker/keeper-hændelse | Begrænset sjælden-hændelsesdækning; almindeligt goal-count kan ikke bruges som sikkert penalty-label. |
| Marked / bookmakerodds | Tidligere simple markedsstudier; ingen ny tilladt matched fil her | Ingen ny oddsfeature aktiveret af auditten | Original quote-tid, markedsdefinition, overround og brugsret kræves. |
| Eksterne spiller-xP | Officiel ep_next verificeret i alle 2.007 rækker | Kun comparator i denne audit | LazyFPL/FPL Review matched archives ikke verificeret; FPL Form-filer må ikke videredistribueres efter deres vilkår. |
| Managerstate og TS-anbefaling | Lokal før-deadline-arkivering og nogle historiske replaylogs | Live TS kræver lovlig trup, bank, FT, salgspriser og chips | Ingen privat historik indsamlet i auditten. Manglende historiske planer er ikke et 0-resultat og kan ikke erstattes med hindsight. |
| Seks-GW TS-vintages | Historisk audit: 33 af 183 nødvendige origin/target-par | Live planlægger kræver fuld horisont | Mangler 150 par i det gamle certificeringsgrundlag; fulde vintages skal bevares fremadrettet. |

## Anvendte features: konkret wiring

Pinned `scripts/run_live_vfinal_bps.py` kalder `feature_frame` og den frosne regression. Baggrundsfamilien `role_recent_detail` bruger positionsindikatorer, rolleakser, historisk baggrund/eksponering og `hist_cross`, `hist_cbi`, `hist_recovery`, `hist_tackle`, `hist_keypass`, `hist_dribble`, `hist_foulwon`, `hist_sot`, `hist_passbps`, `hist_negative`.

`build_verified_live_penalty_bps.py` genbruger `actual_background_ledger`; dens eksplicitte `bg2025_proxy` har CBI//2 og negativ dispossessed-proxy. `bps_2026_27` har CBI//3 og ingen being-tackled-penalty. Det er en mål-/featuresemantisk transportbegrænsning, ikke bevis for at en umiddelbar numerisk rettelse forbedrer forecasts. `b_event_simulator.py` sætter inside-box saves til penalty-saves, men genererer ikke ordinære redningers inside-/big-chance-subtyper eksplicit; DC trækkes separat fra BPS-baggrunden.

Byte-bevarede kildefiler og SHA'er fra den pinned commit findes i `../evidence/active-source/` og `../active-source-files.json`. Kildetilgængelighed alene beviser ikke featurebrug; UI-tekstvisning er heller ikke en lært modelvariabel.

## Datagovernance for næste forsøg

Hvert nyt felt skal have spiller-/fixturekode, eventtid, oprindelig publiceringstid, indsamlingstid, kildeversionshash, enhed/definition og særskilt missingness. Målvariabler fra kampen holdes adskilt fra prædeadline-features. Gem kun data, der må opbevares og deles under kildens vilkår; genbrug af kode under MIT overfører ikke automatisk rettigheder til tredjepartsdata. Denne PR føjer ikke nye kommercielle datasæt eller provideradgang til produktionen.
