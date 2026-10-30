#!/usr/bin/env python3
"""Static checks for the duct-tape2.github.io site.

Dependency-free (Python 3.8+ standard library only). Run from anywhere:

    python3 scripts/check_site.py

Checks:
  * internal links and #anchors in HTML, Markdown, sitemap, feed, llms.txt
    and offers.json resolve to files / ids in this repository
  * every indexable HTML page has the required head tags (lang, title,
    description, canonical, Open Graph, Twitter card, viewport, icon) and
    titles / descriptions are unique
  * every JSON-LD block parses, uses schema.org, and any paid Offer price
    matches offers.json
  * FAQPage questions appear in the visible page text
  * images have alt text and width/height
  * sitemap.xml lists every indexable page and no redirect / noindex page

Exit status is 1 when any ERROR is found; WARN lines do not fail the run.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urldefrag, urlsplit

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SITE = "https://duct-tape2.github.io"

# Paths on the same host that are served by *other* repositories (GitHub
# project pages). They cannot be checked from this repository.
EXTERNAL_PROJECT_PREFIXES = (
    "/ai-language-partner/",
    "/ai-money-stack/",
    "/github-pages-storefront-starter/",
    "/japanese-anki-pack/",
)

SKIP_DIRS = {".git", "node_modules", "scripts", "docs"}

REQUIRED_META = [
    ("name", "description"),
    ("name", "viewport"),
    ("property", "og:type"),
    ("property", "og:title"),
    ("property", "og:description"),
    ("property", "og:url"),
    ("property", "og:image"),
    ("property", "og:site_name"),
    ("name", "twitter:card"),
    ("name", "twitter:title"),
    ("name", "twitter:description"),
]

errors = []
warnings = []


def error(where, msg):
    errors.append("ERROR %s: %s" % (where, msg))


def warn(where, msg):
    warnings.append("WARN  %s: %s" % (where, msg))


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = None
        self._in_title = False
        self.meta = {}
        self.links = []  # (rel, href)
        self.refs = []  # (tag, attr, url, line)
        self.ids = set()
        self.jsonld = []  # (line, text)
        self._jsonld_line = None
        self._jsonld_buf = []
        self._skip_text = 0
        self.text = []
        self.headings = []  # (level, line)
        self.images = []  # (attrs, line)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "name" in a:
            self.ids.add(a["name"])
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
            self.title = ""
        elif tag == "meta":
            for key in ("name", "property", "http-equiv"):
                if key in a:
                    self.meta.setdefault(a[key].lower(), []).append(a.get("content", ""))
        elif tag == "link":
            self.links.append((a.get("rel", "").lower(), a.get("href", "")))
            if a.get("href"):
                self.refs.append((tag, "href", a["href"], line))
        elif tag == "script":
            if a.get("type") == "application/ld+json":
                self._jsonld_line = line
                self._jsonld_buf = []
            else:
                self._skip_text += 1
            if a.get("src"):
                self.refs.append((tag, "src", a["src"], line))
        elif tag == "style":
            self._skip_text += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self.headings.append((int(tag[1]), line))
        if tag in ("a", "area") and a.get("href"):
            self.refs.append((tag, "href", a["href"], line))
        if tag in ("img", "source", "iframe") and a.get("src"):
            self.refs.append((tag, "src", a["src"], line))
        if tag == "img":
            self.images.append((a, line))
        if tag == "form" and a.get("action"):
            self.refs.append((tag, "action", a["action"], line))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            if self._jsonld_line is not None:
                self.jsonld.append((self._jsonld_line, "".join(self._jsonld_buf)))
                self._jsonld_line = None
            else:
                self._skip_text = max(0, self._skip_text - 1)
        elif tag == "style":
            self._skip_text = max(0, self._skip_text - 1)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._jsonld_line is not None:
            self._jsonld_buf.append(data)
        elif not self._skip_text:
            self.text.append(data)


def rel(path):
    return os.path.relpath(path, ROOT)


def page_url(path):
    r = rel(path).replace(os.sep, "/")
    if r == "index.html":
        return SITE + "/"
    if r.endswith("/index.html"):
        return SITE + "/" + r[: -len("index.html")]
    return SITE + "/" + r


def find_files(exts):
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(exts):
                out.append(os.path.join(dirpath, name))
    return out


def resolve_internal(url, base_file):
    """Return (local_path, fragment) for an internal URL, 'external' for a
    same-host project page in another repo, or None for a foreign URL."""
    url = url.strip()
    if not url or url.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None
    if url.startswith("//"):
        url = "https:" + url
    nofrag, frag = urldefrag(url)
    parts = urlsplit(nofrag)
    if parts.scheme in ("http", "https"):
        if parts.netloc != urlsplit(SITE).netloc:
            return None
        path = parts.path or "/"
    elif parts.scheme:
        return None
    elif nofrag == "":
        return (base_file, frag)
    elif nofrag.startswith("/"):
        path = parts.path
    else:
        base_dir = os.path.dirname(base_file)
        local = os.path.normpath(os.path.join(base_dir, unquote(parts.path)))
        path = "/" + os.path.relpath(local, ROOT).replace(os.sep, "/")
        if parts.path.endswith("/"):
            path += "/"
    if path.startswith(EXTERNAL_PROJECT_PREFIXES) or path.rstrip("/") + "/" in EXTERNAL_PROJECT_PREFIXES:
        return "external"
    local = os.path.join(ROOT, unquote(path).lstrip("/"))
    if path.endswith("/"):
        local = os.path.join(local, "index.html")
    elif os.path.isdir(local):
        local = os.path.join(local, "index.html")
    return (os.path.normpath(local), frag)


def load_offers():
    with open(os.path.join(ROOT, "offers.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    prices = {(str(o["price_usd"]), o.get("currency", data.get("currency", "USD"))) for o in data["offers"]}
    return data, prices


def walk_jsonld(node, visit):
    if isinstance(node, dict):
        visit(node)
        for v in node.values():
            walk_jsonld(v, visit)
    elif isinstance(node, list):
        for v in node:
            walk_jsonld(v, visit)


def types_of(node):
    t = node.get("@type", [])
    return t if isinstance(t, list) else [t]


def norm_text(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def main():
    pages = {}
    for path in find_files((".html",)):
        p = PageParser()
        with open(path, encoding="utf-8") as fh:
            p.feed(fh.read())
        pages[os.path.normpath(path)] = p

    try:
        offers, offer_prices = load_offers()
    except (OSError, ValueError, KeyError) as exc:
        error("offers.json", "cannot parse: %s" % exc)
        offers, offer_prices = {}, set()

    def is_redirect(p):
        return "refresh" in p.meta

    def is_noindex(p):
        return any("noindex" in c.lower() for c in p.meta.get("robots", []))

    def indexable(path):
        p = pages[path]
        return not is_redirect(p) and not is_noindex(p)

    anchor_cache = {}

    def ids_for(local):
        if local in pages:
            return pages[local].ids
        return anchor_cache.setdefault(local, set())

    def check_ref(where, url, base_file):
        res = resolve_internal(url, base_file)
        if res is None or res == "external":
            return
        local, frag = res
        if not os.path.exists(local):
            error(where, "broken internal link %s" % url)
            return
        if frag and local.endswith(".html") and frag not in ids_for(local):
            error(where, "missing anchor #%s in %s" % (frag, rel(local)))
        if local in pages and is_redirect(pages[local]) and not base_file.endswith(".xml"):
            if not (base_file in pages and is_redirect(pages[base_file])):
                warn(where, "links to redirect stub %s; link the final URL instead" % url)

    # --- HTML pages -------------------------------------------------------
    titles, descriptions = {}, {}
    for path, p in sorted(pages.items()):
        name = rel(path)
        for tag, attr, url, line in p.refs:
            check_ref("%s:%d" % (name, line), url, path)

        if not p.lang:
            error(name, "missing <html lang>")
        if not (p.title or "").strip():
            error(name, "missing <title>")
        if not any("icon" in r.split() for r, _ in p.links):
            error(name, "missing <link rel=icon>")

        if is_redirect(p):
            continue

        has_main = "<main" in open(path, encoding="utf-8").read()
        if not has_main:
            warn(name, "no <main> landmark")

        levels = [lvl for lvl, _ in p.headings]
        if levels.count(1) != 1:
            error(name, "expected exactly one <h1>, found %d" % levels.count(1))
        prev = 0
        for lvl, line in p.headings:
            if prev and lvl > prev + 1:
                warn("%s:%d" % (name, line), "heading jumps from h%d to h%d" % (prev, lvl))
            prev = lvl

        for a, line in p.images:
            where = "%s:%d" % (name, line)
            if "alt" not in a:
                error(where, "<img> without alt attribute")
            if not (a.get("width") and a.get("height")):
                warn(where, "<img> without width/height")

        if not indexable(path):
            continue

        for key, val in REQUIRED_META:
            if not any(c.strip() for c in p.meta.get(val, [])):
                error(name, "missing meta %s=%s" % (key, val))
        canon = [h for r, h in p.links if r == "canonical"]
        if len(canon) != 1:
            error(name, "expected one canonical link, found %d" % len(canon))
        elif canon[0] != page_url(path):
            error(name, "canonical %s does not match page URL %s" % (canon[0], page_url(path)))
        og_url = p.meta.get("og:url", [""])[0]
        if og_url and og_url != page_url(path):
            error(name, "og:url %s does not match page URL" % og_url)
        for key in ("og:image", "twitter:image"):
            for img in p.meta.get(key, []):
                check_ref(name, img, path)

        t = norm_text(p.title or "")
        titles.setdefault(t, []).append(name)
        for d in p.meta.get("description", []):
            descriptions.setdefault(norm_text(d), []).append(name)
            if len(d) > 170:
                warn(name, "meta description is %d chars (aim for <= 160)" % len(d))
        if len(p.title or "") > 65:
            warn(name, "title is %d chars (aim for <= 65)" % len(p.title))

    for t, names in titles.items():
        if len(names) > 1:
            error(", ".join(names), "duplicate <title> %r" % t)
    for d, names in descriptions.items():
        if len(names) > 1:
            error(", ".join(names), "duplicate meta description")

    # --- JSON-LD ----------------------------------------------------------
    for path, p in sorted(pages.items()):
        name = rel(path)
        visible = norm_text(" ".join(p.text))
        for line, text in p.jsonld:
            where = "%s:%d" % (name, line)
            try:
                data = json.loads(text)
            except ValueError as exc:
                error(where, "JSON-LD does not parse: %s" % exc)
                continue
            blocks = data if isinstance(data, list) else [data]
            for block in blocks:
                ctx = block.get("@context", "")
                if "schema.org" not in str(ctx):
                    error(where, "JSON-LD @context is not schema.org")
                if "@type" not in block and "@graph" not in block:
                    error(where, "JSON-LD block has no @type or @graph")

            def visit(node, where=where, visible=visible):
                ts = types_of(node)
                if "Offer" in ts and "price" in node:
                    key = (str(node["price"]), node.get("priceCurrency"))
                    if key[0] not in ("0", "0.00") and key not in offer_prices:
                        error(where, "Offer price %s %s not in offers.json" % key)
                if "Person" in ts and not node.get("name") and "@id" not in node:
                    error(where, "Person without name")
                if any(t in ts for t in ("AggregateRating", "Review")):
                    error(where, "%s found; ratings/reviews must not be added without real data" % ts)
                if "Question" in ts:
                    q = norm_text(node.get("name", ""))
                    if q and q not in visible:
                        error(where, "FAQ question not visible on page: %r" % node.get("name"))
                    ans = node.get("acceptedAnswer", {}).get("text", "")
                    if ans and norm_text(ans) not in visible:
                        warn(where, "FAQ answer text differs from visible text: %r" % node.get("name"))
                for k, v in node.items():
                    if k in ("url", "item", "image", "mainEntityOfPage") and isinstance(v, str):
                        check_ref(where, v, path)

            walk_jsonld(data, visit)

    # --- Markdown ---------------------------------------------------------
    md_link = re.compile(r"\]\(([^)\s]+)\)|(https?://[^\s)<>\"']+)")
    for path in find_files((".md",)):
        with open(path, encoding="utf-8") as fh:
            for n, text in enumerate(fh, 1):
                for m in md_link.finditer(text):
                    check_ref("%s:%d" % (rel(path), n), m.group(1) or m.group(2), path)

    # --- llms.txt / offers.json / feed.xml / robots.txt -------------------
    url_re = re.compile(r"https?://[^\s)<>\"']+")
    for fname in ("llms.txt", "offers.json", "robots.txt"):
        fpath = os.path.join(ROOT, fname)
        if not os.path.exists(fpath):
            error(fname, "missing")
            continue
        with open(fpath, encoding="utf-8") as fh:
            for n, text in enumerate(fh, 1):
                for u in url_re.findall(text):
                    check_ref("%s:%d" % (fname, n), u.rstrip(".,"), fpath)
    with open(os.path.join(ROOT, "robots.txt"), encoding="utf-8") as fh:
        if "Sitemap: %s/sitemap.xml" % SITE not in fh.read():
            error("robots.txt", "missing Sitemap line")

    feed_path = os.path.join(ROOT, "feed.xml")
    try:
        feed = ET.parse(feed_path)
        for el in feed.iter():
            for attr in ("href", "url"):
                if el.get(attr):
                    check_ref("feed.xml", el.get(attr), feed_path)
    except (OSError, ET.ParseError) as exc:
        error("feed.xml", "cannot parse: %s" % exc)

    # --- sitemap ----------------------------------------------------------
    sm_path = os.path.join(ROOT, "sitemap.xml")
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    listed = set()
    try:
        sm = ET.parse(sm_path)
        for loc in sm.getroot().iterfind("sm:url/sm:loc", ns):
            url = loc.text.strip()
            res = resolve_internal(url, sm_path)
            if res is None:
                error("sitemap.xml", "foreign URL %s" % url)
                continue
            if res == "external":
                warn("sitemap.xml", "%s is served by another repository; not checked" % url)
                continue
            local = res[0]
            listed.add(local)
            if not os.path.exists(local):
                error("sitemap.xml", "lists missing page %s" % url)
            elif local in pages and not indexable(local):
                error("sitemap.xml", "lists redirect/noindex page %s" % url)
        for el in sm.iter():
            if el.get("href"):
                check_ref("sitemap.xml", el.get("href"), sm_path)
        for el in sm.getroot().iterfind(".//{http://www.google.com/schemas/sitemap-image/1.1}loc"):
            check_ref("sitemap.xml", el.text.strip(), sm_path)
    except (OSError, ET.ParseError) as exc:
        error("sitemap.xml", "cannot parse: %s" % exc)
    for path in pages:
        if indexable(path) and path not in listed:
            error("sitemap.xml", "indexable page %s is not listed" % page_url(path))

    # --- report -----------------------------------------------------------
    n_index = sum(1 for p in pages if indexable(p))
    n_redirect = sum(1 for p in pages.values() if is_redirect(p))
    for line in warnings + errors:
        print(line)
    print(
        "\nChecked %d HTML pages (%d indexable, %d redirect stubs), sitemap, feed, "
        "llms.txt, offers.json, Markdown: %d error(s), %d warning(s)."
        % (len(pages), n_index, n_redirect, len(errors), len(warnings))
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
