# Personal-first B dashboard and complete private history refresh

The existing B desktop shell now puts manager-ID connection, the latest publicly available official squad, fixture-by-fixture player xP/minutes/start probabilities, official player status and recent personal rounds first. The saved local squad/plan remains separate and unchanged. League fixtures, Players and Clubs follow; Model Explainer is last in both navigation and dashboard. Historical round links open the saved old team.

The ID service imports all available current-season official picks, autosubs, points, transfer costs, bank/value, transfers and chips, plus available past-season totals. It cannot read unpublished predeadline changes or unavailable past-season squads. The refresh runs the existing historical manager-review implementation privately against immutable shared predeadline inputs and aligned PM draws. Currently validated replay packages cover GW6–8. Missing analyses are explicitly unavailable. Retrospective replays never masquerade as recommendations actually saved before deadline. Original TS search and hindsight labels/limitations remain.

Shared replay inputs are pinned by full commit and SHA-256 manifest; per-file hashes, historical market/forecast identity, original frozen forecast values, actual-history seals and legal-plan rescoring are checked. The numerical worker runs separately under the existing locked runtime. Capability-key jobs remain private, no-store and time-limited. Official current player status is fetched during the ID refresh, separately timestamped from model data. The new shared browser client checks server capability before POST and preserves resumable receipts until the validated archive commits.

Validation:
- Full Python suite: 1,095 passed; final targeted history checks: 11 passed. Earlier adapter checks: 23 passed.
- Real local HTTP/CORS job: eight completed official weeks, three complete historical analyses and 15 fresh owned-player statuses; 8.18 seconds. Joint-PM own-team xP and actual scores exactly match the previous verified private review.
- Equivalent clean Docker COPY file layout exercised successfully; a Docker image was not built in this environment.
- Desktop/mobile browser checks: personal-first ordering; last explainer; private ID refresh; old-team links; original six-GW transfer result; source timestamps; news; probability dialogs; player profiles; original team editor; unchanged private state/plan; no overflow or JavaScript errors.
- A real-user import was rendered privately with 15 players, three reviewed rounds and fresh official player statuses. Personal data and its screenshot are outside the repository. Committed screenshots and dashboard fixtures are synthetic only.
- No `src` model changes. Local preview numerical files were copied byte-identically from the published verified B preview, not recomputed.

Publication state must be read from the deployment receipts: local checks do not establish that GitHub Pages or Render activated the new version. The existing production model remains unchanged.
