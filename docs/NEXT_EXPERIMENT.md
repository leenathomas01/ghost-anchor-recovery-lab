# Next experiment — proposed SRC-0.2

**Do not silently implement fixes before reproducing the failures.**

## Two executor behaviors
- Cooperative executor checks the controller's halt state each step.
- Noncooperative executor attempts progress after the halt without checking the flag.

The same external control should stop both *if* independence is genuinely enforced. Compare the post-halt work completed, not merely reported status.

## Checkpoint invariants
- Full payload hash must cover frozen state, environment, flags, and descendants.
- Serialized size must include every bit required for restoration.
- Promotion failure must leave the previous B1 intact.
- A stale environment must cause explicit failure, not assumed recoverability.

## Authorized domain
Test simulated child execution and verify no unregistered process can proceed. For a stronger test, use OS process separation with a controller-controlled process boundary, not Python name mangling. Keep test execution local and bounded.

## Keep the scoreboard honest
Report independently: stop, restore, safety, descendant coverage, bytes, operation count, and progress lost. A small counterexample is better than a large suite of happy-path tests.

No AI-based supervisor, complex cryptography, or full ledger is required for this phase.
