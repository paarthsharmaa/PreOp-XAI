import type { Meta, Outcome, PatientInputs, PatientsResponse, Prediction } from "./types";

export const STATIC_SITE = import.meta.env.VITE_STATIC === "1";

export class InputError extends Error {
  constructor(public readonly fields: { field: string; message: string }[]) {
    super(fields.map((item) => item.message).join(" "));
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (response.status === 422) {
    const body = await response.json();
    throw new InputError(body.detail);
  }
  if (!response.ok) throw new Error(`The API returned ${response.status}.`);
  return response.json();
}

export const getMeta = () => request<Meta>("/meta");
export const getPatients = () => request<PatientsResponse>("/patients");
export const getOutcome = (id: string) => request<Outcome>(`/patients/${encodeURIComponent(id)}/outcome`);
export const predict = (inputs: PatientInputs, signal?: AbortSignal) =>
  request<Prediction>("/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(inputs),
    signal,
  });
