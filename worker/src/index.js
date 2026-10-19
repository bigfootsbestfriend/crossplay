// Crossplay Guide community API (Cloudflare Worker + D1).
//
//   GET  /api/game/:slug   vote totals and approved tips for one game
//   POST /api/vote         {slug, result: "yes"|"no", a, b}
//   POST /api/post         {slug, kind: "review"|"report", name, platform, body, website (honeypot), token}
//   GET  /admin            moderation queue (HTTP basic auth: admin / ADMIN_PASSWORD)
//   POST /admin            approve / reject / delete / mark done

const SLUG = /^[a-z0-9-]{1,120}$/;
const PLATFORM = /^[a-z0-9]{1,12}$/;
const POSTS_PER_DAY = 5;

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    try {
      if (url.pathname === "/admin") return await admin(req, env, url);
      if (req.method === "OPTIONS") return cors(req, env, new Response(null, { status: 204 }));
      let res;
      const m = url.pathname.match(/^\/api\/game\/([^/]+)$/);
      if (m && req.method === "GET") res = await game(env, m[1]);
      else if (url.pathname === "/api/vote" && req.method === "POST") res = await vote(req, env);
      else if (url.pathname === "/api/post" && req.method === "POST") res = await post(req, env);
      else res = json({ error: "not found" }, 404);
      return cors(req, env, res);
    } catch (err) {
      return cors(req, env, json({ error: err.status ? err.message : "server error" }, err.status || 500));
    }
  },
};

function json(obj, status = 200, headers = {}) {
  return new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json", ...headers } });
}

function fail(message, status = 400) {
  const err = new Error(message);
  err.status = status;
  throw err;
}

function cors(req, env, res) {
  const origin = req.headers.get("origin");
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map(s => s.trim());
  if (origin && allowed.includes(origin)) {
    res.headers.set("access-control-allow-origin", origin);
    res.headers.set("access-control-allow-methods", "GET, POST, OPTIONS");
    res.headers.set("access-control-allow-headers", "content-type");
    res.headers.set("vary", "origin");
  }
  return res;
}

// Who is asking, as a salted hash of the IP: enough to stop repeat votes, useless if leaked.
async function who(req, env) {
  const ip = req.headers.get("cf-connecting-ip") || "local";
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode((env.HASH_SALT || "dev-salt") + ip));
  return [...new Uint8Array(buf)].slice(0, 16).map(b => b.toString(16).padStart(2, "0")).join("");
}

async function body(req) {
  if (Number(req.headers.get("content-length") || 0) > 4000) fail("too long", 413);
  try { return await req.json(); } catch { fail("bad request"); }
}

async function tally(env, slug) {
  const row = await env.DB.prepare(
    "SELECT SUM(result = 'yes') AS yes, SUM(result = 'no') AS no FROM votes WHERE slug = ?").bind(slug).first();
  return { yes: row?.yes || 0, no: row?.no || 0 };
}

async function game(env, slug) {
  if (!SLUG.test(slug)) fail("bad slug");
  const tips = await env.DB.prepare(
    "SELECT name, platform, body, created FROM posts WHERE slug = ? AND kind = 'review' AND status = 'approved' " +
    "ORDER BY created DESC LIMIT 20").bind(slug).all();
  return json({ votes: await tally(env, slug), tips: tips.results }, 200, { "cache-control": "public, max-age=60" });
}

async function vote(req, env) {
  const d = await body(req);
  if (!SLUG.test(d.slug || "")) fail("bad slug");
  if (!["yes", "no"].includes(d.result)) fail("bad result");
  const a = PLATFORM.test(d.a || "") ? d.a : null, b = PLATFORM.test(d.b || "") ? d.b : null;
  await env.DB.prepare(
    "INSERT INTO votes (slug, who, result, a, b, created) VALUES (?, ?, ?, ?, ?, ?) " +
    "ON CONFLICT (slug, who) DO UPDATE SET result = excluded.result, a = excluded.a, b = excluded.b, created = excluded.created"
  ).bind(d.slug, await who(req, env), d.result, a, b, Math.floor(Date.now() / 1000)).run();
  return json({ ok: true, votes: await tally(env, d.slug) });
}

