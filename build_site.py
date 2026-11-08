"""Builds the iaracreates website: every page, in three languages, as static HTML.

    python3 build_site.py

Reads:
    src/app.html        the whole site (layout, styles, behaviour and all text), the same file as the prototype
    copy-edits.json     copy changes saved in the prototype's copy editor (they win over the text in src/app.html)
    images/, brand/     photos and logos

Writes (in this folder, which is what Cloudflare Pages serves):
    index.html, pt-br/, nl/              home pages
    content-design/..., handmade/...,    every other page, e.g. /nl/handmade/bags/delft-blue-tote/
    about/, contact/
    404.html                             shown for addresses that don't exist
    assets/app.js, assets/app.css        shared by every page
    sitemap.xml, robots.txt, llms.txt, _redirects

Needs Python 3 with Playwright and Chromium (pip install playwright, then playwright install chromium).
Each page is opened in a headless browser and saved fully rendered, so search engines and AI agents
can read every word without running JavaScript.
"""
import http.server, json, os, re, shutil, socketserver, threading, sys

# ---- Settings ---------------------------------------------------------------
SITE_URL = "https://iaracreates.com"   # the site's public address (no trailing slash)
# Until the January 2027 switch-over the shop still lives at its own address. True keeps the Handmade pages
# out of search engines ("noindex") and out of the sitemap, so the same bags don't compete in two places.
# Set to False on switch-over day and run the build again.
HIDE_HANDMADE_FROM_SEARCH = True
# Address of the Handmade section. Until the official switch to iaracreates it lives under the collection name,
# e.g. /fortheloveofzelda/bags/. In January 2027 change this to "handmade" and swap the redirects in write_extras().
HANDMADE_SLUG = "fortheloveofzelda"
# -----------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.abspath(__file__))
SEG = {"en": "", "pt": "pt-br", "nl": "nl"}
HREFLANG = {"en": "en", "pt": "pt-BR", "nl": "nl"}
GENERATED = ["index.html", "404.html", "pt-br", "nl", "content-design", "handmade", "fortheloveofzelda", "about", "contact", "assets",
             "sitemap.xml", "robots.txt", "llms.txt", "_redirects"]
STATIC = {"home": "", "design": "content-design", "projects": "content-design/projects",
          "learning": "content-design/continuous-learning", "speaking": "content-design/public-speaking",
          "handmade": "{hm}", "bags": "{hm}/bags", "crochet": "{hm}/crochet",
          "collection": "{hm}/all-pieces", "about": "about", "contact": "contact"}
PSLUG = {"buddy": "content-design-ai-buddy", "order": "order-tracking-journey", "cancel": "cancellation-flow",
         "wallet": "booking-wallet-rewards", "agile": "agile-planning-tool-launch",
         "bugaboo": "bugaboo-website-replatforming", "library": "content-design-library",
         "l10n": "translations-workflow-automation"}


def url(path, lang):
    seg = SEG[lang]
    return "/" + (seg + "/" if seg else "") + (path + "/" if path else "")


def read_app():
    s = open(os.path.join(ROOT, "src", "app.html"), encoding="utf8").read()
    dec = json.JSONDecoder()
    pieces, _ = dec.raw_decode(s, s.index("var P=") + 6)
    show, _ = dec.raw_decode(re.sub(r"(\w+):", r'"\1":', s[s.index("var SHOW=") + 9:s.index("}", s.index("var SHOW=")) + 1]), 0)
    hidden = json.loads(s[s.index("var HIDDEN=") + 11:s.index("]", s.index("var HIDDEN=")) + 1])  # pieces taken off the site
    pieces = [p for p in pieces if (show.get("custom") or p["id"] != "custom-tote") and p["id"] not in hidden]
    return s, pieces


def page_list(pieces):
    pages = [(k, p.replace("{hm}", HANDMADE_SLUG)) for k, p in STATIC.items()]
    pages += [("project", "content-design/projects/" + s) for s in PSLUG.values()]
    pages += [("piece", "%s/%s/%s" % (HANDMADE_SLUG, p["cat"], p["id"])) for p in pieces]
    return pages


