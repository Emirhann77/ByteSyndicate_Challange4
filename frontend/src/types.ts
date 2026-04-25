export type ExperimentPlan = {
  refinedHypothesis: string;
  experimentalDesign: string;
  protocolSteps: string[];
  materials: Array<{ item: string; quantity: string; notes: string; estimatedPriceUsd: number }>;
  estimatedCostUsd: { low: number; high: number; notes?: string };
  timeline: Array<{ phase: string; duration: string; deliverable: string }>;
  feasibilityScore: number;
  feasibilityRationale: string[];
  riskLevel: "Low" | "Medium" | "High";
  safetyEthics: { considerations: string[]; approvals: string[] };
  failureModes: Array<{ risk: string; mitigation: string }>;
  alternatives: Array<{
    name: string;
    summary: string;
    costImpact: string;
    timelineImpact: string;
    tradeoffs: string[];
  }>;
  staffingPlan: Array<{ role: string; headcount: number; hoursPerWeek: number; responsibilities: string }>;
  statisticsPlan: {
    primaryEndpoint: string;
    suggestedReplicates: string;
    analysisMethod: string;
    powerNotes: string;
  };
  nextQuestions: string[];
};

export type GeneratePlanRequest = {
  hypothesis: string;
};

