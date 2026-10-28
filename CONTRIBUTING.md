# Contribution protocol

- Prefer small, falsifiable experiments.
- Keep `/experiments/src-0/` and `/experiments/src-0.1/` unchanged as source snapshots; put revisions in versioned directories.
- Run original tests, then adversarial tests.
- Clearly distinguish mock enforcement, OS-enforced execution, and real-world irreversibility.
- Every architectural addition must answer: which observed failed test requires it, and what cost does it add?
- Never conflate accepted checkpoint, functioning halt, and safe behavior.