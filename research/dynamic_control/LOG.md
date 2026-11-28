# Forskningslog

## 28. november 2026

- Læste den frosne TS-konfiguration og kandidatgeneratoren. Sammenholdt med PR #48, #50 og #57, så det kendte funding-problem og tidligere real-pool-resultater bliver adskilt fra de nye dynamiske cases.
- Afgrænsede fuldsæsonforsøget til den arkiverede 2025/26 Phase5Q-proxy. De offentlige originale 2026/27-udgivelser havde tags for GW12 og GW13 på inspektionstidspunktet. Flere revisioner fra samme deadline tilfører ikke flere uafhængige runder eller et længere originalt udsyn.
- Startede fire chipfri armløb med samme arkiv, budget, starttrup og squad/lineup-funktioner. Anvendte forrige GW's indsamlede metadata fra og med GW3 for at undgå samme-GW ændringer i det eksterne prisinput. GW1-puljen er fælles eksperimentseed. Det oprindelige forecast-input har selv kendte kalender- og metadataafvigelser.
- Udformede seks håndberegnede cases om roll, funding, korttidskøb, ny information og finansielle tærskler. Kontrollerede eksakt optimum, de første handlinger, salg efter prisstigning og forskellen mellem én modal bane og et observeret scenariechok. Valgte 512 UCT-simulationer med 12 seeds som lille, fast beregningsramme. De konstruerede cases er demonstrationscases.
- Den første historiske driver skrev start-FT som en konstant på 1 i metadata. Den frosne `initial_squad` startede faktisk alle beslutningsforløb ved 0. Korrigerede receipt til den faktiske startværdi og verificerede, at GW1-ledgeren også bruger 0. Ændrede ikke valg eller point.
- Beslutninger bruger kun prognose- og metadatafelter fra historiske inddata. Resultatfelterne anvendes i en separat evalueringsfase. Den eksterne arkivlæser dekomprimerer hele metadata/resultatfilen, hvorfra beslutningsdriveren straks udvælger metadatafelterne.
