#!/usr/bin/env python3
"""
Hippo Call Scheduler - AI Agent Staffing Planner

Computes hour-by-hour agent requirements based on customer call demands.
"""

import math
import sys
from dataclasses import dataclass
from parser import CustomerRecord, parse_csv

from cli import parse_args
from output import (
    format_csv_output,
    format_json,
    format_text,
    print_metrics,
    write_result_file,
)


@dataclass
class HourlyAllocation:
    """Agent allocation for a single hour."""

    hour: int
    total_agents: int
    customer_agents: dict[str, int]  # customer_name -> agents
    unmet_demand: dict[
        str, int
    ]  # customer_name -> unmet agents (when capacity-constrained)


def calculate_agents_per_hour(
    record: CustomerRecord, utilization: float
) -> dict[int, int]:
    """Calculate agents needed per hour for a customer."""
    active_hours = record.end_hour - record.start_hour
    if active_hours <= 0:
        return {}

    calls_per_hour = record.num_calls / active_hours
    agents_per_hour = math.ceil(
        calls_per_hour * record.avg_duration_seconds / 3600 / utilization
    )

    return {hour: agents_per_hour for hour in range(record.start_hour, record.end_hour)}


def schedule_unconstrained(
    records: list[CustomerRecord], utilization: float
) -> list[HourlyAllocation]:
    """Schedule without capacity constraints - just sum up all requirements."""
    # Calculate agents per hour for each customer
    customer_hourly = {}
    for record in records:
        customer_hourly[record.name] = calculate_agents_per_hour(record, utilization)

    # Build hourly allocations
    allocations = []
    for hour in range(24):
        customer_agents = {}
        for record in records:
            agents = customer_hourly[record.name].get(hour, 0)
            if agents > 0:
                customer_agents[record.name] = agents

        allocations.append(
            HourlyAllocation(
                hour=hour,
                total_agents=sum(customer_agents.values()),
                customer_agents=customer_agents,
                unmet_demand={},
            )
        )

    return allocations


def schedule_with_capacity(
    records: list[CustomerRecord], utilization: float, capacity: int
) -> list[HourlyAllocation]:
    """Schedule with capacity constraint using priority-based greedy allocation."""
    # Calculate required agents per hour for each customer
    customer_hourly = {}
    for record in records:
        customer_hourly[record.name] = calculate_agents_per_hour(record, utilization)

    # Sort records by priority (1 = highest priority = first)
    sorted_records = sorted(records, key=lambda r: r.priority)

    # Build hourly allocations with capacity constraint
    allocations = []
    for hour in range(24):
        remaining_capacity = capacity
        customer_agents = {}
        unmet_demand = {}

        for record in sorted_records:
            required = customer_hourly[record.name].get(hour, 0)
            if required > 0:
                allocated = min(required, remaining_capacity)
                if allocated > 0:
                    customer_agents[record.name] = allocated
                    remaining_capacity -= allocated

                if required > allocated:
                    unmet_demand[record.name] = required - allocated

        allocations.append(
            HourlyAllocation(
                hour=hour,
                total_agents=sum(customer_agents.values()),
                customer_agents=customer_agents,
                unmet_demand=unmet_demand,
            )
        )

    return allocations


@dataclass
class CustomerHourlyDemand:
    """Track per-hour call/agent distribution for a customer."""

    name: str
    priority: int
    start_hour: int
    end_hour: int
    original_calls: dict[
        int, float
    ]  # hour -> calls (can be fractional during redistribution)
    current_calls: dict[int, float]  # hour -> calls after redistribution
    agents_per_call: float  # avg_duration_seconds / 3600 / utilization


@dataclass
class RedistributionSummary:
    """Track moves made during optimization."""

    customer: str
    from_hour: int
    to_hour: int
    calls_moved: float


