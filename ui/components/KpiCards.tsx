"use client";

function fmtGBPCompact(v: any) {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return v ?? "-";

  // compact: £12.3M etc.
  const abs = Math.abs(n);
  const suffix =
    abs >= 1e9 ? "B" : abs >= 1e6 ? "M" : abs >= 1e3 ? "K" : "";
  const div =
    abs >= 1e9 ? 1e9 : abs >= 1e6 ? 1e6 : abs >= 1e3 ? 1e3 : 1;

  const val = n / div;
  const digits = abs >= 1e6 ? 1 : 0;

  return `£${val.toFixed(digits)}${suffix}`;
}

function fmtPct(v: any) {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return v ?? "-";
  return `${n.toFixed(1)}%`;
}

export default function KpiCards({
  kpis,
}: {
  kpis: Record<string, any> | null | undefined;
}) {
  if (!kpis) return null;

  const items = [
    { label: "Period", value: kpis.period_latest ?? "-" },
    { label: "Left latest", value: fmtGBPCompact(kpis.left_latest_gbp) },
    { label: "Right latest", value: fmtGBPCompact(kpis.right_latest_gbp) },
    { label: "Total latest", value: fmtGBPCompact(kpis.total_latest_gbp) },
    {
      label: "Left share",
      value:
        typeof kpis.left_share_latest === "number"
          ? fmtPct(kpis.left_share_latest * 100)
          : (kpis.left_share_latest_pct ?? "-"),
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {items.map((it) => (
        <div key={it.label} className="rounded-2xl border p-3 shadow-sm bg-white">
          <div className="text-xs text-gray-500">{it.label}</div>
          <div className="text-base font-semibold">{it.value}</div>
        </div>
      ))}
    </div>
  );
}