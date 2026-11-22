import { useEffect, useMemo, useRef, useState } from "react";
import { DriverTable, InputPanel, RiskGauge, Waterfall } from "../components/explorer";
import { Callout, EndpointToggle, PageHeader } from "../components/ui";
import { getMeta, getOutcome, getPatients, InputError, predict, STATIC_SITE } from "../lib/api";
import { plainLanguage } from "../lib/explain";
import { fixed, signed } from "../lib/format";
import { useSite } from "../lib/site";
import {
  MODEL_KEYS,
  type EndpointKey,
  type ExamplePatient,
  type Meta,
  type ModelPrediction,
  type Outcome,
  type PatientInputs,
  type PatientsResponse,
  type Prediction,
} from "../lib/types";

function waterfallDomain(models: ModelPrediction[]): [number, number] {
  const values: number[] = [];
  for (const model of models) {
    let running = model.base_value;
    values.push(running);
    for (const row of model.shap) {
      running += row.contribution;
      values.push(running);
    }
  }
  const low = Math.min(...values);
  const high = Math.max(...values);
  const pad = Math.max((high - low) * 0.08, 0.1);
  return [low - pad, high + pad];
}

function StaticNotice() {
  return (
    <>
      <PageHeader eyebrow="Patient explorer" title="Run locally for the live demo">
        The explorer needs the local API, because its models and SHAP background derive from MOVER patient data and are
        not published with this site.
      </PageHeader>
      <div className="max-w-2xl rounded-lg border border-line p-5">
        <h2 className="text-xl">Start it on your machine</h2>
        <pre className="mt-3 overflow-x-auto rounded bg-wash p-3 text-sm text-ink"><code>{"make setup\nmake export-models\nmake app"}</code></pre>
        <p className="mt-3 text-sm leading-relaxed">
          You need approved access to MOVER and a copy of VitalDB, placed as described in the repository's data guide.
        </p>
      </div>
    </>
  );
}

function VitalDbCaveat({ endpoint }: { endpoint: EndpointKey }) {
  const site = useSite();
  const data = site.endpoints[endpoint];
  const { lr, xgboost } = data.transport;
  return (
    <Callout title="VitalDB patient.">
      These models were developed on MOVER and are miscalibrated at VitalDB, so read this risk with caution. For{" "}
      {data.label.toLowerCase()}, the VitalDB calibration slope was {fixed(lr.slope, 2)} (LR) and {fixed(xgboost.slope, 2)}{" "}
      (XGBoost), where the ideal is one. Calibration-in-the-large was {signed(lr.citl, 2)} and {signed(xgboost.citl, 2)}, and
      AUROC fell by {fixed(lr.drop)} and {fixed(xgboost.drop)}.
    </Callout>
  );
}

function OutcomeReveal({ patient, endpoint }: { patient: ExamplePatient; endpoint: EndpointKey }) {
  const site = useSite();
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setOutcome(null);
    setFailed(false);
  }, [patient.id]);

  if (!patient.has_outcome) return null;
  if (failed) return <p className="m-0 text-sm text-warn">The observed outcome could not be loaded.</p>;
  if (!outcome) {
    return (
      <button type="button" onClick={() => getOutcome(patient.id).then(setOutcome).catch(() => setFailed(true))} className="min-h-9 rounded border border-line px-3 text-sm font-medium text-ink hover:bg-wash">
        Reveal outcome
      </button>
    );
  }
  return (
    <p className="m-0 text-sm text-ink" data-testid="observed-outcome">
      <strong className="font-semibold">Observed:</strong> {site.endpoints[endpoint].label} {outcome[endpoint] ? "occurred" : "did not occur"}.
    </p>
  );
}

export default function Explorer() {
  return STATIC_SITE ? <StaticNotice /> : <LiveExplorer />;
}

