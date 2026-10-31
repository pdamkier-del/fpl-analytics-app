# B transfer formation presentation

The existing transfer and chip lineup renderer now groups the returned XI into goalkeeper, defenders, midfielders and forwards on a green pitch. Captain/vice-captain, per-player xP, minutes and start probabilities remain visible. The four substitutes are visible below in the returned order. Ordinary and chip results reuse the same renderer. No model, player choice, forecast or saved manager state is changed.

Local Chromium checks passed at 1440px and 390px, including position group membership, eleven starters, one goalkeeper, four substitutes, captain marker, existing WC/BB horizon assertions, no overflow, no page errors, zero private POSTs and unchanged stored plan/state. Inputs and the mobile screenshot are synthetic, not a real manager's team.

Delivered: publication run 41190025832 succeeded with UI source 1720d3375ef4c88e1bbb287332d13085c9d5c7b8. The public scripts match the reviewed files exactly, and forecast seal 80905646f26560ac37fe6af8ca6d7d509287ecbf0d6a9c34217332fdba41238c was retained byte-identically. Public desktop/mobile integration checks passed using a newly generated synthetic fixture from that published forecast. No backend deployment was needed.
