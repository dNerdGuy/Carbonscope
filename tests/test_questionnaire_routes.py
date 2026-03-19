"""Tests for questionnaire routes — upload, list, extract, update, delete, templates."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


def _csv_file(content: str = "Question,Category\nWhat is scope 1?,emissions\n"):
    return {"file": ("test.csv", io.BytesIO(content.encode()), "text/csv")}


@pytest.mark.asyncio
class TestQuestionnaireUpload:
    async def test_upload_csv(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "uploaded"
        assert data["file_type"] == "csv"
        assert data["original_filename"] == "test.csv"

    async def test_upload_unsupported_type(self, auth_client: AsyncClient):
        files = {"file": ("test.exe", io.BytesIO(b"MZ"), "application/octet-stream")}
        resp = await auth_client.post("/api/v1/questionnaires/upload", files=files)
        assert resp.status_code == 400

    async def test_upload_too_large(self, auth_client: AsyncClient):
        big = b"x" * (10 * 1024 * 1024 + 1)
        files = {"file": ("big.csv", io.BytesIO(big), "text/csv")}
        resp = await auth_client.post("/api/v1/questionnaires/upload", files=files)
        assert resp.status_code in (400, 413)  # 413 from body-limit middleware or 400 from app


@pytest.mark.asyncio
class TestQuestionnaireList:
    async def test_list_empty(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_after_upload(self, auth_client: AsyncClient):
        await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        resp = await auth_client.get("/api/v1/questionnaires/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_pagination(self, auth_client: AsyncClient):
        for _ in range(3):
            await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        resp = await auth_client.get("/api/v1/questionnaires/", params={"limit": 2})
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] == 3


@pytest.mark.asyncio
class TestQuestionnaireDetail:
    async def test_get_questionnaire(self, auth_client: AsyncClient):
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        qid = upload.json()["id"]
        resp = await auth_client.get(f"/api/v1/questionnaires/{qid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "questionnaire" in data
        assert "questions" in data

    async def test_get_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/nonexistent")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestQuestionnaireExtract:
    async def test_extract(self, auth_client: AsyncClient):
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        qid = upload.json()["id"]
        resp = await auth_client.post(f"/api/v1/questionnaires/{qid}/extract")
        assert resp.status_code == 200
        data = resp.json()
        assert "questionnaire" in data
        assert data["questionnaire"]["status"] in ("extracted", "extracting")

    async def test_extract_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/questionnaires/nonexistent/extract")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestQuestionnaireUpdate:
    async def test_patch_title(self, auth_client: AsyncClient):
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        qid = upload.json()["id"]
        resp = await auth_client.patch(f"/api/v1/questionnaires/{qid}", json={"title": "New Title"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"

    async def test_patch_status(self, auth_client: AsyncClient):
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        qid = upload.json()["id"]
        resp = await auth_client.patch(f"/api/v1/questionnaires/{qid}", json={"status": "reviewed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "reviewed"

    async def test_patch_invalid_status(self, auth_client: AsyncClient):
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        qid = upload.json()["id"]
        resp = await auth_client.patch(f"/api/v1/questionnaires/{qid}", json={"status": "bad_value"})
        assert resp.status_code == 422

    async def test_patch_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/questionnaires/nonexistent", json={"title": "X"})
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestQuestionnaireDelete:
    async def test_delete(self, auth_client: AsyncClient):
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        qid = upload.json()["id"]
        resp = await auth_client.delete(f"/api/v1/questionnaires/{qid}")
        assert resp.status_code == 204
        # Should not appear in list
        listing = await auth_client.get("/api/v1/questionnaires/")
        assert listing.json()["total"] == 0

    async def test_delete_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.delete("/api/v1/questionnaires/nonexistent")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestQuestionnairePDF:
    async def test_export_pdf(self, auth_client: AsyncClient):
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        qid = upload.json()["id"]
        resp = await auth_client.get(f"/api/v1/questionnaires/{qid}/export/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    async def test_export_pdf_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/nonexistent/export/pdf")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestQuestionnaireTemplates:
    async def test_list_templates(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/templates/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_template_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/templates/nonexistent")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestApplyTemplate:
    async def test_apply_known_template(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/questionnaires/templates/cdp_climate/apply")
        assert resp.status_code == 200
        data = resp.json()
        assert "questionnaire" in data
        assert data["questionnaire"]["status"] == "extracted"
        assert len(data["questions"]) > 0

    async def test_apply_nonexistent_template(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/questionnaires/templates/nonexistent/apply")
        assert resp.status_code == 404

    async def test_apply_template_generates_drafts(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/questionnaires/templates/cdp_climate/apply")
        assert resp.status_code == 200
        for q in resp.json()["questions"]:
            assert q.get("ai_draft_answer") is not None


@pytest.mark.asyncio
class TestUpdateQuestion:
    # CSV with clear question patterns the rule-based extractor can match
    _QUESTION_CSV = (
        "Number,Question\n"
        "Q1. What are the total scope 1 greenhouse gas emissions in metric tons?\n"
        "Q2. How does your company measure and report its carbon footprint each year?\n"
    )

    async def _setup(self, auth_client: AsyncClient):
        csv_file = {"file": ("questions.csv", io.BytesIO(self._QUESTION_CSV.encode()), "text/csv")}
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=csv_file)
        qid = upload.json()["id"]
        # extract to get questions
        await auth_client.post(f"/api/v1/questionnaires/{qid}/extract")
        detail = await auth_client.get(f"/api/v1/questionnaires/{qid}")
        data = detail.json()
        questions = data.get("questions", [])
        assert questions, "Expected rule-based extractor to find questions from CSV with Q1./Q2. patterns"
        return qid, questions

    async def test_update_human_answer(self, auth_client: AsyncClient):
        qid, questions = await self._setup(auth_client)
        question_id = questions[0]["id"]
        resp = await auth_client.patch(
            f"/api/v1/questionnaires/{qid}/questions/{question_id}",
            json={"human_answer": "42 metric tons"},
        )
        assert resp.status_code == 200
        assert resp.json()["human_answer"] == "42 metric tons"

    async def test_update_question_status(self, auth_client: AsyncClient):
        qid, questions = await self._setup(auth_client)
        question_id = questions[0]["id"]
        resp = await auth_client.patch(
            f"/api/v1/questionnaires/{qid}/questions/{question_id}",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_update_nonexistent_question(self, auth_client: AsyncClient):
        upload = await auth_client.post("/api/v1/questionnaires/upload", files=_csv_file())
        qid = upload.json()["id"]
        resp = await auth_client.patch(
            f"/api/v1/questionnaires/{qid}/questions/nonexistent",
            json={"human_answer": "test"},
        )
        assert resp.status_code == 404

    async def test_update_question_wrong_questionnaire(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/questionnaires/nonexistent/questions/nonexistent",
            json={"human_answer": "test"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestQuestionnaireAuth:
    async def test_unauthenticated_list(self, client: AsyncClient):
        resp = await client.get("/api/v1/questionnaires/")
        assert resp.status_code == 401

    async def test_unauthenticated_upload(self, client: AsyncClient):
        resp = await client.post("/api/v1/questionnaires/upload", files=_csv_file())
        assert resp.status_code == 401
