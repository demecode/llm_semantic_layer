import { NextResponse } from "next/server";

export async function GET() {
  const base = process.env.API_BASE_URL || "http://localhost:8000";
  const r = await fetch(`${base}/metrics`, { method: "GET" });

  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}