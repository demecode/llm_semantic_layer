"use client";

import { useEffect, useMemo, useState } from "react";
import type { ChatResponse, MetricsResponse, SemanticModelsResponse } from "@/lib/type";
import { postChat, getMetrics, getSemanticModels, runPack } from "@/lib/client";
import KpiCards from "@/components/KpiCards";
import TimeseriesChart from "@/components/TimeseriesChart";
import DebugDrawer from "@/components/DebugDrawer";
import RankingChart from "@/components/RankingChart";

const EXAMPLE_QUESTIONS = [
  "Show total spend by month",
  "Show Digital Solutions spend by month",
  "Show Digital Solutions spend vs the rest of the company by month",
  "Show Digital Solutions share of total spend by month",
  "Show Digital Solutions spend vs the rest of the company for the last 2 years",
  "Show total spend for the last 6 months",
];

type LoadingMode = null | "ask" | "pack:top_n" | "pack:department_vs_company";

export default function Page() {
  const [question, setQuestion] = useState("");
  const [loadingMode, setLoadingMode] = useState<LoadingMode>(null);
  const loading = loadingMode !== null;

  const [resp, setResp] = useState<ChatResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [semanticModels, setSemanticModels] = useState<SemanticModelsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Fetch sidebar data once
  useEffect(() => {
    setErr(null);
    Promise.all([getMetrics(), getSemanticModels()])
      .then(([m, sm]) => {
        setMetrics(m);
        setSemanticModels(sm);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  const statusText = useMemo(() => {
    if (!loadingMode) return null;
    if (loadingMode === "ask") return "Routing question → governed metrics…";
    if (loadingMode === "pack:top_n") return "Running Top-N pack…";
    if (loadingMode === "pack:department_vs_company") return "Running Department vs Company pack…";
    return "Running…";
  }, [loadingMode]);

  async function onAsk() {
    setErr(null);
    setLoadingMode("ask");
    try {
      const r = await postChat(question);
      setResp(r);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setLoadingMode(null);
    }
  }

  async function onRunPackDepartmentVsCompany() {
    setErr(null);
    setLoadingMode("pack:department_vs_company");
    try {
      const r = await runPack("department_vs_company");
      setResp(r as any);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setLoadingMode(null);
    }
  }

  async function onRunPackTopN() {
    setErr(null);
    setLoadingMode("pack:top_n");
    try {
      const r = await runPack("top_n");
      setResp(r as any);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setLoadingMode(null);
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Governed Semantic Analytics Layer</h1>
            <p className="text-sm text-gray-600">
              Natural language → governed dbt metrics → chart + KPIs
            </p>
          </div>

          {/* RIGHT SIDEBAR */}
          <div className="w-[360px] space-y-4 shrink-0">
            <div className="rounded-2xl border bg-white p-3 shadow-sm">
              <div className="text-sm font-semibold mb-2">Available metrics</div>
              <div className="text-xs text-gray-600 space-y-1 max-h-[180px] overflow-auto">
                {(metrics?.metrics || []).map((m) => (
                  <div key={m.name}>
                    <span className="font-mono">{m.name}</span>{" "}
                    <span className="text-gray-400">({m.type})</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border bg-white p-3 shadow-sm">
              <div className="text-sm font-semibold mb-2">Semantic models</div>
              <div className="text-xs text-gray-600 space-y-2 max-h-[180px] overflow-auto">
                {(semanticModels?.semantic_models || []).map((sm) => (
                  <div key={sm.name} className="border rounded-xl p-2">
                    <div className="font-mono text-xs">{sm.name}</div>
                    {sm.relation && (
                      <div className="text-[11px] text-gray-500">{sm.relation}</div>
                    )}
                    <div className="text-[11px] text-gray-500 mt-1">
                      measures: {sm.measures.join(", ")}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* MAIN GRID */}
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4 min-w-0">
          <div className="lg:col-span-1 rounded-2xl border bg-white p-4 shadow-sm">
            <div className="text-sm font-semibold mb-2">Ask</div>

            <button
              onClick={onRunPackTopN}
              disabled={loading}
              className="w-full rounded-xl border py-2 text-sm bg-white hover:bg-gray-50 disabled:opacity-60"
              type="button"
            >
              {loadingMode === "pack:top_n" ? "Running Top-N…" : "Run: Top-N Vendors (Pack)"}
            </button>

            <div className="h-2" />

            <button
              onClick={onRunPackDepartmentVsCompany}
              disabled={loading}
              className="w-full rounded-xl border py-2 text-sm bg-white hover:bg-gray-50 disabled:opacity-60"
              type="button"
            >
              {loadingMode === "pack:department_vs_company"
                ? "Running Comparison…"
                : "Run: Digital Solutions vs Company (Pack)"}
            </button>

            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="mt-3 w-full border rounded-xl p-3 text-sm min-h-[120px]"
              placeholder="e.g. Show total spend by month"
            />

            <div className="mt-3">
              <div className="text-xs font-semibold text-gray-600 mb-2">Try these:</div>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => setQuestion(q)}
                    className="px-3 py-1 rounded-full border text-xs bg-white hover:bg-gray-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={onAsk}
              disabled={loading || !question.trim()}
              className="mt-3 w-full rounded-xl bg-black text-white py-2 text-sm disabled:opacity-50"
              type="button"
            >
              {loadingMode === "ask" ? "Asking…" : "Ask"}
            </button>

            {/* Loading status (no fading) */}
            {statusText && (
              <div className="mt-3 text-xs text-gray-500">{statusText}</div>
            )}

            {err && <div className="mt-3 text-sm text-red-600">{err}</div>}

            {resp?.answer && (
              <div className="mt-4">
                <div className="text-xs text-gray-500 mb-1">Answer</div>
                <div className="text-sm font-medium">{resp.answer}</div>
              </div>
            )}

            <DebugDrawer debug={resp} />
          </div>

          <div className="lg:col-span-2 space-y-4 min-w-0">
            {!resp && (
              <div className="rounded-2xl border p-6 bg-white shadow-sm text-sm text-gray-600">
                Run a pack or ask a question to generate governed charts and KPIs.
              </div>
            )}
            <KpiCards kpis={resp?.kpis} />
            <RankingChart ranking={(resp as any)?.ranking} />
            <TimeseriesChart series={resp?.series} unit={(resp as any)?.chart?.unit || (resp as any)?.unit} />
          </div>
        </div>
      </div>
    </div>
  );
}