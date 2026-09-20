async function ensureSchema(env) {
  await env.DB.prepare(`
    CREATE TABLE IF NOT EXISTS app_state (
      id TEXT PRIMARY KEY,
      data TEXT NOT NULL,
      updated_at INTEGER NOT NULL
    )
  `).run();

  await env.DB.prepare(`
    CREATE TABLE IF NOT EXISTS app_backups (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      data TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      source TEXT NOT NULL DEFAULT 'auto'
    )
  `).run();

  await env.DB.prepare(`
    CREATE INDEX IF NOT EXISTS idx_app_backups_created_at
    ON app_backups(created_at DESC)
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

async function addBackup(env, data, source = "auto") {
  if (!data) return null;

  const latest = await env.DB.prepare(
    "SELECT id, data FROM app_backups ORDER BY created_at DESC, id DESC LIMIT 1"
  ).first();

  if (latest && latest.data === data) {
    return Number(latest.id || 0);
  }

  const createdAt = Date.now();
  const result = await env.DB.prepare(
    "INSERT INTO app_backups (data, created_at, source) VALUES (?, ?, ?)"
  ).bind(data, createdAt, source).run();

  await env.DB.prepare(`
    DELETE FROM app_backups
    WHERE id NOT IN (
      SELECT id FROM app_backups
      ORDER BY created_at DESC, id DESC
      LIMIT 10
    )
  `).run();

  return Number(result?.meta?.last_row_id || 0);
}

async function currentState(env) {
  return await env.DB.prepare(
    "SELECT data, updated_at FROM app_state WHERE id = ?"
  ).bind("main").first();
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/health") {
      try {
        await ensureSchema(env);
        return json({ ok: true, d1: true, backups: true });
      } catch (error) {
        return json({ ok: false, error: String(error?.message || error) }, 500);
      }
    }

    if (url.pathname === "/api/backups") {
      await ensureSchema(env);

      if (request.method === "GET") {
        const rows = await env.DB.prepare(
          "SELECT id, created_at, source FROM app_backups ORDER BY created_at DESC, id DESC LIMIT 10"
        ).all();

        return json({
          backups: (rows?.results || []).map((r) => ({
            id: Number(r.id),
            createdAt: Number(r.created_at || 0),
            source: String(r.source || "auto")
          }))
        });
      }

      if (request.method === "POST") {
        let body = {};
        try {
          body = await request.json();
        } catch {}

        if (body?.action === "create") {
          const row = await currentState(env);
          if (!row?.data) return json({ error: "Todavía no hay datos para guardar" }, 400);
          const id = await addBackup(env, row.data, "manual");
          return json({ ok: true, id });
        }

        if (body?.action === "restore") {
          const id = Number(body.id || 0);
          if (!id) return json({ error: "Copia no válida" }, 400);

          const backup = await env.DB.prepare(
            "SELECT data FROM app_backups WHERE id = ?"
          ).bind(id).first();

          if (!backup?.data) return json({ error: "Copia no encontrada" }, 404);

          const current = await currentState(env);
          if (current?.data) await addBackup(env, current.data, "before_restore");

          const updatedAt = Date.now();
          await env.DB.prepare(`
            INSERT INTO app_state (id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              data = excluded.data,
              updated_at = excluded.updated_at
          `).bind("main", backup.data, updatedAt).run();

          await addBackup(env, backup.data, "restored");
          return json({ ok: true, updatedAt });
        }

        return json({ error: "Acción no válida" }, 400);
      }

      return new Response("Method Not Allowed", { status: 405 });
    }

    if (url.pathname === "/api/sync") {
      await ensureSchema(env);

      if (request.method === "GET") {
        const row = await currentState(env);

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

        await addBackup(env, data, "auto");

        return json({ ok: true, updatedAt });
      }

      return new Response("Method Not Allowed", { status: 405 });
    }

    return env.ASSETS.fetch(request);
  }
};
