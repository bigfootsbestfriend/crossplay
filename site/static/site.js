(() => {
  const root = document.querySelector('link[rel="icon"]').getAttribute("href").replace(/static\/favicon\.svg$/, "");
  let index = null;

  // Long game tables: filter by name and platform, sort. The HTML ships A to Z with every row shown; nothing moves until used.
  document.querySelectorAll("[data-ltools]").forEach(tools => {
    const tbody = tools.nextElementSibling && tools.nextElementSibling.querySelector("tbody");
    if (!tbody) return;
    const rows = [...tbody.rows], q = tools.querySelector("[data-lq]"), sort = tools.querySelector("[data-lsort]");
    const count = tools.querySelector("[data-lcount]"), chips = [...tools.querySelectorAll("[data-p]")];
    const fold = s => s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
    const keys = { n: r => r.dataset.n, y: r => -Number(r.dataset.y), c: r => -Number(r.dataset.c) };
    let plat = "";
    const apply = () => {
      const t = fold(q.value), k = keys[sort.value];
      let shown = 0;
      rows.forEach(r => { const ok = (!t || fold(r.dataset.n).includes(t)) && (!plat || r.dataset.p.split(" ").includes(plat)); r.hidden = !ok; if (ok) shown++; });
      rows.slice().sort((x, y) => { const a = k(x), b = k(y); return a < b ? -1 : a > b ? 1 : x.dataset.n < y.dataset.n ? -1 : 1; }).forEach(r => tbody.appendChild(r));
      count.textContent = shown === rows.length ? `Showing all ${rows.length} games` : shown ? `Showing ${shown} of ${rows.length} games` : "No games match. Try another name or platform.";
    };
    q.addEventListener("input", apply);
    sort.addEventListener("change", apply);
    chips.forEach(c => c.addEventListener("click", () => { plat = c.dataset.p; chips.forEach(x => x.classList.toggle("on", x === c)); apply(); }));
  });

  // Group finder ("Who can I play with?"): a game matches when one of its crossplay groups holds every
  // platform picked. Data loads on first use.
  document.querySelectorAll("[data-together]").forEach(box => {
    const people = box.querySelector("[data-people]"), list = box.querySelector("[data-list]");
    const count = box.querySelector("[data-count]"), more = box.querySelector("[data-more]");
    const genre = box.querySelector("[data-genre]"), onlyChecked = box.querySelector("[data-checked]"), free = box.querySelector("[data-free]");
    const opts = people.dataset.opts, names = ["You", "Friend 1", "Friend 2", "Friend 3", "Friend 4", "Friend 5"];
    let data = null, shown = 24, picks;
    try { picks = JSON.parse(localStorage.getItem("together") || "null"); } catch (e) { picks = null; }
    const shared = new URLSearchParams(location.search).get("p");
    if (shared) picks = shared.split(",").filter(k => opts.includes(`value="${k}"`)).slice(0, names.length);
    if (Array.isArray(picks) && picks.length === 1) picks.push(picks[0]);
    if (!Array.isArray(picks) || picks.length < 2) picks = ["ps5", "pc"];
    const label = {};
    people.insertAdjacentHTML("beforeend", "<select hidden>" + opts + "</select>");
    people.lastChild.querySelectorAll("option").forEach(o => label[o.value] = o.textContent);
    people.lastChild.remove();
    const esc = s => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    const drawPeople = () => {
      people.innerHTML = picks.map((p, i) => `<div class="person"><label for="tp-${i}">${names[i]}</label>
        <select id="tp-${i}" data-i="${i}">${opts}</select>${i > 1 ? `<button type="button" class="x" data-rm="${i}" aria-label="Remove ${names[i]}">×</button>` : ""}</div>`).join("");
      people.querySelectorAll("select").forEach(s => s.value = picks[+s.dataset.i]);
      box.querySelector("[data-add]").hidden = picks.length >= names.length;
    };
    const run = async () => {
      try { localStorage.setItem("together", JSON.stringify(picks)); } catch (e) {}
      if (!data) { count.textContent = "Loading games…"; data = await fetch(box.dataset.src).then(r => r.json()); }
      const need = [...new Set(picks)];
      if (need.length < 2) { count.textContent = `Everyone's on ${label[need[0]]}, so any online multiplayer game works. Pick different platforms to check crossplay.`; list.innerHTML = ""; more.hidden = true; return; }
      const g = genre.value, oc = onlyChecked.checked, fr = free.checked;
      const hits = data.games.filter(x => (!g || x.h.includes(g)) && (!oc || x.c) && (!fr || x.f) && x.g.some(gr => need.every(k => gr.includes(k) || (k === "switch2" && gr.includes("switch")))));
      hits.sort((a, b) => b.c - a.c);
      count.textContent = hits.length ? `${hits.length} game${hits.length === 1 ? "" : "s"} let ${need.map(k => label[k]).join(" + ")} play together` : `No games we know of put ${need.map(k => label[k]).join(" + ")} in one lobby${g || oc || fr ? " with these filters" : ""}.`;
      list.innerHTML = hits.slice(0, shown).map(x => `<li><a href="${data.base}${x.s}/">${esc(x.t)}</a>` +
        (x.c ? ' <span class="tag v-yes">Checked</span>' : "") + (x.f ? ' <span class="tag">Free</span>' : "") +
        (need.some(k => x.q.includes(k)) ? ' <span class="tag v-partial">With limits</span>' : "") + "</li>").join("");
      more.hidden = hits.length <= shown;
    };
    people.addEventListener("change", e => { if (e.target.dataset.i) { picks[+e.target.dataset.i] = e.target.value; shown = 24; run(); } });
    people.addEventListener("click", e => { if (e.target.dataset.rm) { picks.splice(+e.target.dataset.rm, 1); drawPeople(); run(); } });
    box.querySelector("[data-add]").addEventListener("click", () => { picks.push(picks[picks.length - 1]); drawPeople(); people.querySelector(`[data-i="${picks.length - 1}"]`).focus(); run(); });
    genre.addEventListener("change", () => { shown = 24; run(); });
    onlyChecked.addEventListener("change", () => { shown = 24; run(); });
    free.addEventListener("change", () => { shown = 24; run(); });
    more.addEventListener("click", () => { shown += 48; run(); });
    const shareBtn = box.querySelector("[data-share-group]");
    if (shareBtn) shareBtn.addEventListener("click", async () => {
      const link = location.origin + location.pathname + "?p=" + picks.join(",");
      const text = `Games we can all play together (${[...new Set(picks)].map(k => label[k]).join(" + ")})`;
      try {
        if (navigator.share) await navigator.share({ title: text, url: link });
        else { await navigator.clipboard.writeText(link); shareBtn.textContent = "Link copied!"; setTimeout(() => shareBtn.textContent = "Share this group", 2500); }
      } catch (e) { /* share sheet closed */ }
    });
    drawPeople(); run();
  });

  // Contact: the address is stored reversed as char codes and only assembled here, so it never appears
  // in the page source. Links to /contact/?about=Game become mailto links with a subject line.
  // Buttons with data-subject keep their own label and use that subject instead.
  document.querySelectorAll("[data-mail]").forEach(mailEl => {
    const addr = mailEl.dataset.mail.split(",").reverse().map(c => String.fromCharCode(+c)).join("");
    const about = new URLSearchParams(location.search).get("about");
    const subject = mailEl.dataset.subject || (about ? "Correction: " + about : "Crossplay Guide");
    if (!mailEl.dataset.subject) mailEl.textContent = addr;
    mailEl.href = "mailto:" + addr + "?subject=" + encodeURIComponent(subject);
  });

  // Search: loads a small JSON index on first focus.
  const load = () => index || (index = fetch(root + "static/search.json").then(r => r.json()));
  const norm = s => s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]/g, "");
  document.querySelectorAll("[data-search]").forEach(input => {
    const box = input.parentElement.querySelector("[data-results]");
    let sel = -1;
    input.addEventListener("focus", load);
    input.addEventListener("input", async () => {
      const q = norm(input.value);
      if (!q) { box.hidden = true; return; }
      const data = await load();
      const words = input.value.toLowerCase().split(/\s+/).filter(Boolean).map(norm);
      const hits = data.games.filter(g => {
        const t = norm(g.t);
        return t.includes(q) || words.every(w => t.includes(w));
      }).sort((a, b) => (norm(b.t).startsWith(q) - norm(a.t).startsWith(q))).slice(0, 8);
      sel = -1;
      box.innerHTML = hits.length
        ? hits.map(g => `<a href="${data.base}${g.s}/"><span>${g.t.replace(/</g, "&lt;")}${g.d ? " (ended)" : ""}</span><small>${g.p.join(" · ")}</small></a>`).join("")
        : `<div class="none">No match yet. We track ${data.games.length} games; <a href="${root}games/">browse them all</a>.</div>`;
      box.hidden = false;
    });
    input.addEventListener("keydown", ev => {
      const links = [...box.querySelectorAll("a")];
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        sel = Math.max(0, Math.min(links.length - 1, sel + (ev.key === "ArrowDown" ? 1 : -1)));
        links.forEach((a, i) => a.classList.toggle("on", i === sel));
      } else if (ev.key === "Enter" && links.length) {
        location.href = (links[sel] || links[0]).href;
      } else if (ev.key === "Escape") {
        box.hidden = true;
      }
    });
    document.addEventListener("click", ev => { if (!input.parentElement.contains(ev.target)) box.hidden = true; });
  });

  // Game page: "I play on X, my friend plays on Y".
  document.querySelectorAll("[data-checker]").forEach(el => {
    const d = JSON.parse(el.dataset.checker);
    const a = el.querySelector("[data-a]"), b = el.querySelector("[data-b]"), out = el.querySelector("[data-out]");
    if (b.options.length > 1) b.selectedIndex = 1;
    const run = () => {
      const x = a.value, y = b.value, nx = d.names[x], ny = d.names[y];
      if (x === y) { out.innerHTML = `<span class="yes">Yes</span>: you're both on ${nx}.`; return; }
      const g = d.groups.find(g => g.p.includes(x) && g.p.includes(y));
      if (!g) out.innerHTML = `<span class="no">No.</span> ${nx} and ${ny} players can't play ${d.title} together.`;
      else if (g.x.includes(x) || g.x.includes(y)) out.innerHTML = `<span class="partial">Partly.</span> ${nx} and ${ny} can play together, with some limits.`;
      else out.innerHTML = `<span class="yes">Yes!</span> ${nx} and ${ny} players can play ${d.title} together.`;
    };
    a.addEventListener("change", run); b.addEventListener("change", run); run();
  });

  // Home: pick two platform families.
  document.querySelectorAll("[data-pairs]").forEach(el => {
    const pairs = JSON.parse(el.dataset.pairs), fa = el.querySelector("[data-fa]"), fb = el.querySelector("[data-fb]"), go = el.querySelector("[data-go]");
    const order = [...fa.options].map(o => o.value);
    const update = () => {
      let [x, y] = [fa.value, fb.value].sort((p, q) => order.indexOf(p) - order.indexOf(q));
      const slug = `${x}-and-${y}`;
      if (x === y) { go.href = `${root}platforms/`; go.textContent = "Pick two different platforms"; }
      else if (pairs[slug]) { go.href = `${el.dataset.base}${slug}/`; go.textContent = "Show games"; }
      else { go.href = `${root}platforms/`; go.textContent = "No games yet, see all platforms"; }
    };
    fa.addEventListener("change", update); fb.addEventListener("change", update); update();
  });
  // Trailer: swap the thumbnail for YouTube's player only when pressed.
  document.querySelectorAll("[data-yt]").forEach(btn => btn.addEventListener("click", () => {
    const f = document.createElement("iframe");
    f.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(btn.dataset.yt)}?autoplay=1&rel=0`;
    f.title = btn.getAttribute("aria-label");
    f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    btn.replaceWith(f);
  }));

  // Screenshots: open in a lightbox (arrows, swipe, Esc). Falls back to opening the image if <dialog> is missing.
  document.querySelectorAll("[data-lightbox]").forEach(box => {
    const links = [...box.querySelectorAll("a")];
    if (!window.HTMLDialogElement) return;
    const dlg = document.createElement("dialog");
    dlg.className = "lightbox";
    dlg.innerHTML = `<div class="lb-in"><img alt=""><button class="lb-prev" aria-label="Previous screenshot">‹</button>
      <button class="lb-next" aria-label="Next screenshot">›</button><button class="lb-close" aria-label="Close">×</button>
      <p class="lb-count"></p></div>`;
    document.body.appendChild(dlg);
    const img = dlg.querySelector("img"), count = dlg.querySelector(".lb-count");
    let i = 0;
    const show = n => {
      i = (n + links.length) % links.length;
      img.src = links[i].href;
      img.alt = links[i].querySelector("img").alt;
      count.textContent = `${box.dataset.title || "Screenshot"} · ${i + 1} of ${links.length}`;
    };
    links.forEach((a, n) => a.addEventListener("click", ev => { ev.preventDefault(); show(n); dlg.showModal(); }));
    dlg.querySelector(".lb-prev").addEventListener("click", () => show(i - 1));
    dlg.querySelector(".lb-next").addEventListener("click", () => show(i + 1));
    dlg.querySelector(".lb-close").addEventListener("click", () => dlg.close());
    dlg.addEventListener("click", ev => { if (ev.target === dlg || ev.target.classList.contains("lb-in")) dlg.close(); });
    dlg.addEventListener("keydown", ev => {
      if (ev.key === "ArrowLeft") show(i - 1);
      if (ev.key === "ArrowRight") show(i + 1);
    });
    let x0 = null;
    dlg.addEventListener("touchstart", ev => { x0 = ev.touches[0].clientX; }, { passive: true });
    dlg.addEventListener("touchend", ev => {
      if (x0 === null) return;
      const dx = ev.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 40) show(i + (dx < 0 ? 1 : -1));
      x0 = null;
    });
  });

  // Community: "did crossplay work for you?" votes and moderated player tips (Cloudflare Worker API).
  document.querySelectorAll("[data-community]").forEach(async el => {
    const d = JSON.parse(el.dataset.community);
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
    const api = (path, body) => fetch(d.api + path, body ? {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body)
    } : {}).then(async r => { const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || r.status); return j; });
    const opts = Object.entries(d.plats).map(([k, n]) => `<option value="${k}">${esc(n)}</option>`).join("");
    const vote = el.querySelector("[data-vote]"), post = el.querySelector("[data-post]");
    vote.a.innerHTML = opts; vote.b.innerHTML = opts; post.platform.innerHTML = `<option value="">Prefer not to say</option>${opts}`;
    if (vote.b.options.length > 1) vote.b.selectedIndex = 1;
    const tally = el.querySelector("[data-tally]"), tips = el.querySelector("[data-tips]"), sent = el.querySelector("[data-sent]");
    const showTally = v => {
      const n = v.yes + v.no;
      if (!n) { tally.textContent = "No player reports yet. Be the first!"; return; }
      const pct = Math.round(100 * v.yes / n);
      tally.innerHTML = `<b>${v.yes}</b> of ${n} player${n === 1 ? "" : "s"} said crossplay worked for them.`
        + `<span class="bar" role="img" aria-label="${pct}% said it worked"><i style="width:${pct}%"></i></span>`;
    };
    try {
      const data = await api(`/api/game/${d.slug}`);
      showTally(data.votes);
      tips.innerHTML = data.tips.length ? data.tips.map(t => `<div class="tip"><p>${esc(t.body)}</p><p class="small">`
        + `${esc(t.name || "A player")}${t.platform && d.plats[t.platform] ? " on " + esc(d.plats[t.platform]) : ""}`
        + ` · ${new Date(t.created * 1000).toLocaleDateString(undefined, { month: "short", year: "numeric" })}</p></div>`).join("")
        : `<p class="small">No tips yet. Know a trick for getting crossplay working in ${esc(d.title)}? Share it below.</p>`;
      el.hidden = false;
    } catch (err) { return; }  // API down: leave the section hidden

    vote.addEventListener("submit", async ev => {
      ev.preventDefault();
      const result = ev.submitter && ev.submitter.value;
      vote.querySelectorAll("button").forEach(b => b.disabled = true);
      try {
        showTally((await api("/api/vote", { slug: d.slug, result, a: vote.a.value, b: vote.b.value })).votes);
        tally.insertAdjacentHTML("afterbegin", "<b>Thanks!</b> ");
      } catch (err) { tally.textContent = "Couldn't save that, please try again later."; }
      vote.querySelectorAll("button").forEach(b => b.disabled = false);
    });

    let tsToken = "";
    if (d.turnstile) {
      el.querySelector(".tipform").addEventListener("toggle", () => {
        if (window.turnstile || document.getElementById("ts-js")) return;
        window.onTs = () => window.turnstile.render(el.querySelector("[data-ts]"), { sitekey: d.turnstile, callback: t => tsToken = t });
        const sc = document.createElement("script");
        sc.id = "ts-js"; sc.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTs"; sc.async = true;
        document.head.appendChild(sc);
      }, { once: true });
    }
    post.addEventListener("submit", async ev => {
      ev.preventDefault();
      const btn = post.querySelector("button"); btn.disabled = true; sent.className = "sent";
      try {
        await api("/api/post", { slug: d.slug, kind: post.kind.value, name: post.name.value, platform: post.platform.value,
          body: post.body.value, website: post.website.value, token: tsToken });
        sent.textContent = post.kind.value === "report" ? "Thanks, we'll check it." : "Thanks! Your tip will appear once it's been checked.";
        post.body.value = "";
      } catch (err) { sent.className = "sent err"; sent.textContent = "Couldn't send that: " + err.message; }
      btn.disabled = false;
    });
  });
})();

// "Your group" on game pages: the platforms saved on this device (the same list the group finder uses),
// checked against this game's crossplay groups, plus a one-tap "did it work?" vote.
(() => {
  const el = document.querySelector("[data-mine]");
  if (!el) return;
  const d = JSON.parse(el.dataset.mine);
  const get = () => { try { const v = JSON.parse(localStorage.getItem("together") || "null"); return Array.isArray(v) ? v : null; } catch (e) { return null; } };
  const put = (v) => { try { localStorage.setItem("together", JSON.stringify(v)); } catch (e) {} };
  const name = (k) => d.names[k] || k;
  const list = (ks) => ks.length < 3 ? ks.map(name).join(" and ") : ks.slice(0, -1).map(name).join(", ") + " and " + name(ks[ks.length - 1]);
  const fits = (gr, k) => gr.p.includes(k) || (k === "switch2" && gr.p.includes("switch"));
  let picks = get(), editing = !picks, voted = false, tally = null;

  const verdict = (S) => {
    const off = S.filter((k) => !d.on.includes(k));
    const offNote = off.length ? ` It isn't out on ${list(off)}.` : "";
    if (S.length === 1) return d.on.includes(S[0]) ? ["yes", `It's on ${name(S[0])}. Add your friends' platforms to check crossplay.`] : ["no", `It isn't out on ${name(S[0])}.`];
    let best = null;
    d.groups.forEach((gr) => { const c = S.filter((k) => fits(gr, k)); if (!best || c.length > best.c.length) best = { gr, c }; });
    if (best && best.c.length === S.length) {
      const lim = S.filter((k) => best.gr.x.includes(k));
      return lim.length ? ["partial", `Partly: ${list(S)} can play together, with limits on ${list(lim)}.`] : ["yes", `Yes! ${list(S)} can all play together.`];
    }
    if (best && best.c.length >= 2) {
      const out = S.filter((k) => !best.c.includes(k) && d.on.includes(k));
      return ["no", `Not all of you. ${list(best.c)} can play together${out.length ? `, but ${list(out)} ${out.length === 1 ? "is" : "are"} matched separately` : ""}.${offNote}`];
    }
    return ["no", `No: none of your platforms share a lobby in this game.${offNote}`];
  };

  const draw = () => {
    const S = [...new Set(picks || [])].filter((k) => d.names[k]);
    const chips = Object.keys(d.names).map((k) => `<button type="button" class="mchip" data-k="${k}" aria-pressed="${S.includes(k)}">${name(k)}</button>`).join("");
    let html = `<div class="mine-head"><b>Your group</b>`;
    if (S.length && !editing) html += ` <span class="mine-plats">${list(S)}</span> <button type="button" class="linkish" data-edit>Change</button>`;
    html += `</div>`;
    if (editing || !S.length) html += `<p class="small">Tap the platforms you and your friends play on. We'll remember them on this device and check every game for you.</p><div class="mchips">${chips}</div>` + (S.length ? `<button type="button" class="btn small" data-done>Done</button>` : "");
    if (S.length) {
      const [k, text] = verdict(S);
      html += `<p class="mine-out v-${k}"><span class="dot"></span>${text}</p>`;
      const vp = S.filter((x) => d.on.includes(x));
      if (d.api && vp.length >= 2 && !editing) {
        html += voted ? `<p class="small mine-vote">Thanks for reporting!</p>`
          : `<p class="mine-vote"><span class="small">Played together? Did crossplay work?</span> <button type="button" class="btn small yes" data-mv="yes">It worked</button> <button type="button" class="btn small no" data-mv="no">It didn't</button></p>`;
      }
    }
    if (tally && tally.yes + tally.no >= 3) html += `<p class="small mine-tally">${tally.yes} of ${tally.yes + tally.no} players said crossplay worked for them. <a href="#community">Tips and reports</a></p>`;
    html += `<p class="small"><a href="${d.finder}">Find every game your group can play together →</a></p>`;
    el.innerHTML = html;
    el.hidden = false;
  };

  el.addEventListener("click", async (ev) => {
    const c = ev.target.closest("[data-k]");
    if (c) {
      const k = c.dataset.k, S = [...new Set(picks || [])];
      picks = S.includes(k) ? S.filter((x) => x !== k) : [...S, k];
      if (picks.length) put(picks); else { picks = null; try { localStorage.removeItem("together"); } catch (e) {} }
      draw();
      el.querySelector(`[data-k="${k}"]`)?.focus();
      return;
    }
    if (ev.target.closest("[data-edit]")) { editing = true; draw(); return; }
    if (ev.target.closest("[data-done]")) { editing = false; draw(); return; }
    const v = ev.target.closest("[data-mv]");
    if (v) {
      const vp = [...new Set(picks)].filter((x) => d.on.includes(x));
      voted = true; draw();
      try {
        const r = await fetch(d.api + "/api/vote", { method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ slug: d.slug, result: v.dataset.mv, a: vp[0], b: vp[1] }) }).then((x) => x.json());
        if (r.votes) { tally = r.votes; draw(); }
      } catch (e) { /* the thanks still shows; the full form lower down works too */ }
      if (window.gtag) window.gtag("event", "crossplay_vote", { result: v.dataset.mv });
    }
  });
  draw();
  if (d.api) fetch(`${d.api}/api/game/${d.slug}`).then((r) => r.json()).then((x) => { tally = x.votes; draw(); }).catch(() => {});
})();

