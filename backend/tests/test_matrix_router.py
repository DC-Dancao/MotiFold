import pytest
from types import SimpleNamespace

from app.matrix import service as matrix_service
from app.matrix.schemas import (
    BatchEvaluateConsistencyResponse,
    EvaluateConsistencyReasons,
    EvaluateConsistencyRequest,
    EvaluateConsistencyResults,
    GenerateMorphologicalRequest,
    LLMGenerateMorphologicalResponse,
    MorphologicalParameter,
    PairEvaluateConsistencyResponse,
    normalize_morphological_response,
)
from app.matrix.models import MorphologicalAnalysis


def build_test_parameters():
    return [
        MorphologicalParameter(name="Power", states=["Battery", "Solar", "Fuel", "Grid", "Wind", "Hydrogen", "Hybrid"]),
        MorphologicalParameter(name="Environment", states=["Underwater", "Urban", "Desert", "Arctic", "Forest", "Coastal", "Orbital"]),
        MorphologicalParameter(name="Speed", states=["Stopped", "Slow", "Cruise", "Fast", "Sprint", "Dash", "Burst"]),
    ]


def test_build_consistency_table_contains_all_pairs():
    parameters = build_test_parameters()

    table, pair_order = matrix_service.build_consistency_table(parameters)

    assert pair_order == [(0, 1), (0, 2), (1, 2)]
    assert "Pair [0, 1]" in table
    assert "Pair [0, 2]" in table
    assert "Pair [1, 2]" in table
    assert "[0] [0, 0] (Battery) vs (Underwater)" in table
    assert "[8] [1, 1] (Solar) vs (Urban)" in table


def test_apply_consistency_results_maps_statuses():
    parameters = build_test_parameters()
    response = BatchEvaluateConsistencyResponse(
        evaluations=[
            PairEvaluateConsistencyResponse(
                pair=[0, 1],
                results=EvaluateConsistencyResults(
                    red=[[0, 0]],
                    yellow=[[1, 1]],
                    reasons=EvaluateConsistencyReasons(red="r1", yellow="y1"),
                ),
            ),
            PairEvaluateConsistencyResponse(
                pair=[0, 2],
                results=EvaluateConsistencyResults(
                    red=[],
                    yellow=[[0, 1]],
                    reasons=EvaluateConsistencyReasons(red="", yellow="y2"),
                ),
            ),
            PairEvaluateConsistencyResponse(
                pair=[1, 2],
                results=EvaluateConsistencyResults(
                    red=[[1, 0]],
                    yellow=[],
                    reasons=EvaluateConsistencyReasons(red="r3", yellow=""),
                ),
            ),
        ]
    )

    matrix, results_list = matrix_service.apply_consistency_results(parameters, response)

    assert matrix["0_1"]["0_0"] == "red"
    assert matrix["0_1"]["1_1"] == "yellow"
    assert matrix["0_1"]["0_1"] == "green"
    assert matrix["0_2"]["0_1"] == "yellow"
    assert matrix["1_2"]["1_0"] == "red"
    assert len(results_list) == 3


def test_normalize_morphological_response_enforces_7x7():
    raw_response = SimpleNamespace(
        parameters=[
            {
                "name": " Mission Scope ",
                "states": ["Recon", "Patrol", "Strike", "Escort", "Relay", "Rescue", "Training"],
            },
            {"name": "Platform", "states": ["Air", "Sea", "Land", "Space", "Surface", "Subsurface", "Hybrid"]},
            {"name": "platform", "states": ["A", "B", "C", "D", "E", "F", "G"]},
            {"name": "Power Source", "states": ["Battery", "Solar", "Fuel", "Grid", "Wind", "Hydrogen", "Hybrid"]},
            {"name": "Autonomy", "states": ["Manual", "Remote", "Assisted", "Adaptive", "Autonomous", "Collaborative", "Swarm"]},
            {"name": "Payload", "states": ["Camera", "Radar", "EW", "Comms", "LiDAR", "SIGINT", "Cargo"]},
            {"name": "Range", "states": ["Short", "Medium", "Long", "Regional", "Theater", "Global", "Persistent"]},
            {"name": "Stealth", "states": ["Low", "Guarded", "Moderate", "Managed", "High", "Very High", "Extreme"]},
        ]
    )

    result = normalize_morphological_response(raw_response)

    assert len(result.parameters) == 7
    assert result.parameters[0].name == "Mission Scope"
    assert result.parameters[0].states == [
        "Recon",
        "Patrol",
        "Strike",
        "Escort",
        "Relay",
        "Rescue",
        "Training",
    ]
    assert [parameter.name for parameter in result.parameters].count("Platform") == 1


