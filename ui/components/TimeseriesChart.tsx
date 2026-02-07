"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type Point = { period: string; value: number };
export type Series = { name: string; data: Point[] };

function normalizePeriod(raw: string): number | null {
  if (!raw) return null;
  let s = String(raw).trim();
  if (s.includes(" ") && !s.includes("T")) s = s.replace(" ", "T");
  s = s.replace(/\+00:00$/, "Z");
  const ms = Date.parse(s);
  return Number.isFinite(ms) ? ms : null;
}

function fmtYAxis(v: any, unit?: "GBP" | "PERCENT") {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return String(v);

  if (unit === "PERCENT") return `${(n * 100).toFixed(0)}%`;

  // GBP (compact)
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return `£${(n / 1_000_000_000).toFixed(1)}b`;
  if (abs >= 1_000_000) return `£${(n / 1_000_000).toFixed(1)}m`;
  if (abs >= 1_000) return `£${(n / 1_000).toFixed(0)}k`;
  return `£${n.toFixed(0)}`;
}
function mergeSeries(series: Series[]) {
  const map = new Map<number, any>();

  for (const s of series) {
    for (const p of s.data || []) {
      const ts = normalizePeriod(String(p.period));
      if (ts === null) continue;

      const n = typeof p.value === "number" ? p.value : Number(p.value);
      if (!Number.isFinite(n)) continue;

      const row = map.get(ts) || { ts };
      row[s.name] = n;
      map.set(ts, row);
    }
  }

  return Array.from(map.values()).sort((a, b) => a.ts - b.ts);
}

function fmtMonth(ts: number) {
  return new Date(ts).toISOString().slice(0, 7);
}

function fmtDay(ts: number) {
  return new Date(ts).toISOString().slice(0, 10);
}

function fmtGBP(v: any) {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  });
}

function fmtPercentFraction(v: any) {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return String(v);
  return `${(n * 100).toFixed(1)}%`;
}
export default function TimeseriesChart({
  series,
  unit = "GBP",
  title = "Trend",
}: {
  series: Series[] | null | undefined;
  unit?: "GBP" | "PERCENT";
  title?: string;
}) {
  if (!series || series.length === 0) return null;

  const data = mergeSeries(series);

  return (
    <div className="rounded-2xl border p-4 bg-white shadow-sm min-w-0">
      <div className="text-sm font-semibold mb-2">{title}</div>

      <div className="w-full" style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="ts"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={fmtMonth}
            />
            <YAxis tickFormatter={(v) => fmtYAxis(v, unit)} />

            <Tooltip
              labelFormatter={(v) => fmtDay(Number(v))}
              formatter={(v: any) =>
                unit === "PERCENT"
                  ? `${(Number(v) * 100).toFixed(1)}%`
                  : fmtGBP(v)
              }
            />

            <Legend />
            {series.map((s) => (
              <Line key={s.name} dataKey={s.name} strokeWidth={3} dot={false} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}