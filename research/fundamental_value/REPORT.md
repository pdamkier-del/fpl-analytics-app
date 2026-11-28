# Research C · Resultater

## Markedspriser

I de to evalueringssæsoner steg spillere med større fundamental surplus relativt mere i pris over tre gameweeks. Effekten var **£0,0072 mio. pr. standardafvigelse** i den primære model og £0,0085 mio. i følsomhedsanalysen med det endelige kampprogram. Begge estimater ligger under en tiendedel af et enkelt prisstep på £0,1 mio. Den alternative ratio fulgte samme retning. Surplus havde samme fortegn i begge sæsoner, men overlevede kun den særskilte Holm-korrektion i 2024–25. Testen måler prisudvikling og estimerer hverken sikkert salgsprovenu eller et kausalt afkast.

| Signal | £m pr. SD, primær | Holm-justeret p | Fortolkning |
| --- | ---: | ---: | --- |
| Fundamental surplus | +0,00722 | 0,0133 | Positiv prisassociation |
| Surplus pr. ekstra budget | +0,00493 | 0,0158 | Samme retning med alternativ værdidefinition |
| Ownership | −0,00317 | 0,00038 | Efterfølgende relativt lavere prisudvikling |
| Tilbage efter fravær | −0,00010 | 0,787 | Fladt estimat for den observerede proxy |
| Ny starter | +0,00048 | 0,105 | Usikker effekt |
| Underliggende offensiv produktion over faktisk output | −0,00308 | 0,00220 | Negativ prisassociation |
| Seneste haul på mindst 10 point | +0,00456 | <0,00001 | Positiv prisassociation |
| Transfermomentum | +0,00504 | <0,00001 | Positiv prisassociation |

Ejerskab og store pointudbytter kan afspejle markedsadfærd. Prispanelet alene kan ikke afgøre, om spillere var sportsligt overvurderede. Fraværsproxyen blander skader, suspension og bænkning, og starterproxyen fanger kun ændringer i registrerede starter. De pågældende hypoteser om dokumenterede skader og taktiske rolleændringer står åbne. Den negative prisassociation for underliggende offensiv produktion over faktisk output taler imod en prisstrategi baseret på denne proxy. Et særskilt testmål for signalets fremtidige sportslige produktion blev ikke estimeret.

De to evalueringssæsoner giver 39.798 komplette spillerrækker over 56 gameweek-origins. [Samlet tabel](results/market.csv) · [Sæsonopdeling](results/market_by_season.csv) · [Graf med retrospektivt kampprogram](results/market.png)

## Sæsonpoint i transferreplayet

Alle fire kandidater tabte til point-baseline i begge evalueringssæsoner ved alle tre planlagte ejertider. Tabellen viser gennemsnitlig forskel i nettopoint over GW8–38 for tre parrede starttrupper ved fire GW. Intervallerne kommer fra blokresampling af de ugentlige forskelle.

| Strategi | 2023–24, point (95 % interval) | 2024–25, point (95 % interval) |
| --- | ---: | ---: |
| Fundamental value | −141,7 (−237,0 til −52,0) | −212,0 (−301,0 til −126,7) |
| Contrarian | −94,3 (−232,0 til +26,0) | −144,3 (−205,7 til −85,3) |
| Momentum | −42,3 (−138,7 til +57,0) | −103,7 (−166,3 til −41,7) |
| Fundamental value + markedssignaler | −119,7 (−206,3 til −34,3) | −221,0 (−332,7 til −110,0) |

Den positive prisassociation gav således ingen pointgevinst i den afprøvede implementering. Den er lille relativt til prissteppet, og de afprøvede strategier gav flere transfers og flere hitpoint samlet. Vægtene er faste heuristikker med begrænset søgning. De delte kalenderforløb, få sæsoner og deskriptive intervaller begrænser generalisering. En foreløbig prisassociation er utilstrækkelig til at afgøre, om en anden portefølje- eller transferpolitik kan udnytte signalet.

Sammenligningen mod **TS v3** står åben. Det verificerede originalarkiv gav ikke et flerårigt panel af frosne prognoser og state-input, og baseline ovenfor er en selvstændig pointstrategi. Ingen MM-, PM-, TS v3- eller produktionsændringer følger af resultaterne. [Replaygraf](results/replay.png) · [Alle parrede effekter](results/paired_effects.csv) · [Transfers, hits og nettopoint](results/replay_totals.csv) · [Ugentlig ledger](results/weekly_replay.csv) · [Dataaudit](DATA.md)
