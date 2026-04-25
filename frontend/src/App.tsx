import { useState } from "react";
import type { ExperimentPlan } from "./types";
import { generateExperimentPlan } from "./lib/experimentPlanClient";

function formatUsdRange(low: number, high: number) {
  const f = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" });
  return `${f.format(low)}–${f.format(high)}`;
}

function formatUsd(value: number) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(value);
}

type PlanTab = "overview" | "protocol" | "budget" | "risk" | "alternatives";

export function App() {
  const [hypothesis, setHypothesis] = useState("");
  const [useScientificLiterature, setUseScientificLiterature] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<ExperimentPlan | null>(null);
  const [activeTab, setActiveTab] = useState<PlanTab>("overview");

  async function onGenerate() {
    const trimmed = hypothesis.trim();
    setError(null);
    setPlan(null);

    if (!trimmed) {
      setError("Please enter a scientific hypothesis to generate a plan.");
      return;
    }

    setIsLoading(true);
    try {
      const result = await generateExperimentPlan(trimmed, useScientificLiterature);
      setPlan(result);
      setActiveTab("overview");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to generate plan.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  function onUseExample() {
    setHypothesis(
      "Increasing magnesium concentration in growth media increases photosynthetic efficiency in Chlorella vulgaris under constant light."
    );
  }

  function onExportJson() {
    if (!plan) return;
    const blob = new Blob([JSON.stringify(plan, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "experiment-plan.json";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function onExportMaterialsCsv() {
    if (!plan) return;
    const rows = [
      "item,quantity,estimatedPriceUsd,notes",
      ...plan.materials.map((m) =>
        [m.item, m.quantity, m.estimatedPriceUsd.toString(), m.notes]
          .map((value) => `"${value.replaceAll('"', '""')}"`)
          .join(",")
      )
    ];
    const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "materials.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const riskClass = plan ? `risk-pill risk-${plan.riskLevel.toLowerCase()}` : "risk-pill";

  return (
    <div className="container">
      <header className="topbar">
        <div className="brand">
          <div className="logo" aria-hidden="true" />
          <div style={{ minWidth: 0 }}>
            <h1>AI Scientist OS</h1>
            <div className="small">Hackathon edition · hypothesis to executable lab plan</div>
          </div>
        </div>
        <div className="status-pill">FastAPI + GitHub Models</div>
      </header>

      <section className="hero">
        <h2 className="hero-title">From scientific question to lab-ready execution in seconds.</h2>
        <p className="hero-subtitle">
          Generate a complete plan with feasibility scoring, safety and ethics checks, staffing, budget,
          failure mitigations, and alternative execution tracks for decision making.
        </p>
      </section>

      <main className="grid">
        <section className="card">
          <div className="card-header">
            <h3 className="card-title">Hypothesis input</h3>
            <span className="small mono">v2 Hackathon</span>
          </div>
          <div className="card-body">
            <textarea
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
              placeholder="Example: Modulating X will increase/decrease Y in system Z under condition C…"
              aria-label="Scientific hypothesis"
            />

            <div className="controls">
              <div className="hint">
                Tip: include intervention, organism/system, measurable endpoint, and constraints.
              </div>
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={useScientificLiterature}
                  onChange={(e) => setUseScientificLiterature(e.target.checked)}
                  disabled={isLoading}
                />
                <span>Scientific literature grounding</span>
              </label>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <button className="btn btn-secondary" type="button" onClick={onUseExample} disabled={isLoading}>
                  Use example
                </button>
                <button className="btn" type="button" onClick={onGenerate} disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <span className="spinner" aria-hidden="true" />
                      Generating…
                    </>
                  ) : (
                    "Generate Experiment Plan"
                  )}
                </button>
              </div>
            </div>

            {error ? <div style={{ marginTop: 12 }} className="error">{error}</div> : null}

            {plan ? (
              <div className="controls" style={{ marginTop: 14 }}>
                <div className="hint">Export artifacts for judges and lab ops</div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <button className="btn btn-secondary" type="button" onClick={onExportJson}>
                    Export JSON
                  </button>
                  <button className="btn btn-secondary" type="button" onClick={onExportMaterialsCsv}>
                    Export Materials CSV
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h3 className="card-title">Execution dashboard</h3>
            <span className="small">{plan ? "Ready" : isLoading ? "Working…" : "Waiting"}</span>
          </div>
          <div className="card-body">
            {!plan && !isLoading ? (
              <div className="small">
                Your plan dashboard will appear here after generation.
              </div>
            ) : null}

            {isLoading ? (
              <div className="section">
                <h3>Generating</h3>
                <div className="small">
                  Scoring feasibility, drafting protocol, planning staffing, assessing risks, and generating
                  alternatives{useScientificLiterature ? " with literature grounding" : ""}…
                </div>
              </div>
            ) : null}

            {plan ? (
              <>
                <div className="metrics-grid">
                  <div className="metric-card">
                    <div className="metric-label">Feasibility score</div>
                    <div className="metric-value">{plan.feasibilityScore}/100</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-label">Estimated budget</div>
                    <div className="metric-value">{formatUsdRange(plan.estimatedCostUsd.low, plan.estimatedCostUsd.high)}</div>
                  </div>
                  <div className="metric-card">
                    <div className="metric-label">Risk level</div>
                    <div className={riskClass}>{plan.riskLevel}</div>
                  </div>
                </div>

                <div className="tabs">
                  <button type="button" className={`tab-btn ${activeTab === "overview" ? "tab-btn-active" : ""}`} onClick={() => setActiveTab("overview")}>Overview</button>
                  <button type="button" className={`tab-btn ${activeTab === "protocol" ? "tab-btn-active" : ""}`} onClick={() => setActiveTab("protocol")}>Protocol</button>
                  <button type="button" className={`tab-btn ${activeTab === "budget" ? "tab-btn-active" : ""}`} onClick={() => setActiveTab("budget")}>Budget & Team</button>
                  <button type="button" className={`tab-btn ${activeTab === "risk" ? "tab-btn-active" : ""}`} onClick={() => setActiveTab("risk")}>Risk & Ethics</button>
                  <button type="button" className={`tab-btn ${activeTab === "alternatives" ? "tab-btn-active" : ""}`} onClick={() => setActiveTab("alternatives")}>Alternatives</button>
                </div>

                {activeTab === "overview" ? (
                  <>
                    <div className="section">
                      <h3>Refined Hypothesis</h3>
                      <div>{plan.refinedHypothesis}</div>
                    </div>
                    <div className="section">
                      <h3>Experimental Design</h3>
                      <div>{plan.experimentalDesign}</div>
                    </div>
                    <div className="section">
                      <h3>Control vs Experimental Group</h3>
                      <div>
                        <span className="mono">Control:</span> {plan.controlGroup.description}
                      </div>
                      <div className="small">Intervention: {plan.controlGroup.intervention}</div>
                      <div className="small">Sample size: {plan.controlGroup.sampleSize}</div>
                      <div style={{ marginTop: 8 }}>
                        <span className="mono">Experimental:</span> {plan.experimentalGroup.description}
                      </div>
                      <div className="small">Intervention: {plan.experimentalGroup.intervention}</div>
                      <div className="small">Sample size: {plan.experimentalGroup.sampleSize}</div>
                    </div>
                    <div className="section">
                      <h3>Feasibility Rationale</h3>
                      <ul className="list">
                        {plan.feasibilityRationale.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="section">
                      <h3>Timeline</h3>
                      <ul className="list">
                        {plan.timeline.map((phase, index) => (
                          <li key={index}>
                            <span className="mono">{phase.phase}</span> — {phase.duration}
                            <div className="small">Deliverable: {phase.deliverable}</div>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="section">
                      <h3>Evidence Quality</h3>
                      <div className="small">{plan.evidenceQualityNote}</div>
                    </div>
                    {plan.literatureReferences.length ? (
                      <div className="section">
                        <h3>Literature References</h3>
                        <ul className="list">
                          {plan.literatureReferences.map((ref, index) => (
                            <li key={index}>
                              <span className="mono">PMID {ref.pmid}</span> — {ref.title}
                              <div className="small">{ref.journal} ({ref.year})</div>
                              <div className="small">{ref.relevanceNote}</div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </>
                ) : null}

                {activeTab === "protocol" ? (
                  <>
                    <div className="section">
                      <h3>Study Groups</h3>
                      <ul className="list">
                        <li>
                          <span className="mono">Control Group ({plan.controlGroup.name})</span>
                          <div className="small">{plan.controlGroup.description}</div>
                          <div className="small">Intervention: {plan.controlGroup.intervention}</div>
                          <div className="small">Sample size: {plan.controlGroup.sampleSize}</div>
                        </li>
                        <li>
                          <span className="mono">Experimental Group ({plan.experimentalGroup.name})</span>
                          <div className="small">{plan.experimentalGroup.description}</div>
                          <div className="small">Intervention: {plan.experimentalGroup.intervention}</div>
                          <div className="small">Sample size: {plan.experimentalGroup.sampleSize}</div>
                        </li>
                      </ul>
                    </div>
                    <div className="section">
                      <h3>Step-by-step Protocol</h3>
                      <ol className="list">
                        {plan.protocolSteps.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ol>
                    </div>
                    <div className="section">
                      <h3>Statistics Plan</h3>
                      <div><span className="mono">Primary endpoint:</span> {plan.statisticsPlan.primaryEndpoint}</div>
                      <div><span className="mono">Replicates:</span> {plan.statisticsPlan.suggestedReplicates}</div>
                      <div><span className="mono">Method:</span> {plan.statisticsPlan.analysisMethod}</div>
                      <div className="small" style={{ marginTop: 6 }}>{plan.statisticsPlan.powerNotes}</div>
                    </div>
                    <div className="section">
                      <h3>Open Questions</h3>
                      <ul className="list">
                        {plan.nextQuestions.map((question, index) => (
                          <li key={index}>{question}</li>
                        ))}
                      </ul>
                    </div>
                  </>
                ) : null}

                {activeTab === "budget" ? (
                  <>
                    <div className="section">
                      <h3>Materials and Reagents</h3>
                      <ul className="list">
                        {plan.materials.map((m, i) => (
                          <li key={i}>
                            <span className="mono">{m.item}</span> — {m.quantity} — {formatUsd(m.estimatedPriceUsd)}
                            <div className="small">{m.notes}</div>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="section">
                      <h3>Estimated Cost Range</h3>
                      <div className="mono">{formatUsdRange(plan.estimatedCostUsd.low, plan.estimatedCostUsd.high)}</div>
                      <div className="small" style={{ marginTop: 6 }}>{plan.estimatedCostUsd.notes}</div>
                    </div>
                    <div className="section">
                      <h3>Staffing Plan</h3>
                      <ul className="list">
                        {plan.staffingPlan.map((staff, index) => (
                          <li key={index}>
                            <span className="mono">{staff.role}</span> — {staff.headcount} person(s), {staff.hoursPerWeek} hrs/week
                            <div className="small">{staff.responsibilities}</div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </>
                ) : null}

                {activeTab === "risk" ? (
                  <>
                    <div className="section">
                      <h3>Safety Considerations</h3>
                      <ul className="list">
                        {plan.safetyEthics.considerations.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="section">
                      <h3>Required Approvals</h3>
                      <ul className="list">
                        {plan.safetyEthics.approvals.map((approval, index) => (
                          <li key={index}>{approval}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="section">
                      <h3>Failure Modes and Mitigations</h3>
                      <ul className="list">
                        {plan.failureModes.map((mode, index) => (
                          <li key={index}>
                            <span className="mono">{mode.risk}</span>
                            <div className="small">Mitigation: {mode.mitigation}</div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </>
                ) : null}

                {activeTab === "alternatives" ? (
                  <div className="section">
                    <h3>Alternative Execution Paths</h3>
                    <div className="alt-grid">
                      {plan.alternatives.map((alt, index) => (
                        <div className="alt-card" key={index}>
                          <div className="mono">{alt.name}</div>
                          <div className="small" style={{ marginTop: 6 }}>{alt.summary}</div>
                          <div className="small" style={{ marginTop: 8 }}>
                            Cost impact: {alt.costImpact}
                          </div>
                          <div className="small">
                            Timeline impact: {alt.timelineImpact}
                          </div>
                          <ul className="list" style={{ marginTop: 8 }}>
                            {alt.tradeoffs.map((tradeoff, i) => (
                              <li key={i}>{tradeoff}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="small" style={{ marginTop: 10 }}>
                  Demo tip: generate once, then compare the Alternatives tab to pitch budget-vs-speed tradeoffs to judges.
                </div>
              </>
            ) : null}
          </div>
        </section>
      </main>
    </div>
  );
}

