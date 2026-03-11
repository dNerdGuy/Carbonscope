"""LLM-powered data parsing service.

Provides functions that use an LLM (Claude/GPT via API) to:
- Parse unstructured text (invoices, bills, reports) into structured emission data
- Generate natural-language audit trails explaining calculations
- Infer missing data from company description + industry context

When no LLM API key is configured, falls back to rule-based extraction.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# Optional LLM client — only used if API key is set
_llm_client = None


def _get_llm_client():
    """Lazy-init LLM client if API key is available."""
    global _llm_client
    if _llm_client is not None:
        return _llm_client

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    provider = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai"

    if not api_key:
        return None

    if provider == "anthropic":
        try:
            import anthropic
            _llm_client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            logger.warning("anthropic package not installed; LLM features disabled")
            return None
    else:
        try:
            import openai
            _llm_client = openai.OpenAI(api_key=api_key)
        except ImportError:
            logger.warning("openai package not installed; LLM features disabled")
            return None

    return _llm_client


# ── Rule-based extraction (fallback) ────────────────────────────────

_PATTERNS: list[tuple[str, str, float]] = [
    # (regex pattern, output key, unit multiplier)
    (r"(\d[\d,]*\.?\d*)\s*(?:kwh|kilowatt[\s-]?hours?)", "electricity_kwh", 1.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:mwh|megawatt[\s-]?hours?)", "electricity_kwh", 1000.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:therms?)", "natural_gas_therms", 1.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:ccf)\s*(?:of\s+)?(?:natural\s+gas|gas)", "natural_gas_therms", 1.0232),
    (r"(\d[\d,]*\.?\d*)\s*(?:gallons?)\s*(?:of\s+)?diesel", "diesel_gallons", 1.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:gallons?)\s*(?:of\s+)?gasoline", "gasoline_gallons", 1.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:gallons?)\s*(?:of\s+)?propane", "propane_gallons", 1.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:miles)\s*(?:driven|traveled|fleet)", "fleet_miles", 1.0),
    (r"fleet\s*(?:of\s+)?(\d[\d,]*\.?\d*)\s*(?:miles)", "fleet_miles", 1.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:employees?|staff|headcount|fte)", "employee_count", 1.0),
    (r"(?:revenue|sales|turnover)\s*(?:of\s+)?\$?\s*(\d[\d,]*\.?\d*)\s*(?:m(?:illion)?|M)", "revenue_usd", 1_000_000.0),
    (r"(?:revenue|sales|turnover)\s*(?:of\s+)?\$?\s*(\d[\d,]*\.?\d*)\s*(?:b(?:illion)?|B)", "revenue_usd", 1_000_000_000.0),
    (r"(?:revenue|sales|turnover)\s*(?:of\s+)?\$?\s*(\d[\d,]*\.?\d*)", "revenue_usd", 1.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:metric\s+)?(?:tonnes?|tons?)\s*(?:of\s+)?waste", "waste_metric_tons", 1.0),
    (r"(\d[\d,]*\.?\d*)\s*(?:ton[\s-]?miles?)\s*(?:of\s+)?(?:freight|shipping)", "freight_ton_miles", 1.0),
]


def _parse_number(s: str) -> float:
    """Parse a number string, removing commas."""
    return float(s.replace(",", ""))


def parse_text_rule_based(text: str) -> dict[str, Any]:
    """Extract structured emission data from unstructured text using regex."""
    result: dict[str, Any] = {}
    text_lower = text.lower()

    for pattern, key, multiplier in _PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            try:
                val = _parse_number(match.group(1)) * multiplier
                # Don't overwrite if already found with higher specificity
                if key not in result:
                    result[key] = round(val, 2)
            except (ValueError, IndexError):
                continue

    return result


# ── LLM-based extraction ────────────────────────────────────────────

_EXTRACT_PROMPT = """You are a carbon accounting data extraction expert. Extract structured operational data from the following text.

Return ONLY a JSON object with these possible keys (omit any not found):
- electricity_kwh: annual electricity consumption in kWh
- natural_gas_therms: annual natural gas in therms
- diesel_gallons: annual diesel in gallons
- gasoline_gallons: annual gasoline in gallons
- propane_gallons: annual propane in gallons
- fleet_miles: annual fleet vehicle miles
- employee_count: number of employees
- revenue_usd: annual revenue in USD
- purchased_goods_usd: annual purchased goods/services spend in USD
- business_travel_miles: annual business travel miles
- waste_metric_tons: annual waste in metric tons
- freight_ton_miles: annual freight ton-miles
- grid_region: electricity grid region code (e.g., CAMX, RFCW)
- steam_mmbtu: annual steam/heating in MMBtu

Text to parse:
{text}

JSON:"""


async def parse_unstructured_text(text: str) -> dict[str, Any]:
    """Parse unstructured text into structured operational data.

    Uses LLM if available, falls back to rule-based extraction.
    """
    client = _get_llm_client()

    if client is None:
        return parse_text_rule_based(text)

    try:
        provider = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai"
        prompt = _EXTRACT_PROMPT.format(text=text[:4000])  # Limit input size

        if provider == "anthropic":
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
        else:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0,
            )
            content = response.choices[0].message.content

        # Parse JSON from response
        json_match = re.search(r"\{[^}]+\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

        return json.loads(content)

    except Exception as e:
        logger.warning("LLM extraction failed, falling back to rule-based: %s", e)
        return parse_text_rule_based(text)


# ── Audit trail generation ───────────────────────────────────────────

_AUDIT_PROMPT = """You are a GHG Protocol carbon accounting auditor. Given the following emission estimation results, generate a clear, professional audit trail.

