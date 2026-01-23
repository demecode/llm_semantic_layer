export async function postChat(question: string) {
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getMetrics() {
  const r = await fetch("/api/metrics");
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getSemanticModels() {
  const r = await fetch("/api/semantic-models");
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function runPack(packId: string) {
  const r = await fetch(`/api/packs/${packId}/run`, { method: "POST" });
  const text = await r.text();
  if (!r.ok) throw new Error(text);
  return JSON.parse(text);
}