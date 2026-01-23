"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

type Point = { period: string; value: number };
type Series = { name: string; data: Point[] };

const COLORS = [
  "#2563eb", // blue
  "#dc2626", // red
  "#16a34a", // green
  "#7c3aed", // purple
  "#ea580c", // orange
];


function normalizePeriod(raw: string): number | null {
  if (!raw) return null;

  // common formats we see:
  // 1) 2025-02-01T00:00:00Z
  // 2) 2025-02-01 00:00:00+00:00
  // 3) 2025-02-01T00:00:00+00:00

  let s = raw.trim();

  // convert " " -> "T" for ISO-ish strings
  if (s.includes(" ") && !s.includes("T")) s = s.replace(" ", "T");

  // normalize UTC offset form to Z when possible (most compatible)
  s = s.replace(/\+00:00$/, "Z");

  const ms = Date.parse(s);
  if (!Number.isFinite(ms)) return null;

  return ms;
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



export default function TimeseriesChart({ series }: { series: Series[] | null | undefined }) {
  if (!series || series.length === 0) return null;

  const data = mergeSeries(series);

  return (
    <div className="rounded-2xl border p-4 bg-white shadow-sm">
      <div className="text-sm font-semibold mb-2">Trend</div>

      {/* IMPORTANT: explicit pixel height on the container */}
      <div className="w-full" style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis
            dataKey="ts"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(v) =>
              new Date(v).toISOString().slice(0, 7) // YYYY-MM
            }
          />
          <YAxis />
          <Tooltip
            labelFormatter={(v) =>
              new Date(Number(v)).toISOString().slice(0, 10)
            }
            formatter={(v: number) =>
              v.toLocaleString("en-GB", {
                style: "currency",
                currency: "GBP",
                maximumFractionDigits: 0,
              })
            }
          />
          <Legend />

          {series.map((s, i) => (
            <Line
              key={s.name}
              dataKey={s.name}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={3}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

