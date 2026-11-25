import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ENDPOINT_KEYS, type EndpointKey } from "../lib/types";
import { useSite } from "../lib/site";

export function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-line bg-white p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          onClick={() => onChange(option.value)}
          className={`min-h-9 rounded px-3 text-sm font-medium transition-colors ${
            option.value === value ? "bg-accent text-white" : "text-body hover:bg-wash"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function EndpointToggle({ value, onChange }: { value: EndpointKey; onChange: (value: EndpointKey) => void }) {
  const site = useSite();
  return (
    <Segmented
      label="Endpoint"
      value={value}
      onChange={onChange}
      options={ENDPOINT_KEYS.map((key) => ({ value: key, label: site.endpoints[key].label }))}
    />
  );
}

export function ModelKeyLegend({ markers = false }: { markers?: boolean }) {
  const site = useSite();
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
      <span className="inline-flex items-center gap-2">
        {markers ? (
          <svg width="12" height="12" aria-hidden="true">
            <circle cx="6" cy="6" r="4.5" fill="#ffffff" stroke="var(--color-neutral-series)" strokeWidth="2" />
          </svg>
        ) : (
          <svg width="24" height="8" aria-hidden="true">
            <line x1="0" x2="24" y1="4" y2="4" stroke="var(--color-neutral-series)" strokeWidth="2" strokeDasharray="5 3" />
          </svg>
        )}
        {site.labels.models.lr}
      </span>
      <span className="inline-flex items-center gap-2">
        {markers ? (
          <svg width="12" height="12" aria-hidden="true">
            <circle cx="6" cy="6" r="5" fill="var(--color-accent)" />
          </svg>
        ) : (
          <svg width="24" height="8" aria-hidden="true">
            <line x1="0" x2="24" y1="4" y2="4" stroke="var(--color-accent)" strokeWidth="2" />
          </svg>
        )}
        {site.labels.models.xgboost}
      </span>
    </div>
  );
}

export function Figure({
  id,
  title,
  takeaway,
  children,
  table,
  legend = true,
  markers = false,
}: {
  id?: string;
  title: string;
  takeaway?: string;
  children: ReactNode;
  table?: { columns: string[]; rows: (string | number)[][] };
  legend?: boolean;
  markers?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const tableId = useId();
  return (
    <figure id={id} className="m-0 min-w-0 rounded-lg border border-line bg-white p-4 sm:p-5">
      <h3 className="text-lg">{title}</h3>
      {takeaway && <p className="mt-1.5 text-sm leading-relaxed text-body">{takeaway}</p>}
      {legend && (
        <div className="mt-3">
          <ModelKeyLegend markers={markers} />
        </div>
      )}
      <div className="mt-3 min-w-0">{children}</div>
      {table && (
        <div className="mt-2">
          <button
            type="button"
            aria-expanded={open}
            aria-controls={tableId}
            onClick={() => setOpen(!open)}
            className="min-h-8 text-xs font-medium text-accent hover:underline"
          >
            {open ? "Hide data table" : "Show data table"}
          </button>
          {open && (
            <div id={tableId} className="mt-2 max-h-72 overflow-auto border-t border-line">
              <table className="numeric w-full text-left text-xs">
                <thead className="sticky top-0 bg-white text-muted">
                  <tr>
                    {table.columns.map((column) => (
                      <th key={column} scope="col" className="py-1.5 pr-3 font-medium">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, index) => (
                    <tr key={index} className="border-t border-line">
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className="py-1 pr-3">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </figure>
  );
}

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 text-2xl font-semibold text-ink">{value}</div>
      {note && <div className="mt-0.5 text-xs text-muted">{note}</div>}
    </div>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="max-w-3xl pb-8 pt-10 sm:pt-14">
      <p className="text-sm font-medium text-accent">{eyebrow}</p>
      <h1 className="mt-2 text-3xl leading-tight sm:text-4xl">{title}</h1>
      {children && <div className="mt-4 text-base leading-relaxed text-body">{children}</div>}
    </header>
  );
}

export function Callout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <aside className="rounded-md border border-warn/30 bg-warn-soft px-4 py-3 text-sm leading-relaxed text-ink">
      <strong className="font-semibold">{title}</strong> {children}
    </aside>
  );
}

export function useAnimatedNumber(target: number, duration = 420): number {
  const [value, setValue] = useState(target);
  const current = useRef(target);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      current.current = target;
      setValue(target);
      return;
    }
    const from = current.current;
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      current.current = from + (target - from) * eased;
      setValue(current.current);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return value;
}
