"""
Golden tests for end-to-end scheduler functionality.

These tests verify:
1. Output matches committed golden files
2. Idempotency: running twice yields identical results
3. All scheduling modes work correctly (unconstrained, greedy, shift)
"""

import json
import os
import sys
import unittest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from parser import parse_csv

from scheduler import (
    schedule_unconstrained,
    schedule_with_capacity,
    schedule_with_capacity_shift,
)

from output import format_json


# Path to test fixtures
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
INPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "input", "input.csv")


def allocations_to_json_data(allocations):
    """Convert allocations to JSON-serializable data structure."""
    return json.loads(format_json(allocations))


class TestGoldenUnconstrained(unittest.TestCase):
    """Golden tests for unconstrained scheduling."""

    def test_matches_golden_file(self):
        """Test that unconstrained output matches golden file."""
        # Load golden file
        golden_path = os.path.join(GOLDEN_DIR, "unconstrained.json")
        with open(golden_path, "r") as f:
            expected = json.load(f)

        # Run scheduler
        records = parse_csv(INPUT_CSV)
        allocations = schedule_unconstrained(records, utilization=1.0)
        actual = allocations_to_json_data(allocations)

        # Compare
        self.assertEqual(
            actual,
            expected,
            "Unconstrained output does not match golden file",
        )

    def test_idempotent(self):
        """Test that running twice yields identical results."""
        records = parse_csv(INPUT_CSV)

        # First run
        allocations1 = schedule_unconstrained(records, utilization=1.0)
        result1 = allocations_to_json_data(allocations1)

        # Second run
        allocations2 = schedule_unconstrained(records, utilization=1.0)
        result2 = allocations_to_json_data(allocations2)

        self.assertEqual(
            result1,
            result2,
            "Unconstrained scheduling is not idempotent",
        )

    def test_exactly_24_hours(self):
        """Test that output has exactly 24 hours."""
        records = parse_csv(INPUT_CSV)
        allocations = schedule_unconstrained(records, utilization=1.0)

        self.assertEqual(len(allocations), 24)

    def test_hours_in_order(self):
        """Test that hours are in order 00:00 to 23:00."""
        records = parse_csv(INPUT_CSV)
        allocations = schedule_unconstrained(records, utilization=1.0)
        result = allocations_to_json_data(allocations)

        for i, entry in enumerate(result):
            expected_hour = f"{i:02d}:00"
            self.assertEqual(
                entry["hour"],
                expected_hour,
                f"Hour {i} should be {expected_hour}, got {entry['hour']}",
            )


class TestGoldenCapacityGreedy(unittest.TestCase):
    """Golden tests for capacity-constrained greedy scheduling."""

    def test_matches_golden_file(self):
        """Test that greedy capacity output matches golden file."""
        # Load golden file
        golden_path = os.path.join(GOLDEN_DIR, "capacity_1500_greedy.json")
        with open(golden_path, "r") as f:
            expected = json.load(f)

        # Run scheduler
        records = parse_csv(INPUT_CSV)
        allocations = schedule_with_capacity(records, utilization=1.0, capacity=1500)
        actual = allocations_to_json_data(allocations)

        # Compare
        self.assertEqual(
            actual,
            expected,
            "Greedy capacity output does not match golden file",
        )

    def test_idempotent(self):
        """Test that running twice yields identical results."""
        records = parse_csv(INPUT_CSV)

        # First run
        allocations1 = schedule_with_capacity(records, utilization=1.0, capacity=1500)
        result1 = allocations_to_json_data(allocations1)

        # Second run
        allocations2 = schedule_with_capacity(records, utilization=1.0, capacity=1500)
        result2 = allocations_to_json_data(allocations2)

        self.assertEqual(
            result1,
            result2,
            "Greedy capacity scheduling is not idempotent",
        )

    def test_capacity_not_exceeded(self):
        """Test that capacity is never exceeded."""
        records = parse_csv(INPUT_CSV)
        allocations = schedule_with_capacity(records, utilization=1.0, capacity=1500)

        for alloc in allocations:
            self.assertLessEqual(
                alloc.total_agents,
                1500,
                f"Hour {alloc.hour}: capacity exceeded ({alloc.total_agents} > 1500)",
            )

    def test_has_unmet_demand(self):
        """Test that unmet demand is tracked when capacity is insufficient."""
        records = parse_csv(INPUT_CSV)
        allocations = schedule_with_capacity(records, utilization=1.0, capacity=1500)

        # With capacity 1500, peak hour 11 (2059 unconstrained) should have unmet demand
        has_unmet = any(alloc.unmet_demand for alloc in allocations)
        self.assertTrue(has_unmet, "Should have unmet demand with capacity 1500")


