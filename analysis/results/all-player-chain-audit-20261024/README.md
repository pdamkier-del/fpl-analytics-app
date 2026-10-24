# Audit evidence and the minute-clock correction

The first auditor version incorrectly classified reported/modelled minute sums
different from 900 as a physical defect. **That criterion is withdrawn.** FPL
historical labels have a median outfield team total of 897 in both reviewed
seasons with complete minute/red labels and no recorded red card.

- `current/`, `reference/`, `local-complete-source-proof.json` and the initial
  local post-export receipt retain the original version's observations. Their
  equality-to-900 physical verdicts must not be used as current conclusions.
  Their model/source hashes and numerical identity observations remain scoped
  to those original captures; GK source coverage was strengthened afterwards.
- `minute-clock/observed-FPL-minute-totals.json` documents the read-only Core
  check and its source hash. It does not assert a fully validated provider
  rounding or added-time conversion rule.
- Auditor **v2** separates source/individual moment checks from substitution
  count lower bounds and an unverified physical timeline. It never certifies
  a timeline merely because reported totals happen to equal 900. Known GK
  substitutions count towards the standard five-substitution check.
- The physical repair trial's measured errors remain in the adjacent
  `physical-timeline-20261024/` directory. It remains inactive. Its forced
  900-minute grid was compared directly with FPL labels, so its rejection is
  not proof that every correctly measured joint timeline must be worse.

See the [corrected audit](../../../docs/audits/2026-10-24-all-player-chain.md).
Public release receipts are recorded separately after actual deployment and
browser/service checks. None of these files contains a private user team.
