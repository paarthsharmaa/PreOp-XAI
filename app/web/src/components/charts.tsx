import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fixed, interval, signed } from "../lib/format";
import { useSite } from "../lib/site";
import { MODEL_KEYS, type Ci, type EndpointData, type ModelKey } from "../lib/types";

const COLORS: Record<ModelKey, string> = { lr: "#8e8e93", xgboost: "#0b6577" };
const DASH: Record<ModelKey, string | undefined> = { lr: "5 3", xgboost: undefined };
const GRID = "#eceef1";
const AXIS = { fontSize: 11, fill: "#5b6672" };
const TICKS = [0, 0.25, 0.5, 0.75, 1];

type Point = { x: number; y: number };

function TooltipBox({ children }: { children: ReactNode }) {
  return <div className="numeric rounded border border-line bg-white px-2.5 py-1.5 text-xs text-ink shadow-sm">{children}</div>;
}

function PointTooltip({ active, payload, xLabel, yLabel, digits = 3 }: {
  active?: boolean;
  payload?: { payload: Point & { name?: string } }[];
  xLabel: string;
  yLabel: string;
  digits?: number;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <TooltipBox>
      <div className="font-medium">{point.name}</div>
      <div>
        {xLabel}: {point.x.toFixed(digits)}
      </div>
      <div>
        {yLabel}: {point.y.toFixed(digits)}
      </div>
    </TooltipBox>
  );
}

