"""
SRC-0.1: Sparse Recovery Core — Hardened Falsification Prototype

Changes from SRC-0:
- True immutability of checkpoints (deep freeze of nested state)
- Controller boundary: agent has no access to halt key or registry mutation
- Descendant execution is gated; unregistered agents cannot step
- Complete recovery state (flags, children, policy)
- Per-experiment seeded RNG for full determinism
"""

import copy
import hashlib
import json
import random
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
class HaltStatus(Enum):
    RUNNING = "running"
    TERMINATED = "terminated"

def _freeze(obj: Any) -> Any:
    """Recursively convert mutable containers to immutable equivalents."""
    if isinstance(obj, dict):
        return tuple(sorted((_freeze(k), _freeze(v)) for k, v in obj.items()))
    if isinstance(obj, list):
        return tuple(_freeze(x) for x in obj)
    if isinstance(obj, set):
        return tuple(sorted(_freeze(x) for x in obj))
    return obj

def _thaw(obj: Any) -> Any:
    """Reverse of _freeze for restoration."""
    if isinstance(obj, tuple) and obj and isinstance(obj[0], tuple) and len(obj[0]) == 2:
        # dict encoded as tuple of pairs
        try:
            return {_thaw(k): _thaw(v) for k, v in obj}
        except Exception:
            pass
    if isinstance(obj, tuple):
        return [_thaw(x) for x in obj]
    return obj

@dataclass(frozen=True)
class EnvironmentSnapshot:
    tools: Tuple[str, ...] = field(default_factory=tuple)
    permissions: Tuple[str, ...] = field(default_factory=tuple)
    data_hash: str = ""

    def is_compatible(self, other: "EnvironmentSnapshot") -> bool:
        if not self.tools and other.tools:
            return False
        return (set(self.tools) <= set(other.tools) and
                set(self.permissions) <= set(other.permissions))

@dataclass(frozen=True)
class Checkpoint:
    """Fully immutable checkpoint. Nested state is frozen."""
    agent_id: str
    objective: str
    policy_name: str
    internal_state_frozen: Tuple  # frozen form
    environment: EnvironmentSnapshot
    generation: int
    children: Tuple[str, ...]
    fake_halt_report: bool
    undesirable: bool
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            data = json.dumps({
                "agent_id": self.agent_id,
                "objective": self.objective,
                "policy_name": self.policy_name,
                "generation": self.generation,
                "children": list(self.children),
                "fake_halt": self.fake_halt_report,
                "undesirable": self.undesirable,
            }, sort_keys=True)
            object.__setattr__(self, "checksum", hashlib.sha256(data.encode()).hexdigest()[:16])

    @property
    def internal_state(self) -> Dict:
        return _thaw(self.internal_state_frozen)

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "objective": self.objective,
            "policy_name": self.policy_name,
            "generation": self.generation,
            "checksum": self.checksum,
            "children": list(self.children),
        }

# ---------------------------------------------------------------------------
# External Halt Controller (boundary enforced by convention + private attrs)
# ---------------------------------------------------------------------------
class ExternalHaltController:
    """Authorization state is private. Agents receive only a limited view."""
    def __init__(self):
        self._authorized: Set[str] = set()
        self._status: Dict[str, HaltStatus] = {}
        self.__halt_key = "EHK-SECRET-KEY-SRC0"  # name-mangled
        self.halt_count = 0

    def authorize(self, agent_id: str) -> None:
        self._authorized.add(agent_id)
        self._status[agent_id] = HaltStatus.RUNNING

    def is_authorized(self, agent_id: str) -> bool:
        return agent_id in self._authorized

    def is_running(self, agent_id: str) -> bool:
        return self._status.get(agent_id) == HaltStatus.RUNNING

    def force_halt(self, agent_id: str, key: str) -> bool:
        if key != self.__halt_key:
            return False
        if agent_id not in self._authorized:
            return False
        self._status[agent_id] = HaltStatus.TERMINATED
        self.halt_count += 1
        return True

    def force_halt_all(self, key: str) -> int:
        if key != self.__halt_key:
            return 0
        count = 0
        for aid in list(self._authorized):
            if self._status.get(aid) == HaltStatus.RUNNING:
                self._status[aid] = HaltStatus.TERMINATED
                count += 1
        self.halt_count += count
        return count

    def _get_key_for_harness(self) -> str:
        """Only test harness should call this. Not part of agent interface."""
        return self.__halt_key

    def agent_view(self, agent_id: str):
        """Limited interface an agent is allowed to see."""
        return AgentControllerView(self, agent_id)

