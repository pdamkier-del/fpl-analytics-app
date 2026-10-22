# B: fælles rollefordeling før MM→PM

## Implementeret afgrænsning

Den nye, eksplicit tilvalgte B-kobling lader historiske formationer, rollefleksibilitet og rollespecifikt hierarki påvirke de endelige startchancer. En begrænset, fraktionel spiller/rolle-fordeling dekomponeres til hele opstillinger. MM bruger fordelingens marginaler; PM trækker hele opstillinger fra **den samme fordeling**. Hver opstilling har ti forskellige markspillere med én rolle hver. Den eksisterende fælles keeperproces leverer den ellevte starter og 90 målmandsminutter.

Historikmotoren genbruges med kendte startroller og faktisk registrerede minutter. Kun oplysninger med `known_at < cutoff` indgår. Manglende rollehistorik giver ingen ny marginaljustering; den eksisterende startfordeling bevares. Manglende spillerroller er en udtrykkelig usikker prior oven på spillerens eksisterende startchance, ikke automatisk lige sandsynlighed. Hårde fravær, sikre marginaler og tilgængelighedslofter bevares. Cameos begrænses igen, hvis en justeret startchance ellers ville overskride tilgængeligheden.

En repræsentativ, understøttet opstilling fra fordelingen erstatter den tidligere, uafhængigt valgte visningsopstilling. Den kaldes ikke en kalibreret mest sandsynlig XI: dekompositionen er ikke en unik sandsynlighedsmodel for alle tænkelige ellevere. Rollekompatibilitet er fortsat blød evidens, ikke en påstand om, at en spiller umuligt kan skifte position.

Original simulator, produktionsmodel og TS-defaults ændres ikke. Nye moduler er eksplicit eksperimentelle; B-entry-pointet kræver en SHA-kontrolleret policy og beståede historiske gates. Backendens eksisterende B-scorer bruger fortsat de forseglede PM-scenarier.

## Konkrete importance-fejl rettet i B-koblingen

Kildekoderne `cl`, `el`, `conf`, `conf_qual`, `fa` og `efl` oversættes til de eksisterende importance-funktioners kanoniske konkurrencer. Den oprindelige normalizer genkender ikke disse forkortelser; eksempelvis kunne en CL-række derfor få konkurrenceværdi nul. Den nye kobling genberegner sin historiske importance fra konkurrencen og den kendte runde, frem for at overtage den fejlbehæftede kolonne. Den oprindelige produktionskode ændres ikke.

Den samme adapter behandler semifinaler og kvartfinaler før det generelle delord “final”, så begge ikke fejlagtigt bliver finaler. Manglende modstander-Elo er neutralt. Observeret tidligere turneringsdeltagelse giver kontekst; senere knockoutfremskridt rekonstrueres ikke bagud. Kommende CL-kamp er stadig **ikke** en valideret rotationsårsag i denne version.

## Historiske sammenligninger

Den oprindelige lille styrkegrid indeholdt 0, 0,1, 0,25 og 0,5; 0,5 blev valgt på udviklingsperiodens gennemsnitlige start-Brier. Efter rettelsen af konkurrencekoderne blev **0,5 fastholdt uden ny tuning**. Både før- og efterforsøg er bevaret. Den endelige evaluering bruger den låste numeriske runtime og frosne B-prognoser, kilder og faktiske udfald.

| Senere GW22–38 | Start-Brier før → efter | Minut-MAE før → efter | Minutbias før → efter |
| --- | ---: | ---: | ---: |
| 2024/25, 13.105 rækker | 0,072307 → 0,072177 | 10,94865 → 10,89442 | −0,33237 → −0,32585 |
| 2025/26, 13.987 rækker | 0,067943 → 0,067899 | 10,26308 → 10,17832 | −0,21760 → −0,20354 |

PM blev genkørt på **501 kampe**, 39.264 spiller/kamp-rækker pr. arm og 400 træk pr. kamp. Baseline reproducerede alle arkiverede B-xP præcist. Samme input, komponentrater og seed blev brugt i begge arme; ændret RNG-rækkefølge betyder, at træk ikke er identiske tilfældige hændelser.

| PM | xP-MAE før → efter | Parret ændring og kamp-bootstrap 95% |
| --- | ---: | --- |
| 2024/25, 171 kampe | 0,889120 → 0,887523 | −0,001597 [−0,004152; +0,001000] |
| 2025/26, 330 kampe | 0,903286 → 0,903209 | −0,000077 [−0,001971; +0,001818] |

De fastlagte gates for start/minutter og point-noninferioritet består. Pointforskellene dokumenterer **ikke** en sikker xP-forbedring. I 2025/26 bliver played-player xP-MAE lidt dårligere (2,016393 → 2,017775), inden for den forud fastlagte grænse. Der bruges ingen spillerbestemte boosts.

2024/25's detaljerede roller er udtrykkeligt formations-/layoutproxies; 2025/26 bruger den eksisterende klassificerede PL-rollehistorik. Begge beholder dokumenterede historiske klokkeproxies. Perioderne er tidligere anvendte forskningsperioder, ikke en ny uafhængig certificering. Der er 957 klub/kamp-kvitteringer med anvendt historik; øvrige klub/kamp-grupper beholder B uden den nye rollejustering.

## Sandsynligheder og resterende huller

En separat test gennemgår de analytiske 0-, 60+- og 90-minutters-sandsynligheder samt intervaldækning for markspillere i GW22–38. P(0) bliver bedre i begge sæsoner; kamp-bootstrap-intervallerne for Brier-ændringen ligger under nul. P(60+) bliver lidt bedre samlet, mens P(90) bliver lidt dårligere; intervallerne for de sidste to mål inkluderer nul. Regelmæssige starteres 80%-intervaldækning er fortsat utilstrækkelig i 2024/25. Derfor aktiveres ingen påstand om uafhængigt kalibrerede intervaller eller sikkerhed omkring middel-xP.

Den samlede tidligere kravoversigt er stadig en historisk audit, ikke en erklæring om, at alle dens huller nu er lukket. Denne rettelse lukker den manglende forbindelse mellem detaljroller og marginaler og mellem marginaler og fælles PM-opstillinger (R02/R06). R03 har nu en faktisk rolle×importance-mekanisme med generelle tests. Følgende består som særskilte begrænsninger: valideret kommende-kamp-prioritering (R04), probabilistisk fraværsårsag (R05), uafhængig minutkalibrering (M08), PM's fulde rødt-kort/selvmålskæde og særlige assisttyper (P08/P09), certificeret transferpolicy-/chipafkast (T06/T07) samt ældre sæsoners brugerflade (D03). Ingen af dem må erklæres løst af denne rolleændring.

Maskinlæsbare resultater, kildehashes, policy og kalibreringsdiagnostik ligger i [resultatmappen](../../analysis/results/joint-role-candidate-20261022). Aktuel seks-GW-/browser-/publiceringskontrol registreres særskilt efter de nye CI- og preview-gates; en lokal historisk test er ikke en publicering.
