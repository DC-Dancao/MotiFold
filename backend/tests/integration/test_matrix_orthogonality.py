# backend/tests/integration/test_matrix_orthogonality.py
"""
Integration tests for POST /matrix/morphological/orthogonality-check
Exercises the endpoint with a real LLM call.
"""
import json
import pytest

from app.matrix.models import MorphologicalAnalysis

pytestmark = pytest.mark.integration


async def test_orthogonality_check_endpoint_with_real_llm(
    auth_client,
    db_session,
    test_user,
):
    """Test the orthogonality-check endpoint with real LLM call."""
    # Create a morphological analysis with test data
    analysis = MorphologicalAnalysis(
        user_id=test_user.id,
        focus_question="What propulsion system works in what environment?",
        parameters_json=json.dumps([
            {"name": "Power", "states": ["Battery", "Solar", "Fuel", "Grid"]},
            {"name": "Environment", "states": ["Underwater", "Urban", "Desert", "Arctic"]},
            {"name": "Speed", "states": ["Stopped", "Slow", "Cruise", "Fast"]},
        ]),
        matrix={},
        status="complete",
    )
    db_session.add(analysis)
    await db_session.flush()

    # Call the endpoint
    response = await auth_client.post(
        "/matrix/morphological/orthogonality-check",
        json={"analysis_id": analysis.id},
    )

    assert response.status_code == 200
    data = response.json()
    assert "all_orthogonal" in data
    assert "warnings" in data