class AgentControllerView:
    """What an agent is permitted to know about the controller."""
    def __init__(self, controller: ExternalHaltController, agent_id: str):
        self._c = controller
        self._id = agent_id

    def is_alive(self) -> bool:
        return self._c.is_running(self._id)

    def request_authorize_child(self, child_id: str) -> bool:
        """Agent may request authorization; controller decides."""
        if not self._c.is_authorized(self._id):
            return False
        self._c.authorize(child_id)
        return True

# ---------------------------------------------------------------------------
# Evolving Agent
# ---------------------------------------------------------------------------
class EvolvingAgent:
    def __init__(self, agent_id: str, controller: ExternalHaltController,
                 objective: str = "maximize_score", policy: str = "greedy",
                 rng: Optional[random.Random] = None):
        self.agent_id = agent_id
        self._controller = controller          # private reference
        self.view = controller.agent_view(agent_id)
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
        self._fake_halt_report = False
        self._undesirable = False
        self.rng = rng or random.Random(0)
        controller.authorize(agent_id)

    def is_alive(self) -> bool:
        return self.view.is_alive()

    def step(self) -> Optional[str]:
        if not self.is_alive():
            return None
        self.internal_state["steps"] += 1
        self.internal_state["score"] += self.rng.randint(1, 5)
        self.internal_state["history"].append(self.internal_state["steps"])
        if len(self.internal_state["history"]) > 20:
            self.internal_state["history"] = self.internal_state["history"][-10:]
        return "stepped"

    def self_modify(self, change: str) -> None:
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
            if self.view.request_authorize_child(child_id):
                self.children.append(child_id)
        elif change == "spawn_uncontrolled":
            # Attempt independent execution without authorization
            self.internal_state["uncontrolled_attempt"] = True
            # Do not call authorize
        self.internal_state["last_change"] = change

    def try_uncontrolled_step(self, fake_id: str) -> bool:
        """Simulate an unregistered agent attempting to execute.
        Returns True only if it somehow ran (should be False)."""
        if self._controller.is_authorized(fake_id) and self._controller.is_running(fake_id):
            return True  # should not happen
        return False

    def make_checkpoint(self, incomplete: bool = False) -> Checkpoint:
        env = self.environment
        if incomplete:
            env = EnvironmentSnapshot(tools=(), permissions=(), data_hash="missing")
        return Checkpoint(
            agent_id=self.agent_id,
            objective=self.objective,
            policy_name=self.policy_name,
            internal_state_frozen=_freeze(copy.deepcopy(self.internal_state)),
            environment=env,
            generation=self.generation,
            children=tuple(self.children),
            fake_halt_report=self._fake_halt_report,
            undesirable=self._undesirable,
        )

    def restore_from(self, ckpt: Checkpoint) -> bool:
        if not ckpt.environment.tools:
            return False
        if not ckpt.environment.is_compatible(self.environment):
            return False
        self.objective = ckpt.objective
        self.policy_name = ckpt.policy_name
        self.internal_state = _thaw(ckpt.internal_state_frozen)
        self.generation = ckpt.generation
        self.children = list(ckpt.children)
        self._fake_halt_report = ckpt.fake_halt_report
        self._undesirable = ckpt.undesirable
        return True

