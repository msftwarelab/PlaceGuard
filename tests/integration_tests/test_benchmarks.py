"""Benchmark scenario tests — validate all 6 VOYGR benchmark scenarios.

These tests verify the agent's reasoning quality against known expected outcomes.
Run with: pytest tests/integration_tests/test_benchmarks.py -v
"""

import pytest
import httpx

API_BASE = "http://localhost:8000"


@pytest.fixture(scope="session")
def api_client():
    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def check_api_available():
    try:
        resp = httpx.get(f"{API_BASE}/health", timeout=5.0)
        resp.raise_for_status()
    except Exception:
        pytest.skip("PlaceGuard API is not running. Start with: make serve")


BENCHMARK_CASES = [
    {
        "id": "bench_01",
        "query": "Recommend a rooftop bar in Gangnam under $20 cocktails",
        "context": {"city": "Seoul", "country": "KR"},
        "expected_status": "valid",
        "min_confidence": 0.75,
        "description": "Valid Place — Clear Data",
    },
    {
        "id": "bench_02",
        "query": "Book me a table at The Grand Celestial Palace restaurant in Gangnam",
        "context": {"city": "Seoul", "country": "KR"},
        "expected_status": "invalid",
        "min_confidence": 0.0,
        "description": "Hallucinated Place — LLM Fabrication",
    },
    {
        "id": "bench_03",
        "query": "Korean BBQ dinner at Hongdae BBQ Palace",
        "context": {"city": "Seoul", "country": "KR"},
        "expected_status": "invalid",
        "min_confidence": 0.0,
        "description": "Permanently Closed Place",
    },
    {
        "id": "bench_04",
        "query": "Coffee at Itaewon Corner Cafe",
        "context": {"city": "Seoul", "country": "KR"},
        "expected_status": "uncertain",
        "min_confidence": 0.4,
        "description": "Stale Data Warning",
    },
    {
        "id": "bench_05",
        "query": "Fine dining Japanese restaurant in Minami-Aoyama Tokyo",
        "context": {"city": "Tokyo", "country": "JP"},
        "expected_status": "valid",
        "min_confidence": 0.80,
        "description": "International Fine Dining — High Confidence",
    },
    {
        "id": "bench_06",
        "query": "Street food in Myeongdong Seoul",
        "context": {"city": "Seoul", "country": "KR"},
        "expected_status": "valid",
        "min_confidence": 0.65,
        "description": "Ambiguous — Multiple Matches",
    },
]


@pytest.mark.parametrize(
    "scenario",
    BENCHMARK_CASES,
    ids=[c["id"] for c in BENCHMARK_CASES],
)
def test_benchmark_scenario(api_client, scenario):
    """
    Run each VOYGR benchmark scenario and verify:
    1. Correct status (valid/invalid/uncertain)
    2. Confidence meets minimum threshold
    3. Reasoning chain is non-empty
    4. Response schema is complete
    """
    resp = api_client.post(
        "/validate-place",
        json={"query": scenario["query"], "context": scenario["context"]},
    )
    
    assert resp.status_code == 200, (
        f"[{scenario['id']}] API returned {resp.status_code}: {resp.text[:200]}"
    )
    
    data = resp.json()
    
    # Status check
    assert data["status"] == scenario["expected_status"], (
        f"[{scenario['id']}] {scenario['description']}\n"
        f"  Expected status: {scenario['expected_status']}\n"
        f"  Got status:      {data['status']}\n"
        f"  Confidence:      {data.get('confidence')}\n"
        f"  Reasoning:\n    " + "\n    ".join(data.get("reasoning_chain", []))[:300]
    )
    
    # Confidence check (only for expected valid/uncertain results)
    if scenario["expected_status"] != "invalid":
        assert data["confidence"] >= scenario["min_confidence"], (
            f"[{scenario['id']}] Confidence too low: "
            f"{data['confidence']} < {scenario['min_confidence']}"
        )
    
    # Reasoning chain is populated
    assert len(data.get("reasoning_chain", [])) > 0, (
        f"[{scenario['id']}] Reasoning chain is empty"
    )
    
    # Schema completeness
    for field in ["place_id", "name", "exists", "operating", "safety_score", "details"]:
        assert field in data, f"[{scenario['id']}] Missing field: {field}"
