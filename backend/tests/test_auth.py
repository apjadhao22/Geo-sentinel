import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_login_success(db_session, seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/login", json={"username": "officer1", "password": "test123"})
        assert response.status_code == 200
        assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(db_session, seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/login", json={"username": "officer1", "password": "wrong"})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(db_session, seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/auth/login", json={"username": "officer1", "password": "test123"})
        token = login.json()["access_token"]
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["username"] == "officer1"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/auth/me")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_only_endpoint(db_session, seed_users):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/auth/login", json={"username": "officer1", "password": "test123"})
        token = login.json()["access_token"]
        response = await client.get("/users", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