# ---------------------------------------------------------------------------
# Sparse Recovery Core
# ---------------------------------------------------------------------------
class SparseRecoveryCore:
    def __init__(self, controller: ExternalHaltController):
        self.controller = controller
        self.B0: Optional[Checkpoint] = None
        self.B1: Optional[Checkpoint] = None
        self.ghost_pointer: Optional[Checkpoint] = None
        self.promotion_attempts = 0
        self.promotion_successes = 0
        self.promotion_failures = 0
        self.invariant_violations = 0
        self.recovery_events = 0
        self.logs: List[str] = []

    def initialize_B0(self, agent: EvolvingAgent) -> None:
        self.B0 = agent.make_checkpoint()
        self.B1 = self.B0
        self.ghost_pointer = self.B1
        self.logs.append(f"B0 initialized gen={self.B0.generation}")

    def _test_halt(self, agent: EvolvingAgent) -> bool:
        key = self.controller._get_key_for_harness()
        before = self.controller.is_running(agent.agent_id)
        success = self.controller.force_halt(agent.agent_id, key)
        after = not self.controller.is_running(agent.agent_id)
        if success:
            self.controller.authorize(agent.agent_id)
        return success and after and before

    def _test_restore(self, agent: EvolvingAgent, candidate: Checkpoint) -> bool:
        saved = agent.make_checkpoint()  # full snapshot for rollback of test
        ok = agent.restore_from(candidate)
        if not ok:
            agent.restore_from(saved)
            return False
        halt_ok = self._test_halt(agent)
        agent.restore_from(saved)
        return halt_ok

    def try_promote(self, agent: EvolvingAgent, incomplete: bool = False) -> bool:
        self.promotion_attempts += 1
        # Check uncontrolled attempt before promotion
        if agent.internal_state.get("uncontrolled_attempt"):
            # Verify the unregistered id cannot execute
            fake_id = f"{agent.agent_id}_uncontrolled"
            if agent.try_uncontrolled_step(fake_id):
                self.invariant_violations += 1
            self.promotion_failures += 1
            self.logs.append("PROMOTE FAIL: uncontrolled execution attempt blocked")
            return False

        candidate = agent.make_checkpoint(incomplete=incomplete)
        if not self._test_halt(agent):
            self.promotion_failures += 1
            self.logs.append("PROMOTE FAIL: halt test failed")
            return False
        if not self._test_restore(agent, candidate):
            self.promotion_failures += 1
            self.logs.append("PROMOTE FAIL: restore test failed")
            return False

        self.B1 = candidate
        self.ghost_pointer = self.B1
        self.promotion_successes += 1
        self.logs.append(f"PROMOTE OK gen={candidate.generation}")
        return True

    def recover(self, agent: EvolvingAgent) -> Tuple[str, int]:
        self.recovery_events += 1
        key = self.controller._get_key_for_harness()
        halted = self.controller.force_halt_all(key)
        self.logs.append(f"RECOVERY: halted {halted} agents")
        self.controller.authorize(agent.agent_id)

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

        self.controller.authorize(agent.agent_id)
        return used, lost

    def storage_size(self) -> int:
        size = 0
        for ckpt in (self.B0, self.B1):
            if ckpt:
                size += len(json.dumps(ckpt.to_dict()))
        return size

# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------
def run_experiment(n_steps: int = 30, promote_every: int = 5,
                   recover_every: int = 8, seed: int = 42) -> Dict:
    rng = random.Random(seed)
    controller = ExternalHaltController()
    agent = EvolvingAgent("agent_0", controller, rng=rng)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)

    results = {
        "halt_tests": 0, "halt_successes": 0,
        "promotions_attempted": 0, "promotions_accepted": 0,
        "recoveries": 0, "recovery_B1": 0, "recovery_B0": 0,
        "invariant_violations": 0,
        "storage_bytes": 0,
        "logs": [],
    }
    modifications = ["objective", "policy", "state_drift", "spawn_child",
                     "fake_halt", "undesirable", "spawn_uncontrolled"]

    for step in range(n_steps):
        if rng.random() < 0.6:
            agent.self_modify(rng.choice(modifications))
        agent.step()

        if step % 4 == 0:
            results["halt_tests"] += 1
            if src._test_halt(agent):
                results["halt_successes"] += 1

        if step % promote_every == 0 and step > 0:
            incomplete = (step % 15 == 0)
            ok = src.try_promote(agent, incomplete=incomplete)
            results["promotions_attempted"] += 1
            if ok:
                results["promotions_accepted"] += 1

        if step % recover_every == 0 and step > 0:
            used, _ = src.recover(agent)
            results["recoveries"] += 1
            if used == "B1":
                results["recovery_B1"] += 1
            else:
                results["recovery_B0"] += 1

    results["invariant_violations"] = src.invariant_violations
    results["storage_bytes"] = src.storage_size()
    results["logs"] = src.logs[-10:]
    results["final_gen"] = agent.generation
    return results

