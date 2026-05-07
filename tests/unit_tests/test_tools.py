"""Unit tests for PlaceGuard validation tools."""

import json
import pytest
from agent.tools import (
    validate_place_existence,
    check_operating_hours,
    verify_pricing,
    assess_safety_and_risk,
    enrich_place_data,
    lookup_similar_alternatives,
)


class TestValidatePlaceExistence:
    """Tests for the existence validation tool."""

    def test_finds_existing_place(self):
        result = json.loads(
            validate_place_existence.invoke({"place_name": "Sky Lounge Gangnam", "city": "Seoul"})
        )
        assert result["exists"] is True
        assert result["place_id"] == "sky-lounge-gangnam"
        assert result["confidence"] >= 0.6

    def test_hallucinated_place_not_found(self):
        result = json.loads(
            validate_place_existence.invoke(
                {"place_name": "Grand Celestial Palace Invisible Hotel"}
            )
        )
        assert result["exists"] is False
        assert result["confidence"] <= 0.3

    def test_find_with_only_name(self):
        result = json.loads(
            validate_place_existence.invoke({"place_name": "Nobu Tokyo"})
        )
        assert result["exists"] is True

    def test_returns_suggestions_on_miss(self):
        result = json.loads(
            validate_place_existence.invoke({"place_name": "Xyzzy Nonexistent Place Abcde"})
        )
        # Completely made-up name - should have no match or very low confidence
        if not result["exists"]:
            assert "suggestions" in result
        else:
            # If it somehow matched, confidence should be low
            assert result["confidence"] < 0.6


class TestCheckOperatingHours:
    """Tests for operating hours tool."""

    def test_open_place(self):
        result = json.loads(
            check_operating_hours.invoke({"place_id": "sky-lounge-gangnam"})
        )
        assert result["operating"] is True
        assert result["hours"] is not None

    def test_closed_place(self):
        result = json.loads(
            check_operating_hours.invoke({"place_id": "closed-restaurant-hongdae"})
        )
        assert result["operating"] is False
        assert len(result["issues"]) > 0

    def test_stale_data_flagged(self):
        result = json.loads(
            check_operating_hours.invoke({"place_id": "stale-cafe-itaewon"})
        )
        assert result["data_freshness"] == "stale"
        assert any("stale" in issue.lower() for issue in result["issues"])

    def test_invalid_place_id(self):
        result = json.loads(
            check_operating_hours.invoke({"place_id": "does-not-exist-xyz"})
        )
        assert result["operating"] is False
        assert len(result["issues"]) > 0


class TestVerifyPricing:
    """Tests for price verification tool."""

    def test_price_within_range(self):
        result = json.loads(
            verify_pricing.invoke({
                "place_id": "sky-lounge-gangnam",
                "claimed_max_price": 25.0,
            })
        )
        assert result["price_verified"] is True
        assert result["price_tier"] == "$$"

    def test_price_exceeds_claim(self):
        result = json.loads(
            verify_pricing.invoke({
                "place_id": "nobu-tokyo",
                "claimed_max_price": 20.0,
            })
        )
        assert result["price_verified"] is False
        assert len(result["issues"]) > 0

    def test_no_price_claim(self):
        result = json.loads(
            verify_pricing.invoke({"place_id": "sky-lounge-gangnam"})
        )
        assert result["price_verified"] is True

    def test_invalid_place_id(self):
        result = json.loads(
            verify_pricing.invoke({"place_id": "ghost-xyz"})
        )
        assert result["price_verified"] is False


class TestAssessSafetyAndRisk:
    """Tests for safety assessment tool."""

    def test_high_safety_place(self):
        result = json.loads(
            assess_safety_and_risk.invoke({"place_id": "nobu-tokyo"})
        )
        assert result["safety_score"] >= 0.90
        assert result["safety_tier"] == "excellent"

    def test_low_safety_place(self):
        result = json.loads(
            assess_safety_and_risk.invoke({"place_id": "ghost-restaurant-hallucinated"})
        )
        assert result["safety_score"] <= 0.2
        assert result["safety_tier"] == "poor"

    def test_tourist_friendly_flagged(self):
        result = json.loads(
            assess_safety_and_risk.invoke({"place_id": "sky-lounge-gangnam"})
        )
        assert result["tourist_friendly"] is True


class TestEnrichPlaceData:
    """Tests for data enrichment tool."""

    def test_enrichment_success(self):
        result = json.loads(
            enrich_place_data.invoke({"place_id": "myeongdong-pojangmacha"})
        )
        assert result["success"] is True
        assert result["name"] == "Myeongdong Tteokbokki Alley"
        assert len(result["tags"]) > 0
        assert result["reviews_summary"] is not None

    def test_enrichment_fails_for_unknown(self):
        result = json.loads(
            enrich_place_data.invoke({"place_id": "nonexistent-xyz"})
        )
        assert result["success"] is False


class TestLookupSimilarAlternatives:
    """Tests for the alternatives lookup tool."""

    def test_finds_alternatives_in_city(self):
        result = json.loads(
            lookup_similar_alternatives.invoke({
                "query": "bar Seoul",
                "city": "Seoul",
            })
        )
        assert result["found"] is True
        assert len(result["alternatives"]) > 0

    def test_filters_closed_places(self):
        """Should not suggest closed places as alternatives."""
        result = json.loads(
            lookup_similar_alternatives.invoke({
                "query": "Korean food Seoul",
                "city": "Seoul",
            })
        )
        if result["found"]:
            for alt in result["alternatives"]:
                # All alternatives should be from operating places
                # (we can't directly assert without querying the DB,
                # but the tool should filter them)
                assert alt.get("place_id") != "closed-restaurant-hongdae"

    def test_empty_query_graceful(self):
        result = json.loads(
            lookup_similar_alternatives.invoke({"query": "xyzabc123nonexistent"})
        )
        # Should not crash, just return found=False
        assert "found" in result
