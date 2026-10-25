import sys, json
from playwright.sync_api import sync_playwright
src, out = sys.argv[1], sys.argv[2]; tag = sys.argv[3] if len(sys.argv) > 3 else ""
errs = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1920, 1440, 768, 390):
        pg = b.new_page(viewport={"width": w, "height": 1000}); e = []
        pg.on("pageerror", lambda x, e=e: e.append(str(x)))
        pg.on("console", lambda m, e=e: m.type == "error" and e.append("console: " + m.text))
        pg.goto("file://" + src); pg.wait_for_timeout(9000)
        pg.screenshot(path=f"{out}/{tag}{w}.png", full_page=True)
        pg.screenshot(path=f"{out}/{tag}{w}_top.png")
        if w <= 768:
            pg.click("#mbtn"); pg.wait_for_timeout(400); pg.screenshot(path=f"{out}/{tag}{w}_menu.png")
        ov = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        errs[w] = dict(errors=e, hscroll=ov)
    b.close()
print(json.dumps(errs, indent=1))
