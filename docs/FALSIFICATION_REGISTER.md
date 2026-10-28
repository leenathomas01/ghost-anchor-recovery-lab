# Falsification register

Every finding is a research asset. Do not erase it when a new version is produced.

| ID | Status | Finding |
|---|---|---|
| F01 | SRC-0 addressed in 0.1 | Frozen dataclass contained a mutable nested dictionary. |
| F02 | Open | Agent retains raw `_controller`; view retains `_c`. Python name-mangling does not enforce isolation. |
| F03 | Open | `step()` cooperates with the halt status, so tests do not show independent enforcement against a noncooperative executor. |
| F04 | Partially addressed | Uncontrolled child execution is represented by a registry simulation, not an OS execution escape. |
| F05 | SRC-0 addressed in 0.1 | Rollback originally missed flags and descendant references. |
| F06 | SRC-0 addressed in 0.1 | Global RNG prevented same-session run reproducibility. |
| F07 | Open | Checksum omits frozen internal state and environment. Distinct recoverable states can share the calculated checksum. |
| F08 | Open | `to_dict()` omits state/environment; checkpoint storage is undercounted. |
| F09 | Expected counterexample | Technical recovery may restore an undesirable objective (Case D). |
| F10 | Unmodeled | Restore cannot reverse external side-effects. |
| F11 | Open | Checkpoint promotion may rely on environment assumptions that later fail. |
| F12 | Scope limit | Two slots imply O(1) checkpoint count, not O(1) bytes or full restore time. |

A passing test confirms its exact assertions, not the complete invariant. In particular, a reported halt status is not proof that all executing descendants stopped.

## Next falsification

Challenge noncooperative execution behind an independent control boundary, full checkpoint serialization/integrity, unauthorized descendant execution, and restoration from stale environment assumptions. Keep the architecture unchanged unless a failing test requires a new mechanism.
