"""eaa-quick-audit: automated WCAG 2.1/2.2 AA first-pass scan for EU Accessibility Act (EAA) readiness.

Automated tools catch only part of WCAG issues. This report is a first pass, not a conformity
assessment or legal advice.
"""
import argparse, datetime as dt, html, json, re, sys
from collections import Counter, deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
AXE = (HERE / "axe.min.js").read_text(encoding="utf-8")
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
IMPACT_ORDER = ["critical", "serious", "moderate", "minor"]
STATEMENT_WORDS = ["accessibility", "barrierefreiheit", "accessibilité", "accessibilite",
                   "toegankelijkheid", "accesibilidad", "accessibilità", "dostępność", "tillgänglighet"]

L = {
 "en": dict(title="EAA / WCAG quick audit", pages="Pages scanned", issues="Issue types", nodes="Affected elements",
            statement="Accessibility statement link found (heuristic)", yes="Yes", no="No - EAA Annex V expects published accessibility information",
            sc="WCAG criterion", en="EN 301 549", impact="Impact", rule="Rule", count="Elements", fix="How to fix", where="Example",
            manual="Manual checks automation cannot do", disclaimer="Automated testing finds a subset of WCAG failures. This is a first-pass report, not a conformity assessment or legal advice."),
 "de": dict(title="EAA / WCAG Schnellprüfung", pages="Geprüfte Seiten", issues="Fehlertypen", nodes="Betroffene Elemente",
            statement="Link zur Barrierefreiheitserklärung gefunden (Heuristik)", yes="Ja", no="Nein - der EAA (Anhang V) verlangt veröffentlichte Barrierefreiheitsinformationen",
            sc="WCAG-Kriterium", en="EN 301 549", impact="Schwere", rule="Regel", count="Elemente", fix="Behebung", where="Beispiel",
            manual="Manuelle Prüfungen (nicht automatisierbar)", disclaimer="Automatische Tests finden nur einen Teil der WCAG-Fehler. Dies ist eine Erstprüfung, keine Konformitätsbewertung und keine Rechtsberatung."),
 "fr": dict(title="Audit rapide EAA / WCAG", pages="Pages analysées", issues="Types de problèmes", nodes="Éléments concernés",
            statement="Lien vers la déclaration d'accessibilité trouvé (heuristique)", yes="Oui", no="Non - l'EAA (annexe V) exige des informations d'accessibilité publiées",
            sc="Critère WCAG", en="EN 301 549", impact="Gravité", rule="Règle", count="Éléments", fix="Correction", where="Exemple",
            manual="Vérifications manuelles (non automatisables)", disclaimer="Les tests automatiques ne détectent qu'une partie des non-conformités WCAG. Ce rapport est un premier passage, pas une évaluation de conformité ni un conseil juridique."),
}
MANUAL = [
 ("2.1.1", "Keyboard: every menu, filter, cart and checkout step works with Tab/Enter/Space, no mouse."),
 ("2.4.7", "Focus visible: you can always see where keyboard focus is."),
 ("2.4.3", "Focus order follows the visual order; modals trap and return focus."),
 ("1.2.2", "Videos have captions; audio has transcripts."),
 ("1.4.10", "Reflow: page works at 400% zoom / 320 px width without horizontal scrolling."),
 ("3.3.1", "Form errors are described in text, not only by colour."),
 ("2.2.1", "Cookie banners, carts and sessions don't time out without warning."),
 ("4.1.3", "Status messages (added to cart, errors) are announced to screen readers."),
]

WCAG22_ONLY = {"2.4.11", "2.4.12", "2.4.13", "2.5.7", "2.5.8", "3.2.6", "3.3.7", "3.3.8", "3.3.9"}

def en301549(sc):
    """EN 301 549 v3.2.1 clause 9 mirrors WCAG 2.1 (9.x.y.z). WCAG 2.2-only criteria have no clause yet."""
    return "(WCAG 2.2 only)" if sc in WCAG22_ONLY else "9." + sc

def sc_from_tags(tags):
    out = []
    for t in tags:
        m = re.fullmatch(r"wcag(\d)(\d)(\d+)", t)
        if m:
            out.append(f"{m.group(1)}.{m.group(2)}.{m.group(3)}")
    return out

def same_site(a, b):
    return urlparse(a).netloc.lower().removeprefix("www.") == urlparse(b).netloc.lower().removeprefix("www.")

SKIP = re.compile(r"\.(pdf|jpe?g|png|gif|svg|webp|zip|mp4|mp3|css|js|json|xml|txt)$|/(cart|checkout|account|login|logout)\b", re.I)

def crawl_and_scan(start, max_pages, timeout_ms, chrome):
    results, seen, q = [], set(), deque([start])
    statement = False
    with sync_playwright() as p:
        kw = {"executable_path": chrome} if chrome else {}
        browser = p.chromium.launch(**kw)
        page = browser.new_page(user_agent="eaa-quick-audit/0.1 (+https://github.com/paopao-studio-ai/eaa-quick-audit)")
        while q and len(results) < max_pages:
            url = urldefrag(q.popleft())[0]
            if url in seen:
                continue
            seen.add(url)
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                ctype = (resp.headers.get("content-type", "") if resp else "")
                if ctype and "html" not in ctype:
                    continue
                page.wait_for_timeout(1200)
                page.add_script_tag(content=AXE)
                res = page.evaluate("t => axe.run(document, {runOnly:{type:'tag', values:t}, resultTypes:['violations']})", TAGS)
                links = page.eval_on_selector_all("a[href]", "els => els.map(e => [e.href, (e.innerText||'').toLowerCase()])")
            except Exception as e:  # noqa
                results.append({"url": url, "error": str(e)[:200], "violations": []})
                continue
            for href, text in links:
                low = (href + " " + text).lower()
                if any(w in low for w in STATEMENT_WORDS):
                    statement = True
                if href.startswith("http") and same_site(href, start) and not SKIP.search(urlparse(href).path) and "/.well-known/" not in href:
                    q.append(href)
            results.append({"url": url, "title": page.title(), "violations": res["violations"]})
        browser.close()
    return results, statement

