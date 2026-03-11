"""Tests for questionnaire upload, extraction, review, templates, scenarios, and PDF export."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ── Helpers ──────────────────────────────────────────────────────────

async def _create_report(auth_client: AsyncClient) -> str:
    """Create a data upload + estimate to get a report ID."""
    upload = await auth_client.post("/api/v1/data", json={
        "year": 2024,
        "provided_data": {"electricity_kwh": 100000, "natural_gas_therms": 5000},
    })
    upload_id = upload.json()["id"]
    est = await auth_client.post("/api/v1/estimate", json={"data_upload_id": upload_id})
    return est.json()["id"]


# ── Questionnaire Upload ────────────────────────────────────────────

@pytest.mark.asyncio
class TestQuestionnaireUpload:
    async def test_upload_csv(self, auth_client: AsyncClient):
        csv_content = (
            b"Question,Category\n"
            b"What are your Scope 1 emissions?,emissions\n"
            b"Do you have renewable energy targets?,energy\n"
            b"What is your waste management strategy?,waste\n"
        )
        resp = await auth_client.post(
            "/api/v1/questionnaires/upload",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["file_type"] == "csv"
        assert data["status"] == "uploaded"
        assert data["title"] == "test.csv"
        assert data["file_size"] > 0

    async def test_upload_unsupported_type(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/api/v1/questionnaires/upload",
            files={"file": ("test.exe", b"binary", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    async def test_list_questionnaires(self, auth_client: AsyncClient):
        # Upload one
        await auth_client.post(
            "/api/v1/questionnaires/upload",
            files={"file": ("q.csv", b"Q1. What are your emissions?\n", "text/csv")},
        )
        resp = await auth_client.get("/api/v1/questionnaires/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_get_questionnaire_detail(self, auth_client: AsyncClient):
        upload = await auth_client.post(
            "/api/v1/questionnaires/upload",
            files={"file": ("q.csv", b"Q1. What are your emissions?\n", "text/csv")},
        )
        qid = upload.json()["id"]
        resp = await auth_client.get(f"/api/v1/questionnaires/{qid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["questionnaire"]["id"] == qid

    async def test_get_nonexistent_questionnaire(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/nonexistent")
        assert resp.status_code == 404

    async def test_delete_questionnaire(self, auth_client: AsyncClient):
        upload = await auth_client.post(
            "/api/v1/questionnaires/upload",
            files={"file": ("del.csv", b"Q1. foo?\n", "text/csv")},
        )
        qid = upload.json()["id"]
        del_resp = await auth_client.delete(f"/api/v1/questionnaires/{qid}")
        assert del_resp.status_code == 204
        # Verify soft-deleted
        get_resp = await auth_client.get(f"/api/v1/questionnaires/{qid}")
        assert get_resp.status_code == 404


# ── Questionnaire Extraction ────────────────────────────────────────

@pytest.mark.asyncio
class TestQuestionnaireExtraction:
    async def test_extract_questions_from_csv(self, auth_client: AsyncClient):
        csv_content = (
            b"Q1. What are your total Scope 1 greenhouse gas emissions in tCO2e?\n"
            b"Q2. Does your organization track renewable energy consumption?\n"
            b"Q3. What waste reduction targets has your company set?\n"
        )
        upload = await auth_client.post(
            "/api/v1/questionnaires/upload",
            files={"file": ("survey.csv", csv_content, "text/csv")},
        )
        qid = upload.json()["id"]

        resp = await auth_client.post(f"/api/v1/questionnaires/{qid}/extract")
        assert resp.status_code == 200
        data = resp.json()
        assert data["questionnaire"]["status"] == "extracted"
        assert len(data["questions"]) >= 1
        # All questions should have draft answers
        for q in data["questions"]:
            assert q["ai_draft_answer"] is not None
            assert len(q["ai_draft_answer"]) > 0

    async def test_extract_from_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/questionnaires/nonexistent/extract")
        assert resp.status_code == 404


# ── Question Review ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestQuestionReview:
    async def _create_extracted(self, auth_client: AsyncClient) -> dict:
        csv_content = b"Q1. What are your Scope 1 emissions in tCO2e?\n"
        upload = await auth_client.post(
            "/api/v1/questionnaires/upload",
            files={"file": ("review.csv", csv_content, "text/csv")},
        )
        qid = upload.json()["id"]
        resp = await auth_client.post(f"/api/v1/questionnaires/{qid}/extract")
        return resp.json()

    async def test_update_question_answer(self, auth_client: AsyncClient):
        data = await self._create_extracted(auth_client)
        qid = data["questionnaire"]["id"]
        question = data["questions"][0]

        resp = await auth_client.patch(
            f"/api/v1/questionnaires/{qid}/questions/{question['id']}",
            json={"human_answer": "Our Scope 1 emissions were 1,500 tCO2e.", "status": "reviewed"},
        )
        assert resp.status_code == 200
        assert resp.json()["human_answer"] == "Our Scope 1 emissions were 1,500 tCO2e."
        assert resp.json()["status"] == "reviewed"

    async def test_approve_question(self, auth_client: AsyncClient):
        data = await self._create_extracted(auth_client)
        qid = data["questionnaire"]["id"]
        question = data["questions"][0]

        resp = await auth_client.patch(
            f"/api/v1/questionnaires/{qid}/questions/{question['id']}",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_update_nonexistent_question(self, auth_client: AsyncClient):
        data = await self._create_extracted(auth_client)
        qid = data["questionnaire"]["id"]
        resp = await auth_client.patch(
            f"/api/v1/questionnaires/{qid}/questions/nonexistent",
            json={"status": "reviewed"},
        )
        assert resp.status_code == 404


# ── Templates ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestTemplates:
    async def test_list_templates(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/templates/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5  # CDP, EcoVadis, TCFD, GHG Protocol, CSRD
        assert all("id" in t and "title" in t and "question_count" in t for t in data)

    async def test_get_template_detail(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/templates/cdp_climate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["framework"] == "CDP"
        assert len(data["questions"]) >= 5

    async def test_get_nonexistent_template(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/questionnaires/templates/nonexistent")
        assert resp.status_code == 404

    async def test_apply_template(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/questionnaires/templates/ghg_protocol_inventory/apply")
        assert resp.status_code == 200
        data = resp.json()
        assert data["questionnaire"]["title"] == "GHG Protocol Corporate Inventory"
        assert data["questionnaire"]["status"] == "extracted"
        assert len(data["questions"]) >= 5
        # All should have draft answers
        for q in data["questions"]:
            assert q["ai_draft_answer"] is not None


# ── Scenarios ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestScenarios:
    async def test_create_scenario(self, auth_client: AsyncClient):
        report_id = await _create_report(auth_client)
        resp = await auth_client.post("/api/v1/scenarios/", json={
            "name": "100% Renewable",
            "description": "Switch all energy to renewables",
            "base_report_id": report_id,
            "parameters": {
                "energy_switch": {"renewable_pct": 100},
            },
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "100% Renewable"
        assert data["status"] == "draft"

    async def test_create_scenario_invalid_report(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/scenarios/", json={
            "name": "Bad",
            "base_report_id": "nonexistent",
            "parameters": {"energy_switch": {"renewable_pct": 50}},
        })
        assert resp.status_code == 404

    async def test_compute_scenario(self, auth_client: AsyncClient):
        report_id = await _create_report(auth_client)
        create = await auth_client.post("/api/v1/scenarios/", json={
            "name": "Fleet Electrification",
            "base_report_id": report_id,
            "parameters": {
                "fleet_electrification": {"electrification_pct": 50},
            },
        })
        scenario_id = create.json()["id"]

        resp = await auth_client.post(f"/api/v1/scenarios/{scenario_id}/compute")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "computed"
        assert data["results"] is not None
        assert data["results"]["total_adjusted"] <= data["results"]["total_baseline"]
        assert data["results"]["reduction_pct"] >= 0

    async def test_compute_combined_adjustments(self, auth_client: AsyncClient):
        report_id = await _create_report(auth_client)
        create = await auth_client.post("/api/v1/scenarios/", json={
            "name": "Combined Strategy",
            "base_report_id": report_id,
            "parameters": {
                "energy_switch": {"renewable_pct": 80},
                "efficiency": {"efficiency_pct": 20},
                "supplier_change": {"scope3_reduction_pct": 15},
            },
        })
        scenario_id = create.json()["id"]

        resp = await auth_client.post(f"/api/v1/scenarios/{scenario_id}/compute")
        data = resp.json()
        assert data["status"] == "computed"
        assert len(data["results"]["adjustments_applied"]) == 3

    async def test_list_scenarios(self, auth_client: AsyncClient):
        report_id = await _create_report(auth_client)
        await auth_client.post("/api/v1/scenarios/", json={
            "name": "Test",
            "base_report_id": report_id,
            "parameters": {"energy_switch": {"renewable_pct": 25}},
        })
        resp = await auth_client.get("/api/v1/scenarios/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_scenario(self, auth_client: AsyncClient):
        report_id = await _create_report(auth_client)
        create = await auth_client.post("/api/v1/scenarios/", json={
            "name": "Single",
            "base_report_id": report_id,
            "parameters": {"efficiency": {"efficiency_pct": 10}},
        })
        sid = create.json()["id"]
        resp = await auth_client.get(f"/api/v1/scenarios/{sid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Single"

    async def test_delete_scenario(self, auth_client: AsyncClient):
        report_id = await _create_report(auth_client)
        create = await auth_client.post("/api/v1/scenarios/", json={
            "name": "Del",
            "base_report_id": report_id,
            "parameters": {"efficiency": {"efficiency_pct": 5}},
        })
        sid = create.json()["id"]
        del_resp = await auth_client.delete(f"/api/v1/scenarios/{sid}")
        assert del_resp.status_code == 204
        get_resp = await auth_client.get(f"/api/v1/scenarios/{sid}")
        assert get_resp.status_code == 404

    async def test_compute_nonexistent(self, auth_client: AsyncClient):
        resp = await auth_client.post("/api/v1/scenarios/nonexistent/compute")
        assert resp.status_code == 404


# ── PDF Export ───────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestPdfExport:
    async def test_export_report_pdf(self, auth_client: AsyncClient):
        report_id = await _create_report(auth_client)
        resp = await auth_client.get(f"/api/v1/reports/{report_id}/export/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        content = resp.content
        assert content[:4] == b"%PDF"  # Valid PDF header

    async def test_export_report_pdf_not_found(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/reports/nonexistent/export/pdf")
        assert resp.status_code == 404

    async def test_export_questionnaire_pdf(self, auth_client: AsyncClient):
        # Create and extract a questionnaire
        csv_content = b"Q1. What are your Scope 1 emissions in tCO2e?\nQ2. Do you track energy use?\n"
        upload = await auth_client.post(
            "/api/v1/questionnaires/upload",
            files={"file": ("pdf_test.csv", csv_content, "text/csv")},
        )
        qid = upload.json()["id"]
        await auth_client.post(f"/api/v1/questionnaires/{qid}/extract")

        resp = await auth_client.get(f"/api/v1/questionnaires/{qid}/export/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"


# ── Scenario Service Unit Tests ──────────────────────────────────────

@pytest.mark.asyncio
class TestScenarioComputation:
    def test_energy_switch_reduces_scope2(self):
        from api.services.scenarios import compute_scenario

        baseline = {"scope1": 100.0, "scope2": 200.0, "scope3": 300.0}
        result = compute_scenario(baseline, {"energy_switch": {"renewable_pct": 100}})
        assert result["adjusted"]["scope2"] == 0.0
        assert result["adjusted"]["scope1"] == 100.0  # Unchanged
        assert result["reduction_pct"] > 0

    def test_fleet_electrification(self):
        from api.services.scenarios import compute_scenario

        baseline = {"scope1": 1000.0, "scope2": 500.0, "scope3": 300.0}
        result = compute_scenario(baseline, {"fleet_electrification": {"electrification_pct": 100}})
        assert result["adjusted"]["scope1"] < baseline["scope1"]
        assert result["total_adjusted"] < result["total_baseline"]

    def test_supplier_change(self):
        from api.services.scenarios import compute_scenario

        baseline = {"scope1": 100.0, "scope2": 200.0, "scope3": 500.0}
        result = compute_scenario(baseline, {"supplier_change": {"scope3_reduction_pct": 50}})
        assert result["adjusted"]["scope3"] == 250.0

    def test_combined_adjustments(self):
        from api.services.scenarios import compute_scenario

        baseline = {"scope1": 100.0, "scope2": 200.0, "scope3": 300.0}
        result = compute_scenario(baseline, {
            "energy_switch": {"renewable_pct": 50},
            "efficiency": {"efficiency_pct": 10},
        })
        assert len(result["adjustments_applied"]) == 2
        assert result["total_adjusted"] < result["total_baseline"]

    def test_no_adjustments(self):
        from api.services.scenarios import compute_scenario

        baseline = {"scope1": 100.0, "scope2": 200.0, "scope3": 300.0}
        result = compute_scenario(baseline, {})
        assert result["total_adjusted"] == result["total_baseline"]
        assert result["reduction_pct"] == 0.0


# ── Questionnaire Service Unit Tests ─────────────────────────────────

class TestQuestionExtraction:
    def test_rule_based_extraction(self):
        from api.services.questionnaire import extract_questions_rule_based

        text = (
            "Q1. What are your total greenhouse gas emissions?\n"
            "Q2. Does your company have a climate transition plan?\n"
            "Q3. What percentage of energy comes from renewables?\n"
        )
        questions = extract_questions_rule_based(text)
        assert len(questions) >= 2
        assert all("question_text" in q for q in questions)

    def test_question_classification(self):
        from api.services.questionnaire import _classify_question

        assert _classify_question("What are your Scope 1 GHG emissions?") == "emissions"
        assert _classify_question("Do you use renewable energy sources?") == "energy"
        assert _classify_question("What is your waste recycling rate?") == "waste"
        assert _classify_question("How do you manage your supply chain?") == "supply_chain"

    def test_text_extraction_csv(self):
        from api.services.questionnaire import extract_text

        content = b"col1,col2\nval1,val2\n"
        result = extract_text(content, "csv")
        assert "col1" in result
        assert "val2" in result


# ── Template Service Unit Tests ──────────────────────────────────────

class TestTemplateService:
    def test_list_templates(self):
        from api.services.templates import list_templates

        templates = list_templates()
        assert len(templates) >= 5
        ids = {t["id"] for t in templates}
        assert "cdp_climate" in ids
        assert "tcfd_disclosure" in ids
        assert "ghg_protocol_inventory" in ids

    def test_get_template(self):
        from api.services.templates import get_template

        cdp = get_template("cdp_climate")
        assert cdp is not None
        assert cdp["framework"] == "CDP"
        assert len(cdp["questions"]) >= 5

    def test_get_nonexistent_template(self):
        from api.services.templates import get_template

        assert get_template("nonexistent") is None
