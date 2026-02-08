"""Integration tests for FastAPI endpoints."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    async def test_health_returns_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestMetricsEndpoint:
    async def test_metrics_returns_text(self, client):
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


class TestShareEndpoint:
    async def test_invalid_uuid_returns_404(self, client):
        response = await client.get("/share/not-a-uuid")
        assert response.status_code == 404

    @pytest.mark.skipif(
        True,
        reason="Requires beautiful_dates table in app DB; tested via service tests instead",
    )
    async def test_nonexistent_uuid_returns_404(self, client):
        fake_uuid = str(uuid.uuid4())
        response = await client.get(f"/share/{fake_uuid}")
        assert response.status_code == 404
