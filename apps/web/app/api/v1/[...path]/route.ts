// Fixed server-only origin; never forward arbitrary URLs or provider credentials.
export const dynamic = "force-dynamic";
async function proxy(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (
    !/^(health|ready|runs(?:\/[A-Za-z0-9_-]+(?:\/(?:confirm|cancel|events|report))?)?)$/.test(
      path.join("/"),
    )
  )
    return new Response(null, { status: 404 });
  const headers = new Headers();
  for (const name of [
    "content-type",
    "x-run-token",
    "last-event-id",
    "idempotency-key",
  ]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const upstream = await fetch(
      `${process.env.API_ORIGIN || "http://127.0.0.1:8000"}/api/v1/${path.join("/")}`,
      {
        method: request.method,
        headers,
        body: request.method === "POST" ? await request.text() : undefined,
        cache: "no-store",
        signal: request.signal,
      },
    );
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("content-type") || "application/json",
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    return Response.json(
      { detail: "Local research API unavailable" },
      { status: 502 },
    );
  }
}
export { proxy as GET, proxy as POST };