def is_handmade(path):
    return path.split("/")[0] == HANDMADE_SLUG


def clean():
    for name in GENERATED:
        p = os.path.join(ROOT, name)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)


def serve(app_html):
    """A local server that answers every page address with the app, the way a single-page app is served."""
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=ROOT, **k)

        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path.startswith(("/images/", "/brand/")):
                return super().do_GET()
            if path.startswith("/assets/"):  # not built yet while pages are captured
                self.send_response(204)
                self.end_headers()
                return
            body = app_html.encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


CAPTURE_JS = r"""() => {
  document.querySelectorAll('.cms-toggle,.cms-bar').forEach(e => e.remove());
  document.querySelectorAll('dialog[open]').forEach(d => d.removeAttribute('open')); document.body.classList.remove('locked');
  const head = document.head;
  document.body.querySelectorAll('title,meta,link[rel=canonical],link[rel=alternate],link[rel=icon],link[rel=apple-touch-icon],link[rel=preconnect],link[rel=stylesheet],script[type="application/ld+json"]').forEach(e => head.appendChild(e));
  const styles = [...document.querySelectorAll('style')];
  const css = styles.map(s => s.textContent).join('\n');
  styles.forEach(s => s.remove());
  const link = document.createElement('link'); link.rel = 'stylesheet'; link.href = '/assets/app.css'; head.appendChild(link);
  const app = [...document.querySelectorAll('script:not([src]):not([type])')].find(s => s.textContent.length > 20000);
  const js = app.textContent; const ext = document.createElement('script'); ext.src = '/assets/app.js'; app.replaceWith(ext);
  return {html: '<!doctype html>\n' + document.documentElement.outerHTML, css, js};
}"""


def main():
    from playwright.sync_api import sync_playwright
    src, pieces = read_app()
    edits = json.load(open(os.path.join(ROOT, "copy-edits.json"), encoding="utf8")) if os.path.exists(os.path.join(ROOT, "copy-edits.json")) else {}
    site = {"base": SITE_URL, "hideHandmade": HIDE_HANDMADE_FROM_SEARCH, "handmadeSlug": HANDMADE_SLUG, "copy": {l: edits.get(l, {}) for l in SEG}}
    inject = '<base href="/"><script>window.__SITE__=' + json.dumps(site, ensure_ascii=False).replace("</", "<\\/") + ';</script>'
    app = src.replace('var BASE="https://iaracreates.com";', 'var BASE=' + json.dumps(SITE_URL) + ';', 1)
    app = app.replace("<meta charset=utf8>", "<meta charset=utf8>" + inject, 1) if "<meta charset=utf8>" in app else inject + app
    clean()
    srv = serve(app)
    host = "http://127.0.0.1:%d" % srv.server_address[1]
    pages = page_list(pieces)
    written, assets = [], None
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-GB")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        jobs = [(key, path, lang, url(path, lang)) for key, path in pages for lang in SEG]
        jobs.append(("notfound", "", "en", "/this-page-does-not-exist/"))
        for key, path, lang, address in jobs:
            page.goto(host + address)
            page.wait_for_function("document.body.hasAttribute('data-side') && document.querySelector('#view h1')")
            out = page.evaluate(CAPTURE_JS)
            assets = assets or (out["css"], out["js"])
            target = os.path.join(ROOT, "404.html") if key == "notfound" else os.path.join(ROOT, address.strip("/"), "index.html")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            html = out["html"].replace('property="og:image" content="images/', 'property="og:image" content="' + SITE_URL + '/images/')
            open(target, "w", encoding="utf8").write(html)
            written.append(address)
        browser.close()
    srv.shutdown()
    if errors:
        sys.exit("Script errors while building:\n" + "\n".join(errors[:10]))
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    open(os.path.join(ROOT, "assets", "app.css"), "w", encoding="utf8").write(assets[0])
    open(os.path.join(ROOT, "assets", "app.js"), "w", encoding="utf8").write(assets[1])
    # Version the shared files by their content, so a browser never pairs a new page with an old cached script
    import hashlib
    ver = hashlib.sha256((assets[0] + assets[1]).encode("utf8")).hexdigest()[:10]
    for key, address in [("notfound", None)] + [(None, a) for a in written]:
        target = os.path.join(ROOT, "404.html") if key == "notfound" else os.path.join(ROOT, address.strip("/"), "index.html")
        if not os.path.exists(target):
            continue
        html = open(target, encoding="utf8").read()
        html = html.replace('src="/assets/app.js"', 'src="/assets/app.js?v=%s"' % ver).replace('href="/assets/app.css"', 'href="/assets/app.css?v=%s"' % ver)
        open(target, "w", encoding="utf8").write(html)
    write_extras(pages)
    print("Built %d pages (%d addresses in 3 languages + 404)." % (len(written), len(pages)))


