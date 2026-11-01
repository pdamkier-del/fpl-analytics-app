# Kan vi gratis finde begrundelser om roller, tilgængelighed og rotation?

**Ja.** En kontrol 25. oktober 2026 fandt konkrete, kildebelagte eksempler. Syv manuelt gennemgåede tekstuddrag fra fire officielle artikler er gemt i `evidence.json`, med unikke FPL-spiller-/klubkoblinger, artikelhenvisning, kildehash, udgivelsesdatoens præcision og faktisk hentetid. Det er en gennemførlighedsprøve, ikke en komplet nyhedsindlæsning eller et trænet fortolkningssystem.

## Konkrete fund

| Spiller og udgivelsesdato | Hvad kilden faktisk siger | Forsvarlig fortolkning og afgrænsning |
|---|---|---|
| **Rayan Cherki, 22. oktober** | Maresca kalder ham en af Europas bedste, **når han er i den rigtige position**, og fremhæver farlighed mellem kæderne. | Positiv, positionsbetinget rollebeskrivelse og taktisk instruktion. Ikke et løfte om næste start. Denne kilde var allerede identificeret i gennemgangen 23. oktober; den er genkontrolleret, ikke nyopdaget her. |
| **Mike Penders, 17. oktober** | Alonso udtrykker fuld tillid til ham som afløser. | Relevant hierarki-/tillidsevidens sammenholdt med faktiske opstillinger og konkurrenternes status. Ikke en kalibreret startchance eller ubetinget udnævnelse til førstevalg. Også tidligere gennemgået. |
| **Emiliano Martínez, 18. oktober** | Chelsea bekræfter operation for brækket kæbe. | Konkret officiel skadeoplysning. Artiklen giver ingen sikker returdato. Historisk status skal genkontrolleres, før den anvendes som aktuelt fravær til en ny kamp. |
| **Antoine Semenyo, 24. oktober** | Citys officielle holdnyheder siger, at han fortsat ikke er tilgængelig til Villa-kampen under sin skadesrehabilitering. | Kampafgrænset tilgængelighedsevidens. Må ikke uden ny kontrol kopieres til næste PL-kamp. |
| **Erling Haaland, 24. oktober** | Citys skribent forbinder midtugens bænkplads med, at han forhåbentlig er udhvilet og frisk til Villa. | Understøtter en mulig belastnings-/rotationsfortolkning. Ordet **hopefully** bevares. Det er journalistens vurdering på klubhjemmesiden, ikke et direkte trænercitat eller bevis for årsagen til bænkpladsen. |
| **Phil Foden, 24. oktober** | Den officielle artikel beskriver, at Foden og Rico Lewis går på bænken efter at have startet i CL. | Bekræftet udvælgelsesændring; artiklen fastlægger ikke i det uddrag en entydig fysisk eller taktisk årsag. |

Kilder:

1. [City om Cherkis position og betydning](https://www.mancity.com/news/mens/enzo-maresca-aston-villa-press-conference-rayan-cherki-63928260)
2. [Alonso om Martínez og Penders](https://www.chelseafc.com/en/news/article/alonso-issues-emiliano-martinez-update)
3. [Chelseas officielle skadesopdatering](https://www.chelseafc.com/en/news/article/injury-update-emiliano-martinez)
4. [Citys opstilling og holdnyheder til Villa](https://www.mancity.com/news/mens/aston-villa-v-city-premier-league-team-news-63928427)

De fire artikler blev hentet igen 25. oktober omkring **kl. 20.50–20.51 dansk tid**. Citys artikelmetadata for de udvalgte artikler angiver dato, ikke et pålideligt præcist UTC-udgivelsestidspunkt; det gemmes som `publication_precision=day`. Chelseas indlejrede artikeldata har eksplicit tidszone. Relaterede billetsalgstider eller datoer i URL'er bruges ikke som artikeludgivelse.

## Hvor kan vi hente den næste information?

[Citys gratis optakt til Brighton-pokalkampen](https://www.mancity.com/news/mens/city-v-brighton-preview-carabao-cup-28-oct-63928427), dateret **25. oktober**, annoncerer næste pressekonference **tirsdag 27. oktober kl. 10.30 britisk tid / 11.30 dansk tid**. Den oplysning var tilgængelig i den faktisk hentede artikel; det er ikke et gæt baseret på et fremtidigt resultat. Artiklen lover holdnyheder på pressemødet, men indeholder endnu ikke disse fremtidige udtalelser.

[Citys træningsgalleri før Villa](https://www.mancity.com/news/mens/manchester-city-training-gallery-october-23-63928356) kan også hentes gratis. Det har ikke tilstrækkeligt tekstgrundlag til at konkludere, at en bestemt spiller har gennemført fuld træning eller er medicinsk kampklar. Fravær fra et billede betyder heller ikke fravær fra træning.

Citys nyhedsoversigt er teknisk læsbar og indeholder direkte artikelhenvisninger. **Arsenals nyhedsoversigt gav HTTP 403** i denne prøve. Der blev ikke forsøgt at omgå blokeringen. Det er derfor ikke dokumenteret, at vi kan indsamle alle klubber automatisk fra officielle sider.

Sports Mole-prøven fra samme dag viser desuden en læsbar kampoptakt med holdnyheder og mulige startopstillinger. Den er en redaktionel sekundærkilde. De tilsvarende RotoWire-sider havde endnu ingen nye XI-bud for GW9, mens Pundits XI'er var fra GW8. Derfor kan der ikke nu laves en dokumenteret frisk multi-kilde-konsensus for næste PL-runde.

## Hvad ville gøre fortolkningen brugbar?

Gem tre separate lag:

1. **Original kilde:** Hvem sagde/skrev hvad, om hvem, hvilken kamp, udgivelsespræcision og første faktiske modtagelsestid. En citeret træner og artiklens journalist er forskellige afsendere.
2. **Struktureret betydning:** Skade/tilgængelighed, udtrykkelig start-/hvilebesked, minutbegrænsning, tillid/hierarki, taktisk position eller generel ros. Bevar ord som “hvis”, “forhåbentlig” og “måske”. Manglende omtale er ukendt, ikke negativt.
3. **Vores fortolkning:** Hvad oplysningen kan betyde sammen med starter, konkurrenter, positioner og kampbelastning. Vis modstridende og forældede oplysninger frem for at tælle alle omtaler som uafhængige bekræftelser.

Et troværdigt Cherki-kort kan derfor sige: “Træneren fremhæver hans betydning mellem kæderne; dette støtter en vigtig offensiv rolle, men kilden lover ikke næste start.” Det må ikke uden efterfølgende test blive til “derfor 90 % startchance”.

## Hvad er faktisk leveret — og hvad er ikke?

- **Leveret:** Otte HTTP-kontroller med kvitteringer, konkrete kildeeksempler, syv verificerede tekstspænd og spilleridentiteter samt særskilte fortolkninger og begrænsninger. Syv hentninger lykkedes; Arsenal-oversigten gav 403. Originale webbytes ligger lokalt i `/workspace/scratch/player-context-evidence`; repoet indeholder korte strukturerede uddrag og kildehashes, ikke hele artikler.
- **Kontrol:** Hvert gemt uddrag blev verificeret som en entydig, præcis delstreng i den gemte artikels afsnit. Kildebytes matcher kvitteringens SHA-256. Spillerkoblinger bruger entydigt FPL-navn og aktuel klub fra den officielle bootstrap hentet tidligere samme aften. Det er identitetskontrol, ikke statistisk modelvalidering.
- **Ikke leveret:** En generel automatisk NLP-fortolker, komplet klubdækning, løbende pressekonferenceovervågning, appvisning eller ændrede MM-/PM-/TS-prognoser. De menneskelige kategoriseringer er markeret som sådanne. Ingen historisk effekt på start-Brier/minutter/xP er målt.
- **Uændret:** B-modellen, produktionen, appens layout og brugerens hold. Ingen betaling, konto, ekstern besked eller deployment. Der er kun nye forskningsdokumenter, så modelregressionerne er ikke genkørt for denne gennemgang.

Det konkrete svar er dermed: **Ja, den ønskede viden findes gratis og kan knyttes til kilde og dato. Det arbejde, der mangler, er bred og vedvarende indsamling samt en efterprøvbar fortolkning — ikke at opfinde begrundelser til en XI-liste.**
