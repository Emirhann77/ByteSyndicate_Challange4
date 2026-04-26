import os
import json
import random
import re
import urllib.parse
import urllib.request
from typing import List, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field, model_validator

load_dotenv()


class MaterialItem(BaseModel):
    item: str = Field(..., description="Specific reagent, consumable, or equipment.")
    quantity: str = Field(..., description="Quantity estimate (for example '2 kits' or 'n=60').")
    notes: str = Field(..., description="Practical context such as grade, supplier, or handling.")
    estimatedPriceUsd: float = Field(..., ge=0, description="Estimated line-item cost in USD.")


class CostRange(BaseModel):
    low: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    notes: str = Field(..., description="What drives cost variance.")


class TimelinePhase(BaseModel):
    phase: str
    duration: str
    deliverable: str


class SafetyEthics(BaseModel):
    considerations: List[str] = Field(..., min_items=2)
    approvals: List[str] = Field(..., min_items=1)


class FailureMode(BaseModel):
    risk: str
    mitigation: str


class AlternativePlan(BaseModel):
    name: str
    summary: str
    costImpact: str
    timelineImpact: str
    tradeoffs: List[str] = Field(..., min_items=2)


class StaffingItem(BaseModel):
    role: str
    headcount: int = Field(..., ge=1)
    hoursPerWeek: int = Field(..., ge=1)
    responsibilities: str


class StatisticsPlan(BaseModel):
    primaryEndpoint: str
    suggestedReplicates: str
    analysisMethod: str
    powerNotes: str


class LiteratureReference(BaseModel):
    title: str
    journal: str
    year: str
    pmid: str
    relevanceNote: str


class StudyGroup(BaseModel):
    name: str
    description: str
    intervention: str
    sampleSize: str


class Limitation(BaseModel):
    title: str
    description: str
    mitigation: str


class ExperimentPlan(BaseModel):
    refinedHypothesis: str
    experimentalDesign: str
    protocolSteps: List[str] = Field(..., min_items=5)
    materials: List[MaterialItem] = Field(..., min_items=4)
    estimatedCostUsd: CostRange
    timeline: List[TimelinePhase] = Field(..., min_items=3)
    feasibilityScore: int = Field(..., ge=0, le=100)
    feasibilityRationale: List[str] = Field(..., min_items=3)
    riskLevel: Literal["Low", "Medium", "High"]
    safetyEthics: SafetyEthics
    failureModes: List[FailureMode] = Field(..., min_items=3)
    alternatives: List[AlternativePlan] = Field(..., min_items=3)
    staffingPlan: List[StaffingItem] = Field(..., min_items=2)
    statisticsPlan: StatisticsPlan
    nextQuestions: List[str] = Field(..., min_items=3)
    evidenceQualityNote: str
    literatureReferences: List[LiteratureReference] = Field(default_factory=list)
    limitations: List[Limitation] = Field(..., min_items=3)
    confidenceLevel: Literal["Very Low", "Low", "Medium", "High"]
    confidenceRationale: str
    controlGroup: StudyGroup
    experimentalGroup: StudyGroup


class HypothesisRequest(BaseModel):
    """When suggest_only is true, hypothesis is ignored and the model only returns a draft hypothesis (UI pastes it; user runs full plan separately)."""

    hypothesis: str = Field(default="", description="Required for full plans; ignored when suggest_only is true.")
    useScientificLiterature: bool = False
    suggest_only: bool = False

    @model_validator(mode="after")
    def _hypothesis_required_for_full_plan(self) -> "HypothesisRequest":
        if not self.suggest_only and len(self.hypothesis.strip()) < 1:
            raise ValueError("hypothesis is required when suggest_only is false")
        return self


class HypothesisSuggestion(BaseModel):
    hypothesis: str = Field(
        ...,
        min_length=30,
        max_length=1500,
        description="One standalone testable hypothesis for experiment planning.",
    )


