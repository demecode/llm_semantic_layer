"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type Row = { label: string; value: number };

export default function RankingChart({ ranking }: { ranking?: Row[] | null }) {
  if (!ranking || ranking.length === 0) return null;

  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm min-w-0">
      <div className="text-sm font-semibold mb-2">Top-N Ranking</div>
      <div className="h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={ranking}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="value" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}