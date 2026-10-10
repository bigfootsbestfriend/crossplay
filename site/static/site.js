(() => {
  const root = document.querySelector('link[rel="icon"]').getAttribute("href").replace(/static\/favicon\.svg$/, "");
  let index = null;

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
})();
