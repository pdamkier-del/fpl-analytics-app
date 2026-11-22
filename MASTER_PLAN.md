# FPL Research Lab — start her

Den fælles retning og etapeplan findes i **[research/MASTER_PLAN.md](research/MASTER_PLAN.md)**.

**C1 (Codex modelarbejde) starter altid med [research/C1_README.md](research/C1_README.md)** — afkrydsningsliste, videnskabelige krav, historisk evidens og præcis første opgave. C1-filen suppleres af det officielle forskningsregister; afkrydsning alene ændrer ikke et eksperimentresultat.

Før næste arbejde:

```sh
python research/tools/registry.py validate
python research/tools/registry.py status
python research/tools/registry.py next
```

Læs derefter [research/SESSION_HANDOFF.md](research/SESSION_HANDOFF.md). Gennemfør ikke PR #41/#42's allerede afsluttede forsøg igen. Integrations-WIP ligger særskilt i draft PR #43 og er ikke release-klar. Denne branch ændrer kun forskningsplan, registry og deres kontrolværktøjer.
