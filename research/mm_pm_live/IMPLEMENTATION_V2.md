# Archive I/O revision 2 — before prospective outcomes

The protocol, outcome adapter, scorer, baselines, window, selection and inference are unchanged. The v1 preflight at commit e7a7dade recovered an actual original archive and observed zero eligible post-registration issues. Its files, manifest and receipts are retained. Reproduce v1 at that commit; its manifest includes the then-current proposed workflow.

Before activating automation, inspection identified repeated all-release scans in the existing C2 backend's find operation. v2 adds only a per-process release metadata index and an immutable asset-ID/digest byte cache. Uploads refresh the affected release. Nothing persists between cycles. Original C2 recovery and hash validation still run. This reduces repeated metadata pagination; it does not establish a production throughput benchmark. The original API remains unchanged.

run_online_v2.py differs from v1 only in its docstring, archive-runtime import and manifest filename. A test enforces that exact transformation. The v2 manifest freezes this version and its tests before the v2 live archive-link preflight. No outcome-based revision or optimization occurred. The report workflow is proposed on the research branch only, not activated on main.

One inherited TS research test now permits precisely the new report-consumer workflow in its repository scope assertion. No archived TS evidence, numerical test, model or original protocol changes.
