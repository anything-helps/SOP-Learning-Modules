SOP Learning Modules — Maintainers Guide

This repository hosts a GitHub Pages site that lists Standard Operating Procedure (SOP) learning modules. Each module is backed by a PDF and a small set of JSON data files used to render flashcards, questions, scenarios, and extracted content.

Quick glossary
- Module: A folder named after the PDF slug (e.g., `access-to-housing/`).
- PDF: The source document stored at `<slug>/<slug>.pdf`.
- Extracted content: Text and sections under `<slug>/content/`.
- Learning data: JSON files under `<slug>/data/` for flashcards, questions, scenarios.

Naming conventions
- Slugs: Lowercase, letters and numbers, hyphens for separators. Examples:
  - "Access to Housing.pdf" → `access-to-housing/access-to-housing.pdf`
  - "Honoring Client Voice & Choice.pdf" → `honoring-client-voice-and-choice/honoring-client-voice-and-choice.pdf`
- Typos are normalized in slugs (e.g., `coporate` → `corporate`, `fince` → `finance`).
- Each module lives in a folder that matches the slug, and the PDF inside uses the same slug as its filename.

Create a new module (recommended flow)
1) Drop the PDF in the repo root (e.g., `New SOP Topic.pdf`).
2) Normalize, move, and scaffold:
   - `python3 scripts/sync_modules.py`
   - This will:
     - Create a slug for the PDF and move it into `<slug>/<slug>.pdf`.
     - Create `<slug>/index.html` that loads the shared UI (if `assets/module.*` exist) or a placeholder page.
     - Regenerate the root `index.html` list.
   - Optional: Force shared UI for every module page
     - `python3 scripts/sync_modules.py --stamp-index`
3) Extract text and build sections:
   - Single module: `python3 scripts/extract_content.py --slug <slug>`
   - All modules: `python3 scripts/extract_content.py`
   - Notes:
     - Requires `pdftotext` (Poppler). Install: `brew install poppler`.
     - For scanned PDFs, OCR is automatic if you have either:
       - `ocrmypdf` (recommended): `brew install ocrmypdf`
       - or `tesseract` + `pdftoppm`: `brew install tesseract poppler`
     - Outputs to `<slug>/content/`: `raw.txt`, `sections.json`, `meta.json`.

Generate learning data (questions, terms, scenarios)
Option A — Offline (prompts only)
- Create prompts from extracted content:
  - Single module: `python3 scripts/generate_module_content.py --slug <slug> --offline`
  - All modules: `python3 scripts/generate_module_content.py --all --offline`
- Paste each prompt into ChatGPT (or similar) and save the JSON responses into:
  - `<slug>/data/questions.json`
  - `<slug>/data/terms.json`
  - `<slug>/data/scenarios.json`

Option B — Using an OpenAI API key (automatic)
- Install and set up:
  - `pip install openai`
  - `export OPENAI_API_KEY=...`
  - Optional: `export OPENAI_MODEL=gpt-4o-mini`
- Run:
  - Single module: `python3 scripts/generate_module_content.py --slug <slug>`
  - All modules: `python3 scripts/generate_module_content.py --all`
- Tuning:
  - `--max-questions 12 --max-terms 24 --max-scenarios 6` to adjust output sizes.
- Outputs are written under `<slug>/data/`.

Viewing and status
- GitHub Pages serves the site from the repo root. The landing page lists every module folder.
- Each module page uses the shared UI (Flashcards by default, Questions, Scenarios, Content tabs).
- Readiness highlighting:
  - The landing page checks for `data/questions.json` in each module. If found, the module card gets a green border to indicate it’s populated with learning data.

Tips
- Re-run extract with `--force` if the PDF changed: `python3 scripts/extract_content.py --slug <slug> --force`.
- If a module page is still a placeholder, stamp the shared UI across modules: `python3 scripts/sync_modules.py --stamp-index`.
- Content heuristics for section headings are conservative; OCR quality can affect results. Prefer `ocrmypdf` for best text extraction.

Troubleshooting
- `pdftotext not found`: `brew install poppler`.
- OCR errors with `ocrmypdf`: ensure Ghostscript is available via Homebrew.
- Landing page shows no green border: ensure `<slug>/data/questions.json` exists (and reload); Flashcards and Scenarios panels require `terms.json` and `scenarios.json` respectively.

