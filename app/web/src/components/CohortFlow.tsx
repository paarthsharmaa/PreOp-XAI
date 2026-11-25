import { useState } from "react";
import { count } from "../lib/format";
import { useSite } from "../lib/site";
import type { FlowStep } from "../lib/types";
import { Segmented } from "./ui";

type Source = "mover" | "vitaldb";

function detail(step: FlowStep, source: string): string {
  if (step.kind === "out") return `${count(step.n)} records left the ${source} cohort at this step: ${step.label.toLowerCase()}.`;
  if (step.kind === "final") return `${count(step.n)} patients were modelled from ${source}.`;
  if (step.kind === "start") return `${source} starts with ${count(step.n)} records.`;
  return `${count(step.n)} remain after the steps above: ${step.label.toLowerCase()}.`;
}

export function CohortFlow() {
  const site = useSite();
  const [source, setSource] = useState<Source>("mover");
  const [active, setActive] = useState<number | null>(null);
  const steps = site.cohort[source];
  const name = site.sources[source].name;
  const start = steps[0].n as number;
  const shown = active === null ? steps.length - 1 : active;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Cohort"
          value={source}
          onChange={(value) => {
            setSource(value);
            setActive(null);
          }}
          options={[
            { value: "mover", label: "MOVER (development)" },
            { value: "vitaldb", label: "VitalDB (external)" },
          ]}
        />
      </div>
      <p aria-live="polite" className="mt-3 min-h-10 text-sm text-body">
        {detail(steps[shown], name)}
      </p>
      <ol className="m-0 mt-2 list-none space-y-0.5 p-0">
        {steps.map((step, index) => {
          const isOut = step.kind === "out";
          const width = typeof step.n === "number" ? Math.max((step.n / start) * 100, 0.4) : 0.4;
          return (
            <li key={`${source}-${step.label}`}>
              <button
                type="button"
                onMouseEnter={() => setActive(index)}
                onFocus={() => setActive(index)}
                onClick={() => setActive(index)}
                aria-pressed={shown === index}
                className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 rounded px-2 py-1 text-left transition-colors sm:grid-cols-[minmax(0,18rem)_minmax(0,1fr)_5rem] ${
                  shown === index ? "bg-accent-soft" : "hover:bg-wash"
                }`}
              >
                <span className={`text-sm ${isOut ? "pl-3 text-muted" : "font-medium text-ink"}`}>
                  {step.label}
                </span>
                <span className="col-span-2 row-start-2 mt-1 block h-2 sm:col-span-1 sm:row-start-auto sm:mt-0" aria-hidden="true">
                  <span
                    className={`block h-2 rounded-r ${isOut ? "bg-neutral-series/60" : "bg-accent"}`}
                    style={{ width: `${width}%` }}
                  />
                </span>
                <span className={`numeric text-right text-sm ${isOut ? "text-muted" : "font-semibold text-ink"}`}>
                  {isOut ? "−" : ""}
                  {count(step.n)}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
