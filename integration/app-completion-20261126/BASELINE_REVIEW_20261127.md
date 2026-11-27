# Reviewed production advance — 27 November 2026

## Actual publication, not just a replacement SHA

The failed run 45981181923 correctly detected that deployment 8082385148 / SHA 140e3f88 was no longer current. The latest successful deployment reviewed here is **8102173525**, SHA **d4d6e8046ad5d965cf41f5a8fce2b32a49fca16c**, published by the scheduled team-news workflow run **45942704018**, job **140320366222**. The workflow delegates to `mm-team-news.yml` pinned at `9c5095e7802af7414b51b3c81578b71000dbd025`. Its actual deploy-pages input is `team-news-pages-45942704018`.

Downloaded that actual artifact (ID **15172374950**) through the GitHub connector because the local network proxy rejected GitHub's redirected artifact URL. The downloaded ZIP is 455,907,668 bytes and its independently computed SHA-256 is **4ec6bd3cb15cda495fc20cfcf26676824744dadc0c3597c5a44fdc6fd3a86b85**, matching GitHub's artifact digest. The ZIP contains `artifact.tar`. Inspected and hashed all **3,746 regular files**, 561,425,067 bytes, with no absolute/traversal paths, symlinks or duplicate paths.

`baseline-20261127.json` records the actual deployment/run/job/workflow, artifact identity/digest and SHA-256 of every file. No manager data was added to this record.

## Comparison with PR #60's previously reviewed publication

The old Pages artifact is no longer available from run 45799693765. The prior reviewed generated publication mirror `50e39d8cd8aca1ed3545919628c6a3f890fc336b` remains available in Git; compared its complete `app/` tree to the downloaded current artifact using Git blob hashes computed from the actual bytes. Do not confuse this comparison source with recovery of the expired artifact.

See `evidence/baseline-comparison-20261127.json`: **3,724 files unchanged, 14 changed, 8 added, zero removed**. All `mm-preview/app/` code, original TS/forecast guards, the current original six-GW forecast and MM/PM/scenario payloads match the earlier reviewed mirror. Within `mm-preview/`, only the availability news and publication receipt changed. Root-level HTML/status/diagnostic changes and eight newly present production files are retained without alteration, including `tc-samples.csv.gz`, current players, fixtures and historical statistics. The preview never copies the old Git tree over production.

Executed the existing preview builder against UI files extracted from the new artifact; all exact renderer/importer anchors still match. No UI patch reimplementation or model/configuration change was needed. The full CI build uses the complete new artifact, not that local UI-only extraction.

## Stronger publication controls

- Resolve the exact reviewed deployment ID **and** SHA; verify successful workflow provenance and exact artifact ID/name/size/digest/expiry. Same-SHA later news publications now cause rejection too.
- Verify the complete downloaded original-file inventory before building.
- Append the isolated preview. Refuse a pre-existing destination instead of deleting it. Check every original file again after building.
- Under the existing Pages publication concurrency lock, resolve the current production deployment again and rehash every original file in the tested site before upload. Only files under the isolated preview prefix may be added.
- If production advances at any point, stop and perform another content review; no automatic SHA acceptance.

These controls preserve every current production file, including newer root changes, and keep original model/source/sampling/weights intact. The publisher remains the existing protected github-pages job with both preview flags required. No PR merge, permission change or alternate deployment path is involved.

## Reproduction and acceptance

```
python integration/app-completion-20261126/reviewed_baseline.py resolve
python -m unittest discover -s integration/app-completion-20261126 -p 'test_reviewed_baseline.py'
node integration/app-completion-20261126/test_team_model.cjs
node --test integration/model-interface/*.test.js
python -m pytest -q integration/model-interface/test_preview_server.py integration/model-interface/test_archive_preview.py
```

Eight new publication-contract tests cover same-SHA deployment advancement, changed commit, failed deployment, artifact mutation/expiry/missing, wrong workflow and file preservation/path/symlink restrictions. CI then uses the downloaded complete artifact for the builder and Chromium checks. The existing original TS freshness and manager-state gates remain active; successful page delivery is not a claim of an available real TS recommendation.
