
async function ensureSchema(env) {
  await env.DB.prepare(`
    CREATE TABLE IF NOT EXISTS app_state (
      id TEXT PRIMARY KEY,
      data TEXT NOT NULL,
      updated_at INTEGER NOT NULL
    )
  `).run();
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store"
    }
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/health") {
      try {
        await ensureSchema(env);
        return json({ ok: true, d1: true });
      } catch (error) {
        return json({ ok: false, error: String(error?.message || error) }, 500);
      }
    }

    if (url.pathname === "/api/sync") {
      await ensureSchema(env);

      if (request.method === "GET") {
        const row = await env.DB.prepare(
          "SELECT data, updated_at FROM app_state WHERE id = ?"
        ).bind("main").first();

        if (!row) {
          return json({ data: null, updatedAt: 0 });
        }

        let data = {};
        try {
          data = JSON.parse(row.data || "{}");
        } catch {
          data = {};
        }
        return json({ data, updatedAt: Number(row.updated_at || 0) });
      }

      if (request.method === "PUT") {
        let body;
        try {
          body = await request.json();
        } catch {
          return json({ error: "JSON inválido" }, 400);
        }

        if (!body || typeof body.data !== "object" || Array.isArray(body.data)) {
          return json({ error: "Formato de datos no válido" }, 400);
        }

        const updatedAt = Date.now();
        const data = JSON.stringify(body.data);

        await env.DB.prepare(`
          INSERT INTO app_state (id, data, updated_at)
          VALUES (?, ?, ?)
          ON CONFLICT(id) DO UPDATE SET
            data = excluded.data,
            updated_at = excluded.updated_at
        `).bind("main", data, updatedAt).run();

        return json({ ok: true, updatedAt });
      }

      return new Response("Method Not Allowed", { status: 405 });
    }

    return env.ASSETS.fetch(request);
  }
};
