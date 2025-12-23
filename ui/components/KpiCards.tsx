export default function KpiCards({ kpis }: { kpis: Record<string, any> | null | undefined }) {
  if (!kpis) return null;

  const fmtGBP = (v: any) =>
    typeof v === "number" ? `£${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : String(v);

  const items = [
    { label: "Period", value: kpis.period_latest },
    { label: "Left latest", value: fmtGBP(kpis.left_latest_gbp) },
    { label: "Right latest", value: fmtGBP(kpis.right_latest_gbp) },
    { label: "Total latest", value: fmtGBP(kpis.total_latest_gbp) },
    { label: "Left share", value: typeof kpis.left_share_latest === "number" ? `${(kpis.left_share_latest * 100).toFixed(1)}%` : kpis.left_share_latest },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {items.map((it) => (
        <div key={it.label} className="rounded-2xl border p-3 shadow-sm bg-white">
          <div className="text-xs text-gray-500">{it.label}</div>
          <div className="text-base font-semibold">{it.value ?? "-"}</div>
        </div>
      ))}
    </div>
  );
}