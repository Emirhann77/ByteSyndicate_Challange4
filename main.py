import os
import json
import re
import urllib.parse
import urllib.request
from typing import List, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

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
    controlGroup: StudyGroup
    experimentalGroup: StudyGroup


class HypothesisRequest(BaseModel):
    hypothesis: str = Field(..., min_length=1)
    useScientificLiterature: bool = False


SYSTEM_PROMPT = (
    "You are an elite scientific program manager helping teams ship executable experiments quickly. "
    "Given a hypothesis, output a complete operational plan with protocol, costs, staffing, risk, "
    "safety/ethics checks, statistical plan, alternatives, and concrete next questions. "
    "Keep outputs realistic for a hackathon demo and wet-lab execution. "
    "Return only valid structured data matching the response schema exactly. "
    "All costs must be in USD and feasibilityScore must reflect practical deliverability. "
    "Default to small pilot-scale studies unless the user explicitly requests large-scale execution. "
    "For typical classroom/lab pilot designs, keep total budget in a realistic low range and justify it. "
    "Always define explicit controlGroup and experimentalGroup with clear interventions and sample sizes."
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

DEFAULT_MODEL = "gpt-4o"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _raise_harmful_prompt_error() -> None:
    raise HTTPException(
        status_code=400,
        detail="This request is harmful or unsafe. I cannot provide a response for it.",
    )


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


@app.post("/generate-plan", response_model=ExperimentPlan)
def generate_plan(payload: HypothesisRequest) -> ExperimentPlan:
    try:
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

        response = client.beta.chat.completions.parse(
            model=DEFAULT_MODEL,
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
        return parsed
    except HTTPException:
        raise
    except Exception as exc:
        message = str(exc)
        if "content_filter" in message or "ResponsibleAIPolicyViolation" in message:
            _raise_harmful_prompt_error()
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {exc}")