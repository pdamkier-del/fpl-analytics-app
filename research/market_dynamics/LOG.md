# Forskningslogbog

## 28. november 2026 · Kilder og afgrænsning

- Udgangspunkt `a07e8f7aef0e9bdc9e5dfbb6a31f157c37826af9`, seneste observerede C1-lukning i PR #58, sammenholdt med `main` på `d4d6e8046ad5d965cf41f5a8fce2b32a49fca16c`. PR #58 er base for at kunne genbruge auditkilderne og så PR-diffen kun viser den nye forskning. [PR #58](https://github.com/pdamkier-del/fpl-analytics-app/pull/58)
- Gennemgik C1-dataregister, PR #41’s oprindelige forecastaudit og PR #50/#57’s TS-fundingforsøg samt prospective setup i PR #54. Det gamle fundingresultat var en search-/feasibility-test og blev ikke gentaget. Frosne forecasts, originalbehæftede labels, historiske proxyer og syntetiske TS-states har forskellige tidspunkter og fortolkninger. [Dataregister](../DATA_CATALOG.md), [PR #41](https://github.com/pdamkier-del/fpl-analytics-app/pull/41), [PR #54](https://github.com/pdamkier-del/fpl-analytics-app/pull/54), [PR #57](https://github.com/pdamkier-del/fpl-analytics-app/pull/57)
- O’Brien, Gleeson og O’Sullivan viste kollektiv adfærd i samtidige managerpeergrupper og sammenhæng mellem bedre transfers og managerresultat. Det motiverer efterspørgselsmålingen. Denne analyse undersøger spillerpriser og marginal information over modeller på en anden population. [PLOS One, 2021](https://doi.org/10.1371/journal.pone.0246698)
- Vaastav-inspektionen viste dubletter, Assistant Manager-rækker og usikker xP-timing. Valgte genuine pris- og transfer-vintages fra Randdalf og Eicyer. Kilder og analysedelen blev fastlagt i `f059834` efter en dataaudit, før komplette scoretabeller. Arbejdet er retrospektiv forskning på kendte sæsoner, og det blev ikke registreret som et urørt bekræftelsesforsøg.

## 28. november 2026 · Bygning og første kørsler

- Tidlige gennemløb stoppede ved tidsdatatype for manglende næste deadline og ved en hel, blank GW7 i 2022/23. Håndterede begge i koden og beholdt eksplicitte tids- og labelgrænser. Et negativt internt `deadline_correct` for MM udløste manuel kontrol. Bruger nu prædeadline-publicering fra den eksisterende audit sammen med sammenfaldende input- og bytehashes. Egenskaben står fortsat i auditten.
- Gendannede den version af GW11, som den tidligere audit havde valgt, direkte fra dens historiske release-commit. Valgte det første GW11-liveinput med verificerede finalitetsflag. De 10 nyere bundter for GW12–13 blev hashkontrolleret, og deres outcomes forblev uden score i dette studie.
- Holdt input til replay ved prognoseorigin. Prognoser med manglende fremtidigt endpoint behandles fortsat som tilgængelige til selve beslutningen, hvis deres fortid er dækket. Skellet testes direkte. Historiske slutfixtures bruges ved label-verifikation, med kendte vintages som grundlag for samtlige markedscovariater.
- Replayet kører samme starttrup og samme reference-xP til XI, aldrig private manager-inputs. Både transfer- og prisvarianter ændrer senere trup og bank. De tre repeterede sæsonforløb er følsomme over for disse stiændringer.

## Verifikation

- Ni isolerede tests dækker maturitet, testunivers, gap- og identitetsværn, kendt form, blokresampling, købskurser og autosubs.
- Den eksisterende C1-verifikation returnerede 93 beståede, 1 sprunget over, 2 historiske snapshot-tests fravalgt af repositoryets eget værktøj. Ingen tidligere protokoller, workflowfiler eller modeller er redigeret.
