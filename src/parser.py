"""
CSV Parser module for Hippo Call Scheduler.

Handles parsing and validation of input CSV files.
"""

import csv
import sys
from dataclasses import dataclass


class CSVColumns:
    """CSV column name constants. Update here if column names change."""

    CUSTOMER_NAME = "CustomerName"
    AVG_CALL_DURATION_SECONDS = "AverageCallDurationSeconds"
    START_TIME_PT = "StartTimePT"
    END_TIME_PT = "EndTimePT"
    NUMBER_OF_CALLS = "NumberOfCalls"
    PRIORITY = "Priority"

    # All required columns for validation
    REQUIRED = [
        CUSTOMER_NAME,
        AVG_CALL_DURATION_SECONDS,
        START_TIME_PT,
        END_TIME_PT,
        NUMBER_OF_CALLS,
        PRIORITY,
    ]


@dataclass
class CustomerRecord:
    """Validated customer call requirement."""

    name: str
    avg_duration_seconds: int
    start_hour: int  # 0-23 inclusive
    end_hour: int  # 0-23 exclusive
    num_calls: int
    priority: int  # 1-5, 1 is highest


def parse_time(time_str: str) -> int:
    """Parse time string like '9AM', '12PM', '7PM' to hour (0-23)."""
    time_str = time_str.strip().upper()

    # Handle edge cases
    if not time_str:
        raise ValueError("Empty time string")

    # Extract numeric part and AM/PM
    if time_str.endswith("AM"):
        period = "AM"
        hour_str = time_str[:-2]
    elif time_str.endswith("PM"):
        period = "PM"
        hour_str = time_str[:-2]
    else:
        raise ValueError(
            f"Invalid time format: {time_str}. Expected format like '9AM' or '7PM'"
        )

    try:
        hour = int(hour_str)
    except ValueError:
        raise ValueError(f"Invalid hour in time: {time_str}")

    if hour < 1 or hour > 12:
        raise ValueError(f"Hour must be 1-12, got: {hour}")

    # Convert to 24-hour format
    if period == "AM":
        if hour == 12:
            return 0  # 12AM = midnight = 0
        return hour
    else:  # PM
        if hour == 12:
            return 12  # 12PM = noon = 12
        return hour + 12


def parse_csv(filepath: str) -> list[CustomerRecord]:
    """Parse and validate input CSV file."""
    records = []

    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate required columns exist in header
        if reader.fieldnames is None:
            print("Error: CSV file is empty or has no header row", file=sys.stderr)
            sys.exit(1)

        header_cols = {col.strip() for col in reader.fieldnames if col}
        missing_headers = [col for col in CSVColumns.REQUIRED if col not in header_cols]
        if missing_headers:
            print(
                f"Error: CSV header is missing required column(s): {', '.join(missing_headers)}",
                file=sys.stderr,
            )
            sys.exit(1)

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Check for extra columns (None key indicates more values than headers)
                if None in row:
                    raise ValueError(
                        f"Row {row_num} has more columns than expected. Extra value(s): {row[None]}"
                    )

                # Check for missing columns (None value indicates fewer values than headers)
                missing_cols = [k for k, v in row.items() if v is None]
                if missing_cols:
                    raise ValueError(
                        f"Row {row_num} is missing value(s) for column(s): {', '.join(missing_cols)}"
                    )

                # Strip whitespace from keys and values
                row = {k.strip(): v.strip() for k, v in row.items()}

                # Parse fields
                name = row.get(CSVColumns.CUSTOMER_NAME, "")
                if not name:
                    raise ValueError(f"{CSVColumns.CUSTOMER_NAME} is required")

                avg_duration = int(row.get(CSVColumns.AVG_CALL_DURATION_SECONDS, 0))
                if avg_duration <= 0:
                    raise ValueError(f"{CSVColumns.AVG_CALL_DURATION_SECONDS} must be positive")

                start_time_str = row.get(CSVColumns.START_TIME_PT, "")
                end_time_str = row.get(CSVColumns.END_TIME_PT, "")
                start_hour = parse_time(start_time_str)
                end_hour = parse_time(end_time_str)

                # End time is exclusive, so 7PM means up to but not including 19:00
                if end_hour <= start_hour:
                    raise ValueError(
                        f"{CSVColumns.END_TIME_PT} ({end_time_str}) must be after {CSVColumns.START_TIME_PT} ({start_time_str})"
                    )

                num_calls = int(row.get(CSVColumns.NUMBER_OF_CALLS, 0))
                if num_calls < 0:
                    raise ValueError(f"{CSVColumns.NUMBER_OF_CALLS} cannot be negative")

                priority = int(row.get(CSVColumns.PRIORITY, 0))
                if priority < 1 or priority > 5:
                    raise ValueError(f"{CSVColumns.PRIORITY} must be 1-5, got: {priority}")

                records.append(
                    CustomerRecord(
                        name=name,
                        avg_duration_seconds=avg_duration,
                        start_hour=start_hour,
                        end_hour=end_hour,
                        num_calls=num_calls,
                        priority=priority,
                    )
                )

            except Exception as e:
                print(f"Error parsing row {row_num}: {e}", file=sys.stderr)
                sys.exit(1)

    return records
