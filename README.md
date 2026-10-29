# eaa-quick-audit

Free, open-source **first-pass accessibility scan** for websites and online shops that fall under the
**European Accessibility Act (EAA, Directive (EU) 2019/882)**, which applies to many e-commerce and consumer
services since **28 June 2025**. Also handy for US **ADA Title II** (WCAG 2.1 AA) projects.

- Crawls up to N same-site pages (headless Chrome via Playwright)
- Runs [axe-core](https://github.com/dequelabs/axe-core) with WCAG 2.0 / 2.1 / 2.2 **A + AA** rules
- Maps every finding to its **WCAG success criterion** and **EN 301 549 v3.2.1 clause** (9.x.x.x)
- Checks (heuristically) whether an **accessibility statement** link exists (EAA Annex V information)
- Writes a self-contained **HTML report in English, German or French** plus JSON for CI
- Lists the manual checks automation cannot do (keyboard, focus, captions, reflow…)

```bash
pip install git+https://github.com/paopao-studio-ai/eaa-quick-audit
python -m playwright install chromium
eaa-audit https://your-shop.example --max-pages 15 --lang de --out report
# CI: fail the build on serious or critical issues
eaa-audit https://staging.example --fail-on serious
```

Example output (W3C's intentionally inaccessible demo site): [`examples/w3c-bad-demo-en/report.html`](examples/w3c-bad-demo-en/report.html)
· German: [`examples/w3c-bad-demo-de/report.html`](examples/w3c-bad-demo-de/report.html)

## What it is not

Automated tools only detect part of WCAG failures. This is **not** a conformity assessment, certification or
legal advice. Whether the EAA applies to you (e.g. the microenterprise exemption for services) is a legal question.

## Need a human-reviewed report?

**EAA Quick Audit - USD 97 per site** (up to 15 pages): automated scan + manual keyboard/screen-reader pass on
home, product, cart and checkout, prioritised fix list (EN/DE/FR), and a draft accessibility statement.
Delivered remotely within 3 business days. Fix sprints quoted after the audit.

Order / questions: **paopaomusic@mail.grokbot.com** (subject "EAA audit") · https://paopao-studio.pages.dev/eaa-audit/

## License

Code: MIT. Bundled `axe.min.js` is axe-core © Deque Systems, MPL-2.0 (see `eaa_quick_audit/AXE_LICENSE.txt`).
