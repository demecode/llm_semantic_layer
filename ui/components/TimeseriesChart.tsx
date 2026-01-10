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

type Point = { period: string; value: number | string };
type Series = { name: string; data: Point[] };

function parseToMs(period: string) {
  // Normalize "2025-01-01 00:00:00+00:00" -> "2025-01-01T00:00:00+00:00"
  const s = String(period).trim().replace(" ", "T");
  const ms = Date.parse(s);
  return Number.isFinite(ms) ? ms : null;
}

function fmtMonth(ms: number) {
  // "2025-02"
  return new Date(ms).toISOString().slice(0, 7);
}

function mergeSeries(series: Series[]) {
  const map = new Map<number, any>();

  for (const s of series) {
    for (const p of s.data || []) {
      const ms = parseToMs(p.period);
      if (ms === null) continue;

      const n = typeof p.value === "number" ? p.value : Number(p.value);
      if (!Number.isFinite(n)) continue;

      const key = ms; // canonical X key
      const row = map.get(key) || { t: key, label: fmtMonth(key) };
      row[s.name.trim()] = n;
      map.set(key, row);
    }
  }

  return Array.from(map.values()).sort((a, b) => a.t - b.t);
}

export default function TimeseriesChart({
  series,
}: {
  series: Series[] | null | undefined;
}) {
  if (!series || series.length === 0) return null;

  const data = mergeSeries(series);

  return (
    <div className="rounded-2xl border p-4 bg-white shadow-sm h-[360px]">
      <div className="text-sm font-semibold mb-2">Trend</div>

      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="t" type="number" scale="time" tick={{ fontSize: 12 }}
                tickFormatter={(ms) => fmtMonth(Number(ms))} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            labelFormatter={(ms) => fmtMonth(Number(ms))}
            formatter={(v: any) => {
              const n = typeof v === "number" ? v : Number(v);
              if (!Number.isFinite(n)) return v;
              return n.toLocaleString("en-GB", {
                style: "currency",
                currency: "GBP",
                maximumFractionDigits: 0,
              });
            }}
          />
          <Legend />

          {series.map((s, i) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name.trim()}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={3}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

