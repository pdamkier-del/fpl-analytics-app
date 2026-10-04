# Deadline-batched player component contract

Continues `6cec1306ae15d53f14a124bab42754d39186cd9c` without replacing any old
forecast or diagnostic. `deadline_components.py` is a new, explicit input
contract using the recovered frozen attack/DC/discipline parameters.

One common cutoff filters current-season history by caller-supplied
`available_at`; no fixture-by-fixture target updates are allowed. Target outcomes
in retained history, duplicate logical observations, missing event fields,
unverified roster timestamps and invalid positions/minutes are rejected.
Previous-season events cannot supply current-season player/position priors.
First entrants with verified predeadline roster/position evidence use the same
frozen position-shrinkage formula with zero individual history; unknown roster
rows are rejected rather than defaulted to zero.

Attack produces per-90 propensities. DC retains the selected player/opponent
half-lives, position shrinkage, opponent exponent and dispersion. Discipline
retains the original recommended joint candidate: yellow position shrinkage,
effectively position-only red (`tau=1e9`) and no opponent factor. This does not
refit or tune any parameter. Candidate minutes and evaluation targets are not
inputs to this common component function.

114 tests pass, including seven new tests for future-outcome invariance,
previous-season isolation, explicit first-entry priors, missing roster rejection,
target-history rejection, shared DGW rates and refusal to impute missing events.

Next: freeze these common player components against actual recovered deadline
snapshots and Core histories, with explicit outcome-availability semantics.
Team-goal/keeper inputs and complete roster evidence remain separate gates.
The original adapter, simulator, control/v4 diagnostic and transfer/chip policy
are unchanged. GW22–38 remains reused diagnostic, never a new holdout.
