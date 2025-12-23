"use client";

import { useEffect, useState } from "react";
import type { ChatResponse, MetricsResponse } from "@/lib/type";
import { postChat, getMetrics } from "@/lib/client";
import KpiCards from "@/components/KpiCards";
import TimeseriesChart from "@/components/TimeseriesChart";
import DebugDrawer from "@/components/DebugDrawer";

const EXAMPLE_QUESTIONS = [
  "Show total spend by month",
  "Show Digital Solutions spend by month",
  "Show Digital Solutions spend vs the rest of the company by month",
  "Show Digital Solutions share of total spend by month",
  "Show Digital Solutions spend vs the rest of the company for the last 2 years",
  "Show total spend for the last 6 months",
];

export default function Page() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<ChatResponse | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getMetrics()
      .then(setMetrics)
      .catch((e) => setErr(String(e)));
  }, []);

  async function onAsk() {
    setErr(null);
    setLoading(true);
    setResp(null);
    try {
      const r = await postChat(question);
      setResp(r);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Governed Semantic Analytics Copilot</h1>
            <p className="text-sm text-gray-600">Natural language → governed dbt metrics → chart + KPIs</p>
          </div>
          <div className="rounded-2xl border bg-white p-3 shadow-sm w-[360px]">
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
        </div>

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1 rounded-2xl border bg-white p-4 shadow-sm">
            <div className="text-sm font-semibold mb-2">Ask</div>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="w-full border rounded-xl p-3 text-sm min-h-[120px]"
              placeholder="e.g. Show Digital Solutions spend vs the rest of the company for the last 2 years"
            />
            <div className="mt-3">
              <div className="text-xs font-semibold text-gray-600 mb-2">
                Try these:
              </div>
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
            >
              {loading ? "Running..." : "Ask"}
            </button>

            {err && <div className="mt-3 text-sm text-red-600">{err}</div>}

            {resp?.answer && (
              <div className="mt-4">
                <div className="text-xs text-gray-500 mb-1">Answer</div>
                <div className="text-sm font-medium">{resp.answer}</div>
              </div>
            )}

            <DebugDrawer debug={resp} />
          </div>

          <div className="lg:col-span-2 space-y-4">
            <KpiCards kpis={resp?.kpis} />
            <TimeseriesChart series={resp?.series} />
          </div>
        </div>
      </div>
    </div>
  );
}
