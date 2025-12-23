"use client";

import { useEffect, useState } from "react";
import type { ChatResponse, MetricsResponse } from "@/lib/type";
import { postChat, getMetrics } from "@/lib/client";
import KpiCards from "@/components/KpiCards";
import TimeseriesChart from "@/components/TimeseriesChart";
import DebugDrawer from "@/components/DebugDrawer";

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


// import Image from "next/image";

// export default function Home() {
//   return (
//     <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
//       <main className="flex min-h-screen w-full max-w-3xl flex-col items-center justify-between py-32 px-16 bg-white dark:bg-black sm:items-start">
//         <Image
//           className="dark:invert"
//           src="/next.svg"
//           alt="Next.js logo"
//           width={100}
//           height={20}
//           priority
//         />
//         <div className="flex flex-col items-center gap-6 text-center sm:items-start sm:text-left">
//           <h1 className="max-w-xs text-3xl font-semibold leading-10 tracking-tight text-black dark:text-zinc-50">
//             To get started, edit the page.tsx file.
//           </h1>
//           <p className="max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-400">
//             Looking for a starting point or more instructions? Head over to{" "}
//             <a
//               href="https://vercel.com/templates?framework=next.js&utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
//               className="font-medium text-zinc-950 dark:text-zinc-50"
//             >
//               Templates
//             </a>{" "}
//             or the{" "}
//             <a
//               href="https://nextjs.org/learn?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
//               className="font-medium text-zinc-950 dark:text-zinc-50"
//             >
//               Learning
//             </a>{" "}
//             center.
//           </p>
//         </div>
//         <div className="flex flex-col gap-4 text-base font-medium sm:flex-row">
//           <a
//             className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-foreground px-5 text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc] md:w-[158px]"
//             href="https://vercel.com/new?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
//             target="_blank"
//             rel="noopener noreferrer"
//           >
//             <Image
//               className="dark:invert"
//               src="/vercel.svg"
//               alt="Vercel logomark"
//               width={16}
//               height={16}
//             />
//             Deploy Now
//           </a>
//           <a
//             className="flex h-12 w-full items-center justify-center rounded-full border border-solid border-black/[.08] px-5 transition-colors hover:border-transparent hover:bg-black/[.04] dark:border-white/[.145] dark:hover:bg-[#1a1a1a] md:w-[158px]"
//             href="https://nextjs.org/docs?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
//             target="_blank"
//             rel="noopener noreferrer"
//           >
//             Documentation
//           </a>
//         </div>
//       </main>
//     </div>
//   );
// }
