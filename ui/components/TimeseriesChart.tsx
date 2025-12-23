"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

type Point = { period: string; value: number };
type Series = { name: string; data: Point[] };

function mergeSeries(series: Series[]) {
  // Merge by period into chart-friendly rows: { period, "<seriesName>": value, ... }
  const map = new Map<string, any>();

  for (const s of series) {
    for (const p of s.data || []) {
      const row = map.get(p.period) || { period: p.period };
      row[s.name] = p.value;
      map.set(p.period, row);
    }
  }

  return Array.from(map.values()).sort((a, b) => (a.period > b.period ? 1 : -1));
}

export default function TimeseriesChart({ series }: { series: Series[] | null | undefined }) {
  if (!series || series.length === 0) return null;

  const data = mergeSeries(series);

  return (
    <div className="rounded-2xl border p-4 bg-white shadow-sm h-[360px]">
      <div className="text-sm font-semibold mb-2">Trend</div>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="period" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          {series.map((s) => (
            <Line key={s.name} type="monotone" dataKey={s.name} dot={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}