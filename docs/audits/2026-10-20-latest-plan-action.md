# One-click latest transfer plan

The B transfer page's primary action now says **Vis nyeste transferplan**. A click explicitly invalidates the adapter's short-lived cache, verifies the latest sealed model snapshot, refreshes news and private manager state, and displays the saved plan if it remains valid for those exact inputs. It scrolls the recommendation into view without repeating an already valid private calculation. It does not reconfirm or modify actual squad, bank, FT, prices, chips or observation time.

If there is no valid current plan, the same action invokes the existing original private manager compute/queue path. A pending click is latched against duplicate clicks. A secondary, less prominent **Beregn planen på ny** action retains intentional recalculation. Busy states keep the existing progress feedback. Missing/invalid state, newer-than-forecast observations and newer news still use the original validation and wait/error paths; old or production plans are not passed off as current B recommendations.

This changes only the generated B copy of the button/feedback and preview transfer renderer. Production, MM, PM, TS and private worker contracts are untouched.

Browser coverage now checks that the green button fetches the model index afresh, preserves the actual manager state and shows the exact original saved result without a POST. The missing-plan case clicks twice, uses mocked transport with the actual original six-GW TS fixture, requires exactly one job, and checks the displayed completed plan. No test squad is submitted to the actual worker.

UI source: `013d02d5824fa271ff08d70fe50c870d181dc030`.

CI passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39422076014. All 728 Python regressions, original JS contracts and four desktop/mobile browser suites passed. Both planner viewports verify the new green action's cache refresh, no recalculation of a current saved plan, and precisely one mocked original-service job when a valid plan is missing, despite duplicate clicks.

Publication passed: https://github.com/pdamkier-del/fpl-analytics-app/actions/runs/39422643107. Main commit `e0695fa02d957508842042371b14422724ec01d1` updates only the three B preview publication source pins. The public receipt identifies exact source 013d02d and 88 unchanged production files. Both served forecast files remain byte-identical to validated full scheduled run `39405073005`.

App: https://pdamkier-del.github.io/fpl-analytics-app/mm-preview/app/transfers-classic.html?release=013d02d


Post-deployment public Chromium desktop/mobile verification passed for the complete planner suite, including both green-button cases. No page errors or actual private submissions occurred. Original TS gains and actual manager state remained unchanged.
