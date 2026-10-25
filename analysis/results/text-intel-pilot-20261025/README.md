# Lille historisk tekstprøve + forklaringer i det eksisterende spillerpanel

## Resultat

**40 situationer fra 12 klubber i GW22 2025/26 er sammenlignet.** Teksterne er faktisk arkiveret før deadline 17. januar kl. 11.00 UTC. Udvalget blev låst i commit `b3d8513`, før udfald og prognosefejl blev åbnet til scoring. Det er en målrettet gennemførlighedsprøve, ikke en repræsentativ sæsonanalyse.

| Upstream B-MM, de 40 udvalgte spillerkampe | Før | Med eksplicit fraværstekst |
|---|---:|---:|
| Start-Brier, lavere bedre | 0.128460 | 0.102041 |
| Start-log-loss, lavere bedre | 0.376242 | 0.291850 |
| Minut-MAE | 17.8778 | 15.5779 |
| Minutbias | -7.8655 | -9.8177 |

For hele samme origins roster, **799 spillerkampe**, går start-Brier fra 0.068283 til 0.067018 og minut-MAE fra 10.6024 til 10.4809. Minutbias forværres lidt: -0.4256 til -0.4481. Det udvalgte udsnits absolutte bias forværres også. Ingen signifikans, sæsongevinst eller generel accept af en tekstmodel udledes af disse små tal.

### Den konkrete fejl: Marc Guéhi

En arkiveret artikel indeholder Glasners besked om, at Guéhi ikke skal spille mod Sunderland, fordi en transfer er tæt på. Upstream B giver alligevel **94.75 % startchance og 85.29 xM**. Den kildebelagte udelukkelse giver 0/0; det faktiske udfald var ingen start og nul minutter.

Af 16 eksplicitte fravær i prøven havde B allerede håndteret 15 korrekt som nul. **Kun Guéhi får en ny direkte udelukkelse.** Holdets øvrige startsandsynligheder omfordeles gennem den eksisterende projektion, så der stadig er ti markspillere plus én målmand. Andre klubber er numerisk uændrede. Gevinsten er dermed stærkt koncentreret i ét konkret tilfælde og omfordelingen hos Palace — ikke 40 uafhængige beviser for en gevinst. Se `whole-origin-predictions.csv.gz`.

## Hvad blev — og blev ikke — testet?

Den faste, forsigtige intervention fra den forhåndsskrevne protokol er **kun eksplicit utilgængelighed**. Den bruger den eksisterende fraværscap og holdprojektion. Træningsretur, ros, ønsket position eller “mulig udtagelse” bliver ikke til en opdigtet procentforøgelse.

Udvalget indeholder:

- 16 eksplicitte fravær.
- 10 tilgængeligheds-/retursituationer.
- 7 uafklarede situationer.
- Én negativ hierarkibeskrivelse, én gradvis retur og én omtale af minutstyring.
- Fire positive ekspertvurderinger uden et bindende løfte om en start.

Alle fire positivt omtalte spillere startede faktisk. Vi har **ikke** efterfølgende udskiftet dem med spillere, der blev bænket, for at fremstille et ønsket mønster. Denne del af prøven viser derfor ingen falsk positiv ros og kan ikke bruges til at kalibrere et “ros betyder start”-signal. Minutstyringsudtalelserne giver ingen præcis numerisk grænse; der opfindes ingen.

Vi har ikke testet en bred sprogmodels samlede rollefortolkning, lært nye tekstvægte eller ændret den aktive model. Der er ikke kørt en kandidat gennem final fælles rolle-/målmandsfordeling, fysisk minutkernel, PM/xP eller TS; tabellens minutter er **upstream MM's**, ikke en påstand om en valideret fuld MM→PM→TS-forbedring. Ingen xP-gevinst rapporteres.

## Hvordan ved vi, hvad der stod før kampen?

To arkiverede offentlige tekster kunne verificeres:

1. Fredagens GW22-holdnyheder, arkiveret **16. januar 2026 kl. 16.12.45 UTC**.
2. GW22 Scout Picks, arkiveret **17. januar kl. 07.52.57 UTC**.

Begge er før deadline kl. 11.00 UTC. Den hentede originale HTML's SHA-1 i base32 er **identisk med Internet Archives CDX-digest**, og replayets Memento-tid stemmer med arkivet. De to komprimerede originale HTML-versioner er bevaret i `source-archives/`; SHA-256, CDX og replaykvitteringer findes i `archive-receipts.json`.