function LiveExplorer() {
  const site = useSite();
  const [catalog, setCatalog] = useState<PatientsResponse | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [offline, setOffline] = useState(false);
  const [patientId, setPatientId] = useState("");
  const [inputs, setInputs] = useState<PatientInputs | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [reference, setReference] = useState<Prediction | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [endpoint, setEndpoint] = useState<EndpointKey>("mortality");
  const pendingReference = useRef(true);

  useEffect(() => {
    Promise.all([getPatients(), getMeta()])
      .then(([patients, details]) => {
        setCatalog(patients);
        setMeta(details);
        const first = patients.patients.find((patient) => patient.id === "synthetic-moderate") ?? patients.patients[0];
        setPatientId(first.id);
        setInputs(first.inputs);
      })
      .catch(() => setOffline(true));
  }, []);

  useEffect(() => {
    if (!inputs) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      predict(inputs, controller.signal)
        .then((result) => {
          setErrors({});
          setPrediction(result);
          if (pendingReference.current) {
            pendingReference.current = false;
            setReference(result);
          }
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          if (error instanceof InputError) {
            setErrors(Object.fromEntries(error.fields.map((item) => [item.field, item.message])));
          } else {
            setOffline(true);
          }
        });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [inputs]);

  const patient = catalog?.patients.find((item) => item.id === patientId);
  const edited = useMemo(
    () => Boolean(patient && inputs && JSON.stringify(patient.inputs) !== JSON.stringify(inputs)),
    [patient, inputs],
  );

  const choose = (id: string) => {
    const next = catalog?.patients.find((item) => item.id === id);
    if (!next) return;
    pendingReference.current = true;
    setPatientId(id);
    setInputs(next.inputs);
    setErrors({});
  };

  if (offline) {
    return (
      <>
        <PageHeader eyebrow="Patient explorer" title="The local API is not running">
          Start it with <code>make app</code>, then reload this page. The research findings stay available without it.
        </PageHeader>
      </>
    );
  }
  if (!catalog || !meta || !inputs || !patient) return <p className="py-24 text-center text-muted">Loading the explorer…</p>;

  const current = prediction?.[endpoint];
  const before = reference?.[endpoint];
  const data = site.endpoints[endpoint];
  const domain = current ? waterfallDomain([current.lr, current.xgboost, ...(before ? [before.lr, before.xgboost] : [])]) : ([0, 1] as [number, number]);
  const groups = [
    { title: "VitalDB patients", items: catalog.patients.filter((item) => item.source === "vitaldb") },
    { title: "Synthetic teaching profiles", items: catalog.patients.filter((item) => item.source === "synthetic") },
  ];

  return (
    <>
      <PageHeader eyebrow="Patient explorer" title="See why the models give a risk">
        Pick an example or edit the inputs. Both models respond with a calibrated risk and an exact SHAP breakdown, using
        the same background as the study.
      </PageHeader>

      <div className="grid items-start gap-5 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <aside className="rounded-lg border border-line p-4 lg:sticky lg:top-28 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto" aria-label="Patient inputs">
          <label htmlFor="patient" className="text-sm font-medium text-ink">Example patient</label>
          <select id="patient" value={patientId} onChange={(event) => choose(event.target.value)} className="mt-1 h-10 w-full rounded border border-line bg-white px-2 text-sm text-ink">
            {groups.map((group) => (
              <optgroup key={group.title} label={group.title}>
                {group.items.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </optgroup>
            ))}
          </select>
          <p className="m-0 mt-2 text-xs leading-relaxed text-muted">{patient.description}</p>
          {patient.source === "synthetic" && <p className="m-0 mt-1 text-xs font-medium text-warn">Synthetic profile, not a real patient.</p>}
          <div className="mt-3 flex min-h-9 flex-wrap items-center gap-2">
            <OutcomeReveal patient={patient} endpoint={endpoint} />
            {edited && (
              <button type="button" onClick={() => setInputs(patient.inputs)} className="min-h-9 rounded border border-line px-3 text-sm font-medium text-ink hover:bg-wash">
                Reset inputs
              </button>
            )}
          </div>
          <div className="mt-3 border-t border-line pt-2">
            <InputPanel inputs={inputs} meta={meta} errors={errors} onChange={setInputs} />
          </div>
        </aside>

        <div className="min-w-0 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <EndpointToggle value={endpoint} onChange={setEndpoint} />
            {edited && <span className="text-xs font-medium text-accent-dark">What-if mode: showing changes from the selected patient</span>}
          </div>

          {patient.source === "vitaldb" && <VitalDbCaveat endpoint={endpoint} />}
          {Object.keys(errors).length > 0 && <Callout title="Check the inputs.">{Object.values(errors).join(" ")} The last valid result is shown.</Callout>}

          {current ? (
            <>
              <section aria-labelledby="explanation" className="rounded-lg border border-line bg-wash p-4 sm:p-5">
                <h2 id="explanation" className="text-xl">In plain language</h2>
                <div className="mt-2 space-y-2 text-sm leading-relaxed" data-testid="plain-language">
                  {plainLanguage(current.lr, current.xgboost, inputs, data).map((sentence) => <p key={sentence} className="m-0">{sentence}</p>)}
                </div>
              </section>

              <div className="grid gap-5 xl:grid-cols-2">
                {MODEL_KEYS.map((model) => (
                  <section key={model} aria-label={site.labels.models[model]} className="min-w-0 rounded-lg border border-line p-4 sm:p-5">
                    <h2 className="text-lg">{site.labels.models[model]}</h2>
                    <div className="mt-2">
                      <RiskGauge prediction={current[model]} reference={edited ? before?.[model] : undefined} baseRate={data.base_rate.rate} />
                    </div>
                    <h3 className="mt-5 font-sans text-sm font-semibold">SHAP waterfall (raw log-odds)</h3>
                    <div className="mt-1">
                      <Waterfall prediction={current[model]} reference={before?.[model]} inputs={inputs} domain={domain} />
                    </div>
                  </section>
                ))}
              </div>

              <section aria-labelledby="drivers" className="rounded-lg border border-line p-4 sm:p-5">
                <h2 id="drivers" className="text-lg">This patient's drivers against the global ranking</h2>
                <p className="m-0 mt-1 text-sm leading-relaxed">
                  Unstable means the concept moved in and out of the global top five when the model was refitted, so a large contribution here deserves extra caution.
                </p>
                <div className="mt-3 grid gap-5 lg:grid-cols-2">
                  {MODEL_KEYS.map((model) => <DriverTable key={model} endpoint={data} model={model} prediction={current[model]} />)}
                </div>
              </section>

              <p className="text-xs leading-relaxed text-muted">{prediction?.scale} {patient.source === "vitaldb" ? `${catalog.notice} ${catalog.attribution}` : ""}</p>
            </>
          ) : (
            <p className="py-16 text-center text-muted">Calculating…</p>
          )}
        </div>
      </div>
    </>
  );
}