def build_customer_demands(
    records: list[CustomerRecord], utilization: float
) -> list[CustomerHourlyDemand]:
    """Build initial uniform call distribution for all customers."""
    demands = []
    for record in records:
        active_hours = record.end_hour - record.start_hour
        if active_hours <= 0:
            continue

        calls_per_hour = record.num_calls / active_hours
        agents_per_call = record.avg_duration_seconds / 3600 / utilization

        hourly_calls = {
            hour: calls_per_hour for hour in range(record.start_hour, record.end_hour)
        }

        demands.append(
            CustomerHourlyDemand(
                name=record.name,
                priority=record.priority,
                start_hour=record.start_hour,
                end_hour=record.end_hour,
                original_calls=hourly_calls.copy(),
                current_calls=hourly_calls.copy(),
                agents_per_call=agents_per_call,
            )
        )

    return demands


def get_agents_needed(demand: CustomerHourlyDemand, hour: int) -> int:
    """Calculate agents needed for a customer at a specific hour."""
    calls = demand.current_calls.get(hour, 0)
    return math.ceil(calls * demand.agents_per_call)


def get_total_agents_per_hour(demands: list[CustomerHourlyDemand]) -> dict[int, int]:
    """Calculate total agents needed per hour across all customers."""
    totals = {}
    for hour in range(24):
        total = sum(get_agents_needed(d, hour) for d in demands)
        totals[hour] = total
    return totals


def apply_redistribution(
    demands: list[CustomerHourlyDemand],
    capacity: int,
    sorted_by_priority: list[CustomerHourlyDemand],
) -> list[RedistributionSummary]:
    """
    Single-pass redistribution: Move overflow calls to hours with available capacity.

    Process lowest-priority customers first (most flexible).
    Only affects overflowed customers; higher-priority distributions unchanged.
    """
    redistributions = []

    for hour in range(24):
        total_agents = sum(get_agents_needed(d, hour) for d in demands)
        if total_agents <= capacity:
            continue

        # Overflow detected - try to reduce demand at this hour
        overflow = total_agents - capacity

        # Process lowest-priority customers first (they're at the end of sorted_by_priority)
        for demand in reversed(sorted_by_priority):
            if overflow <= 0:
                break

            current_calls = demand.current_calls.get(hour, 0)
            if current_calls <= 0:
                continue

            current_agents = get_agents_needed(demand, hour)
            if current_agents <= 0:
                continue

            # Find spillover candidates: hours within customer's window with available capacity
            spillover_hours = get_spillover_candidates(demand, hour, demands, capacity)

            for target_hour, available_capacity in spillover_hours:
                if overflow <= 0 or current_calls <= 0:
                    break

                # Calculate how many calls we can move
                calls_per_agent = (
                    1 / demand.agents_per_call if demand.agents_per_call > 0 else 0
                )
                # Limit by: source calls, target capacity, AND overflow needed
                calls_to_resolve_overflow = overflow * calls_per_agent
                max_calls_to_move = min(
                    current_calls,
                    available_capacity * calls_per_agent,
                    calls_to_resolve_overflow,
                )

                if max_calls_to_move > 0:
                    # Move calls
                    demand.current_calls[hour] = (
                        demand.current_calls.get(hour, 0) - max_calls_to_move
                    )
                    demand.current_calls[target_hour] = (
                        demand.current_calls.get(target_hour, 0) + max_calls_to_move
                    )
                    current_calls -= max_calls_to_move

                    agents_freed = math.ceil(max_calls_to_move * demand.agents_per_call)
                    overflow -= agents_freed

                    redistributions.append(
                        RedistributionSummary(
                            customer=demand.name,
                            from_hour=hour,
                            to_hour=target_hour,
                            calls_moved=max_calls_to_move,
                        )
                    )

    return redistributions