def aggregate(results):
    agg = {}
    for r in results:
        for v in r["violations"]:
            a = agg.setdefault(v["id"], {"id": v["id"], "impact": v.get("impact") or "minor", "help": v["help"],
                                         "helpUrl": v["helpUrl"], "sc": sc_from_tags(v["tags"]), "nodes": 0,
                                         "pages": set(), "example": None})
            a["nodes"] += len(v["nodes"])
            a["pages"].add(r["url"])
            if not a["example"] and v["nodes"]:
                a["example"] = v["nodes"][0].get("html", "")[:180]
    rows = sorted(agg.values(), key=lambda a: (IMPACT_ORDER.index(a["impact"]) if a["impact"] in IMPACT_ORDER else 9, -a["nodes"]))
    for a in rows:
        a["pages"] = sorted(a["pages"])
    return rows

def render_html(start, results, rows, statement, lang):
    t = L[lang]
    e = html.escape
    imp = Counter()
    for a in rows:
        imp[a["impact"]] += a["nodes"]
    trs = "".join(
        f"<tr><td>{e(a['impact'])}</td><td><a href='{e(a['helpUrl'])}'>{e(a['id'])}</a><br><small>{e(a['help'])}</small></td>"
        f"<td>{', '.join(a['sc']) or '-'}</td><td>{', '.join(en301549(s) for s in a['sc']) or '-'}</td>"
        f"<td style='text-align:right'>{a['nodes']}</td><td><code>{e(a['example'] or '')}</code></td></tr>" for a in rows)
    man = "".join(f"<li><b>{s}</b> {e(x)}</li>" for s, x in MANUAL)
    pages = "".join(f"<li>{e(r['url'])}{' - ERROR' if r.get('error') else ''}</li>" for r in results)
    impline = " · ".join(f"{k}: {imp.get(k,0)}" for k in IMPACT_ORDER)
    return f"""<!doctype html><html lang="{lang}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(t['title'])} - {e(start)}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 16px;color:#1b1b1b}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:6px;vertical-align:top;text-align:left}}
code{{font-size:12px;word-break:break-all}}.k{{display:flex;gap:24px;flex-wrap:wrap}}.k div{{border:1px solid #ccc;border-radius:8px;padding:12px 16px}}
.k b{{display:block;font-size:24px}}</style>
<h1>{e(t['title'])}</h1><p><b>{e(start)}</b> · {dt.date.today().isoformat()} · axe-core · WCAG 2.0/2.1/2.2 A+AA</p>
<div class="k"><div><b>{len(results)}</b>{e(t['pages'])}</div><div><b>{len(rows)}</b>{e(t['issues'])}</div>
<div><b>{sum(a['nodes'] for a in rows)}</b>{e(t['nodes'])}</div></div>
<p>{e(impline)}</p>
<p><b>{e(t['statement'])}:</b> {e(t['yes'] if statement else t['no'])}</p>
<table><tr><th>{e(t['impact'])}</th><th>{e(t['rule'])}</th><th>{e(t['sc'])}</th><th>{e(t['en'])}</th><th>{e(t['count'])}</th><th>{e(t['where'])}</th></tr>{trs}</table>
<h2>{e(t['manual'])}</h2><ul>{man}</ul>
<h2>{e(t['pages'])}</h2><ul>{pages}</ul>
<p><small>{e(t['disclaimer'])}</small></p></html>"""

def main(argv=None):
    ap = argparse.ArgumentParser(description="EAA / WCAG 2.x AA quick audit (axe-core).")
    ap.add_argument("url")
    ap.add_argument("--max-pages", type=int, default=10)
    ap.add_argument("--lang", choices=list(L), default="en")
    ap.add_argument("--out", default="eaa-report")
    ap.add_argument("--timeout", type=int, default=30000)
    ap.add_argument("--chrome", default=None, help="path to a Chrome/Chromium binary (optional)")
    ap.add_argument("--fail-on", choices=IMPACT_ORDER + ["none"], default="none",
                    help="exit 1 if any issue at or above this impact (for CI)")
    a = ap.parse_args(argv)
    results, statement = crawl_and_scan(a.url, a.max_pages, a.timeout, a.chrome)
    rows = aggregate(results)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "report.html").write_text(render_html(a.url, results, rows, statement, a.lang), encoding="utf-8")
    (out / "report.json").write_text(json.dumps({"url": a.url, "date": dt.date.today().isoformat(),
        "accessibility_statement_link": statement, "pages": [r["url"] for r in results], "issues": rows}, indent=2), encoding="utf-8")
    print(f"pages={len(results)} issue_types={len(rows)} elements={sum(r['nodes'] for r in rows)} statement_link={statement}")
    print(f"report: {out/'report.html'}")
    if a.fail_on != "none":
        lim = IMPACT_ORDER.index(a.fail_on)
        if any(r["impact"] in IMPACT_ORDER[:lim+1] for r in rows):
            sys.exit(1)

if __name__ == "__main__":
    main()
