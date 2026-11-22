# A. Model Performance Report

Auditdato: 22. november 2026. Beslutning: behold alle modelparametre og appen uændrede. Audit-branchens base er `e515658e`; dette arbejde publicerer ikke appen.

## Hvad kan faktisk dokumenteres?

De tre afsluttede, oprindeligt publicerede B-prognoser for GW8–10 omfatter 2.007 spiller/GW-rækker og 30 kampe. GW11 er `pending_results` i den hentede sæsonrapport og scores ikke her. GW6–8-backtesten og de mange genbrugte 2024/25–2025/26-forsøg holdes adskilt fra de publicerede prognoser. GW8 indgår både i en senere backtest og i det oprindelige prognosearkiv; de er forskellige forecasts og må ikke tælles som to uafhængige observationer.

Auditten bekræfter filchecksums, spillerkoder, scoringens pointsum, scenariegennemsnit og `input cutoff ≤ publication < deadline`. Fremtidige horisontrækker bruges ikke til at score oprindelsesrunden. Prognoseversionerne ændrer sig mellem GW8, GW9 og GW10; dette er en audit af faktisk publiceret adfærd, ikke en ren holdout af dagens faste B-model. Tidligere undersøgelse af de samme outcomes gør nye undergruppehypoteser eksplorative.

## Låst model og faktisk aktiv kæde

Den hentede offentlige kædekvittering peger på matematikkilden `161b67b6fb8786a38e78c245b92a03ad841575d8`, model `B-MM-PM-TS-v1`, og UI-kilden `27bf5e1e1a17360bdbbfb41fbce7fe55679c6870`. Den arkiverede kontrakt angiver `locked_model_active=false`: den publicerede B-kæde er diagnostisk og må ikke beskrives som fuldt certificeret, selv om dens kode og fit er fastlåst under denne audit. Det gamle `model/active.json` er en legacy app-bridge og identificerer ikke den aktuelle B-matematik.

Historisk låst MM: rolle-/workload-logistik med exact-11, sekvensbaseret cameo-hoved, fast starter-duration og blandet cameo-duration. B-kæden tilføjer fælles rolle/XI-processer; nyere runder har en fysisk normal-kamp-tidslinje. PM benytter adskilte almindelige mål og straffespark, bevarer holdbudgetter, bruger særskilt DC-tælling, keeperlov og BPS-baggrund. TS bruger de fælles pointscenarier, lovlig XI, kaptajn/vice og autosubs.

Den aktuelle TS-konfiguration i kildekoden er seks vægte `(1, .60, .36, .216, .1296, .07776)`, paid-transfer-buffer 1 point, beam width 20 og højst fem transfers pr. søgetrin. Det er ikke de ældre `.85/.70/...`-vægte fra den første TS v3-proxy. Der tilpasses ingen nye vægte her.

## MM og PM: samme spillere og kampe

| Gruppe | N | Minut-MAE | Minut-RMSE | xP-MAE | xP-RMSE | CRPS |
| --- | --- | --- | --- | --- | --- | --- |
| all | 2007 | 11.409 | 20.765 | 1.038 | 1.920 | 0.684 |
| active | 855 | 20.436 | 28.250 | 2.119 | 2.827 | 1.406 |
| rotation | 518 | 26.416 | 31.753 | 1.878 | 2.605 | 1.255 |
| regular | 337 | 11.243 | 21.793 | 2.491 | 3.137 | 1.638 |
| GK | 221 | 2.375 | 7.804 | 0.662 | 1.544 | 0.441 |
| DEF | 652 | 12.345 | 22.942 | 1.194 | 2.079 | 0.785 |
| MID | 897 | 13.404 | 22.084 | 1.026 | 1.835 | 0.677 |
| FWD | 237 | 9.710 | 17.342 | 1.007 | 2.087 | 0.661 |

`active` betyder baseline P(start) ≥ 0,20; `rotation`: 0,20 ≤ P(start) < 0,90; `regular`: P(start) ≥ 0,90. De definitioner afhænger af prognosen, ikke kampens udfald. Alle registrerede spillere indgår i `all`; mange spiller ikke, så all-player-MAE er langt lavere end MAE blandt relevante startere. GK-tallet indeholder også reservemålmænd.

Samlet minutbias er −0,014 minutter og pointbias +0,0007 point pr. række. Det beviser ikke, at delmodellerne er korrekte. Fixture-bootstrap giver minut-MAE 95 %-interval [10,57; 12,32], xP-MAE [0,972; 1,110], start-Brier [0,0624; 0,0823]. Disse er eksplorative kampebaserede intervaller; 30 kampe i tre runder giver ikke sikkerhed om variation over en hel sæson. 400 gemte simuleringer pr. spiller giver desuden Monte Carlo-usikkerhed, som disse intervaller ikke særskilt identificerer.