@pytest.mark.asyncio
async def test_generate_morphological_returns_normalized_7x7(monkeypatch, test_user, db_session):
    response = LLMGenerateMorphologicalResponse(
        parameters=[
            {
                "name": "Mission Scope",
                "states": ["Recon", "Patrol", "Strike", "Escort", "Relay", "Rescue", "Training"],
            },
            {"name": "Platform", "states": ["Air", "Sea", "Land", "Space", "Surface", "Subsurface", "Hybrid"]},
            {"name": "Power Source", "states": ["Battery", "Solar", "Fuel", "Grid", "Wind", "Hydrogen", "Hybrid"]},
            {"name": "Autonomy", "states": ["Manual", "Remote", "Assisted", "Adaptive", "Autonomous", "Collaborative", "Swarm"]},
            {"name": "Payload", "states": ["Camera", "Radar", "EW", "Comms", "LiDAR", "SIGINT", "Cargo"]},
            {"name": "Range", "states": ["Short", "Medium", "Long", "Regional", "Theater", "Global", "Persistent"]},
            {"name": "Stealth", "states": ["Low", "Guarded", "Moderate", "Managed", "High", "Very High", "Extreme"]},
        ]
    )

    class FakeStructuredLLM:
        def __init__(self, payload):
            self.payload = payload
            self.calls = 0

        async def ainvoke(self, messages):
            self.calls += 1
            assert len(messages) == 2
            assert "7x7 rule" in messages[0].content
            return self.payload

    class FakeLLM:
        def __init__(self, payload):
            self.structured = FakeStructuredLLM(payload)

        def with_structured_output(self, schema, method=None, strict=None):
            assert schema is LLMGenerateMorphologicalResponse
            assert method == "json_schema"
            assert strict is True
            return self.structured

    fake_llm = FakeLLM(response)
    monkeypatch.setattr(matrix_service, "get_llm", lambda model_name=None, **kwargs: fake_llm)

    result = await matrix_service.generate_morphological_parameters("How should an alliance surveillance system be configured?")


    assert fake_llm.structured.calls == 1
    assert len(result.parameters) == 7
    assert result.parameters[0].states == [
        "Recon",
        "Patrol",
        "Strike",
        "Escort",
        "Relay",
        "Rescue",
        "Training",
    ]
    assert all(len(parameter.states) == 7 for parameter in result.parameters)


@pytest.mark.asyncio
async def test_evaluate_consistency_uses_single_llm_call(monkeypatch, test_user, db_session):
    analysis = MorphologicalAnalysis(user_id=test_user.id, focus_question="test")
    db_session.add(analysis)
    await db_session.flush()

    parameters = build_test_parameters()
    response = BatchEvaluateConsistencyResponse(
        evaluations=[
            PairEvaluateConsistencyResponse(
                pair=[0, 1],
                results=EvaluateConsistencyResults(
                    red=[[0, 0]],
                    yellow=[],
                    reasons=EvaluateConsistencyReasons(red="r1", yellow=""),
                ),
            ),
            PairEvaluateConsistencyResponse(
                pair=[0, 2],
                results=EvaluateConsistencyResults(
                    red=[],
                    yellow=[[1, 1]],
                    reasons=EvaluateConsistencyReasons(red="", yellow="y2"),
                ),
            ),
            PairEvaluateConsistencyResponse(
                pair=[1, 2],
                results=EvaluateConsistencyResults(
                    red=[],
                    yellow=[],
                    reasons=EvaluateConsistencyReasons(red="", yellow=""),
                ),
            ),
        ]
    )

    class FakeStructuredLLM:
        def __init__(self, payload):
            self.payload = payload
            self.calls = 0

        async def ainvoke(self, messages):
            self.calls += 1
            assert len(messages) == 2
            assert "Indexed comparison table" in messages[1].content
            return self.payload

    class FakeLLM:
        def __init__(self, payload):
            self.structured = FakeStructuredLLM(payload)

        def with_structured_output(self, schema, method=None, strict=None):
            assert schema is BatchEvaluateConsistencyResponse
            assert method == "json_schema"
            assert strict is True
            return self.structured

    fake_llm = FakeLLM(response)
    monkeypatch.setattr(matrix_service, "get_llm", lambda model_name=None, **kwargs: fake_llm)

    result = await matrix_service.evaluate_morphological_consistency(parameters)


    assert fake_llm.structured.calls == 1
    assert result["matrix"]["0_1"]["0_0"] == "red"
    assert result["matrix"]["0_2"]["1_1"] == "yellow"
    assert result["matrix"]["1_2"]["0_0"] == "green"
    assert len(result["results_list"]) == 3
