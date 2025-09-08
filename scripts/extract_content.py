#!/usr/bin/env python3
"""
Extract text from module PDFs into per-module content and build simple sections.

Outputs per module (in <slug>/content/):
- raw.txt: full extracted text
- sections.json: [{"heading": str, "paragraphs": [str, ...]}]
- meta.json: {"title": str, "slug": str}

Usage:
  python3 scripts/extract_content.py               # process all modules found
  python3 scripts/extract_content.py --slug access-to-housing

Requires:
- pdftotext (Xpdf/Poppler). On macOS: `brew install poppler`.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
from pathlib import Path
from subprocess import CalledProcessError, run

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

# Acronyms to preserve capitalization in headings
ACRONYMS = { 'HIPAA', 'HMIS', 'PSH', 'HUD' }

def is_module_dir(d: Path) -> bool:
    if not d.is_dir():
        return False
    if d.name in EXCLUDE_DIRS or d.name.startswith('.'):
        return False
    pdf = d / f"{d.name}.pdf"
    return pdf.exists()

def list_modules(root: Path) -> list[Path]:
    return sorted([d for d in root.iterdir() if is_module_dir(d)])

def ensure_pdftotext() -> None:
    if shutil.which('pdftotext') is None:
        raise SystemExit(
            "pdftotext not found. Install Poppler (e.g., `brew install poppler`) and re-run."
        )

def extract_text(pdf: Path, out_txt: Path) -> None:
    # Use pdftotext to write directly to file; -layout keeps columns somewhat sensible
    cmd = [
        'pdftotext',
        '-enc', 'UTF-8',
        '-eol', 'unix',
        '-nopgbrk',
        '-layout',
        str(pdf),
        str(out_txt),
    ]
    try:
        run(cmd, check=True, capture_output=True)
    except CalledProcessError as e:
        raise SystemExit(f"Failed to extract {pdf.name}: {e.stderr.decode('utf-8', 'ignore')}")

def extract_text_to_str(pdf: Path, mode: str = "") -> str:
    args = ['pdftotext']
    if mode:
        args.extend([mode])
    args.extend(['-enc','UTF-8','-eol','unix','-nopgbrk', str(pdf), '-'])
    try:
        p = run(args, check=True, capture_output=True)
        return p.stdout.decode('utf-8', 'ignore')
    except CalledProcessError:
        return ""

def has_text_layer(pdf: Path) -> bool:
    sample = extract_text_to_str(pdf)
    # Remove form feed and whitespace
    content = re.sub(r"\s+", "", sample.replace("\f", ""))
    return len(content) >= 10

def ensure_ocr_tools() -> str | None:
    """Return available OCR tool: 'ocrmypdf', 'tesseract', or None."""
    if shutil.which('ocrmypdf'):
        return 'ocrmypdf'
    if shutil.which('tesseract') and shutil.which('pdftoppm'):
        return 'tesseract'
    return None

def ocr_pdf_into_text(pdf: Path, out_txt: Path) -> None:
    tool = ensure_ocr_tools()
    if not tool:
        raise SystemExit(
            "PDF appears to be image-only and no OCR tools found. Install either:\n"
            "  - ocrmypdf (recommended): brew install ocrmypdf\n"
            "  - or tesseract + poppler: brew install tesseract poppler\n"
        )
    if tool == 'ocrmypdf':
        tmp_pdf = out_txt.with_suffix('.ocr.pdf')
        # Use sidecar to write text directly; use only one of the mutually exclusive flags.
        cmd = [
            'ocrmypdf',
            '--force-ocr',             # always rasterize/ocr to ensure text output
            '--output-type', 'pdf',
            '--sidecar', str(out_txt), # write extracted text directly here
            str(pdf), str(tmp_pdf)
        ]
        run(cmd, check=True)
        try:
            tmp_pdf.unlink()
        except Exception:
            pass
    else:
        # Fallback: rasterize pages and OCR with tesseract, concatenate
        tmp_dir = out_txt.parent / '.ocr_pages'
        tmp_dir.mkdir(exist_ok=True)
        try:
            # Generate page images
            run(['pdftoppm', '-r', '300', '-png', str(pdf), str(tmp_dir / 'page')], check=True)
            # Concatenate OCR output
            out_txt.write_text('', encoding='utf-8')
            for img in sorted(tmp_dir.glob('page-*.png')):
                p = run(['tesseract', str(img), 'stdout', '-l', 'eng', '--psm', '3'], check=True, capture_output=True)
                text = p.stdout.decode('utf-8', 'ignore')
                with out_txt.open('a', encoding='utf-8') as f:
                    f.write(text)
                    f.write('\n\f\n')
        finally:
            # Cleanup images
            for img in tmp_dir.glob('page-*.png'):
                try:
                    img.unlink()
                except Exception:
                    pass
            try:
                tmp_dir.rmdir()
            except Exception:
                pass

HEADING_MAX_LEN = 90

def is_heading(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # All caps words and short
    letters = [c for c in s if c.isalpha()]
    if letters and len(s) <= HEADING_MAX_LEN and all(c.isupper() for c in letters):
        return True
    # Numbered headings like 1., 1.2, I., A., etc.
    if re.match(r"^(\d+|[IVXLC]+|[A-Z])([.)])\s+\S", s):
        return True
    if re.match(r"^\d+(?:\.\d+)*\s+\S", s):
        return True
    # Title case heuristic (few words, mostly capitalized initials)
    words = s.split()
    if 1 <= len(words) <= 12:
        caps = sum(1 for w in words if re.match(r"^[A-Z]", w))
        if caps >= max(2, int(0.6 * len(words))):
            return True
    return False

def split_paragraphs(text: str) -> list[str]:
    # Normalize multiple blank lines, then split blocks
    blocks = re.split(r"\n\s*\n+", text.strip())
    cleaned = []
    for b in blocks:
        lines = [ln.strip() for ln in b.splitlines()]
        # Re-join single wrapped lines while preserving sentence breaks
        paragraph = re.sub(r"\s+", " ", " ".join(lines)).strip()
        if paragraph:
            cleaned.append(paragraph)
    return cleaned

def build_sections(text: str) -> list[dict]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    # Group into raw blocks split by blank lines
    blocks: list[list[str]] = []
    current: list[str] = []
    for ln in lines:
        if ln.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(ln)
    if current:
        blocks.append(current)

    sections: list[dict] = []
    current_section = {"heading": None, "paragraphs": []}

    for block in blocks:
        first = block[0].strip()
        if is_heading(first):
            # Start a new section
            if current_section["heading"] or current_section["paragraphs"]:
                sections.append(current_section)
            current_section = {"heading": re.sub(r"\s+", " ", first), "paragraphs": []}
            rest = "\n".join(block[1:])
            paras = split_paragraphs(rest)
            current_section["paragraphs"].extend(paras)
        else:
            # Continue current section paragraphs
            paras = split_paragraphs("\n".join(block))
            if not current_section["heading"]:
                current_section["heading"] = "Introduction"
            current_section["paragraphs"].extend(paras)

    if current_section["heading"] or current_section["paragraphs"]:
        sections.append(current_section)

    # Normalize/clean headings and drop nav crumbs
    cleaned_sections: list[dict] = []
    for s in sections:
        heading = s.get("heading")
        if heading:
            h = heading.strip()
            # Drop navigation crumbs like: "Previous: X Next: Y"
            if re.search(r"\bPrevious:\b", h) and re.search(r"\bNext:\b", h):
                # skip this section entirely
                continue
            # Strip trailing revision metadata
            h = re.sub(r"\s*\|\s*Last\s+Revision.*$", "", h, flags=re.I)
            # Title case, preserve some acronyms and FY####
            words = h.split()
            norm_words = []
            for w in words:
                bare = w.rstrip(':')
                up = bare.upper()
                if re.fullmatch(r"FY\d{2,4}", up) or up in ACRONYMS:
                    nw = up
                else:
                    nw = bare.capitalize()
                if w.endswith(':'):
                    nw += ':'
                norm_words.append(nw)
            s["heading"] = re.sub(r"\s+", " ", " ".join(norm_words)).strip()
        if s.get("heading") or s.get("paragraphs"):
            cleaned_sections.append(s)
    sections = cleaned_sections
    return sections

def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding='utf-8')

def process_module(mod_dir: Path) -> None:
    slug = mod_dir.name
    pdf = mod_dir / f"{slug}.pdf"
    content_dir = mod_dir / 'content'
    content_dir.mkdir(exist_ok=True)
    raw_txt = content_dir / 'raw.txt'
    sections_json = content_dir / 'sections.json'
    meta_json = content_dir / 'meta.json'

    print(f"Extracting: {pdf.relative_to(ROOT)}")
    # First try native text extraction
    extract_text(pdf, raw_txt)
    text = raw_txt.read_text(encoding='utf-8', errors='ignore')
    if len(text.strip()) < 10:
        # Try OCR if no text layer
        print("  -> No text layer detected; attempting OCR...")
        ocr_pdf_into_text(pdf, raw_txt)
        text = raw_txt.read_text(encoding='utf-8', errors='ignore')
    sections = build_sections(text)
    # Derive a display title from slug
    title = " ".join(w.capitalize() if w not in {'and','of','the','to','in'} else w for w in slug.replace('-', ' ').split())
    write_json(sections_json, sections)
    write_json(meta_json, {"title": title, "slug": slug})
    print(f"  -> Wrote {sections_json.relative_to(ROOT)} ({len(sections)} sections)")

def is_up_to_date(pdf: Path, raw_txt: Path, sections_json: Path) -> bool:
    if not raw_txt.exists() or not sections_json.exists():
        return False
    try:
        return raw_txt.stat().st_mtime >= pdf.stat().st_mtime and sections_json.stat().st_mtime >= pdf.stat().st_mtime
    except FileNotFoundError:
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="Process only a single module by slug")
    parser.add_argument("--force", action="store_true", help="Rebuild even if outputs are up-to-date")
    args = parser.parse_args()

    ensure_pdftotext()

    if args.slug:
        mod_dir = ROOT / args.slug
        if not is_module_dir(mod_dir):
            raise SystemExit(f"Not a module or missing PDF: {args.slug}")
        # Check freshness
        if not args.force:
            raw = (mod_dir / 'content' / 'raw.txt')
            sec = (mod_dir / 'content' / 'sections.json')
            pdf = mod_dir / f"{mod_dir.name}.pdf"
            if is_up_to_date(pdf, raw, sec):
                print(f"Skipping (up-to-date): {mod_dir.name}")
                return
        process_module(mod_dir)
    else:
        mods = list_modules(ROOT)
        if not mods:
            print("No modules found.")
            return
        for mod in mods:
            if not args.force:
                raw = (mod / 'content' / 'raw.txt')
                sec = (mod / 'content' / 'sections.json')
                pdf = mod / f"{mod.name}.pdf"
                if is_up_to_date(pdf, raw, sec):
                    print(f"Skipping (up-to-date): {mod.name}")
                    continue
            process_module(mod)

if __name__ == "__main__":
    main()
