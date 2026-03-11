"""Pre-built sustainability questionnaire templates.

Provides structured templates for common reporting frameworks so companies
can start answering without uploading a document first.
"""

from __future__ import annotations

from typing import Any

TEMPLATES: dict[str, dict[str, Any]] = {
    "cdp_climate": {
        "title": "CDP Climate Change Questionnaire",
        "description": "Core questions from the CDP Climate Change disclosure framework.",
        "framework": "CDP",
        "questions": [
            {"question_text": "Does your organization have a climate transition plan?", "category": "governance"},
            {"question_text": "What is your organization's gross global Scope 1 emissions in metric tons CO2e?", "category": "emissions"},
            {"question_text": "What is your organization's gross global Scope 2 emissions (location-based) in metric tons CO2e?", "category": "emissions"},
            {"question_text": "What are your organization's gross global Scope 3 emissions in metric tons CO2e?", "category": "emissions"},
            {"question_text": "Does your organization have an emissions reduction target?", "category": "governance"},
            {"question_text": "What percentage of your total energy consumption is from renewable sources?", "category": "energy"},
            {"question_text": "Has your organization identified any climate-related risks with the potential to have a substantive financial impact?", "category": "governance"},
            {"question_text": "What is the total amount of capital expenditure on low-carbon R&D in the reporting year?", "category": "governance"},
            {"question_text": "Does your organization engage with your value chain on climate-related issues?", "category": "supply_chain"},
            {"question_text": "Has your organization verified any of the reported Scope 1, 2, or 3 emissions data?", "category": "reporting"},
        ],
    },
    "ecovadis_environment": {
        "title": "EcoVadis Environment Assessment",
        "description": "Key environmental performance questions from the EcoVadis sustainability rating.",
        "framework": "EcoVadis",
        "questions": [
            {"question_text": "Does your company have a formal environmental policy?", "category": "governance"},
            {"question_text": "Does your company track and report its greenhouse gas emissions?", "category": "emissions"},
            {"question_text": "What measures has your company taken to reduce energy consumption?", "category": "energy"},
            {"question_text": "Does your company have a water management strategy?", "category": "water"},
            {"question_text": "What is your company's approach to waste management and circular economy?", "category": "waste"},
            {"question_text": "Does your company assess the environmental impact of its products/services across their lifecycle?", "category": "emissions"},
            {"question_text": "Has your company set science-based targets for emission reduction?", "category": "governance"},
            {"question_text": "Does your company have an environmental management system (e.g., ISO 14001)?", "category": "governance"},
        ],
    },
    "tcfd_disclosure": {
        "title": "TCFD Recommended Disclosures",
        "description": "Task Force on Climate-related Financial Disclosures core questions.",
        "framework": "TCFD",
        "questions": [
            {"question_text": "Describe the board's oversight of climate-related risks and opportunities.", "category": "governance"},
            {"question_text": "Describe management's role in assessing and managing climate-related risks.", "category": "governance"},
            {"question_text": "Describe the climate-related risks and opportunities the organization has identified.", "category": "governance"},
            {"question_text": "Describe the impact of climate-related risks and opportunities on the organization's businesses, strategy, and financial planning.", "category": "governance"},
            {"question_text": "Describe the organization's processes for identifying and assessing climate-related risks.", "category": "governance"},
            {"question_text": "Describe how processes for managing climate-related risks are integrated into overall risk management.", "category": "governance"},
            {"question_text": "What metrics does the organization use to assess climate-related risks and opportunities?", "category": "reporting"},
            {"question_text": "Disclose Scope 1, Scope 2, and relevant Scope 3 greenhouse gas emissions.", "category": "emissions"},
            {"question_text": "Describe the targets used by the organization to manage climate-related risks and performance.", "category": "governance"},
        ],
    },
    "ghg_protocol_inventory": {
        "title": "GHG Protocol Corporate Inventory",
        "description": "Questions based on the GHG Protocol Corporate Accounting and Reporting Standard.",
        "framework": "GHG Protocol",
        "questions": [
            {"question_text": "What organizational boundary approach does your company use (equity share or control)?", "category": "reporting"},
            {"question_text": "What are your direct GHG emissions from owned or controlled sources (Scope 1)?", "category": "emissions"},
            {"question_text": "What are your indirect GHG emissions from purchased electricity, steam, heating, and cooling (Scope 2)?", "category": "emissions"},
            {"question_text": "What are your other indirect GHG emissions from your value chain (Scope 3)?", "category": "emissions"},
            {"question_text": "Which Scope 3 categories are material to your organization?", "category": "emissions"},
            {"question_text": "What emission factors and data sources are used for your calculations?", "category": "reporting"},
            {"question_text": "What is the base year for your emissions inventory and why was it selected?", "category": "reporting"},
            {"question_text": "Does your organization recalculate base year emissions when structural changes occur?", "category": "reporting"},
        ],
    },
    "csrd_esrs_climate": {
        "title": "CSRD / ESRS E1 Climate Change",
        "description": "Key disclosure requirements from the European Sustainability Reporting Standards on climate change.",
        "framework": "CSRD",
        "questions": [
            {"question_text": "Does your entity have a transition plan for climate change mitigation?", "category": "governance"},
            {"question_text": "What are the entity's policies related to climate change mitigation and adaptation?", "category": "governance"},
            {"question_text": "Describe the actions and resources related to climate change policies and targets.", "category": "governance"},
            {"question_text": "What are the entity's gross Scope 1, 2, and 3 greenhouse gas emissions?", "category": "emissions"},
            {"question_text": "What is the entity's total energy consumption and energy mix?", "category": "energy"},
            {"question_text": "Has the entity set GHG emission reduction targets? If so, what are they?", "category": "governance"},
            {"question_text": "What are the anticipated financial effects of climate-related physical and transition risks?", "category": "governance"},
        ],
    },
}


def list_templates() -> list[dict[str, str]]:
    """Return template summaries (without full question lists)."""
    return [
        {
            "id": key,
            "title": tpl["title"],
            "description": tpl["description"],
            "framework": tpl["framework"],
            "question_count": len(tpl["questions"]),
        }
        for key, tpl in TEMPLATES.items()
    ]


def get_template(template_id: str) -> dict[str, Any] | None:
    """Return a full template by ID, or None."""
    tpl = TEMPLATES.get(template_id)
    if tpl is None:
        return None
    return {"id": template_id, **tpl}
