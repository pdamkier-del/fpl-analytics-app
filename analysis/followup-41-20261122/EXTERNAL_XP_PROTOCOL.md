# Fremadrettet ekstern xP-sammenligning — protokol v1

Status: design klar; kommercielle dataadgangsgates ikke bestået. Ingen scraper, abonnementskøb, automatisk kontakt eller providerintegration er oprettet. PR #41's eksterne kilderegister og vilkår genbruges; rettigheder kontrolleres igen, før indsamling begynder.

## Adgang før første forecast

For hver provider kræves en konkret adgangskvittering: produkt/modelversion, tilladt eksportvej, vilkårs-/aftalereference, dato, tilladelse til automatisering hvis relevant, tilladelse til lokal opbevaring og beregning af afledte scores samt særskilt adgang til at publicere resultater. Et abonnement eller en offentlig side er ikke automatisk tilladelse til scraping eller videredistribution. Hvis rådata ikke må deles, opbevares de privat og PR'en indeholder kun tilladte aggregater og en metodebeskrivelse. Hvis aggregater heller ikke må publiceres, starter et offentligt benchmark ikke.

FPL Review: kun autoriseret eksport/API med bekræftet brugsret. LazyFPL: kun hvis der faktisk findes ubetinget numerisk spiller-xP med stabile ID'er og en tilladt eksport-/licensaftale. Et newsletter-tip, et oddsdiagram eller en kaptajnanbefaling må ikke omdøbes til spiller-xP. Den senest gennemgåede LazyFPL-termside begrænser automatisk udtræk; ingen sådan indsamling startes. Mangler et egnet LazyFPL-produkt, udelades den provider. Der kontaktes ingen på brugerens vegne i denne opgave.

Officiel `ep_next` fortsætter som særskilt simpel reference, når et originalt før-deadline-katalog er tilgængeligt. Det er ikke en stedfortrædende score for FPL Review/LazyFPL.

## Vindue og indefrysning

Første gyldige runde er tidligst GW12, og kun hvis alle gates er bestået før dens cutoff. T = officiel FPL-deadline minus 60 minutter. Frys hver service og vores seneste gyldige, højst 24 timer gamle prognose, som er tilgængelig ved T. Ingen prognose udgivet efter T accepteres; erhvervelse/arkivering skal være afsluttet senest T. Brug ikke senere reviderede CSV'er som erstatning for et manglende snapshot.

Registrér for hver fil: sæson, origin-GW, provider/model, feltdefinition, player-code/fixture-mapping, filhash, provider-publiceringstid når tilgængelig, eget observationstidspunkt og kilde-/rettighedsreference. Hvis providerens egentlige information-cutoff er ukendt, rapporteres det som ukendt. Sammenligningen gælder systemerne, som de var tilgængelige ved T, inklusive deres opdateringsfrekvens; den isolerer ikke matematikkens værdi på identiske informationer. Kilder med væsentligt forskellig alder vises også særskilt.

En lokal systemklokke er ikke en uafhængig tidsattest. Før benchmark kaldes uafhængigt prospective, skal eksporten have providerkvittering eller en på forhånd aftalt betroet tidsattest af en saltet filforpligtelse. Der lægges ikke managerdata eller rå kommercielle prognoser i offentlige tidsstempler. Denne protokol opretter ikke selv en ekstern timestamp-tjeneste.

## Targets og population

Primært: ubetinget forventet FPL-point for origin-GW. Ingen sammenblanding med xP betinget på spilletid, pr.-90-rater eller summer over seks GW. DGW aggregeres over de faktiske fixtures i den frosne GW; senere kampprogramændringer logges og håndteres efter en fast regel, ikke cherry-picking.

Primær population: samme frosne spillerkatalog; mindst 95 % fælles ID-dækning kræves, ellers rapporteres runden som mangelfuld og tæller ikke som fuld evalueringsrunde. Ingen navnebaseret fuzzy joining. Alle fælles rækker indgår, også DNP; manglende forecast er ikke nul. Vis særskilt prædefineret active-gruppe med vores frosne P(start) ≥0,20, positioner og rotation/regular. Dette er vores populationsdefinition og rapporteres som sådan, ikke som provider-neutral udvælgelse.

## Scoring og stopregel

Første review efter 12 nye afsluttede runder og mindst 120 kampe, ikke efter den første gode uge. Primært mål: parret forskel i mean squared point error. Sekundært MAE, bias, kalibrering af forventet xP i faste bins og aktiv-/positionsgrupper. RMSE rapporteres som kvadratrod af samlet MSE. Whole-GW parret bootstrap med 10.000 træk; kampblokke kun som følsomhed. Ingen formel signifikanspåstand med få GW. Ingen løbende hyperparametervalg på scoreperioden.

Højst to prævalgte kommercielle comparators. Ingen erklæring om bedre model, medmindre det primære 95 %-interval for forskellen ligger under nul; reportér begge sammenligninger og korrektion for multiple primære tests. CRPS, haul-Brier og intervaller sammenlignes kun hvis begge providers leverer sammenlignelige fordelinger/sandsynligheder; ellers er de Not Available. Individuelle undergrupper er diagnose, ikke yderligere vindende primære tests.

Kun officielle final/data_checked-GW-outcomes scores. Tidligere GW8–10 tæller ikke med. Vintages, mapping og eksklusionsårsager låses før resultater. Ingen manager-ID, trup, bank, FT eller beslutning sendes til de eksterne tjenester for dette spillerbenchmark.

## Gate der gør forsøget startbart

1. Tilladt numerisk eksport og opbevaring dokumenteret.
2. Ét parse-/mappingtest-snapshot med kendte field-definitioner, ingen betaling eller rettighedsgæt.
3. Første forecast frosset før T med gyldig tidskvittering.
4. Først herefter registreres runden som prospective. Hvis en gate mangler ved GW12, starter forsøget i en senere runde; der backfilles ikke.
