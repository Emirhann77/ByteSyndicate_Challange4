import { useMemo, useState } from "react";
import type { ExperimentPlan } from "./types";
import { createExperimentPlanClient } from "./lib/experimentPlanClient";

function formatUsdRange(low: number, high: number) {
  const f = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" });
  return `${f.format(low)}–${f.format(high)}`;
}

export function App() {
  const client = useMemo(() => createExperimentPlanClient(), []);

  const [hypothesis, setHypothesis] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<ExperimentPlan | null>(null);

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
      const result = await client.generatePlan({ hypothesis: trimmed });
      setPlan(result);
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

  return (
    <div className="container">
      <header className="topbar">
        <div className="brand">
          <div className="logo" aria-hidden="true" />
          <div style={{ minWidth: 0 }}>
            <h1>AI Scientist OS</h1>
            <div className="small">Hackathon demo · hypothesis → experiment plan</div>
          </div>
        </div>
        <div className="status-pill">Mock mode</div>
      </header>

      <section className="hero">
        <h2 className="hero-title">Generate rigorous experiment plans in seconds.</h2>
        <p className="hero-subtitle">
          Paste a hypothesis, then get a structured plan with design, protocol, materials, cost, and
          timeline. Built to plug into a FastAPI backend later.
        </p>
      </section>

      <main className="grid">
        <section className="card">
          <div className="card-header">
            <h3 className="card-title">Hypothesis input</h3>
            <span className="small mono">v0</span>
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
                Tip: be specific about the intervention, system, and measurable outcome.
              </div>
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
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h3 className="card-title">Experiment plan</h3>
            <span className="small">{plan ? "Ready" : isLoading ? "Working…" : "Waiting"}</span>
          </div>
          <div className="card-body">
            {!plan && !isLoading ? (
              <div className="small">
                Your structured plan will appear here. In the real system, this panel will render the
                FastAPI response.
              </div>
            ) : null}

            {isLoading ? (
              <div className="section">
                <h3>Generating</h3>
                <div className="small">
                  Refining the hypothesis, selecting controls, drafting protocol steps, and estimating
                  cost/timeline…
                </div>
              </div>
            ) : null}

            {plan ? (
              <>
                <div className="section">
                  <h3>1. Refined Hypothesis</h3>
                  <div>{plan.refinedHypothesis}</div>
                </div>

                <div className="section">
                  <h3>2. Experimental Design</h3>
                  <div>{plan.experimentalDesign}</div>
                </div>

                <div className="section">
                  <h3>3. Step-by-step Protocol</h3>
                  <ol className="list">
                    {plan.protocolSteps.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ol>
                </div>

                <div className="section">
                  <h3>4. Materials / Reagents</h3>
                  <ul className="list">
                    {plan.materials.map((m, i) => (
                      <li key={i}>
                        <span className="mono">{m.item}</span>
                        {m.quantity ? <span> — {m.quantity}</span> : null}
                        {m.notes ? <span className="small"> ({m.notes})</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="section">
                  <h3>5. Estimated Cost</h3>
                  <div className="mono">{formatUsdRange(plan.estimatedCostUsd.low, plan.estimatedCostUsd.high)}</div>
                  {plan.estimatedCostUsd.notes ? (
                    <div className="small" style={{ marginTop: 6 }}>
                      {plan.estimatedCostUsd.notes}
                    </div>
                  ) : null}
                </div>

                <div className="section">
                  <h3>6. Timeline</h3>
                  <ul className="list">
                    {plan.timeline.map((t, i) => (
                      <li key={i}>
                        <span className="mono">{t.phase}</span> — {t.duration}
                        <div className="small">Deliverable: {t.deliverable}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            ) : null}
          </div>
        </section>
      </main>
    </div>
  );
}

