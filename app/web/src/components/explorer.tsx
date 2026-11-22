import { byImpact, describeValue, driverRows, LABS } from "../lib/explain";
import { fixed, logit, ROMAN, risk, signed } from "../lib/format";
import { useSite } from "../lib/site";
import type { EndpointData, Meta, ModelKey, ModelPrediction, PatientInputs } from "../lib/types";
import { Segmented, useAnimatedNumber } from "./ui";

const GAUGE_MIN = logit(0.0005);
const GAUGE_MAX = logit(0.95);
const GAUGE_TICKS = [0.001, 0.01, 0.1, 0.5, 0.9];
const gaugePosition = (p: number) => {
  const clamped = Math.min(0.95, Math.max(0.0005, p));
  return ((logit(clamped) - GAUGE_MIN) / (GAUGE_MAX - GAUGE_MIN)) * 100;
};

export function RiskGauge({
  prediction,
  reference,
  baseRate,
}: {
  prediction: ModelPrediction;
  reference?: ModelPrediction;
  baseRate: number;
}) {
  const shown = useAnimatedNumber(prediction.calibrated_probability);
  const changed = reference && Math.abs(reference.calibrated_probability - prediction.calibrated_probability) > 1e-9;
  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="text-4xl font-semibold text-ink" data-testid="risk-value">{risk(shown)}</span>
        <span className={`text-sm font-medium ${prediction.above_threshold ? "text-warn" : "text-muted"}`}>
          {prediction.above_threshold ? "Above alert threshold" : "Below alert threshold"}
        </span>
      </div>
      {changed && (
        <p className="m-0 mt-0.5 text-xs text-muted">
          What-if change from {risk(reference.calibrated_probability)} to {risk(prediction.calibrated_probability)}
        </p>
      )}
      <div className="relative mt-7 h-2 rounded-full bg-accent-soft" role="img" aria-label={`Calibrated risk ${risk(prediction.calibrated_probability)}, threshold ${risk(prediction.threshold)}, cohort rate ${risk(baseRate)}`}>
        <span className="absolute -top-3.5 h-2.5 w-2.5 -translate-x-1/2 rotate-45 border-2 border-muted bg-white" style={{ left: `${gaugePosition(baseRate)}%` }} />
        {changed && <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-white" style={{ left: `${gaugePosition(reference.calibrated_probability)}%` }} />}
        <span className="animate-bar absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-accent shadow" style={{ left: `${gaugePosition(prediction.calibrated_probability)}%` }} />
        <span className="absolute -top-1.5 z-10 h-5 w-0.5 -translate-x-1/2 bg-ink" style={{ left: `${gaugePosition(prediction.threshold)}%` }} />
      </div>
      <div className="numeric relative mt-1.5 h-4 text-[10px] text-muted" aria-hidden="true">
        {GAUGE_TICKS.map((tick) => (
          <span key={tick} className="absolute -translate-x-1/2" style={{ left: `${gaugePosition(tick)}%` }}>
            {tick < 0.01 ? `${tick * 100}%` : `${Math.round(tick * 100)}%`}
          </span>
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-0.5 bg-ink" />Threshold {risk(prediction.threshold)}</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rotate-45 border-2 border-muted" />Cohort rate {risk(baseRate)}</span>
      </div>
    </div>
  );
}

export function Waterfall({
  prediction,
  reference,
  inputs,
  domain,
}: {
  prediction: ModelPrediction;
  reference?: ModelPrediction;
  inputs: PatientInputs;
  domain: [number, number];
}) {
  const order = byImpact((reference ?? prediction).shap).map((row) => row.concept);
  const contributions = new Map(prediction.shap.map((row) => [row.concept, row]));
  const referenceRows = new Map(reference?.shap.map((row) => [row.concept, row]));
  const scale = (value: number) => ((value - domain[0]) / (domain[1] - domain[0])) * 100;
  let running = prediction.base_value;
  return (
    <div className="text-xs">
      <div className="grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)_3.25rem] items-center gap-2 py-1">
        <span className="truncate font-medium text-ink">Base value</span>
        <span className="relative block h-4"><span className="animate-bar absolute top-0 h-4 w-0.5 bg-ink" style={{ left: `${scale(prediction.base_value)}%` }} /></span>
        <span className="numeric text-right text-ink">{fixed(prediction.base_value, 2)}</span>
      </div>
      {order.map((concept) => {
        const row = contributions.get(concept)!;
        const start = running;
        running += row.contribution;
        const left = Math.min(scale(start), scale(running));
        const width = Math.abs(scale(running) - scale(start));
        const before = referenceRows.get(concept);
        const moved = before && Math.abs(before.contribution - row.contribution) > 1e-9;
        return (
          <div key={concept} className={`grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)_3.25rem] items-center gap-2 rounded py-0.5 ${moved ? "bg-accent-soft/60" : ""}`} title={`${row.label}: value ${signed(row.value_part)}, missingness ${signed(row.missingness_part)}`}>
            <span className="min-w-0 truncate text-body">
              {row.label} <span className="text-muted">{concept === "asa" ? ROMAN[inputs.asa] : concept === "sex" ? inputs.sex : describeValue(concept, inputs)}</span>
            </span>
            <span className="relative block h-3.5">
              <span className="animate-bar absolute top-0 h-3.5 rounded-sm" style={{ left: `${left}%`, width: `${Math.max(width, 0.4)}%`, background: row.contribution >= 0 ? "var(--color-accent)" : "var(--color-neutral-series)" }} />
            </span>
            <span className="numeric text-right text-body">{signed(row.contribution, 2)}</span>
          </div>
        );
      })}
      <div className="mt-1 grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)_3.25rem] items-center gap-2 border-t border-line py-1">
        <span className="truncate font-medium text-ink">Log-odds</span>
        <span className="relative block h-4"><span className="animate-bar absolute top-0 h-4 w-0.5 bg-ink" style={{ left: `${scale(prediction.log_odds)}%` }} /></span>
        <span className="numeric text-right font-medium text-ink">{fixed(prediction.log_odds, 2)}</span>
      </div>
      <p className="numeric m-0 mt-1 leading-relaxed text-muted">
        Recalibrated: {fixed(prediction.recalibration_intercept, 3)} + {fixed(prediction.recalibration_slope, 3)} × log-odds = {fixed(prediction.calibrated_log_odds, 2)}, so risk is {risk(prediction.calibrated_probability)}.
      </p>
    </div>
  );
}

const STATUS = {
  stable: "Stable",
  unstable: "Unstable",
  outside: "Outside global top five",
};

export function DriverTable({ endpoint, model, prediction }: { endpoint: EndpointData; model: ModelKey; prediction: ModelPrediction }) {
  const site = useSite();
  const rows = driverRows(site, endpoint, model, prediction);
  return (
    <table className="numeric w-full text-left text-xs">
      <caption className="pb-1 text-left text-sm font-semibold text-ink">{site.labels.models[model]}</caption>
      <thead className="text-muted">
        <tr>
          <th scope="col" className="py-1 font-medium">Top driver</th>
          <th scope="col" className="py-1 font-medium">Global rank</th>
          <th scope="col" className="py-1 font-medium">Across refits</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.concept} className="border-t border-line">
            <th scope="row" className="py-1.5 pr-2 font-medium text-ink">{row.label}</th>
            <td className="pr-2">{row.globalRank}</td>
            <td>
              <span className={row.status === "unstable" ? "font-semibold text-warn" : "text-muted"}>{STATUS[row.status]}</span>
              <span className="text-muted"> · {row.refitsInTop}/{row.refits} in top five</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const STEPS: Record<string, number> = { age: 1, hemoglobin: 0.1, platelets: 1, creatinine: 0.1, bun: 1, sodium: 1, potassium: 0.1, glucose: 1 };

function NumberRow({
  name,
  value,
  meta,
  error,
  onChange,
  allowMissing,
}: {
  name: string;
  value: number | null;
  meta: Meta;
  error?: string;
  onChange: (value: number | null) => void;
  allowMissing: boolean;
}) {
  const site = useSite();
  const range = meta.ranges[name];
  const typical = site.cohort.typical[name];
  const spread = typical ? typical.q3 - typical.q1 : 0;
  const low = typical ? Math.max(range.min, typical.q1 - 3 * spread) : range.min;
  const high = typical ? Math.min(range.max, typical.q3 + 3 * spread) : range.max;
  const missing = value === null;
  const fallback = typical?.median ?? low;
  const inputId = `input-${name}`;
  return (
    <div className="py-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={inputId} className="text-sm font-medium text-ink">
          {meta.labels[name]} <span className="text-xs font-normal text-muted">{meta.units[name]}</span>
        </label>
        <div className="flex items-center gap-2">
          {allowMissing && (
            <label className="inline-flex min-h-8 items-center gap-1 text-xs text-muted">
              <input type="checkbox" aria-label={`${meta.labels[name]} missing`} checked={missing} onChange={(event) => onChange(event.target.checked ? null : fallback)} />
              Missing
            </label>
          )}
          <input
            id={inputId}
            type="number"
            inputMode="decimal"
            disabled={missing}
            value={missing ? "" : value}
            min={range.min}
            max={range.max}
            step={STEPS[name]}
            aria-invalid={Boolean(error)}
            onChange={(event) => {
              if (event.target.value !== "") onChange(Number(event.target.value));
            }}
            className={`numeric h-8 w-20 rounded border px-2 text-right text-sm text-ink disabled:bg-wash ${error ? "border-warn" : "border-line"}`}
          />
        </div>
      </div>
      <input
        type="range"
        aria-label={`${meta.labels[name]} slider`}
        disabled={missing}
        min={low}
        max={high}
        step={STEPS[name]}
        value={missing ? fallback : Math.min(high, Math.max(low, value))}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 block w-full disabled:opacity-40"
      />
      {error && <p role="alert" className="m-0 mt-0.5 text-xs text-warn">{error}</p>}
    </div>
  );
}

export function InputPanel({
  inputs,
  meta,
  errors,
  onChange,
}: {
  inputs: PatientInputs;
  meta: Meta;
  errors: Record<string, string>;
  onChange: (next: PatientInputs) => void;
}) {
  return (
    <div>
      <NumberRow name="age" value={inputs.age} meta={meta} error={errors.age} allowMissing={false} onChange={(value) => onChange({ ...inputs, age: value ?? inputs.age })} />
      <div className="flex flex-wrap items-center justify-between gap-2 py-1.5">
        <span className="text-sm font-medium text-ink">{meta.labels.sex}</span>
        <Segmented label="Sex" value={inputs.sex} onChange={(sex) => onChange({ ...inputs, sex })} options={[{ value: "F", label: "Female" }, { value: "M", label: "Male" }]} />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 py-1.5">
        <span className="text-sm font-medium text-ink">{meta.labels.asa}</span>
        <Segmented label="ASA class" value={inputs.asa} onChange={(asa) => onChange({ ...inputs, asa })} options={ROMAN.slice(1).map((label, index) => ({ value: index + 1, label }))} />
      </div>
      <div className="mt-1 divide-y divide-line border-t border-line">
        {LABS.map((lab) => (
          <NumberRow key={lab} name={lab} value={inputs[lab]} meta={meta} error={errors[lab]} allowMissing onChange={(value) => onChange({ ...inputs, [lab]: value })} />
        ))}
      </div>
    </div>
  );
}
