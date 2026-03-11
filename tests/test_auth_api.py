"""Tests for auth routes — registration and login."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthRoutes:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "password123",
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
            "password": "password123",
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
            "password": "password123",
            "full_name": "Login User",
            "company_name": "LoginCorp",
            "industry": "manufacturing",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "wrong@example.com",
            "password": "password123",
            "full_name": "Wrong User",
            "company_name": "WrongCorp",
            "industry": "manufacturing",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrong@example.com",
            "password": "badpassword",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "ghost@example.com",
            "password": "password123",
        })
        assert resp.status_code == 401
