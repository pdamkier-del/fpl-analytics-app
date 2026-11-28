# FPL som dynamisk marked

**Transferflow forbedrer prisprognoser. Den direkte evidens for ekstra information ud over MM/PM er foreløbig.** Historisk transferflow forbedrede også en simpel sportslig reference. I de fire afsluttede GWs med original MM/PM gav en fast markedskorrektion en lille gevinst for minutter og skiftende fortegn for point. De tre sæsonreplays viste, at markedsinformation kan ændre realiserede point, med gevinster og tab afhængigt af sæson og politik.

## Prisprognoser

Alle scorer er walk-forward og sammenlignes på identiske rækker inden for en horisont. En prisbevægelse betyder nettobevægelsen mellem de angivne snapshots. Højere præcision og lavere Brier/log loss er bedre.

| Horisont | Spillerrækker / origins | Bedste observerede model¹ | Brier, model / historisk frekvens | Log loss, model / historisk frekvens | Præcision fald / stigning |
| --- | ---: | --- | ---: | ---: | ---: |
| Dag +1 | 224.603 / 292 | Boosting | 0,0169 / 0,0184 | 0,0397 / 0,0588 | 0,0 % / 61,8 % |
| Dag +3 | 216.382 / 281 | Boosting | 0,0450 / 0,0532 | 0,0921 / 0,1432 | 62,5 % / 59,0 % |
| GW +1 | 78.882 / 105 | Boosting | 0,0991 / 0,1304 | 0,1802 / 0,2937 | 57,4 % / 67,7 % |
| GW +2 | 76.416 / 102 | Boosting | 0,1569 / 0,2211 | 0,2756 / 0,4455 | 61,2 % / 57,5 % |

¹ Laveste observerede Brier blandt de på forhånd fastlagte arme. Resultaterne giver en historisk sammenligning af modellernes score.

For GW +1 er boostings parrede Brier-difference mod frekvensbaselinen −0,0314, med et 95 %-interval på [−0,0364 til −0,0275]. Referencebaselinen opnår 93,11 % klassifikationsnøjagtighed ved altid at forudsige uændret, mens boosting opnår 93,54 %. Det lille løft i nøjagtighed skjuler en større forskel i sandsynlighedsscorer. På dag +1 har boosting Brier 0,0157 i 2025/26 og 0,0232 i 2026/27 mod frekvensbaselinens henholdsvis 0,0172 og 0,0247. Argmax for fald er skrøbeligt på dagsniveau. Samlet forudsagde boosting enkelte fald, og alle faldsforudsigelser var forkerte. Den simple flowlogit har Brier 0,1102 ved GW +1, og L2-logit med alle features har 0,1054. En flow-binmodel opnår 0,1114 trods samme argmax som frekvensbaselinen. Acceleration alene ændrer den lille GW +1-logits Brier fra 0,11020 til 0,11023. Samme ablation giver en marginal forværring ved GW +2.

[Kalibrering](results/kalibrering.png) viser fald og stigning mod den observerede frekvens i hver sandsynlighedsbin. [Alle bins](results/calibration.csv) omfatter også uændret pris. [Scoretabellen](results/price_metrics.csv) viser hver arms nøjagtighed, klassepræcision, argmax-antal og 95 %-intervaller, med separate dagregimer for 2025/26 og 2026/27.

## Markedets dynamik

