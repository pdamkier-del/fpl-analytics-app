# Publication blocker

GitHubActions run45827817575, job139936428268 rejected before steps:

> Branch "integration/app-team-transfers-20261126" is not allowed to deploy to github-pages due to environment protection rules.

The repository environment has custom deployment-branch policies. No policies/permissions were changed or bypassed. Production and Pages files are unchanged. Read-only verification is now separate from protected publication; run45828100909completed that verification and skipped publish. Final code needs a new verification run after fixes.

Owner action: allow this integration branch for the github-pages environment, then explicitly run the existing workflow on this branch with app_completion_preview=true and publish_app_completion_preview=true. A new verification and unchanged-live-baseline guard still precede publication. No production merge is requested or permitted by this delivery.

The intended public URL is /fpl-analytics-app/previews/team-transfers-20261126/app/overview.html, but it is not a working public preview until deployment is approved and verified.
