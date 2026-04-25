export type ExperimentPlan = {
  refinedHypothesis: string;
  experimentalDesign: string;
  protocolSteps: string[];
  materials: Array<{ item: string; quantity?: string; notes?: string }>;
  estimatedCostUsd: { low: number; high: number; notes?: string };
  timeline: Array<{ phase: string; duration: string; deliverable: string }>;
};

export type GeneratePlanRequest = {
  hypothesis: string;
};

