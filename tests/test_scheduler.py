"""
Unit tests for scheduler agent calculation.
"""

import os
import sys
import unittest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from parser import CustomerRecord

from scheduler import (
    calculate_agents_per_hour,
    HourlyAllocation,
    schedule_unconstrained,
    schedule_with_capacity,
    schedule_with_capacity_shift,
)


class TestCalculateAgentsPerHour(unittest.TestCase):
    """Unit tests for calculate_agents_per_hour function."""

    def test_basic_calculation(self):
        """Test basic agent calculation formula."""
        # 3600 calls over 10 hours = 360 calls/hour
        # 360 calls * 10 seconds / 3600 = 1 agent
        record = CustomerRecord(
            name="Test",
            avg_duration_seconds=10,
            start_hour=9,
            end_hour=19,  # 10 hours
            num_calls=3600,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        self.assertEqual(len(result), 10)  # 10 hours
        self.assertEqual(result[9], 1)  # 1 agent per hour

    def test_ceiling_applied(self):
        """Test that ceiling is applied to fractional agents."""
        # 100 calls over 10 hours = 10 calls/hour
        # 10 calls * 100 seconds / 3600 = 0.278 agents -> ceil to 1
        record = CustomerRecord(
            name="Test",
            avg_duration_seconds=100,
            start_hour=9,
            end_hour=19,
            num_calls=100,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        self.assertEqual(result[9], 1)

    def test_utilization_factor(self):
        """Test that utilization factor affects calculation."""
        # 3600 calls over 10 hours = 360 calls/hour
        # 360 * 10 / 3600 / 0.5 = 2 agents (50% utilization)
        record = CustomerRecord(
            name="Test",
            avg_duration_seconds=10,
            start_hour=9,
            end_hour=19,
            num_calls=3600,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=0.5)

        self.assertEqual(result[9], 2)

    def test_only_active_hours(self):
        """Test that only active hours have agents."""
        record = CustomerRecord(
            name="Test",
            avg_duration_seconds=300,
            start_hour=9,
            end_hour=17,  # 9AM to 5PM
            num_calls=1000,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        # Should only have entries for hours 9-16 (17 is exclusive)
        self.assertIn(9, result)
        self.assertIn(16, result)
        self.assertNotIn(8, result)
        self.assertNotIn(17, result)

    def test_zero_active_hours(self):
        """Test edge case where start equals end (invalid but handled)."""
        record = CustomerRecord(
            name="Test",
            avg_duration_seconds=300,
            start_hour=9,
            end_hour=9,  # No active hours
            num_calls=1000,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        self.assertEqual(result, {})

    def test_sample_data_stanford(self):
        """Test with Stanford Hospital sample data."""
        # Stanford: 300s duration, 9AM-7PM (10 hours), 20000 calls
        # 20000/10 = 2000 calls/hour
        # 2000 * 300 / 3600 = 166.67 -> 167 agents
        record = CustomerRecord(
            name="Stanford Hospital",
            avg_duration_seconds=300,
            start_hour=9,
            end_hour=19,
            num_calls=20000,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        self.assertEqual(result[9], 167)
        self.assertEqual(result[18], 167)

    def test_sample_data_vns(self):
        """Test with VNS sample data."""
        # VNS: 120s duration, 6AM-1PM (7 hours), 40500 calls
        # 40500/7 = 5785.7 calls/hour
        # 5785.7 * 120 / 3600 = 192.86 -> 193 agents
        record = CustomerRecord(
            name="VNS",
            avg_duration_seconds=120,
            start_hour=6,
            end_hour=13,
            num_calls=40500,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        self.assertEqual(result[6], 193)


class TestScheduleUnconstrained(unittest.TestCase):
    """Tests for schedule_unconstrained function."""

    def test_single_customer(self):
        """Test unconstrained schedule with single customer."""
        records = [
            CustomerRecord(
                name="Test",
                avg_duration_seconds=300,
                start_hour=9,
                end_hour=17,
                num_calls=8000,  # 1000/hour * 300/3600 = 83.33 -> 84 agents
                priority=1,
            )
        ]
        allocations = schedule_unconstrained(records, utilization=1.0)

        self.assertEqual(len(allocations), 24)

        # Check inactive hours
        self.assertEqual(allocations[0].total_agents, 0)
        self.assertEqual(allocations[8].total_agents, 0)

        # Check active hours
        self.assertEqual(allocations[9].total_agents, 84)
        self.assertEqual(allocations[16].total_agents, 84)

        # Check hour 17 is inactive (end is exclusive)
        self.assertEqual(allocations[17].total_agents, 0)

    def test_multiple_customers_overlap(self):
        """Test that overlapping customers sum correctly."""
        records = [
            CustomerRecord(
                name="A",
                avg_duration_seconds=3600,  # 1 hour duration = 1 agent per call/hour
                start_hour=9,
                end_hour=12,
                num_calls=30,  # 10 calls/hour = 10 agents
                priority=1,
            ),
            CustomerRecord(
                name="B",
                avg_duration_seconds=3600,
                start_hour=10,
                end_hour=14,
                num_calls=40,  # 10 calls/hour = 10 agents
                priority=2,
            ),
        ]
        allocations = schedule_unconstrained(records, utilization=1.0)

        # Hour 9: only A (10 agents)
        self.assertEqual(allocations[9].total_agents, 10)
        self.assertEqual(allocations[9].customer_agents, {"A": 10})

        # Hour 10-11: A + B (20 agents)
        self.assertEqual(allocations[10].total_agents, 20)
        self.assertEqual(allocations[10].customer_agents, {"A": 10, "B": 10})

        # Hour 12-13: only B (10 agents)
        self.assertEqual(allocations[12].total_agents, 10)
        self.assertEqual(allocations[12].customer_agents, {"B": 10})

    def test_exactly_24_allocations(self):
        """Test that exactly 24 allocations are returned."""
        records = [
            CustomerRecord(
                name="Test",
                avg_duration_seconds=300,
                start_hour=9,
                end_hour=17,
                num_calls=1000,
                priority=1,
            )
        ]
        allocations = schedule_unconstrained(records, utilization=1.0)

        self.assertEqual(len(allocations), 24)
        for i, alloc in enumerate(allocations):
            self.assertEqual(alloc.hour, i)


class TestScheduleWithCapacity(unittest.TestCase):
    """Tests for schedule_with_capacity function."""

    def test_capacity_not_exceeded(self):
        """Test that capacity is never exceeded."""
        records = [
            CustomerRecord(
                name="Big",
                avg_duration_seconds=3600,
                start_hour=9,
                end_hour=17,
                num_calls=800,  # 100 calls/hour = 100 agents
                priority=1,
            ),
        ]
        allocations = schedule_with_capacity(records, utilization=1.0, capacity=50)

        for alloc in allocations:
            self.assertLessEqual(alloc.total_agents, 50)

    def test_priority_order_respected(self):
        """Test that higher priority customers are allocated first."""
        records = [
            CustomerRecord(
                name="Low Priority",
                avg_duration_seconds=3600,
                start_hour=9,
                end_hour=17,
                num_calls=800,  # 100 agents/hour
                priority=5,
            ),
            CustomerRecord(
                name="High Priority",
                avg_duration_seconds=3600,
                start_hour=9,
                end_hour=17,
                num_calls=800,  # 100 agents/hour
                priority=1,
            ),
        ]
        allocations = schedule_with_capacity(records, utilization=1.0, capacity=150)

        # High priority should be fully satisfied (100 agents)
        # Low priority should get remaining (50 agents)
        self.assertEqual(allocations[9].customer_agents.get("High Priority"), 100)
        self.assertEqual(allocations[9].customer_agents.get("Low Priority"), 50)

    def test_unmet_demand_tracked(self):
        """Test that unmet demand is correctly tracked."""
        records = [
            CustomerRecord(
                name="Test",
                avg_duration_seconds=3600,
                start_hour=9,
                end_hour=17,
                num_calls=800,  # 100 agents/hour
                priority=1,
            ),
        ]
        allocations = schedule_with_capacity(records, utilization=1.0, capacity=60)

        # Should have 60 allocated, 40 unmet
        self.assertEqual(allocations[9].customer_agents.get("Test"), 60)
        self.assertEqual(allocations[9].unmet_demand.get("Test"), 40)


class TestScheduleWithCapacityShift(unittest.TestCase):
    """Tests for schedule_with_capacity_shift function."""

    def test_redistribution_reduces_overflow(self):
        """Test that redistribution helps reduce overflow."""
        records = [
            CustomerRecord(
                name="Test",
                avg_duration_seconds=3600,
                start_hour=9,
                end_hour=13,  # 4 hours
                num_calls=400,  # 100 agents/hour normally
                priority=1,
            ),
        ]
        # With capacity 80, should redistribute to spread load
        allocations, redistributions = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=80
        )

        # All hours should be at or below capacity after redistribution
        for alloc in allocations:
            if alloc.total_agents > 0:
                self.assertLessEqual(alloc.total_agents, 80)

    def test_redistribution_summary_returned(self):
        """Test that redistribution summary is returned."""
        records = [
            CustomerRecord(
                name="Test",
                avg_duration_seconds=3600,
                start_hour=9,
                end_hour=13,
                num_calls=400,  # 100 agents/hour - exceeds capacity
                priority=1,
            ),
        ]
        allocations, redistributions = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=80
        )

        # Should have some redistributions if capacity is lower than needed
        self.assertIsInstance(redistributions, list)

    def test_no_redistribution_when_under_capacity(self):
        """Test that no redistribution occurs when under capacity."""
        records = [
            CustomerRecord(
                name="Test",
                avg_duration_seconds=3600,
                start_hour=9,
                end_hour=13,
                num_calls=40,  # 10 agents/hour - well under capacity
                priority=1,
            ),
        ]
        allocations, redistributions = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=100
        )

        self.assertEqual(len(redistributions), 0)

    def test_redistribution_preserves_high_priority_even_distribution(self):
        """
        Test that redistribution creates uneven distribution for low priority
        while preserving even distribution for high priority customers.

        Scenario:
        - High priority customer (priority=1): 50 agents/hour, hours 9-11 (2 hours)
        - Low priority customer (priority=5): 60 agents/hour, hours 9-13 (4 hours)
        - Capacity: 100 agents

        Hours 9-10: High(50) + Low(60) = 110 > 100 (overflow of 10)
        Hours 11-12: Only Low(60) < 100 (capacity of 40 available)

        Expected behavior:
        - High priority should maintain even distribution (50 agents each hour)
        - Low priority should be redistributed: reduced in hours 9-10, increased in 11-12
        """
        records = [
            CustomerRecord(
                name="HighPriority",
                avg_duration_seconds=3600,  # 1 hour = 1 agent per call
                start_hour=9,
                end_hour=11,  # 2 hours
                num_calls=100,  # 50 calls/hour = 50 agents/hour
                priority=1,
            ),
            CustomerRecord(
                name="LowPriority",
                avg_duration_seconds=3600,  # 1 hour = 1 agent per call
                start_hour=9,
                end_hour=13,  # 4 hours
                num_calls=240,  # 60 calls/hour = 60 agents/hour normally
                priority=5,
            ),
        ]

        allocations, redistributions = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=100
        )

        # Verify high priority has EVEN distribution (50 each hour it's active)
        for hour in range(9, 11):
            alloc = allocations[hour]
            high_priority_agents = alloc.customer_agents.get("HighPriority", 0)
            low_priority_agents = alloc.customer_agents.get("LowPriority", 0)
            self.assertEqual(
                high_priority_agents,
                50,
                f"Hour {hour}: High priority should have exactly 50 agents (even distribution)",
            )
            self.assertEqual(
                low_priority_agents,
                50,
                f"Hour {hour}: Low priority should have exactly 50 agents",
            )
        alloc_11 = allocations[11]
        low_priority_agents_11 = alloc_11.customer_agents.get("LowPriority", 0)
        self.assertEqual(
            low_priority_agents_11,
            80,
            f"Hour 11 Low priority should have exactly 80 agents",
        )

        # Verify low priority has UNEVEN distribution due to redistribution
        low_priority_by_hour = []
        for hour in range(9, 13):
            alloc = allocations[hour]
            low_priority_agents = alloc.customer_agents.get("LowPriority", 0)
            low_priority_by_hour.append(low_priority_agents)

        # Low priority should have less agents in hours 9-10 (overflow hours)
        # and more in hours 11-12 (non-overlap hours)
        overlap_hours_avg = (low_priority_by_hour[0] + low_priority_by_hour[1]) / 2
        non_overlap_hours_avg = (low_priority_by_hour[2] + low_priority_by_hour[3]) / 2

        self.assertLess(
            overlap_hours_avg,
            non_overlap_hours_avg,
            f"Low priority should have fewer agents in overlap hours (9-10): "
            f"overlap avg={overlap_hours_avg}, non-overlap avg={non_overlap_hours_avg}",
        )

        # Verify capacity is not exceeded in any hour
        for hour in range(9, 13):
            alloc = allocations[hour]
            self.assertLessEqual(
                alloc.total_agents,
                100,
                f"Hour {hour}: Total agents {alloc.total_agents} exceeds capacity 100",
            )

        # Verify redistributions occurred
        self.assertGreater(
            len(redistributions),
            0,
            "Should have some redistributions for low priority customer",
        )

        # Verify only low priority customer was redistributed
        for redist in redistributions:
            self.assertEqual(
                redist.customer,
                "LowPriority",
                f"Only LowPriority should be redistributed, got: {redist.customer}",
            )

    def test_redistribution_maximizes_served_calls(self):
        """
        Test that redistribution maximizes total served calls by moving
        overflow to hours with available capacity.

        Scenario:
        - Single customer with 100 agents/hour need across 4 hours
        - Capacity: 80 agents
        - Total needed: 400 agent-hours
        - Available: 320 agent-hours (80 * 4)

        Expected: All 320 agent-hours should be utilized (no unmet demand
        if calls can be redistributed within the window).
        """
        records = [
            CustomerRecord(
                name="Test",
                avg_duration_seconds=3600,
                start_hour=9,
                end_hour=13,  # 4 hours
                num_calls=400,  # 100 agents/hour normally
                priority=1,
            ),
        ]

        allocations, redistributions = schedule_with_capacity_shift(
            records, utilization=1.0, capacity=80
        )

        # Calculate total agents allocated
        total_allocated = sum(alloc.total_agents for alloc in allocations)

        # Should maximize usage - all 320 agent-hours should be used
        # (80 capacity * 4 hours = 320)
        self.assertEqual(
            total_allocated,
            320,
            f"Should utilize full capacity: expected 320, got {total_allocated}",
        )

        # Each hour should be at capacity
        for hour in range(9, 13):
            self.assertEqual(
                allocations[hour].total_agents,
                80,
                f"Hour {hour} should be at capacity (80)",
            )

        # Should have unmet demand since 400 > 320
        total_unmet = sum(
            sum(alloc.unmet_demand.values())
            for alloc in allocations
            if alloc.unmet_demand
        )
        self.assertEqual(
            total_unmet,
            80,
            f"Should have 80 agent-hours unmet (400 - 320), got {total_unmet}",
        )


class TestAgentCalculationEdgeCases(unittest.TestCase):
    """Edge case tests for agent calculation."""

    def test_very_short_duration(self):
        """Test with very short call duration."""
        record = CustomerRecord(
            name="Quick Calls",
            avg_duration_seconds=1,  # 1 second calls
            start_hour=9,
            end_hour=10,
            num_calls=3600,  # 1 call per second for 1 hour
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        # 3600 calls * 1 second / 3600 = 1 agent
        self.assertEqual(result[9], 1)

    def test_very_long_duration(self):
        """Test with very long call duration."""
        record = CustomerRecord(
            name="Long Calls",
            avg_duration_seconds=7200,  # 2 hour calls
            start_hour=9,
            end_hour=10,
            num_calls=100,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        # 100 calls * 7200 / 3600 = 200 agents
        self.assertEqual(result[9], 200)

    def test_single_hour_window(self):
        """Test with single hour active window."""
        record = CustomerRecord(
            name="One Hour",
            avg_duration_seconds=300,
            start_hour=12,
            end_hour=13,
            num_calls=100,
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        self.assertEqual(len(result), 1)
        self.assertIn(12, result)

    def test_full_day_window(self):
        """Test with full 24-hour window."""
        record = CustomerRecord(
            name="24/7",
            avg_duration_seconds=300,
            start_hour=0,
            end_hour=24,
            num_calls=24000,  # 1000 calls/hour
            priority=1,
        )
        result = calculate_agents_per_hour(record, utilization=1.0)

        self.assertEqual(len(result), 24)
        # 1000 * 300 / 3600 = 83.33 -> 84
        for hour in range(24):
            self.assertEqual(result[hour], 84)


if __name__ == "__main__":
    unittest.main()
