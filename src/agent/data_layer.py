"""Mock data layer for PlaceGuard.

Provides an in-memory database for development and testing.
In production, this would be replaced with PostgreSQL + PostGIS queries.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional
from agent.schemas import PlaceDetails, ValidationIssue


# ---------------------------------------------------------------------------
# Mock Place Database
# This simulates what would be a PostgreSQL + PostGIS table in production.
# The schema is identical to the production schema.
# ---------------------------------------------------------------------------
PLACES_DB: dict[str, dict] = {
    "sky-lounge-gangnam": {
        "id": "sky-lounge-gangnam",
        "name": "Sky Lounge Gangnam",
        "category": "Rooftop Bar",
        "city": "Seoul",
        "country": "KR",
        "address": "22F 123 Gangnam-daero, Gangnam-gu, Seoul",
        "hours": "Mon-Sun 6PM-2AM",
        "price_tier": "$$",
        "average_rating": 4.3,
        "review_count": 2847,
        "reviews_summary": "Stunning views, excellent cocktails, vibey atmosphere",
        "operating": True,
        "verified": True,
        "safety_score": 0.92,
        "tourist_friendly": True,
        "last_updated": (datetime.utcnow() - timedelta(days=2)).isoformat(),
        "coordinates": {"lat": 37.5172, "lng": 127.0473},
        "tags": ["rooftop", "cocktails", "views", "upscale", "Gangnam"],
        "price_range": {"min_usd": 14, "max_usd": 22},
    },
    "myeongdong-pojangmacha": {
        "id": "myeongdong-pojangmacha",
        "name": "Myeongdong Tteokbokki Alley",
        "category": "Street Food Market",
        "city": "Seoul",
        "country": "KR",
        "address": "Myeongdong 2-ga, Jung-gu, Seoul",
        "hours": "Mon-Sun 10AM-11PM",
        "price_tier": "$",
        "average_rating": 4.6,
        "review_count": 15200,
        "reviews_summary": "Authentic Korean street food, must-try for tourists",
        "operating": True,
        "verified": True,
        "safety_score": 0.89,
        "tourist_friendly": True,
        "last_updated": (datetime.utcnow() - timedelta(days=1)).isoformat(),
        "coordinates": {"lat": 37.5636, "lng": 126.9827},
        "tags": ["street food", "affordable", "tourist", "Korean food"],
        "price_range": {"min_usd": 3, "max_usd": 12},
    },
    "nobu-tokyo": {
        "id": "nobu-tokyo",
        "name": "Nobu Tokyo",
        "category": "Japanese Fine Dining",
        "city": "Tokyo",
        "country": "JP",
        "address": "4-1-28 Minami-Aoyama, Minato-ku, Tokyo",
        "hours": "Mon-Sun 6PM-12AM",
        "price_tier": "$$$$",
        "average_rating": 4.8,
        "review_count": 4320,
        "reviews_summary": "World-class sushi, exceptional service, beautiful interior",
        "operating": True,
        "verified": True,
        "safety_score": 0.97,
        "tourist_friendly": True,
        "last_updated": (datetime.utcnow() - timedelta(days=5)).isoformat(),
        "coordinates": {"lat": 35.6654, "lng": 139.7228},
        "tags": ["fine dining", "sushi", "luxury", "reservation required"],
        "price_range": {"min_usd": 80, "max_usd": 200},
    },
    "ghost-restaurant-hallucinated": {
        # This place doesn't exist - used to test hallucination detection
        "id": "ghost-restaurant-hallucinated",
        "name": "Phantom Bistro",
        "category": "Restaurant",
        "city": "Seoul",
        "country": "KR",
        "address": "999 Fake Street, Seoul",
        "hours": None,
        "price_tier": "$$",
        "average_rating": None,
        "review_count": 0,
        "reviews_summary": None,
        "operating": False,
        "verified": False,
        "safety_score": 0.1,
        "tourist_friendly": None,
        "last_updated": (datetime.utcnow() - timedelta(days=365)).isoformat(),
        "coordinates": None,
        "tags": [],
        "price_range": None,
    },
    "stale-cafe-itaewon": {
        "id": "stale-cafe-itaewon",
        "name": "Itaewon Corner Cafe",
        "category": "Cafe",
        "city": "Seoul",
        "country": "KR",
        "address": "45 Itaewon-ro, Yongsan-gu, Seoul",
        "hours": "Tue-Sun 9AM-6PM",  # Closed Mondays
        "price_tier": "$",
        "average_rating": 3.9,
        "review_count": 342,
        "reviews_summary": "Decent coffee, nice ambiance, can be crowded on weekends",
        "operating": True,
        "verified": True,
        "safety_score": 0.78,
        "tourist_friendly": True,
        "last_updated": (datetime.utcnow() - timedelta(days=180)).isoformat(),  # Stale!
        "coordinates": {"lat": 37.5345, "lng": 126.9947},
        "tags": ["cafe", "coffee", "itaewon"],
        "price_range": {"min_usd": 4, "max_usd": 10},
    },
    "closed-restaurant-hongdae": {
        "id": "closed-restaurant-hongdae",
        "name": "Hongdae BBQ Palace",
        "category": "Korean BBQ",
        "city": "Seoul",
        "country": "KR",
        "address": "67 Wausan-ro, Mapo-gu, Seoul",
        "hours": None,
        "price_tier": "$$",
        "average_rating": 4.1,
        "review_count": 890,
        "reviews_summary": "Permanently closed as of March 2026",
        "operating": False,  # Permanently closed
        "verified": True,
        "safety_score": 0.0,
        "tourist_friendly": None,
        "last_updated": (datetime.utcnow() - timedelta(days=30)).isoformat(),
        "coordinates": {"lat": 37.5521, "lng": 126.9241},
        "tags": ["closed", "Korean BBQ", "Hongdae"],
        "price_range": None,
    },
}


def search_places(
    query: str,
    city: Optional[str] = None,
    category: Optional[str] = None,
    price_tier: Optional[str] = None,
    max_results: int = 5,
) -> list[dict]:
    """
    Search places in the mock database.
    
    In production: this would use PostgreSQL full-text search + PostGIS proximity.
    
    Args:
        query: Search query string
        city: Optional city filter
        category: Optional category filter
        price_tier: Optional price tier filter
        max_results: Maximum results to return
        
    Returns:
        List of matching place dicts
    """
    results = []
    query_lower = query.lower()
    
    for place_id, place in PLACES_DB.items():
        score = 0
        
        # Name match
        if query_lower in place["name"].lower():
            score += 10
        
        # City match
        if city and city.lower() in place["city"].lower():
            score += 5
        elif any(word in place["city"].lower() for word in query_lower.split()):
            score += 3
        
        # Category/tag match
        for tag in place.get("tags", []):
            if tag.lower() in query_lower:
                score += 2
        
        if category and category.lower() in place["category"].lower():
            score += 4
        
        # Price tier filter
        if price_tier and place.get("price_tier") == price_tier:
            score += 2
        
        # Keyword matching in query
        keywords = [
            "rooftop", "bar", "restaurant", "cafe", "food", "street",
            "sushi", "bbq", "cocktail", "gangnam", "myeongdong", "itaewon",
            "tokyo", "seoul", "hongdae", "fine dining"
        ]
        for keyword in keywords:
            if keyword in query_lower and keyword in str(place).lower():
                score += 1
        
        if score > 0:
            results.append((score, place))
    
    # Sort by relevance score
    results.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in results[:max_results]]


def get_place_by_id(place_id: str) -> Optional[dict]:
    """Get a specific place by ID."""
    return PLACES_DB.get(place_id)


def check_data_freshness(last_updated_iso: str) -> str:
    """
    Determine data freshness based on last update time.
    
    Returns:
        'current': Updated within 7 days
        'recent': Updated within 30 days
        'stale': Older than 30 days
    """
    last_updated = datetime.fromisoformat(last_updated_iso)
    age = datetime.utcnow() - last_updated
    
    if age.days <= 7:
        return "current"
    elif age.days <= 30:
        return "recent"
    else:
        return "stale"


def calculate_price_match(
    place: dict,
    claimed_max_price: Optional[float] = None,
    currency: str = "USD"
) -> tuple[bool, list[str]]:
    """
    Verify if place price matches claims.
    
    Returns:
        Tuple of (price_verified: bool, issues: list[str])
    """
    issues = []
    price_range = place.get("price_range")
    
    if not price_range:
        return True, ["No price range data available for verification"]
    
    if claimed_max_price is not None:
        if price_range["max_usd"] > claimed_max_price:
            issues.append(
                f"Price may exceed claim: max ${price_range['max_usd']} vs claimed ${claimed_max_price}"
            )
            return False, issues
    
    return True, []


# ---------------------------------------------------------------------------
# Validation History (in-memory, in production use Redis or PostgreSQL)
# ---------------------------------------------------------------------------
_validation_history: list[dict] = []


def save_validation(result_dict: dict) -> None:
    """Save a validation result to history."""
    _validation_history.append(result_dict)
    # Keep only last 100 validations in memory
    if len(_validation_history) > 100:
        _validation_history.pop(0)


def get_validation_history(limit: int = 20) -> list[dict]:
    """Get recent validation history."""
    return list(reversed(_validation_history[-limit:]))