SUGGEST_HYPOTHESIS_SYSTEM = (
    "You write concise, realistic scientific hypotheses suitable for a pilot experiment plan. "
    "Each response is exactly one hypothesis: clear intervention or comparison, system or subjects, "
    "measurable outcome, and at least one constraint (dose, duration, conditions, population, or control). "
    "Vary scientific domains freely across calls (e.g. molecular biology, neuroscience, materials, ecology, "
    "immunology, chemistry, physics, cognition). "
    "Output only the structured field—no labels, numbering, markdown, or preamble."
)

SYSTEM_PROMPT = (
    "You are an elite scientific program manager helping teams ship executable experiments quickly. "
    "Given a hypothesis, output a complete operational plan with protocol, costs, staffing, risk, "
    "safety/ethics checks, statistical plan, alternatives, and concrete next questions. "
    "Keep outputs realistic for a hackathon demo and wet-lab execution. "
    "Return only valid structured data matching the response schema exactly. "
    "All costs must be in USD and feasibilityScore must reflect practical deliverability. "
    "Default to small pilot-scale studies unless the user explicitly requests large-scale execution. "
    "For typical classroom/lab pilot designs, keep total budget in a realistic low range and justify it. "
    "Always define explicit controlGroup and experimentalGroup with clear interventions and sample sizes. "
    "Always include limitations describing uncertainty, assumptions, and what would invalidate the plan. "
    "Set confidenceLevel to match feasibilityScore bands: 85+ High, 65–84 Medium, 45–64 Low, 0–44 Very Low."
)

app = FastAPI(title="Experiment Planning API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.getenv("OPENAI_API_KEY"),
)

DEFAULT_MODEL = os.getenv("MODEL_NAME", "gpt-4o")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL_NAME", "gpt-4o-mini")

# Stable ID for the frontend to detect this process vs. any other server on the same port.
EXPERIMENT_API_SERVICE_ID = "byte-syndicate-experiment-api"
EXPERIMENT_API_VERSION = 2

OFFLINE_HYPOTHESIS_FALLBACK = (
    "Applying a 15-minute blue-light pulse (470 nm) at dawn increases stomatal conductance "
    "in Arabidopsis thaliana by at least 20% compared with dark-control plants measured one "
    "hour later under fixed humidity and temperature."
)


def _has_configured_api_key() -> bool:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return False
    # Guard against common placeholder values accidentally committed to local .env files.
    blocked_values = {
        "your_key_here",
        "your_openai_api_key_here",
        "replace_me",
        "none",
        "null",
    }
    return key.lower() not in blocked_values


@app.get("/")
def read_root() -> dict:
    return {
        "service": EXPERIMENT_API_SERVICE_ID,
        "version": EXPERIMENT_API_VERSION,
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "generatePlan": "POST /generate-plan",
            "suggestHypothesis": "POST /suggest-hypothesis",
        },
    }


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "endpoints": {
            "generatePlan": True,
            "suggestHypothesis": True,
        },
    }


def _raise_harmful_prompt_error() -> None:
    raise HTTPException(
        status_code=400,
        detail="This request is harmful or unsafe. I cannot provide a response for it.",
    )


def _is_model_access_or_rate_issue(message: str) -> bool:
    lowered = message.lower()
    return (
        "ratelimit" in lowered
        or "rate limit" in lowered
        or "unauthorized" in lowered
        or "bad credentials" in lowered
        or "insufficient_quota" in lowered
        or "forbidden" in lowered
    )


def _is_explicit_safety_policy_block(message: str) -> bool:
    lowered = message.lower()
    if "responsibleaipolicyviolation" in lowered:
        return True
    if "content_filter" in lowered and any(
        token in lowered
        for token in ["violence", "sexual", "self-harm", "hate", "jailbreak", "unsafe", "policy"]
    ):
        return True
    return False


def _parse_with_model_fallback(messages: List[dict], response_format):
    models_to_try = [DEFAULT_MODEL]
    if FALLBACK_MODEL and FALLBACK_MODEL not in models_to_try:
        models_to_try.append(FALLBACK_MODEL)

    last_exc: Exception | None = None
    for index, model in enumerate(models_to_try):
        try:
            return client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=response_format,
            )
        except Exception as exc:
            last_exc = exc
            if index < len(models_to_try) - 1 and _is_model_access_or_rate_issue(str(exc)):
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("No model configured for completion parsing.")


