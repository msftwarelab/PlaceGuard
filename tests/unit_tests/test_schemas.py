"""Unit tests for PlaceGuard schemas."""

import pytest
from datetime import datetime
from agent.schemas import (
    PlaceQuery,
    ValidationResult,
    PlaceDetails,
    ValidationIssue,
    BenchmarkScenario,
)


class TestPlaceQuery:
    """Tests for PlaceQuery input model."""

    def test_valid_query(self):
        """Basic valid query."""
        q = PlaceQuery(query="Rooftop bar in Gangnam")
        assert q.query == "Rooftop bar in Gangnam"
        assert q.context is None

    def test_query_with_context(self):
        """Query with context dict."""
        q = PlaceQuery(
            query="Find me a bar",
            context={"city": "Seoul", "country": "KR"},
        )
        assert q.context["city"] == "Seoul"

    def test_query_too_short(self):
        """Query below minimum length should raise."""
        with pytest.raises(Exception):
            PlaceQuery(query="AB")

    def test_query_too_long(self):
        """Query above maximum length should raise."""
        with pytest.raises(Exception):
            PlaceQuery(query="x" * 2001)

    def test_query_with_lm_output(self):
        """Query with raw LLM JSON."""
        lm = {"place": "Sky Lounge", "price": "$18"}
        q = PlaceQuery(query="Sky Lounge Gangnam", lm_output=lm)
        assert q.lm_output["place"] == "Sky Lounge"


class TestValidationIssue:
    """Tests for ValidationIssue model."""

    def test_error_severity(self):
        issue = ValidationIssue(severity="error", field="operating", message="Place is closed")
        assert issue.severity == "error"

    def test_warning_severity(self):
        issue = ValidationIssue(
            severity="warning", field="data", message="Stale data"
        )
        assert issue.severity == "warning"

    def test_invalid_severity(self):
        """Invalid severity should raise."""
        with pytest.raises(Exception):
            ValidationIssue(severity="critical", field="test", message="test")


class TestPlaceDetails:
    """Tests for PlaceDetails model."""

    def test_minimal_details(self):
        """PlaceDetails with only required fields."""
        d = PlaceDetails(address="123 Test St")
        assert d.address == "123 Test St"
        assert d.category == "Unknown"
        assert d.data_freshness == "current"

    def test_full_details(self):
        """PlaceDetails with all fields."""
        d = PlaceDetails(
            address="22F Gangnam-daero, Seoul",
            city="Seoul",
            country="KR",
            hours="Mon-Sun 6PM-2AM",
            price_tier="$$",
            category="Rooftop Bar",
            reviews_summary="Great views",
            average_rating=4.5,
            data_freshness="current",
        )
        assert d.price_tier == "$$"
        assert d.average_rating == 4.5

    def test_rating_bounds(self):
        """Rating must be 0-5."""
        with pytest.raises(Exception):
            PlaceDetails(address="test", average_rating=5.1)
        with pytest.raises(Exception):
            PlaceDetails(address="test", average_rating=-0.1)


class TestValidationResult:
    """Tests for ValidationResult model."""

    def _make_result(self, **kwargs) -> ValidationResult:
        """Helper to create a ValidationResult with defaults."""
        defaults = dict(
            place_id="test-123",
            name="Test Place",
            status="valid",
            confidence=0.85,
            exists=True,
            operating=True,
            price_verified=True,
            safety_score=0.9,
            details=PlaceDetails(address="123 Main St"),
            issues=[],
            reasoning_chain=["Step 1: Found place", "Step 2: Verified hours"],
        )
        defaults.update(kwargs)
        return ValidationResult(**defaults)

    def test_valid_result(self):
        r = self._make_result()
        assert r.status == "valid"
        assert r.confidence == 0.85
        assert r.exists is True

    def test_invalid_result(self):
        r = self._make_result(status="invalid", exists=False, confidence=0.1)
        assert r.status == "invalid"

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            self._make_result(confidence=1.1)
        with pytest.raises(Exception):
            self._make_result(confidence=-0.1)

    def test_safety_score_bounds(self):
        with pytest.raises(Exception):
            self._make_result(safety_score=1.5)

    def test_model_dump(self):
        """Result should serialize to JSON-compatible dict."""
        r = self._make_result()
        data = r.model_dump(mode="json")
        assert data["status"] == "valid"
        assert isinstance(data["timestamp"], str)

    def test_with_issues(self):
        issues = [
            ValidationIssue(severity="warning", field="hours", message="Data stale"),
        ]
        r = self._make_result(issues=issues)
        assert len(r.issues) == 1
        assert r.issues[0].severity == "warning"
