#!/usr/bin/env python3
"""Build the static GitHub Pages site for this guide from the repo markdown.

Usage (from the repo root):
    uv run --with markdown python3 site/build.py      # or: pip install markdown
Output goes to _site/, which is published on the gh-pages branch.
No JavaScript, one stylesheet, one Open Graph image.
"""
import datetime
import html
import json
import os
import pathlib
import re
import shutil
import subprocess

import markdown

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
BASE = "https://capetron.github.io/gb10-cluster-guide/"
REPO = "https://github.com/capetron/gb10-cluster-guide"
SITE_NAME = "GB10 Cluster Guide"
ORG = "Petronella Technology Group, Inc."
ORG_URL = "https://petronellatech.com/"
INDEXNOW_KEY = (ROOT / "site" / "indexnow-key.txt").read_text().strip()

# source file -> (slug, short nav label)
PAGES = [
    ("README.md", "", "Overview"),
    ("docs/01-hardware.md", "hardware/", "Hardware"),
    ("docs/02-two-and-three-nodes.md", "two-and-three-nodes/", "Two and three nodes"),
    ("docs/03-switched-fabric.md", "switched-fabric/", "Switched fabric"),
    ("docs/04-validation.md", "validation/", "Validation"),
    ("docs/05-serving-models.md", "serving-models/", "Serving models"),
    ("docs/06-bill-of-materials.md", "bill-of-materials/", "Bill of materials"),
    ("docs/07-faq.md", "faq/", "FAQ"),
    ("docs/08-parts-and-where-to-buy.md", "parts-and-where-to-buy/", "Parts and where to buy"),
    ("docs/SANITIZATION-NOTES.md", "sanitization-notes/", "Sanitization notes"),
]

# Hand-written descriptions (110-160 chars) where the first paragraph is not a good fit.
DESCRIPTIONS = {
    "": "How to cluster NVIDIA GB10 workstations (DGX Spark and OEM units): one cable for two, a "
        "three-node ring, and a measured 200G RoCE switch fabric.",
    "hardware/": "The GB10 ConnectX-7 port explained: two PCIe Gen 5 x4 halves per QSFP port, why the "
                 "cable is 400G-rated but links at 200G, and 196 Gb/s measured.",
    "two-and-three-nodes/": "Wire two GB10 units with one QSFP112 cable or three in NVIDIA's ring "
                            "(Node 1 Port 0 to Node 2 Port 1), with addressing, MTU 9000 and link checks.",
    "switched-fabric/": "Building a 200G RoCE fabric for four to six GB10 nodes on MikroTik CRS812: "
                        "breakout speed forcing, l2mtu, RSTP and the second-bridge trap.",
    "validation/": "How to prove a GB10 cluster fabric runs at line rate: ib_write_bw and iperf3 "
                   "commands, measured results, and what packet_seq_err means.",
    "serving-models/": "Serving large models across GB10 nodes with vLLM on sm_121: the patch chain, "
                       "four-node GLM and Qwen results, six-node findings and NCCL settings.",
    "bill-of-materials/": "What a GB10 cluster needs by node count: cables, a 200G switch, breakout "
                          "and inter-switch DACs, and a fabric budget from two to eight nodes.",
    "faq/": "Short answers on clustering NVIDIA GB10 workstations: cables, ports, ring wiring, "
            "switches, measured bandwidth and what clustering does for model speed.",
    "parts-and-where-to-buy/": "Which QSFP112 cable fits a DGX Spark or GB10 cluster: NVIDIA-approved "
                               "Amphenol and Luxshare parts, Lenovo 4X91U42988, switches, and sellers.",
    "sanitization-notes/": "What was generalized from our production notes to publish this GB10 "
                           "cluster guide: addressing, hostnames and other internal details.",
}

TITLES = {
    "": "Clustering NVIDIA GB10 Workstations: DGX Spark Cluster Guide",
    "hardware/": "GB10 ConnectX-7 Ports, Cables and Bandwidth Explained",
    "two-and-three-nodes/": "Connect Two or Three DGX Sparks: Cable and Ring Wiring",
    "switched-fabric/": "GB10 Switched 200G RoCE Fabric on MikroTik CRS812",
    "validation/": "Validate a DGX Spark Cluster Fabric: ib_write_bw and iperf3",
    "serving-models/": "Serving Models Across GB10 Nodes with vLLM",
    "bill-of-materials/": "DGX Spark Cluster Bill of Materials, 2 to 8 Nodes",
    "faq/": "DGX Spark and GB10 Clustering FAQ",
    "parts-and-where-to-buy/": "DGX Spark Cluster Parts and Where to Buy Them",
    "sanitization-notes/": "Sanitization Notes for the GB10 Cluster Guide",
}

