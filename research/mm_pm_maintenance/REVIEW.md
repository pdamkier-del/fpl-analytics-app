# C1 → C2: reviewed activation contract, 25 November 2026

PR55 is OPEN, unmerged, head4740721349cb6941d98b27bab86a1ac38ec28fc5. Its sole observed evaluation run45184237876is pull_request verification, success, publication skipped. Main remains d4d6e804; no main evaluation wrapper exists. Workflow API state=active only registers its identity: it does not prove an installed main schedule. Existing natural public archiving is active; latest observed run45595239869failed at original-artifact/permanent-recovery consumption. Public annotation says archive incomplete. Log/status artifact redirect access failed; exact underlying cause is not verified. Do not infer that the existing valid Release was deleted or every newer issue archived successfully.

## Required before activation — small integration, not a model change

1. Independently review this implementation correction and PR54scientific rules. No merge/dispatch/publication performed by C1here. PR55already requests scientific implementation review; do not bypass it.
2. Update PR55's evaluator checkout pin to the reviewed C1maintenance commit containing run_online_v3.py. Keep the C2archive dependency d4d6e804and its byte checks. Keep original scientific registration/protocol/cutoff/window/labels/metrics and source MM/PM/TS unchanged.
3. In the read-only verify job run:
   `python -m pytest -q research/mm_pm_live/tests research/tests research/mm_pm_maintenance/tests --deselect=research/tests/test_registry.py::test_all_evidence_and_protected_protocol_validate`
   The maintenance suite replaces the obsolete65count with event/protocol integrity checks and includes event-time reconciliation validation. The broader `python research/tools/verify_current.py` additionally supersedes the old Stage0eleven-reconciliation snapshot. The old files/manifests/results are retained; no weakening of tamper/cycle/privacy/finality assertions.
4. Change the evaluation command from run_online_v2.py to run_online_v3.py. This only adds audited1e-12boundary-roundoff normalization at scoring time. Raw forecasts and original files remain unchanged; substantive invalid values/NaN/infinity still fail. Exact-valid probabilities produce exactly identical metrics. Corrections count/max magnitude are retained in each new report. The implementation hash versions reports; old reports would never be rewritten. No old real results were rescored.
5. Preserve PR55's verify/read-only versus publish/contents-write separation, successful same-repo main archive gating, daily fallback, PRpublication denial, shared concurrency, pinned dependencies and no Pages/model/private path. Existing main does NOT inherit research workflow changes automatically.
6. Before GW12cutoff27Nov17:30UTC, C2diagnoses the failed archive status using authorized logs/status artifact or reruns existing read-only recovery checks; never replace originals or fabricate a predeadline issue. After reviewed merge retain first main verify/evaluate run/status receipt. No actual complete future score/report publication is certified yet.

## Why v3 is necessary

Fresh original post-registration issue9e03db63/forecast4ff695e3recovers and fully validates, but its MMrows contain363p_play values just below0(up to2.220446049250313e-15). Pinned v2metrics.probability rejects them, so activation of v2alone would reach a scoring-contract failure once GW12is final. This is input-only detection, not new accuracy evidence. v3uses the unchanged score functions in a serial, exception-safe context, canonicalizing only[-1e-12,0)and(1,1+1e-12]at score evaluation; no fitted/model correction. Tolerance is numerical infrastructure, not a football parameter. Scientific protocol and registered baseline/primary endpoints remain unchanged. Review is still required.

No deployment or private-storage change is authorized/implemented in this research maintenance PR. C2handoff is this concrete checklist plus public receipts; no private manager payload or external message is sent.
