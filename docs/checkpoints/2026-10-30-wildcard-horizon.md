# WC recommendation / six-GW integration

User reported WC-now card with only normal no-chip six-GW path. Cause confirmed: frontend always renders plan.plan.path; existing service.manager_job computes WC followup then exports totals only.

Implemented UI463d9b0e2c55b01a8e4ad11e26d7c29ce8fc5b7d on existing experiment branch/PR22. B-only additive wildcard_followup.schema/gw/squad_ids/path exports exactly the existing computed followup; no new search or math. Original non-B numerical outputs unchanged. service/app advertises supports_B_WC_horizon, original B worker SHA remains unchanged. Normal model src unchanged.

Frontend WC choice opens actual WC XI/captain/bench and WC-specific six-GW horizon. Normal plan/lineup/insights/risks/details are a closed no-WC alternative. FutureGW/squad/finite fields/total consistency validated. Old cached results explicitly lack path, never borrow the normal path; capability-checked Beregn WC-forløbet button triggers existing force recompute only after server flag is true.

Full1097 Python tests passed50.99s. Focused export regression confirms B/non-B numerical decisions/totals identical. Current real B forecastCF shared draw chain on synthetic fixture ran66.38s, coordinator genuinely choseWC, all futureGW10–14 and totals correct; output /workspace/scratch/wc-full-B-result.json and fixture wc-ui-synthetic-fixture.json are synthetic, not user data. Real-B browser and synthetic presentation browser pass desktop/mobile, normal-result regression passes. Public-safe proofs/screenshots analysis/results/wildcard-horizon-20261030.

Backend prepared atomically on existing free-github-static-20261010 at d8f8ba33944393ee4cd80571e7d0d58649507562 (only service/app.py and manager_job.py; guards checked prior source matches). Expected adapter0622afb4e426d6162cbfc621543f24f4d6a8cf18908e2b91d81c2438de55abea. Automated Render attempt41031576312 FAILED RENDER_DEPLOY_ACCESS_NOT_CONFIGURED. Owner was asked via async input to Manual Deploy latest commit d8f8ba3 on existing service; DO NOT ask for tokens/login. Continue UI verification while waiting. Old live backend flagfalse; do not claim full WC export live until true.

Guarded UI publication41031570563 running, uses current exact-source numeric40992939652. UI pin463d9... normal math03... Full browser gates include updated verify_transfer_chip_advice. Wait for success and then run public browser checks with current synthetic fixture. Can test actual B output via verify_wildcard_real_chain without a new server request; no private manager data needed. Remote Render activation verified by health supports_B_WC_horizon true and exact adapterSHA; older user cached plans require Beregn WC-forløbet/force recompute (not just reveal old normal path).

## Delivered, after owner activation

Owner replied done. Exact backend adapter0622afb4e426d6162cbfc621543f24f4d6a8cf18908e2b91d81c2438de55abea now live, supports_B_WC_horizon true; existing full history, snapshot policy and original B worker SHA remain correct. NO further Render deploy/admin action needed.

UI publication41031570563 succeeded. Actual public desktop/mobile browser checks passed for both real B-chain output on synthetic state and synthetic edge cases. All6 WC scores match actual exported decisions, WC XI visible, normal plan collapsed/separate, old-cache missing-path message explicit, current state/plan unchanged, no privatePOSTs/errors/overflow. Exact frontend source463d9... verified,3 numerical files unchanged,88 production files match retained artifact. Receipts backend-live.json, public-verified.json, real-B-browser-public.json, chip-browser-public.json.

User must use Beregn WC-forløbet on an OLD cached WC result (or existing Beregn igen). Updated UI deliberately does not fabricate a WC path from the normal cached path. This runs the existing private original B chain with additive export and does not execute any official FPL action. Current recommendation may change if state/forecast changed, but no model parameters were changed here. Direct app transfers-classic.html?update=wc463d9b0e. Do not claim user's device storage was remotely recomputed by our tests.