def get_spillover_candidates(
    demand: CustomerHourlyDemand,
    source_hour: int,
    all_demands: list[CustomerHourlyDemand],
    capacity: int,
) -> list[tuple[int, int]]:
    """
    Find valid target hours for redistribution, sorted by proximity to source hour.

    Returns list of (hour, available_capacity) tuples.
    """
    candidates = []

    for target_hour in range(demand.start_hour, demand.end_hour):
        if target_hour == source_hour:
            continue

        # Calculate current usage at target hour
        total_at_target = sum(get_agents_needed(d, target_hour) for d in all_demands)
        available = capacity - total_at_target

        if available > 0:
            distance = abs(target_hour - source_hour)
            candidates.append((target_hour, available, distance))

    # Sort by distance (prefer closer hours)
    candidates.sort(key=lambda x: x[2])

    return [(h, avail) for h, avail, _ in candidates]


def schedule_with_capacity_shift(
    records: list[CustomerRecord], utilization: float, capacity: int
) -> tuple[list[HourlyAllocation], list[RedistributionSummary]]:
    """
    Schedule with capacity constraint using single-pass redistribution.

    Move overflow calls to hours with available capacity within each customer's window.
    Lower-priority customers are processed first (most flexible for redistribution).
    """
    # Build initial demand distribution
    demands = build_customer_demands(records, utilization)

    # Sort by priority (ascending: 1 = highest priority first)
    sorted_by_priority = sorted(demands, key=lambda d: d.priority)

    # Single-pass redistribution
    redistributions = apply_redistribution(demands, capacity, sorted_by_priority)

    # Now perform final greedy allocation with the redistributed demands
    allocations = []
    for hour in range(24):
        remaining_capacity = capacity
        customer_agents = {}
        unmet_demand = {}

        # Allocate by priority
        for demand in sorted_by_priority:
            required = get_agents_needed(demand, hour)
            if required > 0:
                allocated = min(required, remaining_capacity)
                if allocated > 0:
                    customer_agents[demand.name] = allocated
                    remaining_capacity -= allocated

                if required > allocated:
                    unmet_demand[demand.name] = required - allocated

        allocations.append(
            HourlyAllocation(
                hour=hour,
                total_agents=sum(customer_agents.values()),
                customer_agents=customer_agents,
                unmet_demand=unmet_demand,
            )
        )

    return allocations, redistributions


def main():
    # Parse CLI arguments
    args = parse_args()

    # Parse input CSV
    records = parse_csv(args.input_path)

    if not records:
        print("Error: No valid records found in input file", file=sys.stderr)
        sys.exit(1)

    # Schedule
    if args.capacity is not None:
        if args.algorithm == "shift":
            allocations, redistributions = schedule_with_capacity_shift(
                records, args.utilization, args.capacity
            )
            # Print redistribution summary if any moves were made
            if redistributions:
                print(
                    f"\n[Shift Algorithm] {len(redistributions)} call redistributions made:",
                    file=sys.stderr,
                )
                for r in redistributions[:10]:  # Show first 10
                    print(
                        f"  {r.customer}: {r.from_hour:02d}:00 → {r.to_hour:02d}:00 ({r.calls_moved:.0f} calls)",
                        file=sys.stderr,
                    )
                if len(redistributions) > 10:
                    print(
                        f"  ... and {len(redistributions) - 10} more", file=sys.stderr
                    )
        else:
            # schedule with greedy algorithm by default
            allocations = schedule_with_capacity(
                records, args.utilization, args.capacity
            )
        show_unmet = True
    else:
        allocations = schedule_unconstrained(records, args.utilization)
        show_unmet = False

    # Format output
    if args.format == "text":
        output = format_text(allocations, show_unmet)
    elif args.format == "json":
        output = format_json(allocations)
    else:  # csv
        output = format_csv_output(allocations)

    # Print to stdout
    print(output)

    # Print metrics summary
    print_metrics(records, allocations)

    # Write result file
    result_file = write_result_file(
        output,
        args.format,
        args.input_path,
        args.utilization,
        args.capacity,
        args.algorithm,
    )
    print(f"\nResult written to: {result_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