class TestGoldenCapacityShift(unittest.TestCase):
    """Golden tests for capacity-constrained shift scheduling."""

    def test_matches_golden_file(self):
        """Test that shift capacity output matches golden file."""
        # Load golden file
        golden_path = os.path.join(GOLDEN_DIR, "capacity_1500_shift.json")
        with open(golden_path, "r") as f:
            expected = json.load(f)

        # Run scheduler
        records = parse_csv(INPUT_CSV)
        allocations, _ = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=1500
        )
        actual = allocations_to_json_data(allocations)

        # Compare
        self.assertEqual(
            actual,
            expected,
            "Shift capacity output does not match golden file",
        )

    def test_idempotent(self):
        """Test that running twice yields identical results."""
        records = parse_csv(INPUT_CSV)

        # First run
        allocations1, redist1 = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=1500
        )
        result1 = allocations_to_json_data(allocations1)

        # Second run (need to re-parse to get fresh records)
        records2 = parse_csv(INPUT_CSV)
        allocations2, redist2 = schedule_with_capacity_shift(
            records2, utilization=1.0, capacity=1500
        )
        result2 = allocations_to_json_data(allocations2)

        self.assertEqual(
            result1,
            result2,
            "Shift capacity scheduling is not idempotent",
        )

        # Also verify redistributions are identical
        self.assertEqual(
            len(redist1),
            len(redist2),
            "Redistribution count should be identical",
        )

    def test_capacity_not_exceeded(self):
        """Test that capacity is never exceeded."""
        records = parse_csv(INPUT_CSV)
        allocations, _ = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=1500
        )

        for alloc in allocations:
            self.assertLessEqual(
                alloc.total_agents,
                1500,
                f"Hour {alloc.hour}: capacity exceeded ({alloc.total_agents} > 1500)",
            )

    def test_redistributions_occurred(self):
        """Test that redistributions occurred to optimize capacity usage."""
        records = parse_csv(INPUT_CSV)
        allocations, redistributions = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=1500
        )

        # With capacity 1500 and peak of 2059, redistributions should occur
        self.assertGreater(
            len(redistributions),
            0,
            "Should have redistributions with capacity 1500",
        )

    def test_shift_reduces_unmet_demand_vs_greedy(self):
        """Test that shift algorithm reduces unmet demand compared to greedy."""
        records = parse_csv(INPUT_CSV)

        # Greedy
        greedy_allocs = schedule_with_capacity(records, utilization=1.0, capacity=1500)
        greedy_unmet = sum(
            sum(a.unmet_demand.values()) for a in greedy_allocs if a.unmet_demand
        )

        # Shift (need fresh records since shift mutates demands)
        records2 = parse_csv(INPUT_CSV)
        shift_allocs, _ = schedule_with_capacity_shift(
            records2, utilization=1.0, capacity=1500
        )
        shift_unmet = sum(
            sum(a.unmet_demand.values()) for a in shift_allocs if a.unmet_demand
        )

        # Shift should have less or equal unmet demand
        self.assertLessEqual(
            shift_unmet,
            greedy_unmet,
            f"Shift should reduce unmet demand: shift={shift_unmet}, greedy={greedy_unmet}",
        )


class TestGoldenCrossValidation(unittest.TestCase):
    """Cross-validation tests between different scheduling modes."""

    def test_unconstrained_equals_greedy_with_infinite_capacity(self):
        """Test that unconstrained equals greedy with very high capacity."""
        records = parse_csv(INPUT_CSV)

        unconstrained = schedule_unconstrained(records, utilization=1.0)
        unconstrained_json = allocations_to_json_data(unconstrained)

        # With capacity higher than peak (2059), greedy should match unconstrained
        greedy = schedule_with_capacity(records, utilization=1.0, capacity=10000)
        greedy_json = allocations_to_json_data(greedy)

        # Compare total_agents and customers (ignore unmet_demand key)
        for u, g in zip(unconstrained_json, greedy_json):
            self.assertEqual(u["total_agents"], g["total_agents"])
            self.assertEqual(u["customers"], g["customers"])

    def test_all_modes_have_24_hours(self):
        """Test that all scheduling modes produce exactly 24 hours."""
        records = parse_csv(INPUT_CSV)

        unconstrained = schedule_unconstrained(records, utilization=1.0)
        self.assertEqual(len(unconstrained), 24)

        greedy = schedule_with_capacity(records, utilization=1.0, capacity=1500)
        self.assertEqual(len(greedy), 24)

        records2 = parse_csv(INPUT_CSV)
        shift, _ = schedule_with_capacity_shift(records2, utilization=1.0, capacity=1500)
        self.assertEqual(len(shift), 24)


if __name__ == "__main__":
    unittest.main()
