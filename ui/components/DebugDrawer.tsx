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
        <pre className="mt-2 rounded-2xl border p-3 bg-gray-50 text-xs overflow-auto">
{JSON.stringify(debug, null, 2)}
        </pre>
      )}
    </div>
  );
}