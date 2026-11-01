# FPL Analytics – systematisk præcisionsaudit af MM, PM og TS

**Repository:** `pdamkier-del/fpl-analytics-app`  
**Reference:** PR #22, commit `736d65cacc1afeeaf8c3dcfad317d7ee745b48fa`

Vi har nu en fungerende B-preview med rettede datakilder, skadesreturer, minutter, selvmål og straffesparksregnskab.

Næste opgave er ikke at udvikle flere modeller. Vi skal først finde ud af, **præcis hvor vores eksisterende FPL-model mister forudsigelsespræcision**, og hvilke ændringer der faktisk kan forbedre den.

Arbejd videre på den eksisterende kode. Bevar produktion, låst PM, TS v3 og den nuværende B-preview uændret. Brug en særskilt auditbranch.

## Fase 1 – Isolér kilderne til xP-fejl

Gennemfør en historisk diagnostisk analyse af hele kæden MM → PM.

Sammenlign følgende scenarier:

1. Den normale B-model med prognosticerede input.
2. Samme model, men med faktiske spilleminutter.
3. Samme model, men med faktiske startopstillinger.
4. Samme model, men med faktiske holdmål.
5. Kombinationer af ovenstående.

Mål hvor meget hver ændring påvirker:

- xP-MAE og RMSE.
- xP-bias.
- Fejl opdelt på positioner og spillerroller.
- Individuelle mål-, assist- og clean-sheet-prognoser.

**Vigtigt:** Dette er diagnostiske oracle-tests med facitoplysninger. De må aldrig bruges som en reel fremtidig prognose. Faktiske holdmål og minutter skal integreres på matematisk konsistent vis, og samspillet mellem fejlkilder skal rapporteres, så vi ikke dobbeltoptæller mulige forbedringer.

Målet er at afgøre, hvor vi har det største realistiske forbedringspotentiale.

## Fase 2 – Undersøg Monte Carlo-støj

Vores nuværende sammenligninger anvender blandt andet 400 simulationer pr. kamp.

Undersøg, om det er tilstrækkeligt til stabile individuelle xP-værdier.

Kør gentagne simulationer med uafhængige seeds ved:

- 400 draws.
- 2.000 draws.
- 10.000 draws.

Undersøg:

- Standardafvigelsen på individuel xP.
- Usikkerheden på mål, assists, clean sheets og bonus.
- Ændringer i spillerrangeringer.
- Ændringer i anbefalede transfers, kaptajner og startopstillinger.
- Beregningstid og hukommelsesforbrug.

Sammenlign modeller med fælles tilfældige træk, hvor det er metodisk muligt, og rapportér særskilt den resterende Monte Carlo-usikkerhed.

Brug Penders og Le Fée som konkrete kontrolcases.

Anbefal derefter et passende antal simulationer til den almindelige app og til historisk modelvalidering.

## Fase 3 – Individuel mål- og assistkalibrering

Undersøg PM's individuelle spillerfordeling.

For mål:

- Forventede mål mod faktiske mål.
- Mål pr. 90 minutter.
- xG pr. 90 minutter.
- Kalibrering af sandsynligheden for mindst ét mål.
- Forskel mellem positioner og spillerroller.
- Effekten af skiftende forventede minutter.

For assists:

- Forventede FPL-assists mod faktiske FPL-assists.
- Kalibrering på positioner og spillerroller.
- Særlige FPL-assistregler.
- Sammenhængen mellem holdets målbudget og spillernes assistvægte.

Undersøg konkret, hvorfor Le Fée har relativt høj xP, og fordel forklaringen på forventede minutter, holdmål, mål, assists, clean sheets, bonus og øvrige pointkomponenter.

Test ikke alternative modeller alene på baggrund af enkelte spilleres prognoser. Brug historisk out-of-time-evaluering og dokumentér eventuelle systematiske skævheder.

## Fase 4 – Undersøg minutmodellens fejlstruktur

Den nuværende minut-MAE er cirka 10–11 minutter.

Opdel fejlene på:

- Sikre stamspillere.
- Rotationsspillere.
- Indskiftere.
- Skadede og tilbagevendende spillere.
- Spillere med høj fysisk belastning.
- Spillere med internationale kampe og cupkampe.
- Positioner og klubber.

Mål både minutter og sandsynlighederne for at starte, spille mindst 60 minutter og spille 90 minutter.

Afgør, om enkelte grupper systematisk bliver over- eller undervurderet.

Forsøg ikke at optimere nye MM-parametre, før disse fejl er dokumenteret.

## Fase 5 – Undersøg TS' praktiske optimeringstab

Vi ved allerede, at TS v3 har visse søgebegrænsninger.

Brug realistiske historiske FPL-holdsituationer til at undersøge:

1. Om en midlertidigt negativ finansieringstransfer kan indgå i en samlet bedre transferkombination.
2. Om fælles optimering af XI, bænk, kaptajn og vicekaptajn giver højere forventet FPL-score.
3. Hvor ofte den eksisterende TS v3 overser en bedre løsning.
4. Hvor meget den taber i forventede point, og hvad den ekstra beregning koster.

Brug eksakt søgning på små, afgrænsede tilfælde som reference. Skeln mellem syntetiske modeksempler og dokumenteret performance på realistiske historiske beslutninger.

Implementér ikke en ny TS uden verificeret forbedring.

## Fase 6 – Validering og rangering

De eksisterende 341 historiske kampe er tidligere blevet brugt til modeludvikling. De må derfor ikke præsenteres som en ny uafhængig testmængde.

Brug walk-forward-evaluering med korrekte historiske informationscutoffs. Find om muligt reelt uberørte historiske perioder, ellers etabler en fremadrettet, uforanderlig prognoselog til kommende GW.

Rapportér:

- Antal kampe og spillerobservationer.
- Usikkerhedsintervaller.
- Ændring i relevante fejlmål.
- Bias og probabilistisk kalibrering.
- Forskellen mellem statistisk usikkerhed og Monte Carlo-støj.
- Om forbedringerne er stabile på tværs af sæsoner.

Afslut med at rangere de mulige forbedringer efter:

**Forventet forbedring i prognosepræcision × evidensstyrke / implementeringskompleksitet.**

## Leverance

Jeg vil have én samlet rapport med:

1. En tabel over hvor MM, PM og TS mister mest præcision.
2. Konkrete analyser af Penders og Le Fée.
3. En anbefaling om antal Monte Carlo-simulationer.
4. En prioriteret liste over præcise modelændringer, som bør testes efterfølgende.
5. Reproducerbare scripts, testresultater og CI.
6. Et link til GitHub-rapporten og PR'en.

**Begrænsninger:**

- Ingen ændring af den låste produktionsmodel.
- Ingen ny publicering nødvendig på dette trin.
- Ingen alternative modeller uden konkret begrundelse.
- Ingen overfitting til de tidligere brugte forskningsperioder.
- Ingen påstande om højere præcision uden uafhængig dokumentation.

Arbejd selvstændigt og gennemfør hele auditten. Brug den eksisterende kode og de eksisterende historiske datasæt. Hvis en test mangler valide data, dokumentér præcis hvilke input der mangler, og gennemfør resten.

**Målet er ikke bare at gøre modellen mere kompliceret, men at identificere den største dokumenterbare forbedring, vi kan lave som det næste.**
