# C. External Benchmark Report

Kilder kontrolleret 22. november 2026. Der trækkes ikke nye kommercielle prognoser ind i appen. Offentlige produktbeskrivelser er ikke uafhængige præstationsbeviser. Ingen ekstern artikel lægges ind som input til gamle forecasts.

## En faktisk matchet ekstern baseline: officiel FPL ep_next

Den oprindelige spillerkatalogkopi gemmer `ep_next`. For hver GW8–10 kontrolleres katalogets `next_gw`, eventets `is_next`, spiller-ID, kildetid før modelcutoff og deadline. Dette er derfor den officielle prognose fra samme gemte kildepakke, ikke nutidens opdaterede værdi. Kommercielle værktøjer kan have brugt senere nyheder; der sammenlignes ikke med deres sidste opdatering.

| Gruppe | N | Vores MAE | FPL MAE | Vores RMSE | FPL RMSE |
| --- | --- | --- | --- | --- | --- |
| all | 2007 | 1.038 | 1.142 | 1.920 | 2.195 |
| active | 855 | 2.119 | 2.357 | 2.827 | 3.241 |
| rotation | 518 | 1.878 | 2.057 | 2.605 | 2.960 |
| regular | 337 | 2.491 | 2.817 | 3.137 | 3.631 |
| GW8 | 668 | 1.082 | 1.297 | 2.012 | 2.468 |
| GW9 | 669 | 0.983 | 1.014 | 1.777 | 1.929 |
| GW10 | 670 | 1.051 | 1.116 | 1.963 | 2.157 |

For alle rækker er forskellen i MAE −0,1039 point; eksplorativt matchet kamp-bootstrap-interval [−0,1747; −0,0448]. Relativt ca. 9,1 % lavere MAE og 12,6 % lavere RMSE. Den aktive gruppe er også bedre. Der foreligger ikke eksterne pointfordelinger, så ingen ekstern CRPS-/haul-sandsynlighedsscore opfindes. Tre runder og versionsændringer begrænser generalisering.

## LazyFPL

De offentlige [produktbeskrivelser](https://www.lazyfpl.com/) viser nyheder, skader, kaptajnanbefalinger samt holdmål/clean-sheet-odds. [Arkivet](https://www.lazyfpl.com/archive) indekserer daterede gratis udgaver for GW9 (30. oktober), GW10 (5. november) og GW11 (20. november), sammen med medlemsindhold. Disse kan understøtte en kvalitativ informationsaudit. Kalenderdato er ikke i sig selv et verificeret timepræcist cutoff eller en uforanderlig version.

Vi har ikke verificeret et offentligt, maskinlæsbart spiller-xP-arkiv med stabile ID'er, fuld dækning, vintages og genbrugsrettigheder. Der udføres derfor ingen numerisk LazyFPL-vs-vores-model-rangering. Logoer i afsnittet “Read by ...” er ikke dokumentation for en dataleverandør. LazyFPLs eksakte odds-/modelleverandør og fulde metode er ikke fastslået her.

[Brugsvilkårene](https://www.lazyfpl.com/terms), opdateret 24. juli 2026, begrænser automatisk udtræk og videredistribution. Auditten gemmer alene kildehenvisninger og vores vurdering; ingen newsletter-korpus, premiumindhold eller automatiseret dataindsamling er etableret. Et eventuelt fremtidigt datagrundlag kræver aftalt adgang og verificeret prædeadline-version.

## Andre kilder

| Kilde | Dokumenteret produkt/metode | Historisk sammenlignelighed og genbrug |
| --- | --- | --- |
| [FPL Review Massive Data](https://docs.fplreview.com/the-model/projections/massive-data-model/) | Historiske præstationer, marked, taktik, roller og nyheder; op til 14 GW; beskriver hyppige opdateringer | Ingen matchet tilladt prognosefil fremskaffet her. Egne kvalitetsudsagn er ikke vores benchmarkresultater. |
| [FPL Review Free Model](https://docs.fplreview.com/the-model/projections/free-model/) | Enklere model og kortere horisont | Aktuel visning er ikke en gammel prognose. Samme-cutoff-eksport mangler. |
| [FPL Form eksport](https://fplform.com/export-fpl-form-data) | Spiller-xP med separat appearance-probability; eksport til personlig analyse | Tillader personlig eksport; forbyder deling af datafiler og kræver kildeangivelse for afledt analyse. Ingen datafiler indlemmet. “If appears”-point må ikke sammenlignes med ubetinget xP. |
| [OpenFPL](https://github.com/daniegr/OpenFPL) | Offentlig modelkode, FPL-/Understat-input og et rapporteret kommercielt head-to-head-studie | Kode er MIT ifølge repoet; inputdatasæt skal vurderes separat. De publicerede andre-sæson-resultater kan ikke rangordnes mod vores GW8–10. |
| Bookmakerodds | Kan tilbyde uafhængige team-/mål- og CS-estimater | Marked, tidsstempel, linje, bookmaker, overround og brugsret skal gemmes. Historiske slutodds er ikke et gyldigt tidligere cutoff. |
| Forventede XI og nyheder | Muligt nyt signal om start/tilgængelighed | Kræver original publiceringstid, redigeringshistorik, spillerkode og særskilt evaluering ud over eksisterende status/rollemodel. |

## Protokol for en senere reel kommerciel benchmark

Match sæson, spillerkode, fixture og GW; adskil ubetinget xP fra xP givet spilletid. Sammenlign enten samme cutoff eller angiv præcist den tilladte tidsforskel. Frys kilder før deadline og gem provider-version/indsamlingstid. Brug fælles spillerdækning, både alle og prædefinerede aktive grupper, point-MSE/MAE, passende probabilistiske scores hvor fordelinger findes og parrede GW-/kampblokintervaller. Ingen efterfølgende rang-/kaptajnanbefaling omdannes til opdigtet xP. Hvis historiske versioner mangler, start et nyt tilladt fremadrettet benchmark; genberegn ikke historikken med dagens inputs.