## Minutmodellens styrker og fejltyper

Start-Brier er 0,07173. Samlet forventet startandel 32,883 % mod 32,885 % faktisk er delvist en følge af exact-11 og er ikke i sig selv bevis på god individuel kalibrering. Rotationsgruppen har 59,14 % forventede starter mod 60,42 % faktisk, men minut-MAE 26,42. Høj fejl på en usikker individuel start er derfor ikke automatisk en forkert sandsynlighed.

Forventet positiv spilletid er 43,01 % mod 46,14 % faktisk. P90 er 22,13 % mod 19,93 % faktisk; P60 31,26 % mod 30,94 %. Betinget på observeret bænkstatus er forventet cameo 15,39 % mod 19,75 %. Dette er en retrospektiv diagnose på den observerede bænkgruppe, ikke et selvstændigt prædeadline-scoremål. `positive_minutes` er den eksplicitte target; en kortmodtager med officielt 0 minutter kan stadig tælle som spillet efter autosubreglerne.

Den tidligere tællingsaudit forklarer en mekanisme: GW9 forventer 3,32 markspillerindskiftninger pr. hold mod 4,50 faktisk, GW10 3,51 mod 4,63. I normal-kamp-kernen er summen af P90 præcis 10 minus forventede markspillerudskiftninger. En løs P90-multiplikator kan bryde fem-udskiftningsgrænsen og er ikke en acceptabel generel rettelse. FPLs rapporterede minutter afviger desuden fra fysisk udgangstid; otte af 54 normale holdkampe indebærer mindst ti udskiftede startere stadig krediteret 90 minutter. Det forklarer ikke i sig selv P90-overvurderingen.

En oracle, der får den faktiske startstatus men bevarer de arkiverede individuelle durations, sænker minut-MAE fra 11,41 til 4,91. Den må ikke bruges som en deployerbar prognose eller et løfte om denne gevinst. Præcise udskiftningstidspunkter/årsager mangler. Skadestilbagevenden kan ikke isoleres fra et generelt statusflag; cup-/Europa-belastning kræver verificerede historiske kalender- og nyhedstider. Genbrugte Europa-forsøg findes, men deres mangelfulde timing/dækning står i forskningskortet.

## PM-komponenter og pointfordeling

| Pointkomponent | Forventet sum | Faktisk sum |
| --- | --- | --- |
| appearance_points | 1490.57 | 1547 |
| goal_points | 421.90 | 306 |
| assist_points | 238.39 | 171 |
| cs_points | 374.25 | 502 |
| gc_points | -149.19 | -109 |
| save_points | 35.53 | 38 |
| penalty_save_points | 4.78 | 0 |
| dc_points | 230.76 | 232 |
| expected_bonus | 191.75 | 191 |
| negative_points | -115.27 | -156 |

Angrebsovervurdering og undervurdering af clean-sheet-point samt disciplin udligner hinanden. Bonus- og DC-totaler ser gode ud samlet, men positionsfordelingen er forkert i denne stikprøve: DEF DC 120,54 mod 148; MID DC 106,74 mod 84; GK bonus 7,08 mod 21; MID bonus 88,37 mod 69. De er ikke estimater af universelle korrektionsfaktorer. Bonusreglerne gengiver alle 30 kampe med faktiske BPS-tal; DC-regler/tællere stemmer i 2.011 officielle rækker. Fejlene ligger før pointtildelingen.

Arkiverne indeholder simulerede mål-/assist-komponenter, ikke en separat identificeret prognose for den latente skud-xG/xA. Vi rapporterer forventede mål/FPL-assists mod realiserede hændelser og holder efterkampens skud-xG/xA særskilt. Summerede krediterede mål (eksklusive selvmål til modstanderen) giver 60 holdobservationer og RMSE 1,076. En eksplicit event-conservation-kvittering med fulde holdmål inklusive selvmål findes her kun for GW10: 20 holdobservationer, RMSE 1,124, forventet 28,97 mod 30 mål. Vi opfinder ikke en holdmåls-PMF eller clean-sheet-sandsynlighed fra en målmiddelværdi. Clean-sheet-point-komponenten er evalueret, men er ikke det samme som ubetinget hold-CS.

