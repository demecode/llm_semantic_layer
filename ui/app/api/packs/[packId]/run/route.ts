import { NextResponse } from "next/server";

export async function POST(
  req: Request,
  ctx: { params: Promise<{ packId: string }> } // <-- params is async
) {
  const { packId } = await ctx.params; // <-- unwrap it

  const base = process.env.API_BASE_URL || "http://api:8000";
  const body = await req.text();

  const controller = new AbortController();
  const timeoutMs = 120_000;
  const t = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const r = await fetch(`${base}/packs/${packId}/run`, {
      method: "POST",
      body,
      headers: {
        "content-type": req.headers.get("content-type") || "application/json",
      },
      signal: controller.signal,
    });

    const text = await r.text();
    return new NextResponse(text, { status: r.status });
  } catch (e: any) {
    return NextResponse.json(
      { error: `Upstream API timeout/fetch failed: ${e?.name || "Error"}` },
      { status: 504 }
    );
  } finally {
    clearTimeout(t);
  }
}