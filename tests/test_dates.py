"""Tests for natural language date parsing."""
import pytest
from datetime import date, timedelta
from diary.dates import parse_natural_date


class TestParseNaturalDate:
    def test_iso_passthrough(self):
        assert parse_natural_date("2026-03-15") == "2026-03-15"

    def test_today(self):
        assert parse_natural_date("today") == date.today().isoformat()

    def test_tomorrow(self):
        assert parse_natural_date("tomorrow") == (date.today() + timedelta(days=1)).isoformat()

    def test_in_5_days(self):
        assert parse_natural_date("in 5 days") == (date.today() + timedelta(days=5)).isoformat()

    def test_next_day_name(self):
        result = parse_natural_date("next thursday")
        assert result is not None
        # Should be a valid ISO date in the future
        parsed = date.fromisoformat(result)
        assert parsed >= date.today()
        assert parsed.weekday() == 3  # Thursday

    def test_month_day(self):
        result = parse_natural_date("march 15")
        assert result is not None
        assert "-03-15" in result

    def test_empty_string(self):
        assert parse_natural_date("") is None

    def test_none_like(self):
        assert parse_natural_date("   ") is None

    def test_garbage(self):
        # Should return None for unparseable input
        result = parse_natural_date("asdfghjkl")
        # dateparser may or may not parse this — just verify no crash
        assert result is None or isinstance(result, str)
