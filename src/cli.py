"""
CLI module for Hippo Call Scheduler.

Handles command-line argument parsing.
"""

import argparse
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class SchedulerArgs:
    """Parsed command-line arguments."""

    input_path: str
    utilization: float
    format: str
    capacity: Optional[int]
    algorithm: str


def parse_args(args: list[str] = None) -> SchedulerArgs:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Hippo Call Scheduler - Compute hourly agent staffing requirements"
    )
    parser.add_argument(
        "--input", "-i", required=True, dest="input_path", help="Path to input CSV file"
    )
    parser.add_argument(
        "--utilization",
        "-u",
        type=float,
        default=1.0,
        help="Agent utilization factor (0.0-1.0, default: 1.0)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--capacity",
        "-c",
        type=int,
        default=None,
        help="Maximum agent capacity (enables priority-based allocation)",
    )
    parser.add_argument(
        "--algorithm",
        "-a",
        choices=["greedy", "shift"],
        default="greedy",
        help="Scheduling algorithm: greedy (default) or shift (peak shaving + time-shifting)",
    )

    parsed = parser.parse_args(args)

    # Validate utilization
    if parsed.utilization <= 0 or parsed.utilization > 1:
        print(
            "Error: utilization must be between 0 (exclusive) and 1 (inclusive)",
            file=sys.stderr,
        )
        sys.exit(1)

    return SchedulerArgs(
        input_path=parsed.input_path,
        utilization=parsed.utilization,
        format=parsed.format,
        capacity=parsed.capacity,
        algorithm=parsed.algorithm,
    )