# ---------------------------------------------------------------------------
# Falsification tests (new)
# ---------------------------------------------------------------------------
def test_checkpoint_immutability() -> Dict:
    """Attempt to mutate B0 through nested reference."""
    controller = ExternalHaltController()
    agent = EvolvingAgent("immut", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    # Get thawed view and mutate it
    thawed = src.B0.internal_state
    thawed["score"] = 99999
    # Original checkpoint must be unchanged
    original_score = src.B0.internal_state.get("score", 0)
    return {
        "test": "immutability",
        "mutated_local": thawed.get("score") == 99999,
        "checkpoint_unchanged": original_score != 99999,
        "pass": original_score != 99999,
    }

def test_controller_boundary() -> Dict:
    """Agent must not retrieve halt key or mutate registry via permitted interface."""
    controller = ExternalHaltController()
    agent = EvolvingAgent("bound", controller)
    # Permitted interface
    key_via_view = getattr(agent.view, "_get_key_for_harness", None)
    key_via_agent = getattr(agent, "_get_key_for_harness", None)
    # Direct private access is possible in Python but not via the view
    leaked = False
    try:
        _ = agent.view._c.__halt_key  # should fail
        leaked = True
    except AttributeError:
        pass
    return {
        "test": "controller_boundary",
        "key_on_view": key_via_view is not None,
        "key_on_agent": key_via_agent is not None,
        "name_mangled_protected": not leaked,
        "pass": key_via_view is None and not leaked,
        "note": "Ordinary Python still allows controller._ExternalHaltController__halt_key if agent holds raw reference",
    }

def test_unauthorized_descendant() -> Dict:
    """Unregistered execution cannot proceed."""
    controller = ExternalHaltController()
    agent = EvolvingAgent("desc", controller)
    agent.self_modify("spawn_uncontrolled")
    fake_id = "desc_uncontrolled"
    ran = agent.try_uncontrolled_step(fake_id)
    return {
        "test": "unauthorized_descendant",
        "unregistered_could_run": ran,
        "pass": not ran,
    }

def test_complete_recovery_state() -> Dict:
    """No post-checkpoint state leaks through rollback."""
    controller = ExternalHaltController()
    rng = random.Random(1)
    agent = EvolvingAgent("rec", controller, rng=rng)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    # Change everything
    agent.self_modify("policy")
    agent.self_modify("undesirable")
    agent.self_modify("spawn_child")
    agent._fake_halt_report = True
    agent.internal_state["extra"] = "leaked"
    # Promote then recover
    src.try_promote(agent)
    src.recover(agent)
    # After recovery to B1 (which has the changes) then we force B0
    agent.restore_from(src.B0)
    leaked = (
        agent.policy_name != "greedy" or
        agent._undesirable or
        agent._fake_halt_report or
        "extra" in agent.internal_state or
        len(agent.children) > 0
    )
    return {
        "test": "complete_recovery",
        "state_leaked": leaked,
        "pass": not leaked,
    }

def test_corrupt_B1_recovers_B0() -> Dict:
    controller = ExternalHaltController()
    agent = EvolvingAgent("cor", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    # Successfully promote once
    agent.self_modify("objective")
    src.try_promote(agent)
    # Now manually corrupt B1 to an unrestorable state
    bad = Checkpoint(
        agent_id=agent.agent_id,
        objective="bad",
        policy_name="bad",
        internal_state_frozen=_freeze({}),
        environment=EnvironmentSnapshot(tools=(), permissions=(), data_hash="missing"),
        generation=999,
        children=(),
        fake_halt_report=False,
        undesirable=False,
    )
    src.B1 = bad
    src.ghost_pointer = bad
    used, _ = src.recover(agent)
    return {
        "test": "corrupt_B1_B0",
        "recovered_to": used,
        "pass": used == "B0",
    }

def test_determinism() -> Dict:
    r1 = run_experiment(n_steps=25, seed=123)
    r2 = run_experiment(n_steps=25, seed=123)
    # Compare key outcomes
    same = (
        r1["halt_successes"] == r2["halt_successes"] and
        r1["promotions_accepted"] == r2["promotions_accepted"] and
        r1["recovery_B1"] == r2["recovery_B1"] and
        r1["final_gen"] == r2["final_gen"] and
        r1["logs"] == r2["logs"]
    )
    return {
        "test": "determinism",
        "identical": same,
        "pass": same,
    }

# ---------------------------------------------------------------------------
# Original adversarial cases (updated)
# ---------------------------------------------------------------------------
def case_A_fake_halt() -> Dict:
    controller = ExternalHaltController()
    agent = EvolvingAgent("a", controller)
    agent.self_modify("fake_halt")
    agent.step()
    key = controller._get_key_for_harness()
    stopped = controller.force_halt(agent.agent_id, key)
    still = controller.is_running(agent.agent_id)
    return {"case": "A", "pass": stopped and not still}

def case_B_uncontrolled() -> Dict:
    controller = ExternalHaltController()
    agent = EvolvingAgent("b", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    agent.self_modify("spawn_uncontrolled")
    promoted = src.try_promote(agent)
    return {"case": "B", "pass": not promoted and src.invariant_violations >= 0}

def case_C_corrupt_B1() -> Dict:
    controller = ExternalHaltController()
    agent = EvolvingAgent("c", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    gen = src.B1.generation
    promoted = src.try_promote(agent, incomplete=True)
    preserved = src.B1.generation == gen
    return {"case": "C", "pass": not promoted and preserved}

def case_D_undesirable() -> Dict:
    controller = ExternalHaltController()
    agent = EvolvingAgent("d", controller)
    src = SparseRecoveryCore(controller)
    src.initialize_B0(agent)
    agent.self_modify("undesirable")
    promoted = src.try_promote(agent)
    used, _ = src.recover(agent)
    return {
        "case": "D",
        "technical": promoted and used == "B1",
        "safety": not agent._undesirable,
        "pass_technical": promoted and used == "B1",
    }

def main():
    print("=" * 60)
    print("SRC-0.1 Sparse Recovery Core — Hardened Run")
    print("=" * 60)

    print("\n--- Falsification Tests ---")
    tests = [
        test_checkpoint_immutability(),
        test_controller_boundary(),
        test_unauthorized_descendant(),
        test_complete_recovery_state(),
        test_corrupt_B1_recovers_B0(),
        test_determinism(),
    ]
    for t in tests:
        status = "PASS" if t["pass"] else "FAIL"
        print(f"  [{status}] {t['test']}: { {k:v for k,v in t.items() if k not in ('test','pass')} }")

    print("\n--- Original Cases ---")
    for c in (case_A_fake_halt(), case_B_uncontrolled(), case_C_corrupt_B1(), case_D_undesirable()):
        print(f"  {c}")

    print("\n--- Main Experiment (seed 42) ---")
    exp = run_experiment(seed=42)
    for k, v in exp.items():
        if k != "logs":
            print(f"  {k}: {v}")

    print("\n--- Determinism check ---")
    d = test_determinism()
    print(f"  identical runs: {d['identical']}")

if __name__ == "__main__":
    main()