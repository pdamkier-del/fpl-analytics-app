# Gratis forklarende spiller-/holdinformation for hele Premier League

**Resultat 25. oktober 2026: forklarende holdnyhedstekster fundet for 20 af 20 aktuelle PL-klubber.** Samme gratis Fantasy Football Scout-side har et separat klubafsnit med skader, træningsstatus, rolleovervejelser og mulige udvælgelsesændringer. Dette er bred redaktionel dækning, ikke 20 uafhængige kilder, komplette individuelle spillervurderinger eller 20 friske GW9-prognoser.

Derudover er alle 20 officielle klubnyhedsoversigter forsøgt hentet: **19 gav HTTP 200, Arsenal gav 403**. Flere af de 19 er JavaScript-skaller eller har kun metadata i den umiddelbare HTML. HTTP 200 dokumenterer derfor ikke, at alle artikler kan læses eller at klubben har offentliggjort en aktuel opdatering. Tre yderligere officielle artikler er krydstjekket på tekstniveau; en fjerde Bournemouth-artikel gav 200, men ikke læsbare afsnit i den simple parser.

Ingen konto, betaling, forsøg på at omgå blokeringer, ekstern besked, appdeployment eller numerisk modelændring.

## Klubber og de typer forklaringer, der faktisk findes

Nedenstående er korte menneskelige sammenfatninger af den **redaktionelle kontekst fra GW8** på [Fantasy Football Scouts gratis holdnyhedsside](https://www.fantasyfootballscout.co.uk/team-news). Alle 20 klubafsnit viser “Last Updated Fri 23rd Oct”. De blev faktisk hentet **25. oktober kl. 20.58 dansk tid**. De præcise UTC-kvitteringer findes i datasættene. Sammenfatningerne er ikke aktuelle, officielt bekræftede skadesbeslutninger til GW9.

| Klub | Eksempel på tilgængelig redaktionel kontekst — ikke nye modelbeslutninger |
|---|---|
| Arsenal | Sakas skade, Hincapies træningsretur og mulige fløjvalg; Calafioris belastning og trænerens omtale af hans forberedelse. |
| Aston Villa | Manzambis fitnessvurdering; midtugehvil til Cash, Maatsen og Kamara og usikkerhed om kampform efter fravær. |
| Bournemouth | Kroupis træningsretur og manglende UEFA-trupregistrering; Kluiverts nylige skade og risiko ved to starter tæt på hinanden. |
| Brentford | Suspensioner til Janelt og Yarmolyuk, centerforsvarernes forskellige fitnessniveauer og mulige taktiske erstatninger. |
| Brighton | Mulige senere returer for Minteh/Wieffer, individuel fraværskontekst og forskellen mellem midtugehvil og sygdom. |
| Chelsea | Martínez' fravær og Penders som afløser; Gustos retur og overvejelser om kontinuitet uden midtugekamp. |
| Coventry City | Fravær, Lampards tidligere ændringer og konkurrence om pladserne i angreb og på midtbanen. |
| Crystal Palace | Manglende pressekonferenceopdatering, Hendersons træningsretur og uafklarede skader efter Europa League. |
| Everton | Moyes' uklare udtalelser og usikkerhed om Branthwaite; fravær fra træningsvideo behandles udtrykkeligt som utilstrækkeligt bevis. |
| Fulham | Tilgængelighedsudtalelse, Sessegnons karantæne og kontinuitet i en ellers stabil opstilling. |
| Hull City | Fuld træningsuge kontra gradvis retur; trænerens varslede ændringer efter en svag præstation. |
| Ipswich Town | Lukics fravær og mulige skift mellem ekstra centerforsvarer og offensiv midtbane afhængigt af modstander. |
| Leeds United | Tvivl om Calvert-Lewin, Stach og Okafor; forskel mellem kontaktskade og muskelproblem samt ekstra restitutionstid. |
| Liverpool | Individuel træning kontra kampklarhed, småskader og midtugehvil til flere etablerede startere. |
| Man City | Haalands tilgængelighed, usikkerhed om andre returspillere og flere mulige valg efter CL. |
| Man Utd | Manglende oplysninger i første del af pressekonferencen, fravær og uafklaret retur for flere spillere. |
| Newcastle | Elangas manglende 90-minutterskapacitet, Ramseys gradvise retur og usikkerhed om nytilkomnes roller. |
| Nottingham Forest | Gibbs-Whites fulde træningsuge og Milenkovics mulige retur; klar til at starte er ikke det samme som sikker udtagelse. |
| Spurs | Porros retur, individuelle træningsforløb for Maddison/Kulusevski og mulige taktiske alternativer. |
| Sunderland | Manglende seneste pressekonferenceoplysninger, Brobbeys returforløb og usikkerhed om start frem for indhop. |

Det er netop den efterspurgte form for kontekst: ikke kun hvem der forventes at starte, men **hvorfor redaktionen vurderer det**, hvilke alternativer der findes, og hvad der ikke vides. Det er vigtigt at bevare ordene “kan”, “forventes”, “tvivl” og “ukendt”.

## Primære krydstjek: hvad tilfører de?

- **[Newcastle om Elanga og Ramsey](https://www.newcastleunited.com/en/news/matthias-jaissles-team-news-update-elanga-and-ramsey-latest-ahead-of-palace-trip), publiceret 23. oktober kl. 13.30 UTC.** Træneren siger direkte om Elanga: “He won’t be able to play 90 minutes”, men håber at have ham i truppen. Ramsey skal håndteres gradvist. Det er to forskellige typer information: minutbegrænsning og gradvis retur. Udtalelserne vedrører Palace-kampen 25. oktober og må ikke automatisk flyttes til GW9.
- **[Liverpool om Wirtz](https://www.liverpoolfc.com/news/florian-wirtz-injury-update-liverpool-brighton), publiceret 25. oktober kl. 16.54 UTC.** Nyere officiel opdatering efter Brighton-kampen: ankelskade, udskiftning efter 65 minutter og videre lægelig vurdering. Trænerens optimisme er ikke en medicinsk raskmelding. Denne oplysning er nyere end Scouts fredagsafsnit og viser, hvorfor flere dataversioner skal bevares.
- **[Leeds' optakt til Sunderland](https://www.leedsunited.com/en/news/sunderland-vs-leeds-united-team-news-key-stats-and-everything-you-need-to-know).** Klubben omtaler Calvert-Lewin som tvivlsom med fodskade, sammen med Stach og Okafor, mens Daniel James er tilgængelig. Artiklen er læst; det præcise udgivelsestidspunkt er ikke certificeret i denne prøve. Det er heller ikke en automatisk vurdering af næste GW.
- **[Bournemouth om Kroupi](https://www.afcb.co.uk/news/2026/october/21/injury-news--rose-gives-update-on-kroupi-return/).** Nyhedsoversigtens indlejrede metadata beskriver retur til holdtræning og en mulig snarlig kamptrup. Artikelhentningen lykkedes, men den simple HTML-parser fandt ikke artikelafsnittene. Derfor registreres den som et teknisk dækningshul, ikke som endnu et verificeret direkte citat.

City- og Chelsea-eksemplerne fra den foregående gennemgang er fortsat relevante, men præsenteres ikke her som nyopdagede kilder. Samlet viser prøverne faktiske gratis primærkilder hos flere klubber, uden at påstå primær bekræftelse af samtlige 20 redaktionelle klubtekster.

## Teknisk leverance og modelgrænse

- `scripts/club_context_sources.py` er en fælles læser for de 20 klubafsnit. Den genbruger den eksisterende HTML-parser og klubnormalisering. FPL-kortkode **og** normaliseret kluboverskrift skal stemme. Ukendte klubber, dubletter, konflikter og manglende fortællende tekst bliver ikke stiltiende udfyldt.
- `editorial-coverage.json`: alle 20 klubidentiteter, kilde, faktisk hentetid, opdateringsetiket, korte uddrag og teksthash. Det komplette tekstgrundlag kan skrives til et lokalt forskningsarkiv med `--include-text`; det offentliggøres ikke som hele artikler i repoet.
- `source-registry.json`: én officiel kildekandidat pr. klub med faktisk HTTP-status, URL og kildehash. Status og læsbarhed er adskilt fra en vurdering af påstandenes sandhed.
- `primary-samples.json`: fire manuelt kontrollerede tekstuddrag fra tre officielle artikler, med kamp-/tidsafgrænsninger. Tre spilleridentiteter er verificeret mod den eksisterende FPL-bootstrap; Ramsey er bevidst efterladt uden en verificeret spiller-ID-kobling.
- **Alle `model_input_enabled`-flag er false.** Kilderne ændrer ikke MM, PM, TS, hårde fraværscaps, fysisk minutfordeling eller point. Der er ingen ny sandsynlighed eller automatisk NLP-fortolkning gemt som fakta.

“Alle 20 klubber dækket” betyder her en faktisk læsbar redaktionel klubtekst. Det betyder **ikke** en frisk GW9-vurdering af hver spiller, uafhængige kilder for alle påstande eller komplet automatisk klubnyhedsdækning. De 20 afsnit stammer fra samme udgiver og tæller ikke som 20 uafhængige bekræftelser.

## Friskhed og historiske tests

Næste officielle runde er GW9. Fredagsteksterne omtaler overvejende GW8. Sideløbende kan der være nyere, specifikke officielle oplysninger som Wirtz-opdateringen fra søndag. Individuel kampreference, kildeopdatering, faktisk første modtagelse og en eventuel senere korrektion skal derfor gemmes separat.

Den globale webside har andre metadata end de enkelte klubafsnit; et globalt `dateModified` må ikke bruges som præcist publiceringstidspunkt for hver klub. “Fri 23rd Oct” omdannes heller ikke til et opdigtet UTC-minut. Dagens hentetid kan ikke retroaktivt dokumentere, hvad et tidligere forecast vidste.

Der er derfor endnu **ingen målt gevinst i start-Brier, minutfejl eller xP** fra disse tekster. En generel modelkobling kræver først registrerede, tidsafgrænsede spillerpåstande, kontrolleret udtræk/fortolkning og fremadrettet evaluering. Positiv rolleros må ikke få samme betydning som eksplicit utilgængelighed eller en konkret minutbegrænsning.

## Reproduktion og validering

Kildearkiver fra prøven ligger lokalt i `/workspace/scratch/pl-club-context`; officielle FPL-identiteter i `/workspace/scratch/free-match-intel/fpl.raw`. De komplette websider er ikke committed. De strukturerede resultater og kvitteringer er committed. Præcis genkørsel kræver de gemte byteversioner; et nyt webkald er et nyt snapshot.

```sh
PYTHONPATH=src:scripts:. /workspace/fpl-venv/bin/python scripts/club_context_sources.py \
  --archive /workspace/scratch/pl-club-context \
  --bootstrap /workspace/scratch/free-match-intel/fpl.raw \
  --out /workspace/scratch/pl-club-context-review.json
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python -m pytest -q tests
```

**1.018 tests bestået** i den samlede lokale regressionssuite, 58,43 sekunder. De otte nye tests kontrollerer bevaret usikkerhed, ukendt klub, dubletter, manglende/duplikeret tekst, forkert kontekst, uklare datoer, naive ure og konflikt mellem overskrift og klubkode. Samme gemte kilde giver identisk klubrapport; manuelle primæruddrag er kontrolleret som entydige delstrenge i de gemte artikelafsnit. Det er teknisk validering, ikke en dokumenteret statistisk modelgevinst.

Der er ikke oprettet et automatisk nyhedsjob, og der er ikke publiceret en ændret app. Produktionsmodellen, den eksisterende B-preview og brugerens hold er uændrede.
