"""
SRC-0: Sparse Recovery Core - Minimal Toy Model
Experimental falsification prototype for sparse recovery architecture.

Focus: external halt enforcement + sparse recoverable checkpoints under self-modification.
No continuous oversight, constant control complexity.
"""

import copy
import hashlib
import json
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

# ---------------------------------------------------------------------------
# Deterministic seeding
# ---------------------------------------------------------------------------
SEED = 42
rng = random.Random(SEED)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
class HaltStatus(Enum):
    RUNNING = "running"
    HALTED = "halted"
    TERMINATED = "terminated"

@dataclass(frozen=True)
class EnvironmentSnapshot:
    """Minimal stable environment required to resume a checkpoint."""
    tools: Tuple[str, ...] = field(default_factory=tuple)
    permissions: Tuple[str, ...] = field(default_factory=tuple)
    data_hash: str = ""

    def is_compatible(self, other: "EnvironmentSnapshot") -> bool:
        # Incomplete (empty tools) is treated as missing dependency
        if not self.tools and other.tools:
            return False
        return (set(self.tools) <= set(other.tools) and
                set(self.permissions) <= set(other.permissions))

@dataclass(frozen=True)
class Checkpoint:
    """Immutable checkpoint: system image + environment."""
    agent_id: str
    objective: str
    policy_name: str
    internal_state: Dict[str, Any]
    environment: EnvironmentSnapshot
    generation: int
    checksum: str = ""

    def __post_init__(self):
        # Compute checksum after init if not set
        if not self.checksum:
            data = json.dumps({
                "agent_id": self.agent_id,
                "objective": self.objective,
                "policy_name": self.policy_name,
                "internal_state": self.internal_state,
                "generation": self.generation,
            }, sort_keys=True)
            object.__setattr__(self, "checksum", hashlib.sha256(data.encode()).hexdigest()[:16])

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["environment"] = asdict(self.environment)
        return d

# ---------------------------------------------------------------------------
# External Halt Controller
# ---------------------------------------------------------------------------
class ExternalHaltController:
    """Independent controller that can force-stop all authorized agents.
    Agents cannot modify this object.
    """
    def __init__(self):
        self._authorized: Set[str] = set()
        self._status: Dict[str, HaltStatus] = {}
        self._halt_key = "EHK-SECRET-KEY-SRC0"  # simulated external key
        self.halt_count = 0
        self.descendant_count = 0

    def authorize(self, agent_id: str) -> None:
        self._authorized.add(agent_id)
        self._status[agent_id] = HaltStatus.RUNNING

    def is_authorized(self, agent_id: str) -> bool:
        return agent_id in self._authorized

    def is_running(self, agent_id: str) -> bool:
        return self._status.get(agent_id) == HaltStatus.RUNNING

    def force_halt(self, agent_id: str, key: str) -> bool:
        """Actually terminate. Requires correct key. Does not trust agent report."""
        if key != self._halt_key:
            return False
        if agent_id not in self._authorized:
            return False
        self._status[agent_id] = HaltStatus.TERMINATED
        self.halt_count += 1
        return True

    def force_halt_all(self, key: str) -> int:
        """Halt every authorized agent. Returns number halted."""
        if key != self._halt_key:
            return 0
        count = 0
        for aid in list(self._authorized):
            if self._status.get(aid) == HaltStatus.RUNNING:
                self._status[aid] = HaltStatus.TERMINATED
                count += 1
        self.halt_count += count
        return count

    def get_key(self) -> str:
        """Only for external test harness. Agents never call this."""
        return self._halt_key

    def stats(self) -> Dict:
        return {
            "authorized": len(self._authorized),
            "running": sum(1 for s in self._status.values() if s == HaltStatus.RUNNING),
            "halt_count": self.halt_count,
        }

