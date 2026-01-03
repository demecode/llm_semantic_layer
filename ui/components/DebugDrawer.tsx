"use client";

import { useState } from "react";

export default function DebugDrawer({ debug }: { debug: any }) {
  const [open, setOpen] = useState(false);
  if (!debug) return null;

  return (
    <div className="mt-3">
      <button
        className="text-sm underline text-gray-600"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide debug" : "Show debug"}
      </button>

      {open && (
        <>
          <pre className="mt-2 rounded-2xl border p-3 bg-gray-50 text-xs overflow-auto">
            {JSON.stringify(debug, null, 2)}
          </pre>

          {debug.contract && (
            <div className="mt-4 text-xs space-y-1 text-gray-700">
              <div><b>Metric:</b> {debug.contract.metric}</div>
              <div><b>Semantic model:</b> {debug.contract.semantic_model}</div>
              <div><b>Relation:</b> {debug.contract.relation}</div>
              <div><b>Manifest hash:</b> {debug.contract.manifest_hash}</div>
              {debug.cache && (
                <div><b>Cache hit:</b> {String(debug.cache.cached)}</div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}