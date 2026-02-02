# Design Document: Hippo Call Scheduler

## Overview

**Problem**: Schedule AI agents to call patients throughout the day based on customer requirements.

**Input**: CSV with customer call requirements (name, duration, time window, volume, priority)

**Output**: Hour-by-hour agent staffing plan (24 lines for 00:00-23:00 PT), saved as `<TIMESTAMP>_RESULT.<ext>` where extension matches format (`.txt`, `.json`, or `.csv`)

---

## High-Level Architecture

### Modules

| Module | File | Responsibility |
|--------|------|----------------|
| **CLI Parser** | `cli.py` | Parse and validate command-line arguments |
| **CSV Parser** | `parser.py` | Read/validate input CSV, parse time strings |
| **Scheduler** | `scheduler.py` | Compute agents per hour, format output, write results |

### Data Flow

```
Input CSV → CSV Parser → Validated Records → Scheduler → Hourly Schedule → Formatter → Output
```

---

## Core Algorithm

### Basic Calculation

```
calls_per_hour = NumberOfCalls / active_hours
agents_per_hour = ceil(calls_per_hour * avg_duration_seconds / 3600 / utilization)
```

- Time buckets: hourly, StartTime inclusive, EndTime exclusive
- Calls uniformly distributed across active hours

### Priority-Aware Scheduling (with --capacity)

**Greedy Allocation** (default, `--algorithm greedy`):
1. Sort customers by priority (1 = highest)
2. Fully satisfy high-priority customers first
3. Allocate remaining capacity to lower-priority
4. Report utilization and unmet demand per customer

**Shift: Single-Pass Redistribution** (`--algorithm shift`):

Move overflow calls to hours with available capacity within each customer's time window:
- Process hours sequentially; when overflow detected, redistribute excess calls
- Lower-priority customers processed first (most flexible for redistribution)
- Target hours sorted by proximity to source hour (prefer closer hours)
- Higher-priority customers' distributions remain unchanged

**Shift Algorithm Technical Details**:
  1. demands and sorted_by_priority share the same objects - sorting creates a new list but the CustomerHourlyDemand instances are shared references
  2. Only current_calls is mutated during redistribution to reflect the re-allocation - original_calls is preserved for potential auditing
  3. Processing order: Lowest priority customers are processed first (via reversed(sorted_by_priority)) since they're most flexible to shift
  4. In-place mutation: The redistribution function mutates demand objects directly

**Constraints preserved by shift algorithm:**
- Calls only within customer's active hours (StartTime to EndTime)
- Total calls per customer unchanged
- Higher-priority customers less likely to be affected by redistribution

| Approach | Pro | Con |
|----------|-----|-----|
| Greedy | Guarantees SLA for critical customers | May starve low-priority |
| Shift | Maximizes throughput while respecting priority | More complex; may change expected call times |

---

## Technology

- **Language**: Python 3.x
- **Dependencies**: Standard library only (argparse, csv, math, datetime, json)

---

## Testing Approach

| Test Type | Coverage |
|-----------|----------|
| Unit | CSV parsing, time parsing (12AM/PM), agent calculation |
| Edge cases | End before start, empty rows, invalid priority (outside 1-5) |
| Golden test | Sample CSV produces stable, committed output |
| Idempotency | Same input always yields identical output |

---

## Observability

- Total calls ingested (per run)
- Compute time
- Unmet demand when capacity-constrained

---

## Future Enhancements

- Calendar UI for building input CSV
- Multiple shifts / follow-up calls
- Timezone & daylight saving handling with library support
- Metrics and monitoring integration
