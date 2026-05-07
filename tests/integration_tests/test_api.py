"""Integration tests for PlaceGuard FastAPI endpoints.

These tests require the API server to be running.
Run with: pytest tests/integration_tests/ -v

To skip API tests in CI without a server:
  pytest --ignore=tests/integration_tests
"""

import pytest
import httpx

API_BASE = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_client():
    """Create a shared HTTP client for all integration tests."""
    with httpx.Client(base_url=API_BASE, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def check_api_available():
    """Skip all integration tests if the API server is not running."""
    try:
        resp = httpx.get(f"{API_BASE}/health", timeout=5.0)
        resp.raise_for_status()
    except Exception:
        pytest.skip("PlaceGuard API is not running. Start it with: make serve")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health_returns_200(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_healthy(self, api_client):
        data = api_client.get("/health").json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# POST /validate-place
# ---------------------------------------------------------------------------

class TestValidatePlace:
    def test_valid_place_query(self, api_client):
        """Known good place should return valid status."""
        resp = api_client.post(
            "/validate-place",
            json={"query": "Sky Lounge Gangnam rooftop bar", "context": {"city": "Seoul"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] in ("valid", "uncertain", "invalid")
        assert 0.0 <= data["confidence"] <= 1.0
        assert "exists" in data
        assert "operating" in data
        assert "reasoning_chain" in data
        assert len(data["reasoning_chain"]) > 0

    def test_invalid_place_query(self, api_client):
        """Unknown place should return invalid or uncertain."""
        resp = api_client.post(
            "/validate-place",
            json={"query": "The Grand Celestial Palace Invisible Restaurant Gangnam"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("invalid", "uncertain")

    def test_response_schema_complete(self, api_client):
        """Response should contain all VOYGR API fields."""
        resp = api_client.post(
            "/validate-place",
            json={"query": "Nobu Tokyo fine dining"},
        )
        assert resp.status_code == 200
        data = resp.json()
        
        required_fields = [
            "place_id", "name", "status", "confidence",
            "exists", "operating", "price_verified",
            "safety_score", "details", "issues", "reasoning_chain",
            "timestamp", "model_used"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_query_too_short_rejected(self, api_client):
        """Query shorter than min length should return 422."""
        resp = api_client.post("/validate-place", json={"query": "AB"})
        assert resp.status_code == 422

    def test_empty_query_rejected(self, api_client):
        """Empty query should return 422."""
        resp = api_client.post("/validate-place", json={"query": ""})
        assert resp.status_code == 422

    def test_with_context(self, api_client):
        """Query with context should process correctly."""
        resp = api_client.post(
            "/validate-place",
            json={
                "query": "Street food market Myeongdong",
                "context": {"city": "Seoul", "country": "KR"},
            },
        )
        assert resp.status_code == 200

    def test_price_claim_in_query(self, api_client):
        """Price claims should be validated."""
        resp = api_client.post(
            "/validate-place",
            json={"query": "Rooftop bar in Gangnam under $20 cocktails"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "price_verified" in data

    def test_closed_place_is_invalid(self, api_client):
        """Permanently closed place should return invalid."""
        resp = api_client.post(
            "/validate-place",
            json={"query": "Hongdae BBQ Palace Korean restaurant"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invalid"


# ---------------------------------------------------------------------------
# GET /history
# ---------------------------------------------------------------------------

class TestHistory:
    def test_history_returns_list(self, api_client):
        resp = api_client.get("/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_history_limit_param(self, api_client):
        resp = api_client.get("/history?limit=5")
        assert resp.status_code == 200
        assert len(resp.json()) <= 5

    def test_history_invalid_limit(self, api_client):
        resp = api_client.get("/history?limit=0")
        assert resp.status_code == 400

    def test_history_limit_too_large(self, api_client):
        resp = api_client.get("/history?limit=200")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /benchmarks
# ---------------------------------------------------------------------------

class TestBenchmarks:
    def test_benchmarks_returns_6_scenarios(self, api_client):
        resp = api_client.get("/benchmarks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6

    def test_benchmark_has_required_fields(self, api_client):
        data = api_client.get("/benchmarks").json()
        for scenario in data:
            assert "scenario_id" in scenario
            assert "name" in scenario
            assert "query" in scenario
            assert "expected_status" in scenario
            assert "test_category" in scenario


# ---------------------------------------------------------------------------
# POST /run-benchmark
# ---------------------------------------------------------------------------

class TestRunBenchmark:
    def test_benchmark_run_returns_score(self, api_client):
        resp = api_client.post("/run-benchmark")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "score" in data
        assert "passed" in data
        assert "total" in data
        assert data["total"] == 6
        assert 0 <= data["score"] <= 100
        assert "grade" in data

    def test_benchmark_results_per_scenario(self, api_client):
        resp = api_client.post("/run-benchmark")
        data = resp.json()
        
        assert len(data["results"]) == 6
        for result in data["results"]:
            assert "scenario_id" in result
            assert "passed" in result


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_health_not_rate_limited(self, api_client):
        """Health check should never be rate limited."""
        for _ in range(5):
            resp = api_client.get("/health")
            assert resp.status_code == 200
