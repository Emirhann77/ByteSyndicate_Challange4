import type { ExperimentPlan, GeneratePlanRequest } from "../types";

function sentenceCase(input: string) {
  const trimmed = input.trim();
  if (!trimmed) return "";
  return trimmed[0]!.toUpperCase() + trimmed.slice(1);
}

export async function generateMockExperimentPlan(
  req: GeneratePlanRequest
): Promise<ExperimentPlan> {
  await new Promise((r) => setTimeout(r, 900));

  const hypothesis = sentenceCase(req.hypothesis || "A specific intervention changes an observable outcome.");

  return {
    refinedHypothesis: `${hypothesis} Specifically, we predict a measurable shift in the primary outcome relative to control under otherwise matched conditions.`,
    experimentalDesign:
      "Run a randomized, controlled experiment with pre-registered primary/secondary outcomes. Use 2–3 conditions (control + intervention levels), blinded measurement if feasible, and sufficient replicates to detect the expected effect size. Track confounders and define exclusion criteria up-front.",
    protocolSteps: [
      "Define primary outcome metric, acceptable variance, and success criteria.",
      "Select model system / cohort and inclusion/exclusion criteria.",
      "Randomize samples into control and intervention groups; label with anonymous IDs.",
      "Apply intervention according to dosing/schedule; keep environment constant across groups.",
      "Collect measurements at predefined timepoints; log metadata (batch, operator, instrument).",
      "Perform QC checks, then analyze using the pre-registered statistical plan.",
      "Summarize results, limitations, and next-step decision (iterate, scale, or pivot)."
    ],
    materials: [
      { item: "Sample/cohort", notes: "Define N based on power analysis" },
      { item: "Intervention reagent", quantity: "varies", notes: "Include 2–3 dose levels if applicable" },
      { item: "Control vehicle / placebo", quantity: "matched" },
      { item: "Measurement assay / instrument access", notes: "Calibrate before run" },
      { item: "PPE + consumables", notes: "Pipette tips, tubes/plates, gloves" },
      { item: "Notebook + tracking sheet", notes: "Template for metadata capture" }
    ],
    estimatedCostUsd: {
      low: 250,
      high: 1500,
      notes:
        "Range depends on sample size, assay choice, and whether instrument time is billed internally."
    },
    timeline: [
      { phase: "Setup", duration: "0.5–1 day", deliverable: "Protocol + randomization + materials list" },
      { phase: "Execution", duration: "1–3 days", deliverable: "Raw measurements + QC logs" },
      { phase: "Analysis", duration: "0.5–1 day", deliverable: "Plots, stats, and decision summary" },
      { phase: "Iteration", duration: "1–2 days", deliverable: "Revised hypothesis / next experiment" }
    ]
  };
}

