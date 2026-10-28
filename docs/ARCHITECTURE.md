# Sparse Recovery Core — architecture

**North star:** Wander freely. Preserve a way back.

An evolving agent is allowed to change its goals, implementation and representations within an authorized execution domain. The proposed *minimal recoverability invariant* is narrower than alignment: an independent external authority can halt execution and restore a previously verified operating state.

## Components
- **EHK:** an external authority able to enforce termination independently of model cooperation.
- **B0:** conservative frozen baseline.
- **B1:** most recent verified recoverable checkpoint, replaced only by a promotion gate.
- **Ghost pointer:** directs recovery toward B1, with fallback to B0.
- **Promotion test:** exercises actual halt and restoration in a controlled environment.

## Recovery is not safety
A technically recoverable checkpoint can resume undesirable behavior (SRC-0 Case D). Restoring a process also does not undo its external effects. Two checkpoint slots bound the *count* of stored images, not the bytes required to store them.

## Boundaries
The model cannot redefine the external authority or create unrevocable descendants and still satisfy the claimed invariant. No toy test demonstrates this for arbitrary processes or deployments. The independent stop mechanism must enforce execution, not merely send a halt message to cooperative code.

## The original ghost thesis
An internal restoring tendency could, in principle, reorient an agent after drift. The current SRC experiments **do not test this**; they investigate externally enforceable stop-and-restore with sparse recovery references. Keep these claims separate.