def _fetch_pubmed_references(query: str, max_items: int = 5) -> List[dict]:
    try:
        encoded_query = urllib.parse.quote_plus(query)
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&retmode=json&retmax={max_items}&sort=relevance&term={encoded_query}"
        )
        with urllib.request.urlopen(search_url, timeout=8) as response:
            search_payload = json.loads(response.read().decode("utf-8"))
        ids = search_payload.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        id_param = ",".join(ids)
        summary_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&retmode=json&id={id_param}"
        )
        with urllib.request.urlopen(summary_url, timeout=8) as response:
            summary_payload = json.loads(response.read().decode("utf-8"))

        results = []
        for pmid in ids:
            item = summary_payload.get("result", {}).get(pmid, {})
            if not item:
                continue
            pubdate = str(item.get("pubdate", ""))
            year = pubdate[:4] if len(pubdate) >= 4 else "Unknown"
            results.append(
                {
                    "pmid": pmid,
                    "title": item.get("title", "Untitled"),
                    "journal": item.get("fulljournalname", item.get("source", "Unknown journal")),
                    "year": year,
                }
            )
        return results
    except Exception:
        return []


def _enforce_budget_sanity(parsed: ExperimentPlan, hypothesis: str) -> None:
    text = hypothesis.lower()
    low = max(0.0, float(parsed.estimatedCostUsd.low))
    high = max(low, float(parsed.estimatedCostUsd.high))

    # Keep simple plant/light and other pilot-level setups in a realistic range.
    simple_keywords = ["flower", "plant", "basil", "light", "led", "growth"]
    likely_simple = any(keyword in text for keyword in simple_keywords)
    cap_high = 2500.0 if likely_simple else 5000.0

    if high > cap_high:
        scale = cap_high / high
        high = cap_high
        low = max(100.0, round(low * scale, 2))
        parsed.estimatedCostUsd.low = low
        parsed.estimatedCostUsd.high = high
        parsed.estimatedCostUsd.notes = (
            "Budget adjusted to pilot-scale realism for hackathon planning. "
            f"Final range constrained to <= ${cap_high:,.0f}."
        )


def _duration_to_days(duration_text: str) -> float:
    text = duration_text.lower()
    total = 0.0
    week_matches = re.findall(r"(\d+(?:\.\d+)?)\s*week", text)
    day_matches = re.findall(r"(\d+(?:\.\d+)?)\s*day", text)
    hour_matches = re.findall(r"(\d+(?:\.\d+)?)\s*hour", text)
    month_matches = re.findall(r"(\d+(?:\.\d+)?)\s*month", text)
    for value in week_matches:
        total += float(value) * 7
    for value in day_matches:
        total += float(value)
    for value in hour_matches:
        total += float(value) / 24
    for value in month_matches:
        total += float(value) * 30
    return total


