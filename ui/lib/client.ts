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