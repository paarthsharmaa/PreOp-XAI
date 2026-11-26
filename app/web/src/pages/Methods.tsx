import { PageHeader, Stat } from "../components/ui";
import { count, scientific } from "../lib/format";
import { useSite } from "../lib/site";

const STAGES = [
  { title: "Cohort and labels", text: "One index operation per patient. Unknown outcomes are excluded, never treated as survival." },
  { title: "Train", text: "Logistic regression and XGBoost, tuned by stratified cross-validation on training data." },
  { title: "Recalibrate", text: "Logistic recalibration and a sensitivity-based alert threshold, fixed on validation data." },
  { title: "Evaluate", text: "Held-out test metrics with paired bootstrap intervals." },
  { title: "Explain", text: "Exact interventional SHAP on log-odds, plus stability refits." },
  { title: "Validate externally", text: "Frozen models and recalibration applied to VitalDB." },
];

const COMMANDS = `uv sync                        # locked environment
uv run preopxai prepare        # analysis tables
uv run preopxai protocol       # full study
uv run preopxai export-models  # save the models
uv run preopxai app build      # site data and frontend
uv run preopxai app serve      # app and API on :8000`;

export function Methods() {
  const { methods, endpoints } = useSite();
  const { selftest, determinism, split_check: split, environment } = methods;
  return (
    <>
      <PageHeader eyebrow="Methods and reproducibility" title="How the results were produced">
        The study runs from a locked environment with fixed seeds. The checks below are read from the committed
        verification records.
      </PageHeader>

      <section aria-labelledby="pipeline">
        <h2 id="pipeline" className="text-2xl">Pipeline</h2>
        <ol className="m-0 mt-4 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {STAGES.map((stage, index) => (
            <li key={stage.title} className="relative rounded-lg border border-line p-4">
              <span className="numeric text-xs font-semibold text-accent">{index + 1}</span>
              <h3 className="mt-1 text-base">{stage.title}</h3>
              <p className="m-0 mt-1 text-sm leading-relaxed">{stage.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="checks" className="mt-10">
        <h2 id="checks" className="text-2xl">Reproducibility checks</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-line p-4">
            <Stat label="Determinism check" value={determinism.identical ? "Identical" : "Differs"} note={`${count(determinism.differences)} differing values between two same-machine runs`} />
          </div>
          <div className="rounded-lg border border-line p-4">
            <Stat label="SHAP self-test" value={selftest.passed ? "Passed" : "Failed"} note={`Largest error against brute force: trees ${scientific(selftest.tree_max_error)}, linear ${scientific(selftest.linear_max_error)}`} />
          </div>
          <div className="rounded-lg border border-line p-4">
            <Stat label="Split check, ICU test events" value={count(split.primary_events)} note={`Across ${count(split.seeds)} alternative seeds: ${count(split.low)} to ${count(split.high)}, median ${count(split.median)}`} />
          </div>
        </div>
      </section>

      <section aria-labelledby="environment" className="mt-10 grid gap-6 lg:grid-cols-2">
        <div>
          <h2 id="environment" className="text-2xl">Locked environment</h2>
          <table className="numeric mt-4 w-full text-left text-sm">
            <tbody>
              <tr className="border-t border-line"><th scope="row" className="py-2 font-medium text-ink">Python</th><td>{environment.python}</td></tr>
              {Object.entries(environment.packages).map(([name, version]) => (
                <tr key={name} className="border-t border-line"><th scope="row" className="py-2 font-medium text-ink">{name}</th><td>{version}</td></tr>
              ))}
              <tr className="border-y border-line"><th scope="row" className="py-2 pr-3 font-medium text-ink">Recorded on</th><td className="break-words">{environment.platform}</td></tr>
            </tbody>
          </table>
        </div>
        <div className="min-w-0">
          <h2 className="text-2xl">How to run it</h2>
          <pre className="mt-4 overflow-x-auto rounded-lg bg-wash p-4 text-xs leading-relaxed text-ink"><code>{COMMANDS}</code></pre>
          <p className="mt-3 text-sm leading-relaxed">
            MOVER requires an approved data usage agreement. Model artifacts and patient-level data stay on your machine. SHAP uses {count(endpoints.mortality.shap.background_n)} background rows, which are never sent to the browser.
          </p>
        </div>
      </section>
    </>
  );
}