- **Efterspørgsel og pris følger hinanden.** Gennemsnitlig rangkorrelation mellem netflow og prisændring i samme GW-interval var 0,291 [0,280–0,301]. Flow og næste GW-intervals prisændring gav 0,289 [0,277–0,300]. Dagsværdierne var 0,115 og 0,114. Den aggregerede statistik sammenfatter både prisreglen og spillere, der bliver handlet i flere perioder.
- **Transfers har momentum.** Rangkorrelationen mellem successive netflows var 0,586 [0,573–0,599] pr. GW og 0,880 [0,869–0,891] pr. dag. 56,8 % af spillerne i den øverste 5 %-flowhale var også i den øverste hale næste GW. Det tilsvarende tværsnitsniveau var 5,1 %. Top 1 % målt på køb tog i gennemsnit 32,9 % af alle køb og havde 12,9 % af ownership i samme tværsnit.
- **Managers reagerer efter store præstationer.** Point i GW `t` korrelerede 0,188 med flow frem til næste deadline og 0,115 med flow frem til den aktuelle deadline. De 1.173 matchede pointudbrud blev fulgt af +0,31 pristick [0,27–0,36] mod kontroller og derefter aftagende merflow. Spillerne lå stadig +0,86 [0,66–1,06] point pr. GW over kontrolgruppens udvikling fra kendt form i de næste to runder. Mønsteret viser en kraftig opmærksomhedsreaktion og almindelig tilbagegang fra ekstremresultatet. Det kan ikke afgøre, om den første prisreaktion var økonomisk for stor.
- **Salgsbølger efterfølges af lavere minutter og yderligere prisfald.** De 1.407 matchede salgsbølger havde efter to GWs −0,58 pristick mod kontrol [−0,66 til −0,51]. Ændringen fra tidligere pointform var −0,01 point/GW [−0,24 til +0,21], mens minutterne var −5,13 [−8,49 til −2,29]. Salgsspillernes absolutte forskel fra egen tidligere form var −0,15 point/GW [−0,40 til +0,08] og −13,32 minutter [−16,62 til −10,25]. Det placerer gennemsnitlige point nær den tidligere form, mens minutterne forblev under tidligere niveau. Matchede salgssager havde større afstand end pointudbrud, og fælles årsager som startplads eller skader kan stadig forklare forskellene.
- **Købene er koncentrerede, men prisfeedbacken er lille efter kontrol.** Rang-sammenhængen fra prisændring til næste flow var 0,025 [0,017–0,032] efter kontrol for flow, form, ownership og tilgængelighed. De 126 prisepisoder med mindst tre ticks over to GWs viste yderligere +0,77 ticks over de efterfølgende to GWs mod kontrol [0,44–1,13] og 20 procentpoint lavere sandsynlighed for et prisfald. Den efterfølgende pointudvikling havde et interval, der dækkede nul. Aggregerede data afgør ikke, om managere kopierer hinanden, om de reagerer på fælles nyheder eller om priserne afviger fra en fundamental værdi.

[Lead–lag-figur](results/lead-lag.png) · [Kohorteresultater og intervaller](results/dynamics.json)

## Sportslig information ud over en reference

På 86.314 fælles, historiske spiller-GW-labels på tværs af 114 GWs forbedrer Ridge med markedssignaler den sportslige proxys MAE fra 1,093 til 1,075 point og fra 16,967 til 16,737 minutter. De parrede forskelle er −0,0183 point [−0,0257 til −0,0103] og −0,229 minutter [−0,292 til −0,162]. Relevante MM- og PM-data er rigere end den historiske referencemodel. [Historiske parrede scores](results/sports.json)

I de ægte MM/PM-vintages fra GW8–11 sænkede den faste, ufittede dagsflowjustering MM's minut-MAE med henholdsvis 0,069, 0,109, 0,048 og 0,016 minutter. PM's point-MAE ændrede sig med +0,0084, −0,0065, −0,0002 og +0,0006 point. De 2.679 spillerobservationer har fire fælles tidsorigins. Der er ikke grundlag for et stabilt konfidensinterval eller en robust påstand om inkrementel MM/PM-gevinst. Originalernes interne MM-certificeringsflag var false, selv om publiceringstid og bytehashes er verificerede. [MM/PM-resultater pr. GW](results/frozen_mm_pm.csv)

## Faktiske sæsonpoint

Tre fulde sæsoner starter fra samme budgetlovlige trup. Arme har derefter egne købskurser, bank og transfers. Alle scorer 38 GWs og bruger samme beslutningsbegrænsninger, holdformation, bænk og kaptajnlogik.

| Sæson | Pointproxy | Marked i pointproxy | Prisprognose i transfers |
| --- | ---: | ---: | ---: |
| 2023/24 | 2.155 | 2.123 (−32) | 2.178 (+23) |
| 2024/25 | 2.160 | 2.220 (+60) | 2.148 (−12) |
| 2025/26 | 1.950 | 1.964 (+14) | 2.135 (+185) |

Den prisvægtede politik gav +196 point summeret over tre sæsoner, heraf +185 i én sæson. Den pointvægtede markedsvariant gav +42 samlet. Begge tabte i mindst én sæson. En enkelt transfer ændrer det fremtidige budget og sæt af tilgængelige beslutninger. Resultaterne gælder de valgte regler og starttrupper, hvor alle arme gennemførte 37 transfers pr. sæson, og kan ikke generaliseres til TS v3, som har et andet beslutningsproblem. I gamle API-vintages uden `can_transact` blev en spiller behandlet som købbar, hvis vedkommende ikke havde et eksplicit fjernelsesflag. Tre stiafhængige sæsoner giver for lidt grundlag til at estimere et fremtidigt pointløft. [Replayfigur](results/saesonpoint.png) · [Score og transferlog](results/replay_weeks.csv)

Forsøget giver empirisk støtte til en markedsbaseret prisprognose og en mindre sportslig signalværdi over simple features. Evidensen er utilstrækkelig for et robust MM/PM-løft, en spekulativ boblemekanisme eller stabile ekstra sæsonpoint. Al kode og evidens ligger i forskningsmappen.
