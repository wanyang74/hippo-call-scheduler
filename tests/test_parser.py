"""
Unit tests for CSV parsing and time parsing.
"""

import os
import sys
import tempfile
import unittest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from parser import CustomerRecord, parse_time, parse_csv


class TestParseTime(unittest.TestCase):
    """Unit tests for parse_time function."""

    def test_basic_am_times(self):
        """Test basic AM time parsing."""
        self.assertEqual(parse_time("1AM"), 1)
        self.assertEqual(parse_time("6AM"), 6)
        self.assertEqual(parse_time("9AM"), 9)
        self.assertEqual(parse_time("11AM"), 11)

    def test_basic_pm_times(self):
        """Test basic PM time parsing."""
        self.assertEqual(parse_time("1PM"), 13)
        self.assertEqual(parse_time("3PM"), 15)
        self.assertEqual(parse_time("7PM"), 19)
        self.assertEqual(parse_time("11PM"), 23)

    def test_12am_midnight(self):
        """Test 12AM (midnight) edge case."""
        self.assertEqual(parse_time("12AM"), 0)

    def test_12pm_noon(self):
        """Test 12PM (noon) edge case."""
        self.assertEqual(parse_time("12PM"), 12)

    def test_lowercase_input(self):
        """Test that lowercase input is handled."""
        self.assertEqual(parse_time("9am"), 9)
        self.assertEqual(parse_time("7pm"), 19)

    def test_mixed_case_input(self):
        """Test that mixed case input is handled."""
        self.assertEqual(parse_time("9Am"), 9)
        self.assertEqual(parse_time("7Pm"), 19)

    def test_whitespace_handling(self):
        """Test that whitespace is stripped."""
        self.assertEqual(parse_time(" 9AM "), 9)
        self.assertEqual(parse_time("  7PM  "), 19)

    def test_empty_string_raises(self):
        """Test that empty string raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_time("")
        self.assertIn("Empty time string", str(context.exception))

    def test_missing_am_pm_raises(self):
        """Test that missing AM/PM raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_time("9")
        self.assertIn("Invalid time format", str(context.exception))

    def test_invalid_hour_raises(self):
        """Test that invalid hour (>12) raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_time("13AM")
        self.assertIn("Hour must be 1-12", str(context.exception))

    def test_zero_hour_raises(self):
        """Test that 0AM/0PM raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_time("0AM")
        self.assertIn("Hour must be 1-12", str(context.exception))

    def test_non_numeric_hour_raises(self):
        """Test that non-numeric hour raises ValueError."""
        with self.assertRaises(ValueError) as context:
            parse_time("XYZAM")
        self.assertIn("Invalid hour", str(context.exception))


class TestParseCSV(unittest.TestCase):
    """Unit tests for parse_csv function."""

    def _create_temp_csv(self, content: str) -> str:
        """Create a temporary CSV file with given content."""
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_valid_csv_parsing(self):
        """Test parsing a valid CSV file."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Stanford Hospital,300,9AM,7PM,20000,1
VNS,120,6AM,1PM,40500,2"""

        path = self._create_temp_csv(csv_content)
        try:
            records = parse_csv(path)
            self.assertEqual(len(records), 2)

            # Check first record
            self.assertEqual(records[0].name, "Stanford Hospital")
            self.assertEqual(records[0].avg_duration_seconds, 300)
            self.assertEqual(records[0].start_hour, 9)
            self.assertEqual(records[0].end_hour, 19)
            self.assertEqual(records[0].num_calls, 20000)
            self.assertEqual(records[0].priority, 1)

            # Check second record
            self.assertEqual(records[1].name, "VNS")
            self.assertEqual(records[1].avg_duration_seconds, 120)
            self.assertEqual(records[1].start_hour, 6)
            self.assertEqual(records[1].end_hour, 13)
            self.assertEqual(records[1].num_calls, 40500)
            self.assertEqual(records[1].priority, 2)
        finally:
            os.unlink(path)

    def test_whitespace_in_values(self):
        """Test that whitespace in values is handled."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
  Stanford Hospital  , 300 , 9AM , 7PM , 20000 , 1 """

        path = self._create_temp_csv(csv_content)
        try:
            records = parse_csv(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].name, "Stanford Hospital")
            self.assertEqual(records[0].avg_duration_seconds, 300)
        finally:
            os.unlink(path)

    def test_12am_12pm_in_csv(self):
        """Test 12AM and 12PM edge cases in CSV."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Midnight Shift,300,12AM,6AM,1000,1
Noon Shift,300,12PM,6PM,1000,2"""

        path = self._create_temp_csv(csv_content)
        try:
            records = parse_csv(path)
            self.assertEqual(len(records), 2)

            # 12AM = 0, 6AM = 6
            self.assertEqual(records[0].start_hour, 0)
            self.assertEqual(records[0].end_hour, 6)

            # 12PM = 12, 6PM = 18
            self.assertEqual(records[1].start_hour, 12)
            self.assertEqual(records[1].end_hour, 18)
        finally:
            os.unlink(path)


class TestParseCSVEdgeCases(unittest.TestCase):
    """Edge case tests for parse_csv function."""

    def _create_temp_csv(self, content: str) -> str:
        """Create a temporary CSV file with given content."""
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_end_before_start_exits(self):
        """Test that end time before start time causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Bad Customer,300,7PM,9AM,1000,1"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_end_equals_start_exits(self):
        """Test that end time equal to start time causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Bad Customer,300,9AM,9AM,1000,1"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_invalid_priority_too_low_exits(self):
        """Test that priority < 1 causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Bad Customer,300,9AM,5PM,1000,0"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_invalid_priority_too_high_exits(self):
        """Test that priority > 5 causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Bad Customer,300,9AM,5PM,1000,6"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_negative_calls_exits(self):
        """Test that negative number of calls causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Bad Customer,300,9AM,5PM,-100,1"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_zero_duration_exits(self):
        """Test that zero duration causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Bad Customer,0,9AM,5PM,1000,1"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_negative_duration_exits(self):
        """Test that negative duration causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Bad Customer,-100,9AM,5PM,1000,1"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_empty_customer_name_exits(self):
        """Test that empty customer name causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
,300,9AM,5PM,1000,1"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_missing_column_in_row_exits(self):
        """Test that missing column value causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Stanford Hospital,300,9AM,7PM,20000"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_missing_header_column_exits(self):
        """Test that missing header column causes exit."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls
Stanford Hospital,300,9AM,7PM,20000"""

        path = self._create_temp_csv(csv_content)
        try:
            with self.assertRaises(SystemExit):
                parse_csv(path)
        finally:
            os.unlink(path)

    def test_zero_calls_allowed(self):
        """Test that zero calls is allowed (edge case)."""
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
No Calls Customer,300,9AM,5PM,0,1"""

        path = self._create_temp_csv(csv_content)
        try:
            records = parse_csv(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].num_calls, 0)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