Company: {company}
Industry: {industry}
Year: {year}

Results:
- Scope 1: {scope1} tCO2e
- Scope 2: {scope2} tCO2e
- Scope 3: {scope3} tCO2e
- Total: {total} tCO2e

Breakdown: {breakdown}

Assumptions: {assumptions}

Sources: {sources}

Write a concise audit narrative (3-5 paragraphs) explaining:
1. Methodology used and GHG Protocol alignment
2. Key data inputs and how each scope was calculated
3. Data quality assessment and confidence level
4. Key assumptions and their impact on results
5. Recommendations for improving data quality"""


def generate_audit_trail_local(
    company: str,
    industry: str,
    year: int,
    scope1: float,
    scope2: float,
    scope3: float,
    total: float,
    breakdown: dict | None,
    assumptions: list | None,
    sources: list | None,
    confidence: float,
) -> str:
    """Generate a rule-based audit trail without LLM."""
    lines = [
        f"## Carbon Emission Audit Trail — {company} ({year})",
        "",
        "### Methodology",
        f"This assessment follows the GHG Protocol Corporate Standard. "
        f"Emissions were calculated using activity-based methods where data was available, "
        f"with industry-average gap-filling for missing categories.",
        "",
        "### Results Summary",
        f"Total estimated emissions: **{total:,.1f} tCO₂e**",
        f"- Scope 1 (Direct): {scope1:,.1f} tCO₂e ({scope1/total*100:.0f}%)" if total > 0 else f"- Scope 1: {scope1:,.1f} tCO₂e",
        f"- Scope 2 (Energy): {scope2:,.1f} tCO₂e ({scope2/total*100:.0f}%)" if total > 0 else f"- Scope 2: {scope2:,.1f} tCO₂e",
        f"- Scope 3 (Value Chain): {scope3:,.1f} tCO₂e ({scope3/total*100:.0f}%)" if total > 0 else f"- Scope 3: {scope3:,.1f} tCO₂e",
        "",
        "### Data Quality",
        f"Confidence score: **{confidence*100:.0f}%**. ",
    ]

    if confidence >= 0.8:
        lines.append("Data quality is high — primary data provided for most emission categories.")
    elif confidence >= 0.5:
        lines.append("Data quality is moderate — primary data covers key categories but gap-filling was applied for some Scope 3 categories.")
    else:
        lines.append("Data quality is limited — significant gap-filling was applied. Improving data collection for fuel use, electricity, and supply chain will increase accuracy.")

    if assumptions:
        lines.extend(["", "### Key Assumptions"])
        for a in assumptions:
            lines.append(f"- {a}")

    if sources:
        lines.extend(["", "### Data Sources"])
        for s in sources:
            lines.append(f"- {s}")

    if breakdown:
        lines.extend(["", "### Recommendations"])
        missing = []
        s1d = breakdown.get("scope1_detail", {})
        s2d = breakdown.get("scope2_detail", {})
        if not s1d:
            missing.append("direct fuel and vehicle data (Scope 1)")
        if not s2d.get("location_based"):
            missing.append("electricity consumption data (Scope 2)")
        if missing:
            lines.append(f"- Prioritize collecting: {', '.join(missing)}")
        lines.append("- Consider sub-metering critical facilities for higher granularity")
        lines.append("- Engage key suppliers for primary Scope 3 data")

    return "\n".join(lines)


async def generate_audit_trail(
    company: str,
    industry: str,
    year: int,
    scope1: float,
    scope2: float,
    scope3: float,
    total: float,
    breakdown: dict | None,
    assumptions: list | None,
    sources: list | None,
    confidence: float,
) -> str:
    """Generate audit trail — LLM if available, else rule-based."""
    client = _get_llm_client()

    if client is None:
        return generate_audit_trail_local(
            company, industry, year, scope1, scope2, scope3, total,
            breakdown, assumptions, sources, confidence,
        )

    try:
        provider = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai"
        prompt = _AUDIT_PROMPT.format(
            company=company, industry=industry, year=year,
            scope1=f"{scope1:,.1f}", scope2=f"{scope2:,.1f}",
            scope3=f"{scope3:,.1f}", total=f"{total:,.1f}",
            breakdown=json.dumps(breakdown, indent=2) if breakdown else "N/A",
            assumptions="\n".join(f"- {a}" for a in (assumptions or [])) or "None",
            sources="\n".join(f"- {s}" for s in (sources or [])) or "N/A",
        )

        if provider == "anthropic":
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        else:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.3,
            )
            return response.choices[0].message.content

    except Exception as e:
        logger.warning("LLM audit trail failed, falling back to rule-based: %s", e)
        return generate_audit_trail_local(
            company, industry, year, scope1, scope2, scope3, total,
            breakdown, assumptions, sources, confidence,
        )