Redningspoint er 35,53 mod 38. De enkelte redningstal og deres subtyper er ikke fuldt identificeret af `floor(saves/3)`-point. Forventede straffesparksredningspoint er 4,78 mod 0; sjældne hændelser i 30 kampe kan ikke bruges til at sætte sandsynligheden til nul. Straffesparksscoring kræver eksplicitte taker-/hændelseslabels; vi rapporterer de gemte komponenter og de historiske exposure-tests frem for at antage, at alle mål er ikke-straffesparksmål.

10+-point-høster: 2,028 % forventet mod 1,844 % faktisk, Brier 0,01741. 80 %-pointintervaller dækker 92,78 %, men deres faktiske diskrete sandsynlighedsmasse er 93,83 %: den høje dækning skal ikke bedømmes som et kontinuerligt præcist 80 %-interval. CRPS er 0,6843 for alle og 1,4060 for aktive. At være bedre end en punktmasse ved xP er ikke en sammenligning mod en konkurrerende probabilistisk fodboldmodel.

## MM → PM-sammenhæng

Korrelationen mellem signerede minut- og pointfejl er 0,464; mellem absolutte fejl 0,415. En retrospektiv conditioning på faktisk minutbin reducerer point-RMSE 1,756 → 1,604 på de 1.828 understøttede rækker; 179 rækker mangler mindst 30 relevante scenarier. Det er en sensitivitet med support-/selektionsbegrænsning, ikke en kausal MM-ablation. Komponent-oracles i `results/evaluation.json` er heller ikke additive eller implementerbare forbedringer.

## Høj andel af holdets angreb

Andele beregnes af prognosens forventede mål eller assists relativt til holdets forventede hændelser. Ved målshare 25–40 % er der 28 rækker; ved ≥40 % kun tre. Den sidste gruppe har 1,75 forventede mod to faktiske mål og understøtter ikke en generel overestimering. Assistshare 10–25 % har 188 rækker: 34,92 forventede mod 16 FPL-assists; xP-bias +0,421. Der er kun tre rækker over 25 %. Det er et relevant lokalt signal, men ikke bevis på, at høj share i sig selv er årsagen.

Et større eksisterende budget-ablation-forsøg på 341 kampe/27.092 rækker pr. arm tester netop dette. En 50 %-blanding sænker high-forecast-RMSE 3,914 → 3,747 i 2024/25 og 3,793 → 3,773 i 2025/26, men forværrer samlet RMSE i begge sæsoner. Perioderne er genbrugte. En generel nedskalering af stjerner eller angrebsbudgetter er derfor ikke dokumenteret.

## TS v3 og samlet beslutningskvalitet

Der findes to forskellige historiske resultater, som ikke må blandes:

- Ældre Phase5Q-proxy, chips OFF: TS v3 1.992 point/45 transfers/32 hitpoint; no-transfer-control 1.425. TS v2 på samme proxy opnår 2.137 og 68 hitpoint. Det er ikke dagens B/PM vFinal-kæde.
- Senere reproduktion af det oprindelige arkiv: 2.125 point, 44 transfers og 28 hitpoint; cold-start GW1–5, låst MM+vFinal GW6–38, chips OFF. Loggen er reproduceret bortset fra runtime, men horizon-auditten har kun 33 af 183 krævede origin/target-par. Dette er derfor ikke certificering af en fuld seks-GW-policy.

Autentiske private før-deadline-anbefalinger gemmes lokalt i brugerens browser; vi har ikke inddraget private managerfiler eller erstattet dem med et hindsight-hold. Holdets faktisk scorede point eller ligaens bedste XI efter kampene er ikke et TS-afkastmål. Der kan derfor ikke gives et verificeret nutidigt sæsontal for den samlede MM → PM → TS-kæde, en kausal værdi af en gemt FT eller hver chip. Korrekte budget-, autosub-, kaptajn- og chipmekaniktests findes; de måler korrekthed, ikke prognosemæssig gevinst.

Nødvendigt næste TS-evidensgrundlag er et før-deadline-logget managerstate, salgspriser/FT/chips, den fulde oprindelige horisont, både plan og keep-squad-kontrol, samt på forhånd definerede alternative politikker. Chips/FT-roll skal evalueres i sammenhængende stateful forløb, ikke som uafhængige engangsbytter på samme senere kendte trup. Ingen dyre TS-simulationer er genkørt i denne audit.

## Reproduktion og begrænsninger

Se `../README.md`, input-/resultatmanifest, tests og de fire regnescripts. Alle nye analyser er aritmetik på arkiverede scenarier; ingen model er trænet eller simuleret igen. Resultater efter klub/spiller er et fejl-atlas med meget små delstikprøver, ikke en rangliste over sikre modelfejl. Den kvalitative eksterne research er observeret nu og bruges ikke som historiske prognosefeatures.
