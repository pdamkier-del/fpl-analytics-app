# Privat TS-logning uden ændring af app eller model

En separat logger er implementeret og testet i `code/private_ts_ledger.py`. Den læser allerede producerede originale forecast-/TS-resultater og en eksplicit managerbeslutning. Den kalder ingen model, ændrer ikke TS, udfører ingen transfers og sender intet til GitHub eller en ekstern tjeneste.

## Etableret nu

Et tomt privat ledger er initialiseret på `/workspace/shared/fpl-ts-private-ledger`, uden for projektets Git-worktree, med mappeadgang 0700. Nye filer oprettes 0600. Det ligger ikke i denne branch og er ikke en GitHub Actions-artifact. Ingen reel managerbeslutning er indlæst eller opfundet. GW11-deadline er passeret; historiske data kan derfor ikke optages som nye før-deadline-logs.

Dette er en fungerende lokal sidecar med eksplicit capture-kald — ikke en påstand om, at appens eller Render-jobbets output allerede overvåges automatisk. En automatisk produktionshook er ikke aktiveret, fordi app-/produktionsintegration er udelukket i opgaven. Workspace-lagring er ikke i sig selv en garanti for varig backup.

## Optagelse ved næste gyldige TS-beregning

Bevar forecast, managerstate og uændret TS-resultat fra samme beregning lokalt. Eksportér desuden managerens faktiske tiltænkte beslutning før deadline; den må ikke udledes af modellens anbefaling uden et valg fra manageren. Det er en intention/nomination, ikke verificeret eksekvering af en transfer.

```sh
python analysis/followup-41-20261122/code/private_ts_ledger.py capture \
  --root /workspace/shared/fpl-ts-private-ledger \
  --forecast /PRIVATE/forecast.json \
  --state /PRIVATE/manager-state.json \
  --plan /PRIVATE/original-ts-result.json \
  --decision /PRIVATE/manager-decision.json
```

`/PRIVATE/...` er pladsholdere; ingen rigtige managerfiler lægges i repoet. Kaldet placeres efter en isoleret TS-kørsel, hvis før-deadline-output er tilgængeligt. Loggeren afviser capture efter deadline, en for gammel prognose, manglende fuld seks-GW-horisont (undtagen sæsonslut), ugyldig forecast-hash, forkert state-hash, manglende FT/bank/købskurser/chiphistorik, manglende hold-kontrol og ulovlig XI/kaptajn/bænk. Der er ingen CLI-mulighed for at vælge et gammelt issue-tidspunkt.

Managerbeslutningens schema:

- `source`, `observed_at`, `semantics="intended_predeadline_not_verified_execution"`.
- `choice`: `keep_squad`, `follow_plan` eller `custom`.
- `rows`: 15 egne player-ID'er med præcis én `C`, én `VC`, ni `XI`, én `BGK` og `B1`, `B2`, `B3`.
- `incoming`, `outgoing`: skal stemme med forskellen fra inputtruppen.
- `active_chip`: null eller tilgængelig `wildcard`, `free_hit`, `bench_boost`, `triple_captain`.

## Hvad gemmes?

Det fulde sealed forecast med seks-GW-horisont og dets fælles scenarier, issue/deadline/cutoff, managerstate med trup/købspriser/FT/bank/chiphistorik, uændret TS-anbefaling, kaptajn/vice/bænk, plansti, chipstatus, den konkrete managerintention og eksisterende `comparison.hold_squad_without_transfers` for alle horisont-GW.

Hold-kontrollen er originalplanlæggerens forventede scores ved ingen transfers, med planlæggerens XI-/kaptajnvalg. Det er ikke samme ting som en uændret manager-XI. Den originale bridge gemmer ikke alle seks kontrol-XI'er; hele kildescenariet og managerstate bevares, så de kan reproduceres med den samme frozen engine uden nye inputs. Loggeren erklærer derfor ikke de manglende kontrol-XI'er eller fremtidige udførte handlinger som verificeret.

## Integritet og privatliv

Hver fil er append-only med tilfældigt navn og nonce; et privat hashkædet indeks, filhashes, låsning og fsync afslører efterfølgende fejl/ændringer. En reel Git-worktree som destination afvises. Ingen offentlig eksportfunktion findes; stdout er kun en generisk status/tælling og fejlmeddelelser viser ikke payload eller filstier.

```sh
python analysis/followup-41-20261122/code/private_ts_ledger.py verify \
  --root /workspace/shared/fpl-ts-private-ledger
```

Filerne er ikke krypterede; privathed bygger her på adgangsrettigheder og at de aldrig indlemmes i Git/CI-artifacts. En komplet omskrivning udført af den samme lokale administrator kan ikke uafhængigt afvises af en lokal hashkæde. Derfor markeres hver optagelse `local_system_clock_only_not_independent_timestamp`. En eventuel senere betroet tidsattest af saltede commitments kræver særskilt afklaring; ingen private data skal publiceres for at dokumentere tidspunkt.

## Hvad kræves for første rigtige datapunkt?

Et nyt gyldigt forecast og det matchende TS-resultat før en kommende deadline plus et faktisk managerstate og en eksplicit beslutning. Tidligst GW12, hvis dette eksisterer i tide. Et tomt initialiseret ledger eller testernes syntetiske fixtures tæller ikke som observationsdata. Ingen historiske beslutninger genskabes med dagens model.
