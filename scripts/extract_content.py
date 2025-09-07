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

    # Filter out empty sections
    sections = [s for s in sections if s["paragraphs"] or s["heading"]]
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
    extract_text(pdf, raw_txt)
    text = raw_txt.read_text(encoding='utf-8', errors='ignore')
    sections = build_sections(text)
    # Derive a display title from slug
    title = " ".join(w.capitalize() if w not in {'and','of','the','to','in'} else w for w in slug.replace('-', ' ').split())
    write_json(sections_json, sections)
    write_json(meta_json, {"title": title, "slug": slug})
    print(f"  -> Wrote {sections_json.relative_to(ROOT)} ({len(sections)} sections)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="Process only a single module by slug")
    args = parser.parse_args()

    ensure_pdftotext()

    if args.slug:
        mod_dir = ROOT / args.slug
        if not is_module_dir(mod_dir):
            raise SystemExit(f"Not a module or missing PDF: {args.slug}")
        process_module(mod_dir)
    else:
        mods = list_modules(ROOT)
        if not mods:
            print("No modules found.")
            return
        for mod in mods:
            process_module(mod)

if __name__ == "__main__":
    main()