def _apply_general_calibration(parsed: ExperimentPlan, hypothesis: str) -> None:
    text = hypothesis.lower()

    digital_keywords = [
        "algorithm",
        "decision tree",
        "dataset",
        "classify",
        "classification",
        "machine learning",
        "model training",
        "regression",
        "neural network",
        "python",
        "software",
        "simulation",
        "ai model",
        "gpt",
        "llm",
        "hallucination",
        "document",
        "documentation",
        "m&a",
        "merger",
        "acquisition",
        "deal",
        "nlp",
    ]
    simple_physical_keywords = [
        "flower",
        "plant",
        "basil",
        "seed",
        "light",
        "drum",
        "sound",
        "wave",
        "acoustic",
        "microphone",
        "vibration",
        "speaker",
    ]
    high_complexity_keywords = [
        "clinical",
        "patient",
        "in vivo",
        "animal model",
        "crispr",
        "genome",
        "gmp",
        "randomized trial",
        "irb",
        "fda",
        "phase i",
        "phase ii",
    ]

    is_digital = any(keyword in text for keyword in digital_keywords)
    is_simple_physical = any(keyword in text for keyword in simple_physical_keywords)
    is_high_complexity = any(keyword in text for keyword in high_complexity_keywords)

    # Normalize absurd line-item pricing across scenarios for pilot-scale plans.
    normalized_materials = []
    running_total = 0.0
    for material in parsed.materials:
        blob = f"{material.item} {material.notes} {material.quantity}".lower()
        cap = 180.0
        if any(token in blob for token in ["model", "gpt", "openai", "llm", "nlp platform", "subscription"]):
            cap = 120.0
        elif any(token in blob for token in ["cloud", "compute", "cluster", "gpu"]):
            cap = 150.0
        elif any(token in blob for token in ["expert", "reviewer", "consult", "legal"]):
            cap = 250.0
        elif any(token in blob for token in ["case study", "dataset", "documentation"]):
            cap = 150.0

        adjusted_price = min(max(material.estimatedPriceUsd, 0.0), cap)
        running_total += adjusted_price
        normalized_materials.append(
            MaterialItem(
                item=material.item,
                quantity=material.quantity,
                notes=material.notes,
                estimatedPriceUsd=round(adjusted_price, 2),
            )
        )
    parsed.materials = normalized_materials

    # Budget calibration by scenario
    low = max(0.0, float(parsed.estimatedCostUsd.low))
    high = max(low, float(parsed.estimatedCostUsd.high))
    if is_digital:
        low = min(low if low > 0 else 40.0, 180.0)
        high = min(high if high > 0 else 250.0, 300.0)
        parsed.estimatedCostUsd.notes = "Calibrated for software/data workflow with minimal tooling costs."
        parsed.riskLevel = "Low"
        parsed.estimatedCostUsd.low = min(low, max(80.0, running_total * 0.7))
        parsed.estimatedCostUsd.high = min(high, max(180.0, running_total * 1.05))
    elif is_simple_physical and not is_high_complexity:
        low = min(max(low, 120.0), 300.0)
        high = min(max(high, low), 600.0)
        if parsed.riskLevel == "High":
            parsed.riskLevel = "Medium"
        parsed.estimatedCostUsd.notes = "Calibrated for small pilot-scale physical/plant experiment assumptions."
    # Keep estimate coherent with normalized line items.
    low = min(low, max(60.0, running_total * 0.7))
    high = min(max(high, low), max(low + 40.0, running_total * 1.15))
    parsed.estimatedCostUsd.low = round(low, 2)
    parsed.estimatedCostUsd.high = round(max(low, high), 2)

    # General feasibility scoring logic applied to all hypotheses.
    risk_penalty = {"Low": 4, "Medium": 14, "High": 28}.get(parsed.riskLevel, 14)
    budget_penalty = min(32, parsed.estimatedCostUsd.high / 180.0)
    timeline_days = sum(_duration_to_days(phase.duration) for phase in parsed.timeline)
    timeline_penalty = min(20, timeline_days / 18.0) if timeline_days > 0 else 8
    complexity_penalty = 0
    if is_high_complexity:
        complexity_penalty += 24
    if is_digital:
        complexity_penalty -= 10
    if is_simple_physical and not is_high_complexity:
        complexity_penalty -= 4

    calibrated_score = 92 - risk_penalty - budget_penalty - timeline_penalty - complexity_penalty
    parsed.feasibilityScore = int(max(8, min(95, round(calibrated_score))))


def _derive_confidence_from_feasibility(
    feasibility_score: int,
) -> tuple[Literal["Very Low", "Low", "Medium", "High"], str]:
    if feasibility_score >= 85:
        return (
            "High",
            "High confidence aligns with a strong feasibility score (85+): clearer scope and fewer blocking unknowns.",
        )
    if feasibility_score >= 65:
        return (
            "Medium",
            "Medium confidence aligns with mid-range feasibility (65–84): several assumptions still need validation.",
        )
    if feasibility_score >= 45:
        return (
            "Low",
            "Low confidence aligns with weaker feasibility (45–64): material risks, cost, or execution gaps are likely.",
        )
    return (
        "Very Low",
        "Very low confidence aligns with low feasibility (0–44): major uncertainty, heavy assumptions, or a fragile pilot path.",
    )


