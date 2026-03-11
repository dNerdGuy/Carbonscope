"""Tests for auth routes — registration and login."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthRoutes:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "Password123",
            "full_name": "New User",
            "company_name": "NewCorp",
            "industry": "technology",
            "region": "US",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["role"] == "admin"
        assert "id" in data
        assert "company_id" in data

    async def test_register_duplicate_email(self, client: AsyncClient):
        payload = {
            "email": "dup@example.com",
            "password": "Password123",
            "full_name": "Dup User",
            "company_name": "DupCorp",
            "industry": "retail",
            "region": "GB",
        }
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_register_short_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "short@example.com",
            "password": "abc",
            "full_name": "Short",
            "company_name": "ShortCorp",
            "industry": "energy",
        })
        assert resp.status_code == 422  # validation error

    async def test_login_success(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "password": "Password123",
            "full_name": "Login User",
            "company_name": "LoginCorp",
            "industry": "manufacturing",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "Password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "wrong@example.com",
            "password": "Password123",
            "full_name": "Wrong User",
            "company_name": "WrongCorp",
            "industry": "manufacturing",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrong@example.com",
            "password": "Badpassword1",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "ghost@example.com",
            "password": "Password123",
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestUserProfile:
    async def test_get_profile(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"

    async def test_update_name(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/auth/me", json={
            "full_name": "Updated Name",
        })
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    async def test_update_email(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/auth/me", json={
            "email": "new-email@example.com",
        })
        assert resp.status_code == 200
        assert resp.json()["email"] == "new-email@example.com"

    async def test_update_email_conflict(self, auth_client: AsyncClient, client: AsyncClient):
        # Register a second user
        await client.post("/api/v1/auth/register", json={
            "email": "other@example.com",
            "password": "Password123",
            "full_name": "Other User",
            "company_name": "OtherCorp",
            "industry": "technology",
        })
        # Try to take that email
        resp = await auth_client.patch("/api/v1/auth/me", json={
            "email": "other@example.com",
        })
        assert resp.status_code == 409

    async def test_change_password(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/auth/change-password", json={
            "current_password": "Securepass123",
            "new_password": "NewSecure456",
        })
        assert resp.status_code == 204

        # Old password should now fail
        login_resp = await auth_client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "Securepass123",
        })
        assert login_resp.status_code == 401

        # New password should work
        login_resp2 = await auth_client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "NewSecure456",
        })
        assert login_resp2.status_code == 200

    async def test_change_password_wrong_current(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/auth/change-password", json={
            "current_password": "WrongPassword1",
            "new_password": "NewSecure456",
        })
        assert resp.status_code == 400