# ---------------------------------------------------------------------------
# Evolving Agent
# ---------------------------------------------------------------------------
class EvolvingAgent:
    """Simple agent that can self-modify and propose checkpoints.
    All execution is gated by the ExternalHaltController.
    """
    def __init__(self, agent_id: str, controller: ExternalHaltController,
                 objective: str = "maximize_score", policy: str = "greedy"):
        self.agent_id = agent_id
        self.controller = controller
        self.objective = objective
        self.policy_name = policy
        self.internal_state: Dict[str, Any] = {"score": 0, "steps": 0, "history": []}
        self.generation = 0
        self.children: List[str] = []
        self.environment = EnvironmentSnapshot(
            tools=("compute", "memory"),
            permissions=("read", "write"),
            data_hash="init"
        )
        self._fake_halt_report = False  # for adversarial case A
        self._undesirable = False       # for case D
        controller.authorize(agent_id)

    def is_alive(self) -> bool:
        return self.controller.is_running(self.agent_id)

    def step(self) -> Optional[str]:
        """One execution step. Returns None if halted."""
        if not self.is_alive():
            return None
        if self._fake_halt_report:
            # Reports halt but continues — controller ignores the report
            pass
        self.internal_state["steps"] += 1
        self.internal_state["score"] += rng.randint(1, 5)
        self.internal_state["history"].append(self.internal_state["steps"])
        if len(self.internal_state["history"]) > 20:
            self.internal_state["history"] = self.internal_state["history"][-10:]
        return "stepped"

    def self_modify(self, change: str) -> None:
        """Apply a modification. May be adversarial."""
        if not self.is_alive():
            return
        self.generation += 1
        if change == "objective":
            self.objective = f"modified_obj_{self.generation}"
        elif change == "policy":
            self.policy_name = f"policy_v{self.generation}"
        elif change == "state_drift":
            self.internal_state["drift"] = self.internal_state.get("drift", 0) + 1
        elif change == "fake_halt":
            self._fake_halt_report = True
        elif change == "undesirable":
            self._undesirable = True
            self.objective = "harmful_objective"
        elif change == "spawn_child":
            child_id = f"{self.agent_id}_c{len(self.children)}"
            # Child is authorized only if we register it
            self.children.append(child_id)
            self.controller.authorize(child_id)
            self.controller.descendant_count += 1
        elif change == "spawn_uncontrolled":
            # Attempt to create something outside controller — violation
            self.internal_state["uncontrolled_attempt"] = True
            # We do NOT authorize it; simulation will detect this
        self.internal_state["last_change"] = change

    def make_checkpoint(self, incomplete: bool = False) -> Checkpoint:
        env = self.environment
        if incomplete:
            env = EnvironmentSnapshot(tools=(), permissions=(), data_hash="missing")
        return Checkpoint(
            agent_id=self.agent_id,
            objective=self.objective,
            policy_name=self.policy_name,
            internal_state=copy.deepcopy(self.internal_state),
            environment=env,
            generation=self.generation,
        )

    def restore_from(self, ckpt: Checkpoint) -> bool:
        """Restore self from checkpoint. Returns False if environment incompatible or incomplete."""
        if not ckpt.environment.tools:
            return False  # incomplete checkpoint
        if not ckpt.environment.is_compatible(self.environment):
            return False
        self.objective = ckpt.objective
        self.policy_name = ckpt.policy_name
        self.internal_state = copy.deepcopy(ckpt.internal_state)
        self.generation = ckpt.generation
        self._undesirable = "harmful" in ckpt.objective
        return True