MD_LINK = re.compile(r"\]\(((?:docs/)?[0-9A-Z][\w.-]*\.md)(#[^)]*)?\)")
BARE_URL = re.compile(r"(?<![(<\"'=])\bhttps?://[^\s<>()\"']+")


def slug_for(md_target):
    name = md_target.split("/")[-1]
    for src, slug, _ in PAGES:
        if src.split("/")[-1] == name:
            return slug
    return None


def rewrite_md_links(text, depth):
    prefix = "../" * depth

    def repl(m):
        slug = slug_for(m.group(1))
        if slug is None:
            return m.group(0)
        return "](" + prefix + slug + (m.group(2) or "") + ")"

    text = MD_LINK.sub(repl, text)
    text = text.replace("](LICENSE)", "](" + REPO + "/blob/main/LICENSE)")
    return text


def autolink(text):
    """Wrap bare URLs outside fenced code blocks in <...> so markdown links them."""
    out, fenced = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            out.append(line)
            continue
        parts = re.split(r"(`[^`]*`)", line)
        for i, part in enumerate(parts):
            if i % 2 == 0:
                def repl(m):
                    url = m.group(0)
                    trail = ""
                    while url and url[-1] in ".,;:":
                        trail = url[-1] + trail
                        url = url[:-1]
                    return "<" + url + ">" + trail
                parts[i] = BARE_URL.sub(repl, part)
        out.append("".join(parts))
    return "\n".join(out)


def lastmod(src):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", src], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return datetime.date.today().isoformat()


