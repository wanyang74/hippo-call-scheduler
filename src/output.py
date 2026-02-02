#!/usr/bin/env python3
"""
Output formatting, metrics, and file writing for Hippo Call Scheduler.
"""

import json
import os
import sys
from datetime import datetime

from parser import CustomerRecord


def format_text(allocations: list, show_unmet: bool = False) -> str:
    """Format allocations as text output."""
    lines = []
    for alloc in allocations:
        hour_str = f"{alloc.hour:02d}:00"

        if alloc.customer_agents:
            customers_str = ", ".join(
                f"{name}={agents}" for name, agents in alloc.customer_agents.items()
            )
        else:
            customers_str = "none"

        line = f"{hour_str} : total={alloc.total_agents} ; {customers_str}"

        if show_unmet and alloc.unmet_demand:
            unmet_str = ", ".join(
                f"{name}={agents}" for name, agents in alloc.unmet_demand.items()
            )
            line += f" | unmet: {unmet_str}"

        lines.append(line)

    return "\n".join(lines)


def format_json(allocations: list) -> str:
    """Format allocations as JSON output."""
    data = []
    for alloc in allocations:
        entry = {
            "hour": f"{alloc.hour:02d}:00",
            "total_agents": alloc.total_agents,
            "customers": alloc.customer_agents,
        }
        if alloc.unmet_demand:
            entry["unmet_demand"] = alloc.unmet_demand
        data.append(entry)

    return json.dumps(data, indent=2)


def format_csv_output(allocations: list) -> str:
    """Format allocations as CSV output."""
    lines = ["hour,total_agents,customers,unmet_demand"]
    for alloc in allocations:
        customers_str = (
            ";".join(f"{k}={v}" for k, v in alloc.customer_agents.items()) or "none"
        )
        unmet_str = ";".join(f"{k}={v}" for k, v in alloc.unmet_demand.items()) or ""
        lines.append(
            f'{alloc.hour:02d}:00,{alloc.total_agents},"{customers_str}","{unmet_str}"'
        )

    return "\n".join(lines)


def write_result_file(
    content: str,
    format_type: str,
    input_path: str,
    utilization: float,
    capacity: int | None,
    algorithm: str = "greedy",
) -> str:
    """Write result to file with descriptive name in results/ directory.

    Filename format: {timestamp}_{input_name}_util{utilization}[_cap{capacity}][_{algorithm}].{ext}
    """
    # Ensure results directory exists
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Extract input file name without path and extension
    input_name = os.path.splitext(os.path.basename(input_path))[0]

    # Format utilization (remove trailing zeros, e.g., 1.0 -> 1, 0.85 -> 0.85)
    util_str = f"{utilization:.2f}".rstrip("0").rstrip(".")

    # Build filename parts
    name_parts = [timestamp, input_name, f"util{util_str}"]
    if capacity is not None:
        name_parts.append(f"cap{capacity}")
        if algorithm != "greedy":
            name_parts.append(algorithm)

    # Choose extension based on format type
    extensions = {"text": "txt", "json": "json", "csv": "csv"}
    ext = extensions.get(format_type, "txt")
    filename = os.path.join(results_dir, f"{'_'.join(name_parts)}_RESULT.{ext}")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


def print_metrics(
    records: list[CustomerRecord], allocations: list
) -> None:
    """Print observability metrics summary to stderr."""
    # Total calls ingested
    total_calls = sum(r.num_calls for r in records)

    # Total agents for the day (sum of hourly totals)
    total_agents_day = sum(a.total_agents for a in allocations)

    # Peak agents (max in any hour)
    peak_agents = max(a.total_agents for a in allocations) if allocations else 0

    # Unmet demand analysis
    unmet_by_hour: dict[int, dict[str, int]] = {}
    total_unmet_agents = 0
    for alloc in allocations:
        if alloc.unmet_demand:
            unmet_by_hour[alloc.hour] = alloc.unmet_demand
            total_unmet_agents += sum(alloc.unmet_demand.values())

    # Calculate actual calls conducted (estimate based on agent allocation ratio)
    total_agents_required = total_agents_day + total_unmet_agents
    if total_agents_required > 0:
        allocation_ratio = total_agents_day / total_agents_required
        calls_conducted = int(total_calls * allocation_ratio)
    else:
        allocation_ratio = 1.0
        calls_conducted = 0

    # Print metrics
    print("\n" + "=" * 50, file=sys.stderr)
    print("METRICS SUMMARY", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print(f"Total calls required:    {total_calls:,}", file=sys.stderr)
    print(f"Total calls conducted:   {calls_conducted:,} ({allocation_ratio:.1%})", file=sys.stderr)
    print(f"Total agent-hours:       {total_agents_day:,}", file=sys.stderr)
    print(f"Peak agents (any hour):  {peak_agents:,}", file=sys.stderr)

    if unmet_by_hour:
        print(f"\nUnmet demand:            {total_unmet_agents:,} agent-hours", file=sys.stderr)
        print("-" * 50, file=sys.stderr)
        print("Unmet demand breakdown by hour:", file=sys.stderr)
        for hour in sorted(unmet_by_hour.keys()):
            unmet = unmet_by_hour[hour]
            hour_total = sum(unmet.values())
            customers_str = ", ".join(f"{name}={agents}" for name, agents in unmet.items())
            print(f"  {hour:02d}:00 : {hour_total:,} agents ({customers_str})", file=sys.stderr)
    else:
        print("\nUnmet demand:            None", file=sys.stderr)

    print("=" * 50 + "\n", file=sys.stderr)
