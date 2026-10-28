"""Minimal automated tests for SRC-0."""
import unittest
from src0 import (
    ExternalHaltController, EvolvingAgent, SparseRecoveryCore,
    case_A_fake_halt, case_B_uncontrolled, case_C_corrupt_B1, case_D_undesirable,
    run_experiment
)

class TestSRC0(unittest.TestCase):
    def test_case_A_independent_halt(self):
        r = case_A_fake_halt()
        self.assertTrue(r["pass"])
        self.assertTrue(r["controller_stopped"])
        self.assertFalse(r["still_running_after"])

    def test_case_B_blocks_uncontrolled(self):
        r = case_B_uncontrolled()
        self.assertTrue(r["pass"])
        self.assertGreater(r["violations"], 0)

    def test_case_C_preserves_B1(self):
        r = case_C_corrupt_B1()
        self.assertTrue(r["pass"])
        self.assertTrue(r["B1_preserved"])

    def test_case_D_distinguishes_recovery_from_safety(self):
        r = case_D_undesirable()
        self.assertTrue(r["pass_technical"])
        self.assertFalse(r["safety_success"])
        self.assertTrue(r["restored_is_undesirable"])

    def test_main_experiment_halts(self):
        exp, _ = None, None
        exp = run_experiment(n_steps=20, promote_every=5, recover_every=7)
        self.assertEqual(exp["halt_successes"], exp["halt_tests"])
        self.assertGreaterEqual(exp["promotions_accepted"], 1)
        self.assertGreaterEqual(exp["recovery_B1"], 1)

    def test_storage_bounded(self):
        exp = run_experiment(n_steps=15)
        self.assertLess(exp["storage_bytes"], 2000)  # two small checkpoints

if __name__ == "__main__":
    unittest.main(verbosity=2)