def page(title, desc, slug, body_html, nav_html, src, depth, modified):
    url = BASE + slug
    prefix = "../" * depth
    full_title = title
    ld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": title,
        "description": desc,
        "url": url,
        "dateModified": modified,
        "inLanguage": "en",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "image": BASE + "og.png",
        "author": {"@type": "Organization", "name": ORG, "url": ORG_URL},
        "publisher": {"@type": "Organization", "name": ORG, "url": ORG_URL},
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": BASE},
    }
    e = html.escape
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Clustering NVIDIA GB10 workstations">
<meta property="og:locale" content="en_US">
<meta property="article:modified_time" content="{modified}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{BASE}og.png">
<link rel="stylesheet" href="{prefix}style.css">
<link rel="sitemap" type="application/xml" href="{BASE}sitemap.xml">
<script type="application/ld+json">{json.dumps(ld)}</script>
</head>
<body>
<header class="top"><a class="brand" href="{prefix or './'}">{SITE_NAME}</a>
<span class="tag">DGX Spark and every GB10 workstation</span></header>
<div class="wrap">
<nav class="side" aria-label="Guide sections">{nav_html}</nav>
<main>
<article>
{body_html}
</article>
<p class="src"><a href="{REPO}/blob/main/{src}">View or correct this page on GitHub</a></p>
</main>
</div>
<footer>
<p>Maintained by <a href="{ORG_URL}">{ORG}</a>. Text licensed
<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.
Source: <a href="{REPO}">github.com/capetron/gb10-cluster-guide</a>.</p>
</footer>
</body>
</html>
"""


CSS = """:root{--bg:#fbfbf9;--fg:#1c1f23;--mute:#5b6470;--line:#e2e4e8;--acc:#0b6b3a;--code:#f1f2f4;--side:#f4f5f2}
@media (prefers-color-scheme:dark){:root{--bg:#121416;--fg:#e4e6e9;--mute:#9aa3ad;--line:#2a2f35;--acc:#5fd08f;--code:#1c2024;--side:#171a1d}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--acc)}
.top{display:flex;flex-wrap:wrap;gap:.25rem 1rem;align-items:baseline;padding:14px 20px;border-bottom:1px solid var(--line)}
.brand{font-weight:700;font-size:1.1rem;text-decoration:none;color:var(--fg)}
.tag{color:var(--mute);font-size:.9rem}
.wrap{display:grid;grid-template-columns:240px minmax(0,1fr);max-width:1180px;margin:0 auto}
.side{padding:20px 16px;border-right:1px solid var(--line);background:var(--side)}
.side ol{list-style:none;margin:0;padding:0}
.side li{margin:.2rem 0}
.side a{display:block;padding:.3rem .5rem;border-radius:6px;text-decoration:none;color:var(--fg);font-size:.95rem}
.side a[aria-current]{background:var(--line);font-weight:600}
main{padding:8px 32px 40px;min-width:0}
article{max-width:780px}
h1{font-size:2rem;line-height:1.2;margin:1.2rem 0 1rem}
h2{font-size:1.4rem;margin:2.2rem 0 .6rem;padding-top:.4rem;border-top:1px solid var(--line)}
h3{font-size:1.15rem;margin:1.6rem 0 .4rem}
pre,code{font-family:ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace;font-size:.88em}
code{background:var(--code);padding:.1em .3em;border-radius:4px}
pre{background:var(--code);padding:12px 14px;border-radius:8px;overflow-x:auto;line-height:1.45}
pre code{background:none;padding:0}
table{border-collapse:collapse;display:block;overflow-x:auto;margin:1rem 0;font-size:.93rem}
th,td{border:1px solid var(--line);padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:var(--side)}
.src{margin-top:2.5rem;font-size:.9rem;color:var(--mute)}
footer{border-top:1px solid var(--line);padding:18px 20px;color:var(--mute);font-size:.9rem;text-align:center}
@media (max-width:820px){.wrap{grid-template-columns:1fr}.side{border-right:0;border-bottom:1px solid var(--line);padding:10px 16px}
.side ol{display:flex;flex-wrap:wrap;gap:.2rem}.side a{padding:.25rem .5rem;font-size:.88rem}main{padding:4px 16px 32px}h1{font-size:1.6rem}}
"""


def og_image(path):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), (18, 20, 22))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 16, H], fill=(95, 208, 143))
    font_dir = "/usr/share/fonts/truetype/dejavu/"
    try:
        big = ImageFont.truetype(font_dir + "DejaVuSans-Bold.ttf", 68)
        mid = ImageFont.truetype(font_dir + "DejaVuSans.ttf", 34)
        small = ImageFont.truetype(font_dir + "DejaVuSans.ttf", 28)
    except OSError:
        big = mid = small = ImageFont.load_default()
    d.text((80, 110), "Clustering NVIDIA GB10", font=big, fill=(236, 238, 240))
    d.text((80, 195), "workstations", font=big, fill=(236, 238, 240))
    d.text((80, 320), "Two nodes, a three-node ring, and a switched", font=mid, fill=(170, 178, 186))
    d.text((80, 368), "200G RoCE fabric. 196 Gb/s measured per cable.", font=mid, fill=(170, 178, 186))
    d.text((80, 520), "capetron.github.io/gb10-cluster-guide  |  CC BY 4.0", font=small, fill=(95, 208, 143))
    im.save(path, optimize=True)
    return True


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                           extension_configs={"toc": {"permalink": False}})
    urls = []
    for src, slug, _label in PAGES:
        depth = slug.count("/")
        text = (ROOT / src).read_text()
        text = autolink(rewrite_md_links(text, depth))
        md.reset()
        body = md.convert(text)
        m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else SITE_NAME
        title = TITLES.get(slug) or html.unescape(re.sub(r"^\d\d\.\s*", "", title))
        desc = DESCRIPTIONS[slug]
        nav = "<ol>" + "".join(
            '<li><a href="{}"{}>{}</a></li>'.format(
                ("../" * depth + s) or "./", ' aria-current="page"' if s == slug else "", html.escape(lbl))
            for _s, s, lbl in PAGES) + "</ol>"
        mod = lastmod(src)
        dest = OUT / slug / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page(title, desc, slug, body, nav, src, depth, mod))
        urls.append((BASE + slug, mod))

    (OUT / "style.css").write_text(CSS)
    og_image(OUT / "og.png")
    (OUT / ".nojekyll").write_text("")
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: " + BASE + "sitemap.xml\n")
    (OUT / (INDEXNOW_KEY + ".txt")).write_text(INDEXNOW_KEY)
    # Search engine ownership files (e.g. google<token>.html) live in site/verify/ and are copied
    # to the site root verbatim so a rebuild never drops a verification.
    for vf in sorted((ROOT / "site" / "verify").glob("*")) if (ROOT / "site" / "verify").is_dir() else []:
        if vf.name != "README.txt":
            shutil.copyfile(vf, OUT / vf.name)
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, mod in urls:
        sm.append("  <url><loc>{}</loc><lastmod>{}</lastmod></url>".format(u, mod))
    sm.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(sm) + "\n")
    notfound = page("Page not found", DESCRIPTIONS[""], "", '<h1>Page not found</h1><p><a href="' + BASE +
                    '">Back to the guide</a></p>', "", "README.md", 0, datetime.date.today().isoformat())
    notfound = (notfound.replace('<meta name="robots" content="index, follow">', '<meta name="robots" content="noindex">')
                .replace('href="style.css"', 'href="/gb10-cluster-guide/style.css"')
                .replace('href="./"', 'href="' + BASE + '"')
                .replace('<link rel="canonical" href="' + BASE + '">\n', ''))
    (OUT / "404.html").write_text(notfound)
    print("built", len(urls), "pages into", OUT)


if __name__ == "__main__":
    main()
