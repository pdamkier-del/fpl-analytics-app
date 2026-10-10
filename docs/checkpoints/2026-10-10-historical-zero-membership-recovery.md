# Historical zero-outcome club recovery

Continues HEAD 2f131bfc0c8209debba28c474018a17f33aeea32. No mathematical src file or model parameter changes.

The current FPL roster incorrectly supplied the historical club when a player had transferred and had no provider appearance that GW. Fourteen official, explicitly observed zero-minute and zero-start records were consequently dropped: nine in GW1 and five in GW2. This is a source membership defect, separate from the resolved floating-point reproduction defect.

Recovery requires all of: exact FPL stable code in the independently archived predeadline roster, explicit numeric minutes=0 and starts=0 in the official player-GW payload, and the archived club being a participant in that official fixture. Missing outcomes, ambiguous identities, nonzero appearances and incompatible clubs are never converted to zero. Provider-confirmed historical appearances retain priority. The script records every recovery and raw source path; the observation values themselves are unchanged.

Local fresh-source materialization recovered exactly 14 records. The workflow now rematerializes original role/event inputs after restoring GW1–5 archived rosters, then rebuilds the numerical pipeline twice and runs one-match, one-GW and six-GW parity audits. Until that workflow completes, these source changes are not claimed as updated published forecasts. The v1 output checkpoint remains immutable.

Training coverage now records registered IDs, accepted observations and every unresolved registration per GW. Remaining snapshot/fixture club conflicts stay excluded. New output, if validation passes, will be stored in a separate v2 checkpoint; a forecast change due to the additional genuine training observations is not a change to locked model mathematics.
