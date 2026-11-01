# FPL Analytics – implementér næste tre forbedringer i B-modellen

**Repository:** `pdamkier-del/fpl-analytics-app`

**Udgangspunkt:**
- Den fungerende B-preview fra PR #22.
- Den systematiske præcisionsaudit fra PR #29.
- Auditrapport: `docs/2026-11-01-systematic-precision-audit.md`.

## Målsætning

Vi har afsluttet den brede audit. Nu skal du implementere og teste tre konkrete forbedringer:

1. Reducér Monte Carlo-støj.
2. Forbedr MM's håndtering af skadesreturer og sandsynligheden for at spille 90 minutter.
3. Undersøg og korrigér den systematiske undervurdering af FPL-assists til angribere.

**Dette er en implementeringsopgave, ikke en ny generel forskningsaudit.**

Arbejd direkte videre fra den seneste fungerende integrationskode på én separat udviklingsbranch.

Bevar den låste produktion, PM's øvrige matematik, TS v3 og eksisterende benchmarks som uændrede referencer.

## Fase 1 – Implementér mere stabile Monte Carlo-prognoser

Den seneste audit viser, at 400 simulationer giver betydelig variation i xP og kan ændre kaptajn- og transferanbefalinger.

Implementér:

- 2.000 simulationer til normale prognoser.
- 10.000 simulationer til modelvalidering og tætte beslutninger, hvor ekstra præcision er relevant.
- Deterministisk seedstyring og parrede sammenligninger, hvor det er muligt.
- Kompakt backend-opsummering, så appen ikke skal hente tusindvis af rå scenarier unødvendigt.

Kontrollér, at TS stadig modtager de fælles scenarier, den faktisk behøver til korrelationer, autosubs, kaptajn og transferplanlægning. Bevar de låste TS-beslutningsregler.

Test beregningstid, hukommelse, payload og rangeringernes stabilitet. Hvis 10.000 draws er for dyrt til alle beslutninger, anvend en adaptiv metode med dokumenterede grænser.

**Leverance:** En fungerende B-preview med mere stabile xP-estimater og uændret modelmatematik.

## Fase 2 – Forbedr MM's skadesreturer og fuldkampssandsynligheder

Auditten viser to gentagne skævheder:

- Tilbagevendende spillere undervurderes i gennemsnit med ca. 7–8 minutter.
- Sikre stamspilleres P(90) overvurderes med ca. 6–9 procentpoint.

Byg videre på den eksisterende B-MM. Opret ikke en ny minutmodel.

Undersøg separat:

**A. Skadesretur**

Skeln mellem sandsynligheden for at være tilgængelig, starte kampen og varigheden af en eventuel start.

En etableret stamspiller, der har misset én kamp, skal ikke automatisk behandles som en langsomt indfaset rotationsspiller. Omvendt må længere skadesforløb ikke automatisk give 90 minutter ved tilbagekomst.

Test en afgrænset rolle- og fraværsafhængig kalibrering.

**B. P(90)**

Undersøg om modellen overvurderer fulde kampe, fordi den undervurderer taktiske udskiftninger, fysisk belastning eller kampsituationens betydning.

Kontrollér definitionen af FPL's registrerede 90 minutter mod simulatorens fysiske minutur.

Bevar fælles startopstilling, 90 målmandsminutter, maksimalt fem udskiftninger og øvrige fysiske invariants.

**Acceptkrav:** En kandidat skal forbedre relevante minutfejl og P(start)/P(60+)/P(90)-kalibrering uden at forværre samlet xP på en meningsfuld måde. Rapportér usikkerhedsintervaller, gruppestørrelser og eventuelle forringelser.

Hvis en kandidat ikke består, skal den forkastes frem for at blive aktiveret.

## Fase 3 – Forbedr angribernes assistkalibrering

Den historiske audit viste:

- 2024/25: 25,9 forventede mod 37 faktiske FPL-assists til FWD.
- 2025/26: 27,2 forventede mod 57 faktiske FPL-assists til FWD.

Undersøg en begrænset korrektion af den eksisterende assistfordeling, baseret på position, rolle og forventet spilletid.

Kontrollér især:

- FPL-assists kontra almindelige Opta-assists.
- Om angribere får for lav assistandel relativt til midtbanespillere og forsvarere.
- Om start-/minutusikkerhed skævvrider assistvægtene.
- Om FPL's særlige assistregler kan forklare noget af forskellen.

Bevar fælles holdmålbudget, gyldig målscorer-/assisttilskrivning og alle PM's hændelsesinvarianskrav.

Forsøg ikke at rette assistfejlen med et vilkårligt positionstillæg eller ved at opfinde ekstra holdmål.

Test kandidatens probabilistiske kalibrering og samlede xP mod den eksisterende PM.

Aktivér kun en ændring, hvis den viser robust forbedring.

## Fase 4 – Integration og tests

Arbejd trinvis:

1. Én aktuel kamp gennem MM → PM.
2. Én komplet GW.
3. Seks GW gennem MM → PM → TS.
4. Relevante historiske regressionstests.
5. Browserkontrol på mobil og desktop.
6. Publicér den opdaterede B-preview, hvis valideringen består.

Gem hver kandidat og dens resultater adskilt fra den uændrede baseline.

De eksisterende historiske perioder har været brugt til modeludvikling. De må ikke bruges som uafhængigt bevis for højere præcision. Bevar den forseglede fremadrettede prognoselog og evaluer kommende GW uden efterfølgende datalækage.

## Afsluttende rapport

Rapportér i en samlet tabel:

- Før/efter Monte Carlo-støj ved 400, 2.000 og 10.000 draws.
- Beregningstid og hukommelsesforbrug.
- Minut-MAE og bias for skadesreturer.
- P(90)-kalibrering for stamspillere.
- Start-/60+-kalibrering og samlet xP.
- FWD-assistkalibrering og effekten på øvrige positioner.
- Hvilke kandidatændringer der blev accepteret eller forkastet.
- Konkrete konsekvenser for Penders og Le Fée.
- Regressionstest, CI-resultater, PR og preview-link.

Skeln tydeligt mellem forbedret simulationsstabilitet og dokumenteret forbedret prognosepræcision.

## Vigtige begrænsninger

- Bevar produktionens 88 filer uændrede.
- Bevar TS v3 og alle låste benchmarks.
- Ingen navnespecifik tuning af spillere.
- Ingen store nye forskningsbranches.
- Ingen ændring af modellen uden dokumenteret test.
- Hvis en kandidat fejler, behold den eksisterende version.

**Arbejd selvstændigt hele vejen gennem implementering, test og publicering. Stop ikke efter den første analyse eller PR-oprettelse.**

Målet er en mere stabil og præcis B-model, som vi efterfølgende kan bruge som fundament for automatisk læring efter hver GW.