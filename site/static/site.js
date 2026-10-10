(() => {
  const root = document.querySelector('link[rel="icon"]').getAttribute("href").replace(/static\/favicon\.svg$/, "");
  let index = null;

  // Contact: the address is stored reversed as char codes and only assembled here, so it never appears
  // in the page source. Links to /contact/?about=Game become mailto links with a subject line.
  const mailEl = document.querySelector("[data-mail]");
  const addr = mailEl ? mailEl.dataset.mail.split(",").reverse().map(c => String.fromCharCode(+c)).join("") : null;
  if (mailEl) {
    const about = new URLSearchParams(location.search).get("about");
    mailEl.textContent = addr;
    mailEl.href = "mailto:" + addr + "?subject=" + encodeURIComponent(about ? "Correction: " + about : "Crossplay Guide");
  }

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
