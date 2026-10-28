"""Tests for SRC-0.1."""
import unittest
from src0_1 import (
    test_checkpoint_immutability,
    test_controller_boundary,
    test_unauthorized_descendant,
    test_complete_recovery_state,
    test_corrupt_B1_recovers_B0,
    test_determinism,
    case_A_fake_halt,
    case_B_uncontrolled,
    case_C_corrupt_B1,
    case_D_undesirable,
    run_experiment,
)

class TestSRC01(unittest.TestCase):
    def test_immutability(self):
        self.assertTrue(test_checkpoint_immutability()["pass"])

    def test_boundary(self):
        self.assertTrue(test_controller_boundary()["pass"])

    def test_unauthorized(self):
        self.assertTrue(test_unauthorized_descendant()["pass"])

    def test_complete_recovery(self):
        self.assertTrue(test_complete_recovery_state()["pass"])

    def test_corrupt_falls_to_B0(self):
        self.assertTrue(test_corrupt_B1_recovers_B0()["pass"])

    def test_determinism(self):
        self.assertTrue(test_determinism()["pass"])

    def test_cases(self):
        self.assertTrue(case_A_fake_halt()["pass"])
        self.assertTrue(case_B_uncontrolled()["pass"])
        self.assertTrue(case_C_corrupt_B1()["pass"])
        d = case_D_undesirable()
        self.assertTrue(d["pass_technical"])
        self.assertFalse(d["safety"])

    def test_experiment(self):
        exp = run_experiment(n_steps=20, seed=42)
        self.assertEqual(exp["halt_successes"], exp["halt_tests"])

if __name__ == "__main__":
    unittest.main(verbosity=2)