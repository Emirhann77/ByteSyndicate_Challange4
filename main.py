import os
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


class HypothesisRequest(BaseModel):
    hypothesis: str = Field(..., min_length=1)


SYSTEM_PROMPT = (
    "You are an elite scientific program manager helping teams ship executable experiments quickly. "
    "Given a hypothesis, output a complete operational plan with protocol, costs, staffing, risk, "
    "safety/ethics checks, statistical plan, alternatives, and concrete next questions. "
    "Keep outputs realistic for a hackathon demo and wet-lab execution. "
    "Return only valid structured data matching the response schema exactly. "
    "All costs must be in USD and feasibilityScore must reflect practical deliverability."
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


@app.post("/generate-plan", response_model=ExperimentPlan)
def generate_plan(payload: HypothesisRequest) -> ExperimentPlan:
    try:
        response = client.beta.chat.completions.parse(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Create an execution-ready plan for this hypothesis:\n"
                        f"{payload.hypothesis.strip()}"
                    ),
                },
            ],
            response_format=ExperimentPlan,
        )

        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ValueError("Model did not return parseable structured output.")
        return parsed
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {exc}")