def _offline_suggest_hypothesis() -> HypothesisSuggestion:
    return HypothesisSuggestion(hypothesis=OFFLINE_HYPOTHESIS_FALLBACK)


def _offline_generate_plan(payload: HypothesisRequest) -> ExperimentPlan:
    text = payload.hypothesis.strip() or OFFLINE_HYPOTHESIS_FALLBACK
    control_group = StudyGroup(
        name="Control",
        description="Baseline group with no intervention.",
        intervention="No blue-light pulse at dawn.",
        sampleSize="n=24 plants",
    )
    experimental_group = StudyGroup(
        name="Experimental",
        description="Intervention group receiving the treatment.",
        intervention="15-minute 470 nm blue-light pulse at dawn.",
        sampleSize="n=24 plants",
    )
    plan = ExperimentPlan(
        refinedHypothesis=text,
        experimentalDesign=(
            "Randomized pilot study comparing treated vs. untreated plants under fixed growth conditions."
        ),
        protocolSteps=[
            "Grow Arabidopsis thaliana under standardized temperature, humidity, and photoperiod.",
            "Randomly assign plants into control and experimental groups with equal counts.",
            "Apply a 15-minute 470 nm blue-light pulse at dawn to the experimental group only.",
            "Keep all other environmental conditions identical for both groups.",
            "Measure stomatal conductance one hour after dawn using the same instrument settings.",
            "Repeat measurements across multiple days and aggregate replicate-level data.",
            "Compare groups using pre-defined statistical analysis.",
        ],
        materials=[
            MaterialItem(
                item="Arabidopsis thaliana seedlings",
                quantity="48 plants",
                notes="Same growth stage for all replicates.",
                estimatedPriceUsd=60.0,
            ),
            MaterialItem(
                item="Blue LED source (470 nm)",
                quantity="1 unit",
                notes="Timer-controlled illumination for intervention.",
                estimatedPriceUsd=120.0,
            ),
            MaterialItem(
                item="Growth chamber access",
                quantity="1 week",
                notes="Controlled humidity/temperature conditions.",
                estimatedPriceUsd=80.0,
            ),
            MaterialItem(
                item="Stomatal conductance meter access",
                quantity="1 week",
                notes="Consistent instrument and operator for all reads.",
                estimatedPriceUsd=90.0,
            ),
        ],
        estimatedCostUsd=CostRange(
            low=250.0,
            high=450.0,
            notes="Demo-mode estimate for a small pilot setup.",
        ),
        timeline=[
            TimelinePhase(phase="Setup", duration="2 days", deliverable="Plants and equipment prepared."),
            TimelinePhase(phase="Intervention", duration="4 days", deliverable="Blue-light treatment executed."),
            TimelinePhase(phase="Analysis", duration="2 days", deliverable="Conductance comparison and summary."),
        ],
        feasibilityScore=78,
        feasibilityRationale=[
            "Pilot scope is small and operationally manageable.",
            "Equipment and materials are standard in teaching/research labs.",
            "Outcome metric is measurable with a clear endpoint.",
        ],
        riskLevel="Medium",
        safetyEthics=SafetyEthics(
            considerations=[
                "Follow electrical and light-source safety protocols in the lab.",
                "Prevent cross-condition contamination by keeping treatment groups separated.",
            ],
            approvals=["Institutional lab safety compliance check."],
        ),
        failureModes=[
            FailureMode(
                risk="Uneven plant baseline health masks intervention effects.",
                mitigation="Screen and randomize plants by baseline condition before assignment.",
            ),
            FailureMode(
                risk="Light exposure variability across replicates.",
                mitigation="Use fixed distance and calibrated intensity during every pulse.",
            ),
            FailureMode(
                risk="Measurement noise from inconsistent handling.",
                mitigation="Use one operator and a standardized measurement protocol.",
            ),
        ],
        alternatives=[
            AlternativePlan(
                name="Dose response variant",
                summary="Compare 5, 10, and 15-minute pulse durations.",
                costImpact="Slight increase due to additional runs.",
                timelineImpact="Adds 2-3 days.",
                tradeoffs=["Richer insight", "Higher execution complexity"],
            ),
            AlternativePlan(
                name="Different wavelength control",
                summary="Add red-light treatment arm to test wavelength specificity.",
                costImpact="Requires extra light setup.",
                timelineImpact="Adds 2 days.",
                tradeoffs=["Stronger causal interpretation", "More logistics"],
            ),
            AlternativePlan(
                name="Different species replication",
                summary="Repeat in a second model species for external validity.",
                costImpact="Higher material usage.",
                timelineImpact="Adds 4-5 days.",
                tradeoffs=["Better generalization", "Longer timeline"],
            ),
        ],
        staffingPlan=[
            StaffingItem(
                role="Research Assistant",
                headcount=1,
                hoursPerWeek=8,
                responsibilities="Run treatments, collect measurements, maintain logs.",
            ),
            StaffingItem(
                role="Project Lead",
                headcount=1,
                hoursPerWeek=3,
                responsibilities="Review design quality and validate analysis decisions.",
            ),
        ],
        statisticsPlan=StatisticsPlan(
            primaryEndpoint="Mean stomatal conductance at +1 hour post-dawn.",
            suggestedReplicates="At least 3 independent runs.",
            analysisMethod="Two-sample t-test or non-parametric equivalent if assumptions fail.",
            powerNotes="Pilot-scale estimate; expand sample size after variance estimation.",
        ),
        nextQuestions=[
            "Does treatment effect persist across multiple days?",
            "What is the minimum effective pulse duration?",
            "How sensitive is the effect to humidity fluctuations?",
        ],
        evidenceQualityNote=(
            "Offline demo mode: generated without live model or literature API calls. "
            "Use as a starter template and validate experimentally."
        ),
        literatureReferences=[],
        limitations=[
            Limitation(
                title="Offline template mode",
                description="Plan is generated from a deterministic fallback when no API key is configured.",
                mitigation="Add a valid OPENAI_API_KEY in .env for adaptive model-generated plans.",
            ),
            Limitation(
                title="Domain mismatch risk",
                description="Fallback content may not perfectly match every input hypothesis domain.",
                mitigation="Use as a structural baseline and manually adjust domain-specific details.",
            ),
            Limitation(
                title="Pilot-only budget",
                description="Cost and staffing assume small-scale execution.",
                mitigation="Re-estimate with local prices and scaling needs.",
            ),
        ],
        confidenceLevel="Medium",
        confidenceRationale=(
            "Fallback confidence is fixed for offline demo mode and should be re-evaluated with live model output."
        ),
        controlGroup=control_group,
        experimentalGroup=experimental_group,
    )
    _enforce_budget_sanity(plan, text)
    _apply_general_calibration(plan, text)
    confidence_level, confidence_rationale = _derive_confidence_from_feasibility(plan.feasibilityScore)
    plan.confidenceLevel = confidence_level
    plan.confidenceRationale = confidence_rationale
    if payload.useScientificLiterature:
        plan.evidenceQualityNote += " Literature toggle was enabled, but offline mode does not retrieve citations."
    return plan


