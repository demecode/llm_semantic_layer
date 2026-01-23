import { NextResponse } from "next/server";

export async function POST(
  req: Request,
  ctx: { params: Promise<{ packId: string }> }
) {
  const { packId } = await ctx.params;

  const base = process.env.API_BASE_URL || "http://localhost:8000";

  // Forward request body (optional, but future-proof for params)
  const body = await req.text();

  const r = await fetch(`${base}/packs/${packId}/run`, {
    method: "POST",
    headers: {
      "content-type": req.headers.get("content-type") || "application/json",
    },
    body: body || undefined,
  });

  const text = await r.text();
  return new NextResponse(text, { status: r.status });
}