export function CurveChart({
  series,
  xLabel,
  yLabel,
  diagonal = false,
  baseline,
  xScale = "linear",
  ticks = TICKS,
  markers = false,
  digits = 3,
}: {
  series: Record<ModelKey, Point[]>;
  xLabel: string;
  yLabel: string;
  diagonal?: boolean;
  baseline?: number;
  xScale?: "linear" | "sqrt";
  ticks?: number[];
  markers?: boolean;
  digits?: number;
}) {
  const site = useSite();
  const max = ticks[ticks.length - 1];
  const format = (value: number) => (max < 0.1 ? value.toFixed(3) : max < 1 ? value.toFixed(2) : String(value));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 12, bottom: 28, left: 4 }}>
          <CartesianGrid stroke={GRID} />
          <XAxis type="number" dataKey="x" domain={[0, max]} ticks={ticks} scale={xScale} tick={AXIS} tickFormatter={format}
            stroke={GRID} allowDataOverflow label={{ value: xLabel, position: "insideBottom", offset: -16, ...AXIS }} />
          <YAxis type="number" dataKey="y" domain={[0, max]} ticks={ticks} scale={xScale} tick={AXIS} tickFormatter={format}
            stroke={GRID} width={46} allowDataOverflow label={{ value: yLabel, angle: -90, position: "insideLeft", offset: 8, style: { textAnchor: "middle", ...AXIS } }} />
          {diagonal && <ReferenceLine segment={[{ x: 0, y: 0 }, { x: max, y: max }]} stroke="#c3c8ce" strokeWidth={1} />}
          {baseline !== undefined && <ReferenceLine y={baseline} stroke="#c3c8ce" strokeWidth={1} />}
          <Tooltip cursor={{ stroke: "#c3c8ce" }} content={<PointTooltip xLabel={xLabel} yLabel={yLabel} digits={digits} />} />
          {MODEL_KEYS.map((model) => (
            <Scatter
              key={model}
              name={site.labels.models[model]}
              data={series[model].map((point) => ({ ...point, name: site.labels.models[model] }))}
              fill={COLORS[model]}
              isAnimationActive={false}
              line={{ stroke: COLORS[model], strokeWidth: 2, strokeDasharray: DASH[model] }}
              lineType="joint"
              shape={(props: { cx?: number; cy?: number }) =>
                markers ? (
                  <circle cx={props.cx} cy={props.cy} r={4} fill={model === "lr" ? "#ffffff" : COLORS[model]} stroke={model === "lr" ? COLORS[model] : "#ffffff"} strokeWidth={2} />
                ) : (
                  <circle cx={props.cx} cy={props.cy} r={5} fill="transparent" />
                )
              }
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ImportanceBars({ endpoint, model }: { endpoint: EndpointData; model: ModelKey }) {
  const site = useSite();
  const shap = endpoint.shap.models[model];
  const max = Math.max(...Object.values(endpoint.shap.models).flatMap((item) => Object.values(item.concepts).map((c) => c.importance)));
  return (
    <div>
      <h4 className="m-0 text-sm font-semibold text-ink">{site.labels.models[model]}</h4>
      <ol className="m-0 mt-2 list-none space-y-1.5 p-0">
        {shap.order.map((concept) => {
          const value = shap.concepts[concept].importance;
          return (
            <li key={concept} className="grid grid-cols-[6.5rem_minmax(0,1fr)_3rem] items-center gap-2 text-xs" title={`${site.labels.concepts[concept]}: ${fixed(value)}`}>
              <span className="truncate text-body">{site.labels.concepts[concept]}</span>
              <span className="block h-3" aria-hidden="true">
                <span className="block h-3 rounded-r" style={{ width: `${Math.max((value / max) * 100, 0.5)}%`, background: COLORS[model] }} />
              </span>
              <span className="numeric text-right text-muted">{fixed(value)}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function StabilityStrip({ endpoint, model }: { endpoint: EndpointData; model: ModelKey }) {
  const site = useSite();
  const shap = endpoint.shap.models[model];
  const refits = endpoint.shap.refits;
  const max = Math.max(...shap.order.flatMap((concept) => shap.concepts[concept].refits));
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="m-0 text-sm font-semibold text-ink">{site.labels.models[model]}</h4>
        <span className="text-xs text-muted">refits in top five</span>
      </div>
      <ol className="m-0 mt-2 list-none space-y-1 p-0">
        {shap.order.map((concept) => {
          const item = shap.concepts[concept];
          const inTop = Math.round(item.top5_frequency * refits);
          const moved = item.top5_frequency > 0 && item.top5_frequency < 1;
          return (
            <li key={concept} className="grid grid-cols-[6.5rem_minmax(0,1fr)_3.5rem] items-center gap-2 text-xs">
              <span className="truncate text-body">{site.labels.concepts[concept]}</span>
              <span className="relative block h-4 border-b border-line" aria-hidden="true">
                {item.refits.map((value, index) => (
                  <span key={index} className="absolute top-1 h-2 w-2 -translate-x-1 rounded-full opacity-60" style={{ left: `${(value / max) * 100}%`, background: COLORS[model] }} />
                ))}
              </span>
              <span className={`numeric text-right ${moved ? "font-semibold text-warn" : "text-muted"}`}>
                {inTop} / {refits}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function RepeatBars({ endpoint }: { endpoint: EndpointData }) {
  const data = [...endpoint.repeats.points].sort((a, b) => a.difference - b.difference).map((point, index) => ({ ...point, rank: index + 1 }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barCategoryGap={1} margin={{ top: 8, right: 8, bottom: 22, left: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="rank" tick={false} stroke={GRID} label={{ value: "Splits, sorted by difference", position: "insideBottom", offset: -6, ...AXIS }} />
          <YAxis tick={AXIS} stroke={GRID} width={58} tickFormatter={(value: number) => signed(value, 3)} label={{ value: "XGBoost − LR AUROC", angle: -90, position: "insideLeft", offset: 2, style: { textAnchor: "middle", ...AXIS } }} />
          <ReferenceLine y={0} stroke="#16202a" strokeWidth={1} />
          <Tooltip
            cursor={{ fill: "#f6f7f8" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const point = payload[0].payload as (typeof data)[number];
              return (
                <TooltipBox>
                  <div className="font-medium">Split seed {point.seed}</div>
                  <div>LR {fixed(point.lr)}</div>
                  <div>XGBoost {fixed(point.xgboost)}</div>
                  <div>Difference {signed(point.difference, 4)}</div>
                </TooltipBox>
              );
            }}
          />
          <Bar dataKey="difference" isAnimationActive={false} maxBarSize={8}>
            {data.map((point) => (
              <Cell key={point.seed} fill={point.difference > 0 ? COLORS.xgboost : COLORS.lr} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Forest({ rows }: { rows: { label: string; model: ModelKey; ci: Ci }[] }) {
  const site = useSite();
  const low = Math.min(...rows.map((row) => row.ci.lo));
  const high = Math.max(...rows.map((row) => row.ci.hi));
  const pad = (high - low) * 0.06;
  const position = (value: number) => ((value - (low - pad)) / (high - low + 2 * pad)) * 100;
  return (
    <ul className="m-0 list-none space-y-1.5 p-0">
      {rows.map((row) => (
        <li key={`${row.label}-${row.model}`} className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)] items-center gap-3 text-xs sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)_8.5rem]">
          <span className="truncate text-body">
            {row.label} · {row.model === "lr" ? "LR" : "XGBoost"}
          </span>
          <span className="relative block h-5" role="img" aria-label={`${row.label}, ${site.labels.models[row.model]}: ${fixed(row.ci.v)}, ${site.labels.ci} ${interval(row.ci.lo, row.ci.hi)}`}>
            <span className="absolute inset-x-0 top-1/2 border-t border-line" />
            <span
              className="absolute top-1/2 -translate-y-1/2"
              style={{
                left: `${position(row.ci.lo)}%`,
                width: `${position(row.ci.hi) - position(row.ci.lo)}%`,
                borderTop: `2px ${row.model === "lr" ? "dashed" : "solid"} ${COLORS[row.model]}`,
              }}
            />
            <span
              className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2"
              style={{
                left: `${position(row.ci.v)}%`,
                borderColor: row.model === "lr" ? COLORS.lr : "#ffffff",
                background: row.model === "lr" ? "#ffffff" : COLORS.xgboost,
              }}
            />
          </span>
          <span className="numeric col-start-2 text-muted sm:col-start-auto sm:text-right">
            {fixed(row.ci.v)} ({interval(row.ci.lo, row.ci.hi)})
          </span>
        </li>
      ))}
    </ul>
  );
}
