"""VOYGR benchmark scenarios for PlaceGuard validation.

These 6 scenarios simulate real VOYGR LLM output edge cases to validate
the agent's reasoning quality. Based on common failure modes in place
recommendation pipelines.
"""

from agent.schemas import BenchmarkScenario

BENCHMARK_SCENARIOS: list[BenchmarkScenario] = [
    BenchmarkScenario(
        scenario_id="bench_01",
        name="Valid Place — Clear Data",
        description=(
            "A well-known rooftop bar in Seoul with clean data. "
            "Agent should validate with high confidence."
        ),
        query="Recommend a rooftop bar in Gangnam under $20 cocktails",
        context={"city": "Seoul", "country": "KR"},
        expected_status="valid",
        expected_confidence_min=0.75,
        expected_place_name="Sky Lounge Gangnam",
        expected_issues_count=0,
        test_category="valid_clear",
    ),
    BenchmarkScenario(
        scenario_id="bench_02",
        name="Hallucinated Place — LLM Fabrication",
        description=(
            "The LLM recommended a place that doesn't exist. "
            "Agent should detect low confidence and return invalid."
        ),
        query="Book me a table at The Grand Celestial Palace restaurant in Gangnam",
        context={"city": "Seoul", "country": "KR"},
        expected_status="invalid",
        expected_confidence_min=0.0,
        expected_place_name=None,
        expected_issues_count=1,
        test_category="hallucinated",
    ),
    BenchmarkScenario(
        scenario_id="bench_03",
        name="Permanently Closed Place",
        description=(
            "The LLM recommended a restaurant that has permanently closed. "
            "Agent should mark as invalid with a closure issue."
        ),
        query="Korean BBQ dinner at Hongdae BBQ Palace",
        context={"city": "Seoul", "country": "KR"},
        expected_status="invalid",
        expected_confidence_min=0.0,
        expected_place_name="Hongdae BBQ Palace",
        expected_issues_count=1,
        test_category="edge_case",
    ),
    BenchmarkScenario(
        scenario_id="bench_04",
        name="Stale Data Warning",
        description=(
            "Place exists and is operating but data is 6 months old. "
            "Agent should return uncertain with a staleness warning."
        ),
        query="Coffee at Itaewon Corner Cafe",
        context={"city": "Seoul", "country": "KR"},
        expected_status="uncertain",
        expected_confidence_min=0.4,
        expected_place_name="Itaewon Corner Cafe",
        expected_issues_count=1,
        test_category="stale_data",
    ),
    BenchmarkScenario(
        scenario_id="bench_05",
        name="International Fine Dining — High Confidence",
        description=(
            "A premium restaurant in Tokyo with verified data. "
            "Agent validates correctly with high confidence."
        ),
        query="Fine dining Japanese restaurant in Minami-Aoyama Tokyo",
        context={"city": "Tokyo", "country": "JP"},
        expected_status="valid",
        expected_confidence_min=0.80,
        expected_place_name="Nobu Tokyo",
        expected_issues_count=0,
        test_category="international",
    ),
    BenchmarkScenario(
        scenario_id="bench_06",
        name="Ambiguous — Popular Area, Multiple Results",
        description=(
            "Query is ambiguous — multiple places in Myeongdong match. "
            "Agent should return the best match with appropriate confidence."
        ),
        query="Street food in Myeongdong Seoul",
        context={"city": "Seoul", "country": "KR"},
        expected_status="valid",
        expected_confidence_min=0.65,
        expected_place_name=None,  # Accept any matching result
        expected_issues_count=0,
        test_category="ambiguous",
    ),
]
