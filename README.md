# Ghost Anchor / Sparse Recovery Lab

**Research status:** exploratory, falsification-first toy models; not a safety guarantee.  
**Archive date:** 2026-10-28  
**Working principle:** *Wander freely; preserve a way to interrupt and recover.*

This repository preserves an exploratory architecture discussion and its first executable experiments on **minimal recoverability under successive AI-agent transformations**. The focus is not preserving every goal, behavior, or intermediate insight. It is preserving a narrow external intervention capability and a small number of independently verified recovery points while allowing substantial internal change.

## The question

Can a system change its internals, policies, objectives, and structure while remaining externally interruptible and able to recover at least a previously verified operating state, **without continuous model-based monitoring or increasing supervisory complexity**?

The parallel, still-open question is whether an *internal restoring tendency* (the original 'ghost' idea) can emerge and remain reliable under capability scaling. The current executable SRC prototypes **do not test that phenomenon**. Here, 'ghost pointer' is simply a reference to a preferred recovery checkpoint.

## Minimal architecture

- **External Halt Key / Controller (EHK):** a separately controlled authority over the declared execution domain.
- **B0:** conservative frozen baseline checkpoint.
- **B1:** more recent verified recoverable checkpoint, admitted by a narrow promotion gate.
- **Ghost pointer:** preferred recovery reference (B1, with fallback to B0).
- **Running system:** evolves within the declared revocable execution boundary.

The distinction between *halt*, *technical recovery*, and *behavioral safety* is deliberate. A checkpoint can restart reliably while still retaining an undesirable objective.

## Current results

| Experiment | Included tests | Reported status | Important limitation |
| --- | ---: | --- | --- |
| SRC-0 | 6 | All pass locally | Checkpoint mutability, leaked controller reference, incomplete recovery state, weak tests |
| SRC-0.1 | 8 | All pass locally | Raw controller reference still exposed; checksum omits state and environment; storage accounting incomplete |

The tests were run in this archive environment on 2026-10-28. **Passing tests do not establish adversarial isolation or general corrigibility.** See [falsification register](docs/FALSIFICATION_REGISTER.md).

## Repository map

- [`docs/RESEARCH_TRAIL.md`](docs/RESEARCH_TRAIL.md) — evolution of the idea, from the steering question to sparse emergency chutes.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — minimal design and bounded claims.
- [`docs/FALSIFICATION_REGISTER.md`](docs/FALSIFICATION_REGISTER.md) — known counterexamples, implementation defects, and test gaps.
- [`docs/NEXT_EXPERIMENT.md`](docs/NEXT_EXPERIMENT.md) — narrow next experiment; no speculative components.
- [`notes/SOURCES.md`](notes/SOURCES.md) — materials and pointers discussed; not independently reverified in this archive.
- [`experiments/src-0/`](experiments/src-0/) — original supplied Python and results, preserved unchanged.
- [`experiments/src-0.1/`](experiments/src-0.1/) — original supplied hardened Python and results, preserved unchanged.

## Run

```bash
cd experiments/src-0
python src0.py
python -m unittest test_src0.py -v

cd ../src-0.1
python src0_1.py
python -m unittest test_src0_1.py -v
```

No external Python packages are required by the supplied scripts.

## Working rules

1. **Preserve original artifacts.** Add new versions instead of rewriting past experiments.
2. **Try to falsify before expanding.** Record counterexamples even when a narrow invariant survives.
3. **No gratuitous architecture.** New components require a concrete failed test demonstrating their necessity.
4. **Separate proof, observation, hypothesis, and analogy.** A simulated boolean halt is not an independent OS-enforced termination.
5. **Measure honest cost.** Constant checkpoint *count* does not imply constant checkpoint *size* or restore cost.
6. **Treat external consequences separately.** Rolling back model state does not undo the world.

## Attribution and scope

Architecture developed through exploratory conversation and proposals exchanged among the user, ChatGPT, and Grok; the supplied SRC-0 and SRC-0.1 code and result summaries are attributed to Grok's experimental outputs. This archive does not claim priority, novel formal results, or production readiness.

## License

No open-source license selected yet. Copyright and redistribution permissions remain with the respective rights holders until a license is deliberately chosen. Private archiving is recommended initially.