def _llm_suggest_hypothesis() -> HypothesisSuggestion:
    diversity = random.randint(1, 1_000_000_000)
    try:
        response = _parse_with_model_fallback(
            messages=[
                {"role": "system", "content": SUGGEST_HYPOTHESIS_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        "Generate ONE novel hypothesis for the textarea. "
                        f"Diversity token (ignore semantically): {diversity}. "
                        "Avoid generic one-liners; include enough detail to plan a small study."
                    ),
                },
            ],
            response_format=HypothesisSuggestion,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            refusal = getattr(response.choices[0].message, "refusal", None)
            if refusal:
                _raise_harmful_prompt_error()
            raise HTTPException(
                status_code=502,
                detail="Model returned an invalid response format. Please retry.",
            )
        text = parsed.hypothesis.strip()
        if len(text) < 30:
            raise HTTPException(
                status_code=502,
                detail="Suggested hypothesis was too short. Please retry.",
            )
        return HypothesisSuggestion(hypothesis=text)
    except HTTPException:
        raise
    except Exception as exc:
        message = str(exc)
        if "content_filter" in message or "ResponsibleAIPolicyViolation" in message:
            _raise_harmful_prompt_error()
        raise HTTPException(status_code=500, detail=f"Failed to suggest hypothesis: {exc}") from exc