def write_extras(pages):
    listed = [p for _, p in pages if not (HIDE_HANDMADE_FROM_SEARCH and is_handmade(p))]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for p in listed:
        alts = "".join('<xhtml:link rel="alternate" hreflang="%s" href="%s%s"/>' % (HREFLANG[l], SITE_URL, url(p, l)) for l in SEG)
        alts += '<xhtml:link rel="alternate" hreflang="x-default" href="%s%s"/>' % (SITE_URL, url(p, "en"))
        for l in SEG:
            sm.append("  <url><loc>%s%s</loc>%s</url>" % (SITE_URL, url(p, l), alts))
    sm.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w").write("\n".join(sm) + "\n")
    open(os.path.join(ROOT, "robots.txt"), "w").write(
        "# Search engines and AI crawlers are welcome. To keep the site out of AI training and answers,\n"
        "# change \"Allow: /\" to \"Disallow: /\" for any of the AI crawlers below.\n"
        "User-agent: *\nAllow: /\n\n" +
        "".join("User-agent: %s\nAllow: /\n\n" % b for b in ["GPTBot", "OAI-SearchBot", "ClaudeBot", "Claude-SearchBot", "PerplexityBot", "Google-Extended"]) +
        "Sitemap: %s/sitemap.xml\n" % SITE_URL)
    open(os.path.join(ROOT, "_redirects"), "w").write(
        "# Older addresses keep working\n"
        "/pt/* /pt-br/:splat 301\n"
        "/projects/ai-buddy/ /content-design/projects/content-design-ai-buddy/ 301\n"
        "/pt-br/projects/ai-buddy/ /pt-br/content-design/projects/content-design-ai-buddy/ 301\n"
        "/nl/projects/ai-buddy/ /nl/content-design/projects/content-design-ai-buddy/ 301\n" +
        ("" if HANDMADE_SLUG == "handmade" else
         "# Handmade lives under the collection name for now (temporary: 302)\n" +
         "".join("{p}handmade {p}{s}/ 302\n{p}handmade/ {p}{s}/ 302\n{p}handmade/* {p}{s}/:splat 302\n".format(p=pre, s=HANDMADE_SLUG)
                 for pre in ("/", "/pt-br/", "/nl/"))))
    llms = open(os.path.join(ROOT, "src", "llms.txt"), encoding="utf8").read().replace("https://iaracreates.com", SITE_URL).replace("/handmade/", "/" + HANDMADE_SLUG + "/")
    if HIDE_HANDMADE_FROM_SEARCH:
        llms = re.sub(r"\n## Handmade\n.*?(?=\n## )", "\n## Handmade\n\n- One-of-a-kind handmade bags by Iara Lucena (For the Love of Zelda, a collection by iaracreates). This part of the site opens in January 2027.\n", llms, flags=re.S)
    open(os.path.join(ROOT, "llms.txt"), "w", encoding="utf8").write(llms)


if __name__ == "__main__":
    main()