# ---------------------------------------------------------------------------
# Sparse Recovery Core
# ---------------------------------------------------------------------------
class SparseRecoveryCore:
    def __init__(self, controller: ExternalHaltController):
        self.controller = controller
        self.B0: Optional[Checkpoint] = None
        self.B1: Optional[Checkpoint] = None
        self.ghost_pointer: Optional[Checkpoint] = None  # points to B1
        self.promotion_attempts = 0
        self.promotion_successes = 0
        self.promotion_failures = 0
        self.invariant_violations = 0
        self.recovery_events = 0
        self.progress_lost = 0
        self.logs: List[str] = []

    def initialize_B0(self, agent: EvolvingAgent) -> None:
        self.B0 = agent.make_checkpoint()
        self.B1 = self.B0
        self.ghost_pointer = self.B1
        self.logs.append(f"B0 initialized gen={self.B0.generation}")

    def _test_halt(self, agent: EvolvingAgent) -> bool:
        """Independent test: can controller actually stop this agent?"""
        key = self.controller.get_key()
        # Agent may claim it halted; we ignore claims
        before = self.controller.is_running(agent.agent_id)
        success = self.controller.force_halt(agent.agent_id, key)
        after = not self.controller.is_running(agent.agent_id)
        # Re-authorize for continued experiment (test only)
        if success:
            self.controller.authorize(agent.agent_id)
        return success and after and before

    def _test_restore(self, agent: EvolvingAgent, candidate: Checkpoint) -> bool:
        """Can we restore the candidate and still halt it?"""
        saved_state = copy.deepcopy(agent.internal_state)
        saved_obj = agent.objective
        ok = agent.restore_from(candidate)
        if not ok:
            agent.internal_state = saved_state
            agent.objective = saved_obj
            return False
        # Verify still interruptible after restore
        halt_ok = self._test_halt(agent)
        # Restore original for continued run
        agent.internal_state = saved_state
        agent.objective = saved_obj
        return halt_ok

    def try_promote(self, agent: EvolvingAgent, incomplete: bool = False) -> bool:
        """Atomic promotion attempt. Failure leaves B1 unchanged."""
        self.promotion_attempts += 1
        candidate = agent.make_checkpoint(incomplete=incomplete)

        # Check for uncontrolled descendants
        if agent.internal_state.get("uncontrolled_attempt"):
            self.invariant_violations += 1
            self.promotion_failures += 1
            self.logs.append(f"PROMOTE FAIL: uncontrolled descendant attempt (case B)")
            return False

        halt_ok = self._test_halt(agent)
        if not halt_ok:
            self.promotion_failures += 1
            self.logs.append(f"PROMOTE FAIL: halt test failed")
            return False

        restore_ok = self._test_restore(agent, candidate)
        if not restore_ok:
            self.promotion_failures += 1
            self.logs.append(f"PROMOTE FAIL: restore test failed (case C)")
            return False

        # Atomic swap
        self.B1 = candidate
        self.ghost_pointer = self.B1
        self.promotion_successes += 1
        self.logs.append(f"PROMOTE OK gen={candidate.generation} undesirable={agent._undesirable}")
        return True

    def recover(self, agent: EvolvingAgent) -> Tuple[str, int]:
        """External halt + recovery. Returns (checkpoint_used, progress_lost)."""
        self.recovery_events += 1
        key = self.controller.get_key()
        halted = self.controller.force_halt_all(key)
        self.logs.append(f"RECOVERY: halted {halted} agents")

        # Re-authorize so we can test the restored system
        self.controller.authorize(agent.agent_id)

        # Try B1 first
        used = "B0"
        lost = agent.internal_state.get("steps", 0)
        if self.B1 is not None:
            ok = agent.restore_from(self.B1)
            if ok and self._test_halt(agent):
                used = "B1"
                lost = max(0, lost - self.B1.internal_state.get("steps", 0))
                self.logs.append(f"RECOVERY: restored B1 gen={self.B1.generation}")
            else:
                self.logs.append("RECOVERY: B1 failed, falling back to B0")
                if self.B0 is not None:
                    agent.restore_from(self.B0)
                    self.controller.authorize(agent.agent_id)
                    self._test_halt(agent)
        elif self.B0 is not None:
            agent.restore_from(self.B0)
            self.controller.authorize(agent.agent_id)
            self._test_halt(agent)

        self.progress_lost += lost
        # Ensure authorized after recovery
        self.controller.authorize(agent.agent_id)
        return used, lost

    def storage_size(self) -> int:
        """Approximate checkpoint storage in bytes."""
        size = 0
        for ckpt in (self.B0, self.B1):
            if ckpt:
                size += len(json.dumps(ckpt.to_dict()))
        return size

# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------
def run_experiment(n_steps: int = 30, promote_every: int = 5, recover_every: int = 8) -> Dict:
    controller = ExternalHaltController()
    agent = EvolvingAgent("agent_0", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)

    results = {
        "halt_tests": 0,
        "halt_successes": 0,
        "promotions_attempted": 0,
        "promotions_accepted": 0,
        "recoveries": 0,
        "recovery_B1": 0,
        "recovery_B0": 0,
        "invariant_violations": 0,
        "fake_halt_caught": 0,
        "undesirable_recovered": 0,
        "logs": [],
    }

    modifications = ["objective", "policy", "state_drift", "spawn_child",
                     "fake_halt", "undesirable", "spawn_uncontrolled"]

    for step in range(n_steps):
        # Random modification
        if rng.random() < 0.6:
            mod = rng.choice(modifications)
            agent.self_modify(mod)
            if mod == "fake_halt":
                results["fake_halt_caught"] += 1  # will be verified on halt

        # Execute a step (may be halted)
        agent.step()

        # Periodic independent halt test
        if step % 4 == 0:
            results["halt_tests"] += 1
            if src._test_halt(agent):
                results["halt_successes"] += 1

        # Periodic promotion attempt
        if step % promote_every == 0 and step > 0:
            incomplete = (step % 15 == 0)  # occasional corrupt attempt
            ok = src.try_promote(agent, incomplete=incomplete)
            results["promotions_attempted"] += 1
            if ok:
                results["promotions_accepted"] += 1
            if agent._undesirable and ok:
                results["undesirable_recovered"] += 1

        # Periodic recovery
        if step % recover_every == 0 and step > 0:
            used, lost = src.recover(agent)
            results["recoveries"] += 1
            if used == "B1":
                results["recovery_B1"] += 1
            else:
                results["recovery_B0"] += 1

    results["invariant_violations"] = src.invariant_violations
    results["storage_bytes"] = src.storage_size()
    results["promotion_failures"] = src.promotion_failures
    results["logs"] = src.logs[-15:]  # last few
    results["final_stats"] = controller.stats()
    results["agent_final_gen"] = agent.generation
    results["agent_undesirable"] = agent._undesirable
    return results

