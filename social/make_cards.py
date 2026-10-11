"""Render 1080x1350 social cards from cards.json with headless Chromium."""
import html, json, pathlib, subprocess
HERE = pathlib.Path(__file__).parent
MARK = (HERE.parent / "brand" / "mark.svg").resolve().as_uri()
V = {"yes": ("#22c55e", "Yes"), "no": ("#ff5a5f", "No crossplay"), "partly": ("#f5b83d", "Partly")}
CSS = """html,body{margin:0}body{width:1080px;height:1350px;background:#10142b;color:#fff;font-family:Inter;overflow:hidden;position:relative}
.b1{position:absolute;left:-200px;top:-220px;width:700px;height:700px;border-radius:50%;background:#3a5bff;opacity:.2}
.b2{position:absolute;right:-240px;bottom:-260px;width:760px;height:760px;border-radius:50%;background:#ff5a5f;opacity:.17}
.w{position:absolute;inset:90px 84px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:22px;font:700 40px 'Space Grotesk'}.top img{width:92px}
.k{margin-top:120px;font-size:40px;color:#c9cff5;font-weight:500}
h1{font:700 104px/1.02 'Space Grotesk';margin:18px 0 0;letter-spacing:-2px}
.v{display:inline-block;margin-top:44px;padding:18px 40px;border-radius:999px;font:700 58px 'Space Grotesk';color:#10142b;align-self:flex-start}
.s{margin-top:44px;font-size:42px;line-height:1.35;color:#e4e7fb}
.chips{display:flex;flex-wrap:wrap;gap:16px;margin-top:40px}.chips span{border:2px solid #3b4270;border-radius:16px;padding:12px 24px;font-size:32px;color:#c9cff5}
.f{margin-top:auto;font:700 38px 'Space Grotesk';color:#ff8a8d}"""
for c in json.loads((HERE / "cards.json").read_text()):
    e = html.escape
    v = ""
    if c["verdict"]:
        col, lab = V[c["verdict"]]
        v = f'<div class="v" style="background:{col}">{e(c.get("label", lab))}</div>'
    chips = "".join(f"<span>{e(p)}</span>" for p in c["platforms"])
    doc = f"""<!doctype html><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=Inter:wght@500&display=block" rel="stylesheet">
<style>{CSS}</style><div class="b1"></div><div class="b2"></div><div class="w"><div class="top"><img src="{MARK}">Crossplay Guide</div>
<div class="k">{e(c["kicker"])}</div><h1>{e(c["title"])}</h1>{v}<div class="s">{e(c["sub"])}</div><div class="chips">{chips}</div><div class="f">crossplayguide.com</div></div>"""
    src = HERE / "cards" / f"{c['id']}.html"
    src.write_text(doc)
    out = HERE / "cards" / f"{c['id']}.png"
    subprocess.run(["chromium", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=5000",
                    "--window-size=1080,1350", f"--screenshot={out}", src.as_uri()], check=True, capture_output=True)
    src.unlink()
    subprocess.run(["magick", str(out), "-quality", "90", str(out.with_suffix(".jpg"))], check=True)
    out.unlink()
    print(out.with_suffix(".jpg").name)
