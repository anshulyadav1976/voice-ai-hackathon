"""
Integration tests for EchoDiary
Run with: pytest test_integration.py -v
"""
import asyncio
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "services" in data


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_calls_endpoint():
    """Test GET /api/calls"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/calls")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_api_graph_endpoint():
    """Test GET /api/graph"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data


@pytest.mark.asyncio
async def test_twilio_incoming_webhook():
    """Test Twilio incoming call webhook"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/voice/incoming",
            data={
                "CallSid": "CA1234567890",
                "From": "+1234567890",
                "To": "+0987654321",
                "CallStatus": "ringing"
            }
        )
        assert response.status_code == 200
        # Should return TwiML
        assert "xml" in response.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_twilio_mode_selection():
    """Test mode selection webhook"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/voice/mode",
            data={
                "CallSid": "CA1234567890",
                "Digits": "1"
            }
        )
        assert response.status_code == 200
        assert "xml" in response.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_cron_health():
    """Test cron health check"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/cron/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


# Service Integration Tests (require API keys)

@pytest.mark.skipif(
    not pytest.config.getoption("--integration"),
    reason="Requires --integration flag and API keys"
)
@pytest.mark.asyncio
async def test_deepgram_service():
    """Test Deepgram service integration"""
    from app.services.deepgram_service import DeepgramService
    
    service = DeepgramService()
    # Test would require actual audio file or stream
    assert service.client is not None


@pytest.mark.skipif(
    not pytest.config.getoption("--integration"),
    reason="Requires --integration flag and API keys"
)
@pytest.mark.asyncio
async def test_openai_service():
    """Test OpenAI service integration"""
    from app.services.openai_service import OpenAIService
    
    service = OpenAIService()
    
    # Test response generation
    response = await service.generate_response(
        transcript="I had a rough day at work",
        context=[],
        mode="reassure"
    )
    
    assert isinstance(response, str)
    assert len(response) > 0
    print(f"\nGPT Response: {response}")


@pytest.mark.skipif(
    not pytest.config.getoption("--integration"),
    reason="Requires --integration flag and API keys"
)
@pytest.mark.asyncio
async def test_entity_extraction():
    """Test entity extraction"""
    from app.services.openai_service import OpenAIService
    
    service = OpenAIService()
    
    transcript = "I had lunch with Sarah at the office today. I felt stressed about the project."
    
    result = await service.extract_entities_and_relations(transcript)
    
    assert "entities" in result
    assert "relations" in result
    assert len(result["entities"]) > 0
    print(f"\nExtracted Entities: {result}")


@pytest.mark.skipif(
    not pytest.config.getoption("--integration"),
    reason="Requires --integration flag and API keys"
)
@pytest.mark.asyncio
async def test_mood_scoring():
    """Test mood scoring"""
    from app.services.openai_service import OpenAIService
    
    service = OpenAIService()
    
    transcript = "Today was amazing! I got a promotion and celebrated with friends. Feeling grateful."
    
    result = await service.calculate_mood_score(transcript)
    
    assert "score" in result
    assert "sentiment" in result
    assert "emotions" in result
    assert 1 <= result["score"] <= 10
    print(f"\nMood Analysis: {result}")


# Add pytest configuration hook
def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests that require API keys"
    )


if __name__ == "__main__":
    # Run basic tests
    print("🧪 Running EchoDiary Integration Tests\n")
    pytest.main([__file__, "-v", "--tb=short"])

