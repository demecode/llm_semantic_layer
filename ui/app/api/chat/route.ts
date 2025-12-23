import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const { question } = await req.json();
  const base = process.env.API_BASE_URL || "http://localhost:8000";

  const r = await fetch(`${base}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}