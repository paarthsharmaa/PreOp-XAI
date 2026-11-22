import { ROMAN, risk } from "./format";
import type { Contribution, EndpointData, ModelKey, ModelPrediction, PatientInputs, SiteData } from "./types";

const TOP = 3;
export const LABS = ["hemoglobin", "platelets", "creatinine", "bun", "sodium", "potassium", "glucose"] as const;

export const byImpact = (shap: Contribution[]) =>
  [...shap].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution) || a.concept.localeCompare(b.concept));

export function describeValue(concept: string, inputs: PatientInputs): string {
  if (concept === "asa") return `ASA ${ROMAN[inputs.asa]}`;
  if (concept === "sex") return inputs.sex === "F" ? "Female" : "Male";
  if (concept === "age") return `${inputs.age.toFixed(0)} y`;
  const value = inputs[concept as keyof PatientInputs];
  return value === null ? "missing" : String(value);
}

function factorName(row: Contribution, inputs: PatientInputs): string {
  if (row.concept === "asa") return `ASA ${ROMAN[inputs.asa]}`;
  if (row.concept === "age") return `age ${inputs.age.toFixed(0)}`;
  if (row.concept === "sex") return inputs.sex === "F" ? "female sex" : "male sex";
  const value = inputs[row.concept as keyof PatientInputs];
  return value === null ? `missing ${row.label.toLowerCase()}` : `${row.label.toLowerCase()} of ${value}`;
}

const capitalise = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

function extremeSentence(lr: ModelPrediction, xgb: ModelPrediction, inputs: PatientInputs, direction: 1 | -1): string {
  const verb = direction > 0 ? "raising" : "lowering";
  const pick = (model: ModelPrediction) =>
    [...model.shap]
      .filter((row) => row.contribution * direction > 0)
      .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))[0];
  const first = pick(lr);
  const second = pick(xgb);
  if (!first && !second) return `Neither model has a factor ${verb} risk.`;
  if (first && second && first.concept === second.concept) {
    return `${capitalise(factorName(first, inputs))} is the biggest factor ${verb} risk in both models.`;
  }
  const part = (row: Contribution | undefined, name: string) =>
    row ? `${factorName(row, inputs)} in ${name}` : `nothing in ${name}`;
  return `The biggest factor ${verb} risk is ${part(first, "LR")} and ${part(second, "XGBoost")}.`;
}

export function agreement(lr: ModelPrediction, xgb: ModelPrediction): number {
  const first = new Set(byImpact(lr.shap).slice(0, TOP).map((row) => row.concept));
  return byImpact(xgb.shap)
    .slice(0, TOP)
    .filter((row) => first.has(row.concept)).length;
}

export function plainLanguage(
  lr: ModelPrediction,
  xgb: ModelPrediction,
  inputs: PatientInputs,
  endpoint: EndpointData,
): string[] {
  const outcome = endpoint.label.toLowerCase();
  const level = (model: ModelPrediction) => (model.above_threshold ? "above" : "below");
  const position =
    lr.above_threshold === xgb.above_threshold
      ? `Both models place this patient ${level(lr)} their alert threshold.`
      : `The models disagree: LR is ${level(lr)} its alert threshold and XGBoost is ${level(xgb)} its own.`;
  const sentences = [
    `Estimated risk of ${outcome} is ${risk(lr.calibrated_probability)} with LR and ${risk(
      xgb.calibrated_probability,
    )} with XGBoost, against a development cohort rate of ${risk(endpoint.base_rate.rate)}. ${position}`,
    `${extremeSentence(lr, xgb, inputs, 1)} ${extremeSentence(lr, xgb, inputs, -1)}`,
    `LR and XGBoost agree on ${agreement(lr, xgb)} of the top ${TOP} drivers.`,
  ];
  const missing = LABS.filter((lab) => inputs[lab] === null).length;
  if (missing) {
    sentences.push(
      `${missing} of ${LABS.length} labs are missing. The models treat missingness itself as a signal, so these contributions describe how the data were recorded and are not a physiological effect.`,
    );
  }
  return sentences;
}

export interface DriverRow {
  concept: string;
  label: string;
  contribution: number;
  globalRank: number;
  refitsInTop: number;
  refits: number;
  status: "stable" | "unstable" | "outside";
}

export function driverRows(site: SiteData, endpoint: EndpointData, model: ModelKey, prediction: ModelPrediction) {
  const shap = endpoint.shap.models[model];
  return byImpact(prediction.shap)
    .slice(0, TOP)
    .map((row): DriverRow => {
      const frequency = shap.concepts[row.concept].top5_frequency;
      const refits = endpoint.shap.refits;
      return {
        concept: row.concept,
        label: site.labels.concepts[row.concept],
        contribution: row.contribution,
        globalRank: shap.order.indexOf(row.concept) + 1,
        refitsInTop: Math.round(frequency * refits),
        refits,
        status: frequency === 1 ? "stable" : frequency === 0 ? "outside" : "unstable",
      };
    });
}
