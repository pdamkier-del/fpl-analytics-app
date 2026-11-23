# Implementation and immutable observation contract

This is infrastructure for existing EXP-MM-LIVE-001, new EXP-PM-LIVE-001 and
OPS-EVAL-001. The original64registrations stay byte-identical. Phase4does not
repurpose PM-CS-BPS or create another duplicate DCstudy: identified DCawards are
a secondary endpoint of the new frozen-PMstudy, as recommended after PR49.

The registered PROTOCOL remains unchanged. Operational clarifications fixed
before any new outcome evaluation:

- The16-origin window stores the original first-selected issue's full official
  calendar and fixes the final lock from its last-origin deadline plus30days.
  Later outcome inspection never moves that clock.
- After the lock, primary analysis reads only versioned research reports retained
  by that instant. It does not fetch new late labels; outages produce an
  inconclusive primary dataset. Subsequent provider corrections need a separate
  sensitivity record. The first final primary record cannot be overwritten.
- Original current-season count baselines are unavailable while the original
  club has a kicked-off but unfinished fixture: aggregate official totals may
  then contain provisional exposure not matching the completed-match denominator.
  This is a predeadline data-quality guard, not an outcome-selected reference.
- Every report contains the original selection, protocol/implementation and label
  hashes. Retrieval clocks do not manufacture another semantic outcome revision.
  The first retained raw label snapshot for a semantic revision is preserved;
  changed official values produce a separate report. A partial upload with no
  record asset can be completed; differing existing records are never clobbered.
- Missing original/label contracts yield blocked/partial rows and fail the report
  job rather than silent zeros. A catastrophic partial run reports unknown score
  count, not a false0. Pending future events fetch only official finality flags,
  never their event-live results. No conditional resimulation or model calls.

## Existing code reused

- PR53public `archive.py`/`releases.py`, configuration and frozen export, loaded
  from exact main d4d6e804with transitive file hashes: original publication,
  raw-byte, source, scenario, official deadline and recovery checks stay intact.
- PR41/43empirical CRPS and original canonical point-award mapping. The older
  reporter assumed some per-fixture starts/labels; this adapter explicitly gates
  DGWstarts/history and closed-world DNPzeros instead of repeating that limitation.
- PR49 PM-COMPONENTS-1.0.0 canonical totals and DCthreshold contracts. Nonlinear
  save buckets, bonus/BPS and CSqualification semantics are not redefined.
- Existing official completed-GWcollector payload and public API transport.
  `element-summary` supplements only the missing DGWfixture starts/BPSlabels.

## Proposed automatic cycle

The separate research workflow is a consumer of the original public archive,
not a forecast producer. It can run after archive completion and daily. It has
no app deployment/private endpoint/model runtime dependency. Tests run first;
new study state, selections and evaluation reports use public prerelease assets
under `fpl-research-mm-pm-v1-*`, outside the forecast namespace. Pending status
remains an operational artifact, not a fabricated efficacy result.

This workflow is supplied in the research PR, not deployed by modifying main or
merging the old research/app stack here. Activation needs reviewed integration
of this research code/registry. Before that, reproducible CLI plus local live
archive-link/finality verification is the actual tested scope. No claim that
main is already automatically publishing scientific reports.
