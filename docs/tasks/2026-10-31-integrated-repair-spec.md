# FPL Analytics – samlet implementering og fejlrettelse

Du skal nu overtage implementeringen af de fejl og forbedringsmuligheder, vi har identificeret i vores FPL Analytics-model.

**Repository:** `pdamkier-del/fpl-analytics-app`

Fortsæt fra den seneste fungerende kode, de eksisterende PR'er og den publicerede B-preview. Start ikke projektet forfra.

## Fase 1 – Ret MM (højeste prioritet)

Følg den tekniske specifikation i:

https://github.com/pdamkier-del/fpl-analytics-app/issues/24

Ret følgende fire forhold:

1. De 85 dokumenterede solgte eller udlejede spillere må ikke få forventede minutter i fremtidige GW, hvor de fortsat er utilgængelige.
2. Fysisk belastning skal inkludere relevante kampe fra alle turneringer, ikke kun Premier League. Historisk træning og prognose skal bruge konsistente featuredefinitioner.
3. Forventede skadesreturdatoer skal bruges til tidsafhængige tilgængelighedssandsynligheder, ikke som absolutte garantier.
4. Undersøg rotation og prioritering af kommende vigtige kampe. Implementér kun ændringer, hvis historiske tests understøtter dem.

Bevar den forbedrede målmandsmodel, herunder fælles 90-minuttersdækning og realistisk usikkerhed.

## Fase 2 – Ret PM's hændelsesregnskab

Følg:

https://github.com/pdamkier-del/fpl-analytics-app/issues/26

Læs også vores selvstændige kodeaudit:

https://github.com/pdamkier-del/fpl-analytics-app/blob/audit-pm-event-conservation-20261031/analysis/audits/2026-10-31-pm-event-conservation.md

Vi har fundet tre konkrete problemer, som kræver test og korrektion:

**A. Selvmål og clean sheets**

Selvmål bliver simuleret individuelt, men indgår ikke konsekvent i kampens fælles målregnskab.

Ret dette, så selvmål påvirker korrekt:
- Kampens resultat.
- Modstanderens mål.
- Goals conceded og clean sheets.
- Individuelle FPL-point og BPS.

Undgå dobbeltoptælling af mål.

**B. Mål uden målscorer og assists**

Simulatoren kan generere et holdmål uden at tildele en målscorer, og assistlogikken kan i visse tilfælde stadig tildele en assist.

Indfør korrekt hændelsesklassifikation og kontrol af mål-/assistregnskabet. Respektér særlige FPL-regler om selvmål og assists.

**C. Straffesparksmodellen**

Modellen trækker forventede straffesparksmål fra holdets målbudget efter én konverteringssandsynlighed, mens den simulerede skytte kan have en anden.

Undersøg og ret, så det samlede forventede målbudget er konsistent med den faktiske simulationsproces, også ved skader, rotation og udskiftning af straffesparksskytte.

Kør reproducerbare tests for alle tre forhold, og mål deres betydning på historiske prognoser.

## Fase 3 – Undersøg overestimering af mål og assists

Vi mistænker, at nogle spillere får en for stor andel af holdets forventede mål, som vi tidligere har set med Le Fée.

Undersøg derfor:

1. Holdenes forventede mål sammenlignet med faktiske mål og xG.
2. Om faktisk målproduktion kan forbedre vores nuværende xG-baserede holdmodel.
3. Fordelingen af mål mellem spillere efter position, rolle, spilletid og xG.
4. Fordelingen af FPL-assists, herunder om vores nuværende assist-sandsynligheder er korrekt kalibreret.
5. Om ændringer i MM's forventede minutter giver utilsigtede ændringer i den individuelle målfordeling.

Sammenlign med den eksisterende låste PM og brug historiske walk-forward-tests.

**Implementér ikke blot lavere målprognoser.** En ændring skal dokumentere bedre præcision eller bedre kalibrering.

## Fase 4 – Kontroller TS

https://github.com/pdamkier-del/fpl-analytics-app/issues/25

Test, om vores transfermodel overser fordelagtige kombinationer, hvor én transfer isoleret set er negativ, men frigør penge til en større forbedring.

Test også, om startopstilling, bænk, kaptajn og vicekaptajn kan optimeres bedre ud fra den samlede Monte Carlo-simulation frem for kun individuelle xP.

Bevar den låste TS v3 som benchmark, og aktiver ikke udokumenterede ændringer.

## Fase 5 – Integration og publicering

Når en ændring har bestået relevante tests:

- Integrér den i den eksisterende B-model.
- Kør Python- og JavaScript-regressionstests.
- Test én kamp, én GW og seks GW gennem MM → PM → TS.
- Sammenlign med den tidligere model.
- Kontrollér brugerfladen på mobil og desktop.
- Publicér en ny fungerende B-preview.
- Verificér, at produktionen er uændret.

Arbejd på en samlet integrationsbranch og undgå flere unødvendige forskningsbranches.

## Afsluttende rapport

Jeg vil have en oversigt over:

- Hvilke fejl der faktisk er rettet.
- Hvilke mistanker der blev afvist.
- Ændringen i minut-MAE, start-Brier og xP-MAE.
- Ændringen i holdmåls-, målscorer- og assistkalibrering.
- Konsekvenserne for relevante spillere, eksempelvis Penders og Le Fée.
- Hvilke ændringer der forbedrer modellen, og hvilke der ikke gør.
- Links til tests, PR og den publicerede app.

**Vigtigt:** Arbejd selvstændigt. Undersøg, implementér, test og ret selv fejlene. Stop ikke efter at have oprettet en PR. Spørg kun, hvis en nødvendig tilladelse eller en konkret blokering kræver min beslutning.

Bevar den eksisterende produktionsmodel og alle låste benchmarks uændret. Ingen automatisk produktionsaktivering.

Målet er en mere præcis, matematisk konsistent og fuldt integreret FPL-app – ikke endnu et ufærdigt modelprojekt.