// Email signup prompts: "Tell me…" buttons open the signup box, and a small bar offers it once after a while
// on the page. The bar is easy to close and stays away for 14 days; it never shows to subscribers.
(() => {
  const box = document.querySelector(".signup");
  if (!box) return;
  const form = box.querySelector("form");
  const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  const open = () => {
    box.scrollIntoView({ behavior: "smooth", block: "center" });
    box.classList.remove("flash"); void box.offsetWidth; box.classList.add("flash");
    setTimeout(() => form.querySelector('input[type="email"]').focus({ preventScroll: true }), 500);
    if (bar) bar.hidden = true;
  };
  document.addEventListener("click", (ev) => { const b = ev.target.closest("[data-signup]"); if (b) { ev.preventDefault(); open(); } });
  form.addEventListener("submit", () => {
    store("nl-subbed", "1");
    if (window.gtag) window.gtag("event", "sign_up", { method: "email", page: location.pathname });
  });
  let bar = null;
  if (store("nl-subbed") || Date.now() - (+store("nl-bar") || 0) < 14 * 864e5) return;
  bar = document.createElement("div");
  bar.className = "signup-bar";
  bar.hidden = true;
  bar.innerHTML = `<span><b>Free weekly email</b> · ${box.dataset.bar || box.querySelector("h2").textContent}</span>` +
    `<button type="button" class="go" data-signup>Sign up</button><button type="button" class="x" aria-label="No thanks">×</button>`;
  document.body.appendChild(bar);
  bar.querySelector(".x").addEventListener("click", () => { store("nl-bar", String(Date.now())); bar.remove(); });
  let inView = false, shown = false;
  new IntersectionObserver(([en]) => { inView = en.isIntersecting; if (inView) bar.hidden = true; }).observe(box);
  const show = () => {
    if (shown || inView) return;
    shown = true;
    store("nl-bar", String(Date.now()));
    bar.hidden = false;
  };
  setTimeout(show, 25000);
  addEventListener("scroll", () => { if (scrollY > (document.documentElement.scrollHeight - innerHeight) * 0.5) show(); }, { passive: true });

})();
