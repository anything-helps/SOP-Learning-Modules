#!/usr/bin/env python3
"""
Sync PDFs in repo root into slug-named module folders and regenerate the
landing page. Safe to run multiple times (idempotent).

Behavior:
- Detect root PDFs (excluding inside example/reference folders)
- Create slug from a cleaned title, fix common cases (e.g., '&' -> 'and')
- Create folder <slug>/ and move PDF to <slug>/<slug>.pdf (if not already)
- Add placeholder <slug>/index.html if missing
- Rebuild root index.html listing all modules

Usage:
  python3 scripts/sync_modules.py
"""
from __future__ import annotations
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDE_DIRS = {
    'CE_Learning_Module',
    'FCS-Provider-Game',
    'fcs-study-tool',
    '.git',
    '.github',
    '.vscode',
    'scripts',
}

KNOWN_TYPO_FIXES = {
    'coporate': 'corporate',
    'fince': 'finance',
}

ACRONYMS = { 'HIPAA', 'HMIS' }

def clean_title_from_filename(name: str) -> str:
    base = Path(name).stem
    s = base
    s = s.replace('&', ' and ')
    s = s.replace('+', ' and ')
    s = s.replace('@', ' at ')
    # Space normalize
    s = re.sub(r'[\-_]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # Fix known typos at word level
    words = []
    for w in s.split(' '):
        lw = w.lower()
        if lw in KNOWN_TYPO_FIXES:
            w = KNOWN_TYPO_FIXES[lw]
        words.append(w)
    s = ' '.join(words)
    return s

def slugify(title: str) -> str:
    s = title.lower()
    s = s.replace('&', ' and ')
    s = s.replace('+', ' and ')
    s = s.replace('@', ' at ')
    # Fix known typos
    for k, v in KNOWN_TYPO_FIXES.items():
        s = re.sub(rf'\b{k}\b', v, s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s

def display_title_from_title(raw: str) -> str:
    # Preserve FYxxxx uppercase and known acronyms
    words = raw.split()
    out = []
    for w in words:
        if re.fullmatch(r'FY\d{2,4}', w.upper()):
            out.append(w.upper())
        elif w.upper() in ACRONYMS:
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return ' '.join(out)

def build_placeholder_html(title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{title} | Learning Module</title>
    <style>
      :root {{ --bg:#f9fafb; --text:#0f172a; --muted:#64748b; --border:#e5e7eb; --accent:#2563eb; }}
      *{{box-sizing:border-box}}
      body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text)}}
      .wrap{{max-width:800px;margin:0 auto;padding:40px 20px}}
      a{{color:var(--accent);text-decoration:none}}
      a:hover{{text-decoration:underline}}
      .card{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:24px}}
      h1{{margin:0 0 8px;font-size:26px}}
      p{{margin:0 0 8px;color:var(--muted)}}
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <div class=\"card\">
        <h1>Future site of {title} Learning Module</h1>
        <p>This is a placeholder. The interactive module will be built here.</p>
        <p><a href=\"../\">← Back to all modules</a></p>
      </div>
    </div>
  </body>
  </html>\n"""

def build_root_index(slugs: list[str]) -> str:
    # Keep alphabetical order by slug
    slugs = sorted(slugs)
    cards = "\n".join(
        f"        <a class=\"card\" href=\"./{s}/\"><div class=\"slug\">{s}</div></a>" for s in slugs
    )
    return f"""<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Anything Helps | SOP Learning Modules</title>
    <meta name=\"description\" content=\"Landing page for SOP Learning Modules\" />
    <style>
      :root {{
        --bg: #f9fafb;
        --text: #0f172a;
        --muted: #64748b;
        --card-bg: #ffffff;
        --accent: #2563eb;
        --border: #e5e7eb;
      }}
      * {{ box-sizing: border-box; }}
      html, body {{ height: 100%; }}
      body {{
        margin: 0;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Inter, Helvetica, Arial, sans-serif;
        background: var(--bg);
        color: var(--text);
      }}
      .wrap {{ max-width: 1060px; margin: 0 auto; padding: 32px 20px 48px; }}
      header {{ margin-bottom: 24px; }}
      h1 {{ font-size: 28px; line-height: 1.2; margin: 0 0 6px; }}
      p.lead {{ margin: 0; color: var(--muted); }}
      .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; margin-top: 24px; }}
      a.card {{ display: block; padding: 14px 16px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; color: inherit; text-decoration: none; transition: border-color .15s, box-shadow .15s, transform .02s; }}
      a.card:hover {{ border-color: var(--accent); box-shadow: 0 2px 10px rgba(0,0,0,0.06); }}
      a.card:active {{ transform: translateY(1px); }}
      .slug {{ font-weight: 600; font-size: 15px; word-break: break-word; }}
      footer {{ margin-top: 36px; color: var(--muted); font-size: 13px; }}
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <header>
        <h1>Anything Helps — SOP Learning Modules</h1>
        <p class=\"lead\">Select a module below to open its placeholder page.</p>
      </header>
      <main class=\"grid\">
{cards}
      </main>
      <footer>
        Hosted on GitHub Pages. Example modules are excluded.
      </footer>
    </div>
  </body>
  </html>\n"""

def bootstrap_index_html() -> str:
    return """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Learning Module</title>
    <link rel=\"stylesheet\" href=\"../assets/module.css\" />
  </head>
  <body>
    <div class=\"wrap\" id=\"app\"></div>
    <script defer src=\"../assets/module.js\"></script>
  </body>
  </html>\n"""

def is_module_dir(d: Path) -> bool:
    if not d.is_dir():
        return False
    if d.name in EXCLUDE_DIRS or d.name.startswith('.'):  # ignore hidden/refs
        return False
    pdf = d / f"{d.name}.pdf"
    return pdf.exists()

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--stamp-index', action='store_true', help='Overwrite each module index.html with shared bootstrap if assets exist')
    args = ap.parse_args([]) if False else ap.parse_args()
    os.chdir(ROOT)

    # 1) Find root PDFs and move them to slug dirs
    for entry in sorted(ROOT.iterdir()):
        if entry.is_file() and entry.suffix.lower() == '.pdf':
            title_raw = clean_title_from_filename(entry.name)
            title = display_title_from_title(title_raw)
            slug = slugify(title_raw)
            target_dir = ROOT / slug
            target_dir.mkdir(exist_ok=True)
            target_pdf = target_dir / f"{slug}.pdf"
            if not target_pdf.exists():
                entry.rename(target_pdf)

    # 2) Ensure placeholder index.html exists for each module dir (or keep existing)
    modules = []
    for d in sorted(ROOT.iterdir()):
        if is_module_dir(d):
            modules.append(d.name)
            idx = d / 'index.html'
            if args.stamp_index:
                assets_css = ROOT / 'assets' / 'module.css'
                assets_js = ROOT / 'assets' / 'module.js'
                if assets_css.exists() and assets_js.exists():
                    idx.write_text(bootstrap_index_html(), encoding='utf-8')
                else:
                    human = display_title_from_title(clean_title_from_filename(d.name))
                    idx.write_text(build_placeholder_html(human), encoding='utf-8')
            elif not idx.exists():
                # Default to bootstrap shared UI if assets exist; else use placeholder
                assets_css = ROOT / 'assets' / 'module.css'
                assets_js = ROOT / 'assets' / 'module.js'
                if assets_css.exists() and assets_js.exists():
                    idx.write_text(bootstrap_index_html(), encoding='utf-8')
                else:
                    human = display_title_from_title(clean_title_from_filename(d.name))
                    idx.write_text(build_placeholder_html(human), encoding='utf-8')

    # 3) Regenerate root index.html
    (ROOT / 'index.html').write_text(build_root_index(modules), encoding='utf-8')

if __name__ == '__main__':
    main()