async function post(req, env) {
  const d = await body(req);
  if (d.website) return json({ ok: true });  // honeypot filled in: a bot; pretend it worked
  if (!SLUG.test(d.slug || "")) fail("bad slug");
  if (!["review", "report"].includes(d.kind)) fail("bad kind");
  const text = String(d.body || "").trim();
  if (text.length < 10) fail("please write a little more");
  if (text.length > 600) fail("please keep it under 600 characters");
  if ((text.match(/https?:\/\//g) || []).length > 1) fail("please leave out links");
  if (env.TURNSTILE_SECRET) {
    const form = new FormData();
    form.append("secret", env.TURNSTILE_SECRET);
    form.append("response", d.token || "");
    form.append("remoteip", req.headers.get("cf-connecting-ip") || "");
    const v = await (await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form })).json();
    if (!v.success) fail("the spam check failed, please try again");
  }
  const id = await who(req, env), now = Math.floor(Date.now() / 1000);
  const recent = await env.DB.prepare("SELECT COUNT(*) AS n FROM posts WHERE who = ? AND created > ?")
    .bind(id, now - 86400).first();
  if (recent.n >= POSTS_PER_DAY) fail("that's enough for today, thanks!", 429);
  await env.DB.prepare("INSERT INTO posts (kind, slug, name, platform, body, who, created) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .bind(d.kind, d.slug, String(d.name || "").trim().slice(0, 40) || null,
          PLATFORM.test(d.platform || "") ? d.platform : null, text, id, now).run();
  // Tell Mike about every submission (it waits in /admin until approved).
  if (env.OWNER_EMAIL && env.RESEND_API_KEY) {
    const esc = (v) => String(v).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
    try {
      await fetch("https://api.resend.com/emails", {
        method: "POST", headers: { authorization: `Bearer ${env.RESEND_API_KEY}`, "content-type": "application/json" },
        body: JSON.stringify({
          from: "Crossplay Guide <hello@crossplayguide.com>", to: [env.OWNER_EMAIL],
          subject: `New player ${d.kind} to approve: ${d.slug}`,
          html: `<p>New player <b>${esc(d.kind)}</b> on <a href="https://crossplayguide.com/games/${esc(d.slug)}/">${esc(d.slug)}</a>${d.platform ? ` (${esc(d.platform)})` : ""}:</p>
<blockquote>${esc(text)}</blockquote><p><a href="https://crossplay-community.crossplayguide.workers.dev/admin">Approve or reject it</a></p>`,
        }),
      });
    } catch (err) { console.error(err.stack || err); }
  }
  return json({ ok: true });
}

// ------------------------------------------------------------------ moderation page

function authorised(req, env) {
  if (!env.ADMIN_PASSWORD) return false;
  const h = req.headers.get("authorization") || "";
  if (!h.startsWith("Basic ")) return false;
  const [user, pass] = atob(h.slice(6)).split(":");
  return user === "admin" && pass === env.ADMIN_PASSWORD;
}

const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function admin(req, env, url) {
  if (!authorised(req, env)) {
    return new Response("Login required", { status: 401, headers: { "www-authenticate": 'Basic realm="Crossplay admin"' } });
  }
  if (req.method === "POST") {
    const f = await req.formData();
    const id = Number(f.get("id")), action = f.get("action");
    const status = { approve: "approved", reject: "rejected", done: "done", pending: "pending" }[action];
    if (action === "delete") await env.DB.prepare("DELETE FROM posts WHERE id = ?").bind(id).run();
    else if (status) await env.DB.prepare("UPDATE posts SET status = ? WHERE id = ?").bind(status, id).run();
    return Response.redirect(url.origin + "/admin" + (f.get("view") ? "?view=" + f.get("view") : ""), 303);
  }
  const view = ["pending", "approved", "rejected", "done"].includes(url.searchParams.get("view")) ? url.searchParams.get("view") : "pending";
  const rows = (await env.DB.prepare("SELECT * FROM posts WHERE status = ? ORDER BY created DESC LIMIT 200").bind(view).all()).results;
  const counts = Object.fromEntries((await env.DB.prepare("SELECT status, COUNT(*) AS n FROM posts GROUP BY status").all())
    .results.map(r => [r.status, r.n]));
  const votes = (await env.DB.prepare(
    "SELECT slug, SUM(result = 'yes') AS yes, SUM(result = 'no') AS no FROM votes GROUP BY slug " +
    "HAVING no > 0 ORDER BY 1.0 * no / (yes + no) DESC, no DESC LIMIT 25").all()).results;
  const site = env.SITE_URL || "";
  const btn = (id, action, label) =>
    `<form method="post"><input type="hidden" name="id" value="${id}"><input type="hidden" name="view" value="${view}">` +
    `<button name="action" value="${action}" class="${action}">${label}</button></form>`;
  const actions = {
    pending: id => btn(id, "approve", "Approve") + btn(id, "reject", "Reject") + btn(id, "done", "Done (report)"),
    approved: id => btn(id, "pending", "Unpublish") + btn(id, "delete", "Delete"),
    rejected: id => btn(id, "pending", "Back to queue") + btn(id, "delete", "Delete"),
    done: id => btn(id, "delete", "Delete"),
  }[view];
  const list = rows.map(r => `<article class="${r.kind}">
    <p class="meta"><b>${r.kind === "report" ? "⚠ Report" : "Tip"}</b> on <a href="${esc(site)}/games/${esc(r.slug)}/" target="_blank">${esc(r.slug)}</a>
    · ${esc(r.name || "anonymous")}${r.platform ? " · " + esc(r.platform) : ""} · ${new Date(r.created * 1000).toLocaleString("en-CA")}</p>
    <p class="body">${esc(r.body)}</p><div class="act">${actions(r.id)}</div></article>`).join("") || "<p>Nothing here.</p>";
  const tabs = ["pending", "approved", "rejected", "done"].map(s =>
    `<a href="?view=${s}" class="${s === view ? "on" : ""}">${s} (${counts[s] || 0})</a>`).join("");
  const disputed = votes.length ? `<h2>Games where players report crossplay failing</h2><table>
    <tr><th>Game</th><th>Worked</th><th>Didn't</th></tr>${votes.map(v =>
      `<tr><td><a href="${esc(site)}/games/${esc(v.slug)}/" target="_blank">${esc(v.slug)}</a></td><td>${v.yes}</td><td>${v.no}</td></tr>`).join("")}</table>` : "";
  return new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crossplay moderation</title><meta name="robots" content="noindex"><style>
:root{--ink:#10142b;--paper:#f5f6fb;--card:#fff;--line:#e2e5f0;--blue:#3a5bff;--yes:#10a36a;--no:#d23b46}
@media (prefers-color-scheme:dark){:root{--ink:#eef0ff;--paper:#0d1022;--card:#161a33;--line:#262b4a}}
body{margin:0;padding:16px;background:var(--paper);color:var(--ink);font:15px/1.5 system-ui,sans-serif;max-width:900px;margin-inline:auto}
a{color:var(--blue)}nav{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}nav a{padding:.35rem .8rem;border-radius:99px;border:1px solid var(--line);text-decoration:none;text-transform:capitalize}
nav a.on{background:var(--blue);color:#fff;border-color:var(--blue)}article{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem;margin:.7rem 0}
article.report{border-left:4px solid var(--no)}.meta{margin:0;font-size:.85rem;opacity:.8}.body{white-space:pre-wrap;margin:.4rem 0}
.act{display:flex;gap:.4rem;flex-wrap:wrap}.act form{margin:0}button{font:inherit;border:0;border-radius:8px;padding:.35rem .8rem;cursor:pointer;background:var(--line);color:var(--ink)}
button.approve{background:var(--yes);color:#fff}button.reject,button.delete{background:var(--no);color:#fff}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:.3rem .5rem;border-bottom:1px solid var(--line)}
</style></head><body><h1>Crossplay moderation</h1><nav>${tabs}</nav>${list}${disputed}</body></html>`,
    { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}