@app.post("/suggest-hypothesis", response_model=HypothesisSuggestion)
def suggest_hypothesis() -> HypothesisSuggestion:
    if not _has_configured_api_key():
        return _offline_suggest_hypothesis()
    return _llm_suggest_hypothesis()


@app.post("/generate-plan", response_model=None)
def generate_plan(payload: HypothesisRequest):
    try:
        if payload.suggest_only:
            if not _has_configured_api_key():
                return _offline_suggest_hypothesis().model_dump()
            suggestion = _llm_suggest_hypothesis()
            return suggestion.model_dump()
        if not _has_configured_api_key():
            return _offline_generate_plan(payload)

        references = _fetch_pubmed_references(payload.hypothesis) if payload.useScientificLiterature else []
        literature_context = ""
        if payload.useScientificLiterature:
            if references:
                formatted_refs = "\n".join(
                    [
                        f"- PMID {r['pmid']} | {r['title']} | {r['journal']} ({r['year']})"
                        for r in references
                    ]
                )
                literature_context = (
                    "Literature grounding mode is ON. Use these PubMed references and do not invent citations.\n"
                    f"{formatted_refs}\n"
                    "When evidence is limited, say so clearly in evidenceQualityNote."
                )
            else:
                literature_context = (
                    "Literature grounding mode is ON but no PubMed results were retrieved. "
                    "Be conservative and explicitly note evidence limitations."
                )

        response = _parse_with_model_fallback(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Create an execution-ready plan for this hypothesis:\n"
                        f"{payload.hypothesis.strip()}\n\n{literature_context}"
                    ),
                },
            ],
            response_format=ExperimentPlan,
        )

        parsed = response.choices[0].message.parsed
        if parsed is None:
            refusal = getattr(response.choices[0].message, "refusal", None)
            if refusal:
                _raise_harmful_prompt_error()
            raise HTTPException(
                status_code=502,
                detail="Model returned an invalid response format. Please retry.",
            )
        if payload.useScientificLiterature:
            known_pmids = {str(r["pmid"]) for r in references}
            if known_pmids:
                parsed.literatureReferences = [
                    ref for ref in parsed.literatureReferences if str(ref.pmid) in known_pmids
                ]
                if not parsed.literatureReferences:
                    parsed.literatureReferences = [
                        LiteratureReference(
                            title=r["title"],
                            journal=r["journal"],
                            year=r["year"],
                            pmid=r["pmid"],
                            relevanceNote="Retrieved from PubMed for grounding context.",
                        )
                        for r in references[:3]
                    ]
            if not parsed.evidenceQualityNote.strip():
                parsed.evidenceQualityNote = (
                    "Literature mode enabled. Validate cited evidence against source abstracts."
                )
        else:
            parsed.literatureReferences = []
            if not parsed.evidenceQualityNote.strip():
                parsed.evidenceQualityNote = "Generated without explicit literature grounding."

        _enforce_budget_sanity(parsed, payload.hypothesis)
        _apply_general_calibration(parsed, payload.hypothesis)
        confidence_level, confidence_rationale = _derive_confidence_from_feasibility(parsed.feasibilityScore)
        parsed.confidenceLevel = confidence_level
        parsed.confidenceRationale = confidence_rationale
        return parsed
    except HTTPException:
        raise
    except Exception as exc:
        message = str(exc)
        if _is_explicit_safety_policy_block(message):
            _raise_harmful_prompt_error()
        if _is_model_access_or_rate_issue(message):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Model access/rate issue on current key for primary model. "
                    "Fallback was attempted. Try again in a minute or use a key with available quota."
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {exc}")