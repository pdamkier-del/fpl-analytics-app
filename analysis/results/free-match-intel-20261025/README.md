# Gratis kampinformation: fungerende indsamler og første liveprøve

25. oktober 2026. Afgrænset prøve, ikke aktiveret i appens model. Ingen betalt API, konto, abonnement, privat holdtilstand eller officiel FPL-handling.

## Hvad er lavet?

`scripts/free_match_intel.py` genbruger den eksisterende FPL-nyhedsbygger og Fantasy Football Pundit-parser. Den tilføjer:

- Append-only indsamling af FPL-bootstrap/kampprogram, RotoWire, Sports Moles optaktoversigt og Pundits opstillingsside. En valgfri Sports Mole-artikel kan hentes, hvis den findes i den indsamlede oversigt. HTTP-kilder får tidspunkt og SHA-256; arkivreplay kræver identiske bytes.
- RotoWire-opstillinger matches på præcis hjemme-/udeidentitet og kickoff UTC. Sidens ET-tid oversættes med `America/New_York`, inklusive forskellen mellem EDT og EST. Allerede startede kampe afvises.
- `not_posted`, `editorial_prediction` og `provider_reported_confirmed` er særskilte kategorier. En leverandørs “confirmed” bliver ikke til uafhængig officiel bekræftelse.
- En redaktionel XI kvalificeres kun som en komplet ekstern XI ved præcis elleve forskellige, entydigt matchede spillere på den verificerede nuværende klub. Ingen efternavns-/initial-/fuzzy-match. Dette er stadig en kildes mening, ikke en kalibreret startsandsynlighed eller godkendt MM-feature.
- Skades-/suspensionsmærker holdes adskilt fra XI-listen. De bevares som leverandørpåstande sammen med den særskilte officielle FPL-status; der udledes ingen skade, hvileårsag eller hård udelukkelse.
- Sports Mole-artikler får overskrift, udgivelses-/ændringstid og kildeangivne mulige opstillinger. Manglende/uklare spiller- og kampidentiteter bliver ikke gættet. En pokaloptakt må ikke blive en PL-opstilling.
- Pundit genbruges til kontrol af GW-friskhed. Den eksisterende parser mangler den præcise fixture-/spillerkobling fra denne prøves kontrakt og bliver ikke gjort modelberettiget.

Alle nye modelinputflag er **false**. Der er ingen import i den aktive MM→PM→TS-kæde, ingen appintegration, ingen automatisk tidsplan og ingen deployment.

## Første faktiske resultat

Hentet **25. oktober kl. 20.33 dansk tid**; den særskilte artikel kl. **20.37**. De præcise UTC-tidspunkter, URL'er og kontrolsummer er i `report.json`.

| Kontrol | Resultat |
|---|---|
| Officiel næste runde | GW9, deadline 31. oktober kl. 12.00 dansk tid |
| Officielle GW9-kampe | 10 |
| RotoWire-kampe matchet til GW9 | 8 / 10, 16 holdsider |
| Redaktionelle, komplette og identitetsmatchede XI'er i GW9 | **0** |
| RotoWire-status på de 16 holdsider | Alle “Unknown Lineup” / ikke offentliggjort |
| Manglende GW9-kampe i denne RotoWire-side | Liverpool–Arsenal og Newcastle–Everton; ingen opfundne erstatningsbud |
| Pundit | Alle 20 opstillinger afvist som gamle GW8-opstillinger |
| Sports Mole-oversigt | 17 artikelhenvisninger; oversigten er ikke dokumenteret komplet |
| Konkret Sports Mole-artikel | Fleetwood–Arsenal i League Cup, publiceret 25. oktober kl. 12.10 dansk tid; opdateret 12.29 |

Sports Mole-optakten har to lister med elleve spillernavne. De er **ikke** verificerede spiller-ID'er, kampprogramkoblingen er **ikke** bekræftet, og listen gælder ikke næste PL-kamp. Den kan bruges som kildehenvisning og eksempel på redaktionel information, ikke til at overføre et startbud direkte til MM.

RotoWire gav også 82 kildemærkede fraværsposter på de 16 holdsider; 72 havde entydig nuværende FPL-klub-/navnekobling, 10 forblev uafklarede. Det er **ikke 82 bekræftede skader**. Kategorier kan omfatte tvivl, suspension og andre statustyper, og leverandørens klub-/statusoplysninger kan afvige fra FPL. Ingen af posterne ændrer hårde tilgængelighedscaps.

## Hvad har vi lært?

Gratis information kan hentes og afgrænses teknisk. Den konkrete aftens data giver endnu ingen frisk, verificerbar ekspert-XI for næste runde. At acceptere Pundits gamle bud eller behandle RotoWires manglende bud som lav startchance ville indføre en fejl. Prøven gør ingen af delene.

Det er for tidligt at måle, om disse kilder forbedrer P(start), xM eller xP. Der er ingen konstrueret historisk gevinst: et dokument hentet i dag kan ikke bruges som dokumentation for, hvad modellen vidste før en tidligere deadline. Indsamleren er klar til nye, separate snapshots nær en kommende deadline; den er ikke sat til at køre automatisk. Ingen ekstra sandsynlighed indføres, før der findes faktiske predeadline-snapshots og en generel sammenligning.

Officielle klub-/pressekonferencecitater er ikke automatisk struktureret af denne prøve. Den genbrugte officielle FPL-kilde bidrager med faktisk registreret status/nyheder; den er ikke en generel NLP-fortolkning af interviews. Kildernes indbyrdes uafhængighed er heller ikke verificeret: to ens opstillinger tæller ikke som to uafhængige beviser.

## Gentag prøven

Brug altid en **ny** arkivmappe. Følgende er en manuel, gratis indsamling, ikke en appopdatering:

```sh
PYTHONPATH=src:scripts:. /workspace/fpl-venv/bin/python scripts/free_match_intel.py \
  --capture --archive /workspace/scratch/free-match-intel-NEW \
  --out /workspace/scratch/free-match-intel-report-NEW
```

Tilvalg: `--article-url URL`, hvor URL'en skal findes i Sports Moles netop hentede oversigt. Ved kildefejl afbrydes prøven; den genbruger ikke en gammel XI som en frisk. Originale fulde webcaptures fra denne prøve ligger lokalt i `/workspace/scratch/free-match-intel` og er ikke lagt i repoet. Rapporten beholder kvitteringer og strukturerede uddrag. Nye hentninger får nye tidsstempler og kan ikke forventes at reproducere gamle webbytes.

```sh
PYTHONPATH=src:scripts:. OPENBLAS_NUM_THREADS=1 /workspace/fpl-venv/bin/python -m pytest -q tests/test_free_match_intel.py tests/test_predicted_lineup_source.py tests/test_dashboard_news.py
```

Målrettet validering: **21 tests bestået**. Dækker kildeklasser, 11 unikke identiteter, forkert klub, tvetydige navne, kickoff-/modstanderkobling, afvisning efter kampstart, EDT/EST, ukendt XI med skadesliste, artikelure, cup/PL-adskillelse, discovery-domæne og kildekontrolsum. Se `verification.json` for den endelige regressionsstatus og kode-/rapporthashes.

Produktionsmodellen, B-prognoserne, appens layout og brugerens hold er uændrede. Der er ingen ny preview at publicere for denne selvstændige indsamlingstest.
