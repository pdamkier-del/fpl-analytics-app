# Explicit latest-verified B snapshot plans

The same next-gameweek forecast previously stopped working after six hours, a later manager confirmation, or later availability news. Re-running the model temporarily removed the symptom but did not fix the recurring dependency.

The B desktop copies now request `latest_verified_snapshot_v1`. They accept the latest sealed unified B forecast for its still-open official next gameweek. A later genuine manager observation is allowed; neither manager nor forecast timestamps are altered. The original model/prices cutoff and separate computation/decision times are retained in the result and displayed in Copenhagen time. New injury news and price changes are advisory, not silently incorporated into the old projections. A passed deadline, changed official GW/deadline, future timestamp, invalid squad or unsealed/inconsistent forecast still rejects the request. Production `/plans` rejects the new policy.

The B subprocess uses the original transfer search, costs, chips and shared PM scenarios with explicit input-time adapters. Default validation is unchanged. `check_snapshot_adapter.py` reverses only the four reviewed textual adapter edits and requires the SHA-256 of the frozen TS source. Original `service/manager_job.py`, model coefficients and production forecast assets are unchanged.

Validation: 799 Python tests passed. Coverage includes a real six-GW B calculation with a 30-hour-old forecast, six-hour source age limit and genuine later manager observation; old strict mode rejects the same inputs. Unit checks retain expired/future timestamp guards, reject snapshot policy on production, and compare the frozen source. Desktop/mobile browser checks use an explicitly synthetic fixture, require backend capability, verify original timestamps and the explicit policy, preserve the roster/plan after later injury news, display the six-GW plan and check dashboard readiness. No actual user roster, private job key or official FPL action is involved.

Deployment receipts and public browser verification will be recorded separately. Do not infer deployment from these source tests.