En tredje, ellers relevant Scout Squad-side gav en anden body-digest end CDX. **Den blev afvist**, og ingen case bruger den. Et ratebegrænset Wayback-availability-kald blev ikke forsøgt omgået. Protokollens tilbagefald til ukvalificeret nutidig artikeltekst var ikke nødvendigt for de 40 scorede cases.

Spilleridentiteter kommer fra den eksisterende, strengt før-deadline FPL-arkivregistrering til GW22. Manuelt gennemgåede, eksplicitte navnealiaser bevares i udvælgelsesscriptet. Alle 40 matchede præcis én historisk spiller/klub/kamp. Det blev ikke brugt, om spilleren senere startede eller scorede. Efter ændring fra lokale HTTP-filer til de bevarede komprimerede arkiver reproducerer casefilen præcis den allerede låste SHA-256.

Udvalget er håndannoteret og beriget med relevante hændelser. Det er ikke en blind, uafhængig måling af en automatisk tekstklassifikators præcision, og stikprøven fordeler sig ikke på alle fire planlagte GWs: tilstrækkeligt materiale fandtes allerede til GW22. Vi stopper ved 40 som aftalt frem for at udvide til en hel sæson.

## I appen: forklaring før utestet prognosepåvirkning

Det eksisterende desktop-spillerkort får sektionen **“Holdnyt og rolle”**. Den viser:

- Originalt kildeuddrag, artikeldato og kildehenvisning.
- En separat dansk vurdering med betingelser og usikkerhed bevaret.
- Om oplysningen gælder en tidligere kamp, en dateret status eller en længerevarende rollebeskrivelse.
- En tydelig besked om, at teksten endnu ikke ændrer xMin/xP.

Første datasæt indeholder **10 gennemgåede udsagn om 9 spillere**, bl.a. Cherki, Penders, Haaland, Elanga og Wirtz. Det er de faktisk gennemgåede aktuelle 2026/27-kilder fra de foregående prøver, **ikke** de historiske 2025/26-cases flyttet til den aktuelle trup. Alle 20 klubber har desuden en separat, sammenfoldet klubkontekst fra GW8, tydeligt markeret som historisk og ikke en individuel GW9-besked. Ingen ny individuel besked opfindes for spillere uden kilder.

Det er et begrænset første datasæt, ikke et automatisk live-nyhedsfeed. Gamle kampoplysninger bliver ikke til nye fraværsbeslutninger. Oplysninger fra en tidligere klub vises ikke automatisk ved et klubskifte. API-loaderen verificerer indeks/kontrolsum, kildedomæner, tider, skema og fravær af aktive modelflag. HTML-tekst indsættes med `textContent`; kilder åbnes separat. Fejl eller manipulerede data skjuler kun tekstkonteksten, ikke prognoserne.

Layout, otte sandsynlighedskort og tidligere/næste kampe beholdes. Brugerens hold og priser skrives ikke. Den numeriske B-model og produktionen ændres ikke.

## Genkørsel

```sh
PYTHONPATH=src:scripts:. /workspace/fpl-venv/bin/python analysis/select_text_intel_pilot.py
PYTHONPATH=src:scripts:.:analysis /workspace/fpl-venv/bin/python scripts/locked_numerical_runtime.py analysis/score_text_intel_pilot.py
PYTHONPATH=src:scripts:. /workspace/fpl-venv/bin/python scripts/build_player_text_context.py
node tests/test_player_text_context.js
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python -m pytest -q tests
```

`selection-lock.json` skal fortsat matche casefilen. Scoringen afviser et forkert arkivdigest eller et arkivtidspunkt på/efter deadline. Den bygger ikke en ny baseline: original frosset B og eksisterende projektion genbruges.

Lokal validering: **1.018 Python-tests bestået** (58.01 sekunder), JavaScript-datakontroller bestået, desktop/mobile-browserkontrol bestået. Browseren verificerer bevarede betingelser, særskilt vurdering, historisk scope, uændrede sandsynlighedskort, intet overløb, ingen privat POST og uændret lokal holdlagring. En forfalsket tekstfil afvises, mens prognosen forbliver synlig. Originale numeriske forecast-/GK-filer er byte-identiske efter lokal genopbygning. Offentlig releasekvittering tilføjes efter publicering.
