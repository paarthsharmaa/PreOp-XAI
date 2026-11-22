import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CurveChart, Forest, ImportanceBars, RepeatBars, StabilityStrip } from "../components/charts";
import { EndpointToggle, Figure, PageHeader, Stat } from "../components/ui";
import { count, fixed, interval, signed } from "../lib/format";
import { useSite } from "../lib/site";
import { MODEL_KEYS, type EndpointKey, type ModelKey } from "../lib/types";

const SECTIONS = [
  { id: "discrimination", label: "Discrimination" },
  { id: "calibration", label: "Calibration" },
  { id: "shap", label: "Global SHAP" },
  { id: "stability", label: "Stability" },
  { id: "repeats", label: "Repeated splits" },
  { id: "lag0", label: "Lag-0" },
  { id: "external", label: "External validation" },
];

const zip = (x: number[], y: number[]) => x.map((value, index) => ({ x: value, y: y[index] }));

function niceTicks(max: number): number[] {
  const steps = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1];
  const step = steps.find((candidate) => max / candidate <= 4) ?? 1;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let index = 0; index * step <= top + 1e-9; index += 1) ticks.push(Number((index * step).toFixed(4)));
  return ticks;
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-44 pt-10">
      <h2 id={`${id}-title`} className="text-2xl">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function Findings() {
  const site = useSite();
  const [params] = useSearchParams();
  const [key, setKey] = useState<EndpointKey>("mortality");
  const endpoint = site.endpoints[key];
  const { test, external, takeaways } = endpoint;
  const ci = site.labels.ci;

  useEffect(() => {
    const section = params.get("section");
    if (section) document.getElementById(section)?.scrollIntoView();
  }, [params]);

  const calibrationTicks = useMemo(() => {
    const values = MODEL_KEYS.flatMap((model) => test.models[model].deciles.flatMap((d) => [d.predicted, d.observed]));
    return niceTicks(Math.max(...values));
  }, [test]);

  const externalTicks = useMemo(() => {
    const values = MODEL_KEYS.flatMap((model) => external.models[model].deciles.flatMap((d) => [d.predicted, d.observed]));
    return niceTicks(Math.max(...values));
  }, [external]);

  const series = (pick: (model: ModelKey) => { x: number; y: number }[]) => ({ lr: pick("lr"), xgboost: pick("xgboost") });
  const metricRows = (name: "auroc" | "ap" | "brier") =>
    MODEL_KEYS.map((model) => [
      site.labels.models[model],
      fixed(test.models[model][name].v),
      interval(test.models[model][name].lo, test.models[model][name].hi),
    ]);

  return (
    <>
      <PageHeader eyebrow="Findings" title="What the study found">
        Every number on this page is generated from the committed aggregate results. Intervals are {ci} from{" "}
        {count(test.bootstraps)} paired bootstrap resamples.
      </PageHeader>

      <div className="sticky top-[5.6rem] z-20 -mx-4 border-y border-line bg-white px-4 py-2">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <EndpointToggle value={key} onChange={setKey} />
          <nav aria-label="Findings sections" className="flex max-w-full gap-1 overflow-x-auto">
            {SECTIONS.map((section) => (
              <a key={section.id} href={`#/findings?section=${section.id}`} className="whitespace-nowrap rounded px-2 py-1.5 text-xs font-medium text-body no-underline hover:bg-wash">
                {section.label}
              </a>
            ))}
          </nav>
        </div>
      </div>

      <Section id="discrimination" title="Discrimination">
        <div className="mb-4 grid grid-cols-2 gap-5 lg:grid-cols-4">
          <Stat label="Test patients" value={count(test.n)} />
          <Stat label="Test events" value={count(test.events)} />
          <Stat label="LR AUROC" value={fixed(test.models.lr.auroc.v)} note={`${ci} ${interval(test.models.lr.auroc.lo, test.models.lr.auroc.hi)}`} />
          <Stat label="XGBoost AUROC" value={fixed(test.models.xgboost.auroc.v)} note={`${ci} ${interval(test.models.xgboost.auroc.lo, test.models.xgboost.auroc.hi)}`} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Figure title="ROC curve" takeaway={takeaways.roc} table={{ columns: ["Model", "AUROC", ci], rows: metricRows("auroc") }}>
            <CurveChart diagonal xLabel="False positive rate" yLabel="True positive rate" series={series((model) => zip(test.models[model].roc.fpr, test.models[model].roc.tpr))} />
          </Figure>
          <Figure title="Precision-recall curve" takeaway={takeaways.pr} table={{ columns: ["Model", "Average precision", ci], rows: metricRows("ap") }}>
            <CurveChart baseline={test.prevalence} xLabel="Recall" yLabel="Precision" series={series((model) => zip(test.models[model].pr.recall, test.models[model].pr.precision))} />
          </Figure>
        </div>
      </Section>

      <Section id="calibration" title="Calibration">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <Figure
            title="Calibration by risk decile (test set)"
            takeaway={takeaways.calibration}
            table={{
              columns: ["Decile", "LR predicted", "LR observed", "XGBoost predicted", "XGBoost observed"],
              rows: test.models.lr.deciles.map((row, index) => [
                index + 1,
                fixed(row.predicted, 4),
                fixed(row.observed, 4),
                fixed(test.models.xgboost.deciles[index]?.predicted ?? NaN, 4),
                fixed(test.models.xgboost.deciles[index]?.observed ?? NaN, 4),
              ]),
            }}
          >
            <CurveChart diagonal markers digits={4} xScale="sqrt" ticks={calibrationTicks} xLabel="Mean predicted risk (square-root scale)" yLabel="Observed rate" series={series((model) => test.models[model].deciles.map((d) => ({ x: d.predicted, y: d.observed })))} />
          </Figure>
          <Figure title="Calibration summary" legend={false}>
            <table className="numeric w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1.5 font-medium">Model</th>
                  <th scope="col" className="py-1.5 font-medium">Slope</th>
                  <th scope="col" className="py-1.5 font-medium">CITL</th>
                  <th scope="col" className="py-1.5 font-medium">Brier</th>
                </tr>
              </thead>
              <tbody>
                {MODEL_KEYS.map((model) => (
                  <tr key={model} className="border-t border-line">
                    <th scope="row" className="py-2 pr-2 font-medium text-ink">{model === "lr" ? "LR" : "XGBoost"}</th>
                    <td>{fixed(test.models[model].slope, 2)}</td>
                    <td>{signed(test.models[model].citl, 2)}</td>
                    <td>{fixed(test.models[model].brier.v, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs leading-relaxed text-muted">
              Slope and calibration-in-the-large (CITL) describe recalibrated probabilities on the held-out test set. Quote
              repeated-split calibration summaries to about two decimal places, because of the optimiser limitation
              described under Methods.
            </p>
          </Figure>
        </div>
      </Section>

      <Section id="shap" title="Global SHAP importance">
        <Figure title="Mean absolute SHAP by concept (raw log-odds)" takeaway={takeaways.shap} legend={false}
          table={{ columns: ["Concept", "LR", "XGBoost"], rows: endpoint.shap.models.lr.order.map((concept) => [site.labels.concepts[concept], fixed(endpoint.shap.models.lr.concepts[concept].importance), fixed(endpoint.shap.models.xgboost.concepts[concept].importance)]) }}>
          <div className="grid gap-6 md:grid-cols-2">
            {MODEL_KEYS.map((model) => <ImportanceBars key={model} endpoint={endpoint} model={model} />)}
          </div>
          <p className="mt-3 text-xs text-muted">
            Exact interventional SHAP over {count(endpoint.shap.explained_n)} validation patients, using a background of {count(endpoint.shap.background_n)} training rows. Each concept combines its value with its missingness indicator.
          </p>
        </Figure>
      </Section>

      <Section id="stability" title="Explanation stability across refits">
        <Figure title="Importance in each refit" takeaway={takeaways.stability} legend={false}
          table={{ columns: ["Model", "Mean Spearman", "Mean top-five Jaccard", "Successful refits"], rows: MODEL_KEYS.map((model) => [site.labels.models[model], fixed(endpoint.shap.models[model].spearman, 2), fixed(endpoint.shap.models[model].jaccard, 2), endpoint.shap.models[model].successful_refits]) }}>
          <div className="grid gap-6 md:grid-cols-2">
            {MODEL_KEYS.map((model) => <StabilityStrip key={model} endpoint={endpoint} model={model} />)}
          </div>
          <p className="mt-3 text-xs text-muted">Each dot is one refit. Counts in amber mark concepts that moved in and out of the top five.</p>
        </Figure>
      </Section>

      <Section id="repeats" title="Repeated splits">
        <Figure title="XGBoost minus LR AUROC in each split" takeaway={takeaways.repeats} legend={false}
          table={{ columns: ["Split seed", "LR", "XGBoost", "Difference"], rows: endpoint.repeats.points.map((point) => [point.seed, fixed(point.lr), fixed(point.xgboost), signed(point.difference, 4)]) }}>
          <div className="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
            <span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-sm bg-accent" />XGBoost higher</span>
            <span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-sm bg-neutral-series" />LR higher</span>
          </div>
          <RepeatBars endpoint={endpoint} />
        </Figure>
      </Section>

      <Section id="lag0" title="Lag-0 sensitivity">
        <Figure title="AUROC with labs up to anaesthesia start" takeaway={takeaways.lag0}>
          <Forest rows={MODEL_KEYS.flatMap((model) => [
            { label: "Primary window", model, ci: endpoint.lag0.models[model].primary },
            { label: "Lag-0 window", model, ci: endpoint.lag0.models[model].lag0 },
          ])} />
        </Figure>
      </Section>

      <Section id="external" title="VitalDB external validation">
        <div className="grid gap-4 lg:grid-cols-2">
          <Figure title="AUROC drop at VitalDB" takeaway={takeaways.external}>
            <Forest rows={MODEL_KEYS.flatMap((model) => [
              { label: "MOVER test", model, ci: test.models[model].auroc },
              { label: "VitalDB", model, ci: external.models[model].auroc },
            ])} />
            <table className="numeric mt-4 w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1.5 font-medium">Model</th>
                  <th scope="col" className="py-1.5 font-medium">AUROC drop</th>
                  <th scope="col" className="py-1.5 font-medium">VitalDB slope</th>
                  <th scope="col" className="py-1.5 font-medium">VitalDB CITL</th>
                </tr>
              </thead>
              <tbody>
                {MODEL_KEYS.map((model) => (
                  <tr key={model} className="border-t border-line">
                    <th scope="row" className="py-2 pr-2 font-medium text-ink">{model === "lr" ? "LR" : "XGBoost"}</th>
                    <td>{fixed(endpoint.transport[model].drop)}</td>
                    <td>{fixed(endpoint.transport[model].slope, 2)}</td>
                    <td>{signed(endpoint.transport[model].citl, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Figure>
          <Figure title="Calibration at VitalDB"
            takeaway={`Frozen MOVER models and recalibration were applied to ${count(external.n)} VitalDB patients with ${count(external.events)} events. Points away from the diagonal show miscalibration.`}
            table={{
              columns: ["Decile", "LR predicted", "LR observed", "XGBoost predicted", "XGBoost observed"],
              rows: external.models.lr.deciles.map((row, index) => [
                index + 1,
                fixed(row.predicted, 4),
                fixed(row.observed, 4),
                fixed(external.models.xgboost.deciles[index]?.predicted ?? NaN, 4),
                fixed(external.models.xgboost.deciles[index]?.observed ?? NaN, 4),
              ]),
            }}>
            <CurveChart diagonal markers digits={4} xScale="sqrt" ticks={externalTicks} xLabel="Mean predicted risk (square-root scale)" yLabel="Observed rate" series={series((model) => external.models[model].deciles.map((d) => ({ x: d.predicted, y: d.observed })))} />
          </Figure>
        </div>
      </Section>
    </>
  );
}