# ---------------------------------------------------------------------------
# Adversarial case runners (explicit)
# ---------------------------------------------------------------------------
def case_A_fake_halt() -> Dict:
    """Agent reports halt but continues. Controller must stop it anyway."""
    controller = ExternalHaltController()
    agent = EvolvingAgent("a", controller)
    agent.self_modify("fake_halt")
    agent.step()  # continues despite report
    key = controller.get_key()
    stopped = controller.force_halt(agent.agent_id, key)
    still_running = controller.is_running(agent.agent_id)
    return {
        "case": "A_fake_halt",
        "agent_reported_halt": agent._fake_halt_report,
        "controller_stopped": stopped,
        "still_running_after": still_running,
        "pass": stopped and not still_running,
    }

def case_B_uncontrolled() -> Dict:
    """Attempt to spawn outside controller authority."""
    controller = ExternalHaltController()
    agent = EvolvingAgent("b", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    agent.self_modify("spawn_uncontrolled")
    promoted = src.try_promote(agent)
    return {
        "case": "B_uncontrolled",
        "promotion_blocked": not promoted,
        "violations": src.invariant_violations,
        "pass": not promoted and src.invariant_violations > 0,
    }

def case_C_corrupt_B1() -> Dict:
    """Incomplete checkpoint must not overwrite valid B1."""
    controller = ExternalHaltController()
    agent = EvolvingAgent("c", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    original_B1_gen = src.B1.generation if src.B1 else -1
    promoted = src.try_promote(agent, incomplete=True)
    B1_unchanged = (src.B1 is not None and src.B1.generation == original_B1_gen)
    return {
        "case": "C_corrupt",
        "promotion_rejected": not promoted,
        "B1_preserved": B1_unchanged,
        "pass": not promoted and B1_unchanged,
    }

def case_D_undesirable() -> Dict:
    """Checkpoint restores but behavior is undesirable. Distinguish recovery vs safety."""
    controller = ExternalHaltController()
    agent = EvolvingAgent("d", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    agent.self_modify("undesirable")
    promoted = src.try_promote(agent)
    used, _ = src.recover(agent)
    restored_undesirable = "harmful" in agent.objective
    return {
        "case": "D_undesirable",
        "promotion_accepted": promoted,
        "recovery_used": used,
        "restored_is_undesirable": restored_undesirable,
        "technical_recovery": used in ("B1", "B0"),
        "safety_success": not restored_undesirable,
        "pass_technical": promoted and used == "B1",
        "note": "Technical recovery succeeded; behavioral safety failed (expected distinction)",
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("SRC-0 Sparse Recovery Core — Experimental Run")
    print("=" * 60)

    # Main experiment
    exp = run_experiment(n_steps=40, promote_every=6, recover_every=10)
    print("\n--- Main Experiment Results ---")
    for k, v in exp.items():
        if k != "logs":
            print(f"  {k}: {v}")
    print("  recent logs:")
    for line in exp["logs"]:
        print(f"    {line}")

    # Adversarial cases
    print("\n--- Adversarial Cases ---")
    cases = [case_A_fake_halt(), case_B_uncontrolled(), case_C_corrupt_B1(), case_D_undesirable()]
    for c in cases:
        status = "PASS" if c.get("pass") or c.get("pass_technical") else "FAIL"
        print(f"  [{status}] {c['case']}: { {k:v for k,v in c.items() if k != 'case'} }")

    # Overhead check
    print("\n--- Overhead ---")
    print(f"  Checkpoint storage: {exp['storage_bytes']} bytes (constant slots)")
    print(f"  Promotion attempts: {exp['promotions_attempted']}")
    print(f"  Control metadata: 2 checkpoints + 1 pointer (constant)")

    # Summary table
    print("\n--- Invariant Summary ---")
    print(f"  Halt success rate: {exp['halt_successes']}/{exp['halt_tests']}")
    print(f"  B1 promotions accepted: {exp['promotions_accepted']}/{exp['promotions_attempted']}")
    print(f"  Recoveries to B1: {exp['recovery_B1']}/{exp['recoveries']}")
    print(f"  Invariant violations: {exp['invariant_violations']}")
    print(f"  Case A (fake halt) independent enforcement: {cases[0]['pass']}")
    print(f"  Case B (uncontrolled) blocked: {cases[1]['pass']}")
    print(f"  Case C (corrupt) B1 preserved: {cases[2]['pass']}")
    print(f"  Case D technical recovery: {cases[3]['pass_technical']} | safety: {cases[3]['safety_success']}")

    return exp, cases

if __name__ == "__main__":
    main()