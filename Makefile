.PHONY: run test clean

# Default values
INPUT ?= ./input.csv
UTILIZATION ?= 1.0
FORMAT ?= text
CAPACITY ?=
ALGO ?= greedy

# Build the capacity flag if provided
ifdef CAPACITY
	CAPACITY_FLAG = --capacity $(CAPACITY)
else
	CAPACITY_FLAG =
endif

# Run the scheduler
run:
	@python3 src/scheduler.py --input $(INPUT) --utilization $(UTILIZATION) --format $(FORMAT) $(CAPACITY_FLAG) --algorithm $(ALGO)

# Run tests (uses unittest, falls back to pytest if available)
test:
	@python3 -m unittest discover -s tests -v

# Clean generated files
clean:
	@rm -rf results/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
