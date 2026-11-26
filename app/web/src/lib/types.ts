export type EndpointKey = "mortality" | "icu";
export type ModelKey = "lr" | "xgboost";
export const ENDPOINT_KEYS: EndpointKey[] = ["mortality", "icu"];
export const MODEL_KEYS: ModelKey[] = ["lr", "xgboost"];

export interface Ci {
  v: number;
  lo: number;
  hi: number;
}

export interface ModelEvaluation {
  auroc: Ci;
  ap: Ci;
  brier: Ci;
  slope: number;
  citl: number;
  roc: { fpr: number[]; tpr: number[] };
  pr: { recall: number[]; precision: number[] };
  deciles: { predicted: number; observed: number }[];
}

export interface Evaluation {
  n: number;
  events: number;
  prevalence: number;
  bootstraps: number;
  auroc_difference: Ci;
  models: Record<ModelKey, ModelEvaluation>;
}

export interface ConceptShap {
  importance: number;
  missingness: number;
  top5_frequency: number;
  refits: number[];
}

export interface ModelShap {
  order: string[];
  concepts: Record<string, ConceptShap>;
  spearman: number;
  jaccard: number;
  successful_refits: number;
  baseline: number;
}

export interface Transport {
  drop: number;
  test_auroc: number;
  external_auroc: number;
  slope: number;
  citl: number;
  test_slope: number;
  test_citl: number;
}

export interface EndpointData {
  label: string;
  test: Evaluation;
  external: Evaluation;
  transport: Record<ModelKey, Transport>;
  shap: { background_n: number; explained_n: number; refits: number; models: Record<ModelKey, ModelShap> };
  repeats: {
    splits: number;
    points: { seed: number; lr: number; xgboost: number; difference: number }[];
    difference: { median: number; p2_5: number; p97_5: number; share_xgb_better: number };
    xgb_wins: number;
    auroc: Record<ModelKey, { median: number; p2_5: number; p97_5: number }>;
  };
  lag0: {
    models: Record<ModelKey, { primary: Ci; lag0: Ci; change: number }>;
    missing_primary: number;
    missing_lag0: number;
  };
  base_rate: { n: number; events: number; rate: number };
  thresholds: Record<ModelKey, number>;
  takeaways: Record<"roc" | "pr" | "calibration" | "shap" | "stability" | "repeats" | "lag0" | "external", string>;
}

export interface FlowStep {
  label: string;
  n: number | string;
  kind: "start" | "out" | "keep" | "final";
}

export interface SiteData {
  notice: string;
  labels: { models: Record<ModelKey, string>; concepts: Record<string, string>; ci: string };
  sources: {
    mover: { name: string; detail: string; url: string };
    vitaldb: { name: string; detail: string; url: string; licence: string; licence_url: string; changes: string };
  };
  overview: { question: string; answer: string; detail: string; link: string }[];
  cohort: {
    mover: FlowStep[];
    vitaldb: FlowStep[];
    mover_events: Record<EndpointKey, number>;
    vitaldb_events: Record<EndpointKey, number>;
    missing_labs: Record<string, number>;
    typical: Record<string, { median: number; q1: number; q3: number }>;
  };
  endpoints: Record<EndpointKey, EndpointData>;
  methods: {
    environment: { python: string; platform: string; packages: Record<string, string> };
    determinism: { identical: boolean; differences: number };
    selftest: { tree_max_error: number; tree_trials: number; linear_max_error: number; passed: boolean };
    split_check: { primary_events: number; low: number; median: number; high: number; seeds: number };
  };
}

export interface PatientInputs {
  age: number;
  sex: "F" | "M";
  asa: number;
  hemoglobin: number | null;
  platelets: number | null;
  creatinine: number | null;
  bun: number | null;
  sodium: number | null;
  potassium: number | null;
  glucose: number | null;
}

export interface Contribution {
  concept: string;
  label: string;
  contribution: number;
  value_part: number;
  missingness_part: number;
}

export interface ModelPrediction {
  log_odds: number;
  native_margin: number;
  base_value: number;
  calibrated_log_odds: number;
  calibrated_probability: number;
  threshold: number;
  above_threshold: boolean;
  recalibration_intercept: number;
  recalibration_slope: number;
  shap: Contribution[];
}

export type Prediction = Record<EndpointKey, Record<ModelKey, ModelPrediction>> & { scale: string; notice: string };

export interface ExamplePatient {
  id: string;
  label: string;
  source: "vitaldb" | "synthetic";
  description: string;
  inputs: PatientInputs;
  has_outcome: boolean;
}

export interface PatientsResponse {
  notice: string;
  attribution: string;
  patients: ExamplePatient[];
}

export interface Meta {
  labels: Record<string, string>;
  units: Record<string, string>;
  ranges: Record<string, { min: number; max: number }>;
}

export interface Outcome {
  id: string;
  mortality: boolean;
  icu: boolean;
}
