#!/usr/bin/env python3
"""
Generate questions, terms, and scenarios for a module using AI from extracted sections.

Inputs per module:
  <slug>/content/sections.json (from scripts/extract_content.py)

Outputs per module (by default):
  <slug>/data/questions.json
  <slug>/data/terms.json
  <slug>/data/scenarios.json

Two modes:
  - Online (default): calls OpenAI API. Requires OPENAI_API_KEY. Optional OPENAI_MODEL (default: gpt-4o-mini).
  - Offline prompt export: --offline writes three prompt files under <slug>/prompts/ for manual use in ChatGPT, then paste results back.

Usage examples:
  python3 scripts/generate_module_content.py --slug access-to-housing
  python3 scripts/generate_module_content.py --slug access-to-housing --offline
  python3 scripts/generate_module_content.py --all --max-questions 12 --max-terms 24 --max-scenarios 6
"""
from __future__ import annotations
import argparse
import json
import os
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_sections(slug: str) -> list[dict]:
    sec_path = ROOT / slug / 'content' / 'sections.json'
    if not sec_path.exists():
        raise SystemExit(f"Missing sections for {slug}: {sec_path}")
    return json.loads(sec_path.read_text(encoding='utf-8'))

def clamp_text(sections: list[dict], max_chars: int = 16000) -> str:
    # Flatten to a readable outline and clamp to max_chars
    parts: list[str] = []
    for s in sections:
        h = s.get('heading') or 'Section'
        parts.append(f"\n# {h}\n")
        for p in (s.get('paragraphs') or [])[:20]:  # avoid flooding
            parts.append(p.strip())
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[TRUNCATED]"
    return text

def build_prompts(slug: str, module_text: str, limits: dict) -> dict[str, str]:
    title = " ".join(w.capitalize() if w not in {'and','of','the','to','in'} else w for w in slug.replace('-', ' ').split())
    base_context = textwrap.dedent(f"""
    You are helping create a training module for staff. Source content below came from the
    policy PDF called "{title}". Generate outputs strictly as compact JSON only. Keep content
    faithful to the source; do not invent details.

    SOURCE CONTENT (outline; may be truncated):
    {module_text}
    """
    ).strip()

    q_prompt = textwrap.dedent(f"""
    {base_context}

    TASK: Create multiple-choice questions JSON with the following shape:
    {{
      "questions": [
        {{
          "id": "q_001",  // unique per module
          "category": "string", // from a relevant section heading
          "text": "Question?",
          "options": {{"A":"...","B":"...","C":"...","D":"..."}},
          "correct": "A|B|C|D",
          "explanation": "One-sentence justification based on the source",
          "difficulty": "Easy|Medium|Hard"
        }}
      ]
    }}
    RULES:
    - Create up to {limits['questions']} questions.
    - Prefer concrete, policy-accurate content.
    - Keep choices concise and non-overlapping.
    - Difficulty should reflect cognitive effort.
    - Output JSON only. No trailing commentary.
    """
    ).strip()

    t_prompt = textwrap.dedent(f"""
    {base_context}

    TASK: Extract key terms and definitions JSON:
    {{
      "terms": [
        {{"term":"...","definition":"...","category":"string"}}
      ]
    }}
    RULES:
    - Create up to {limits['terms']} terms.
    - Definitions must be derived from the source wording when possible.
    - Category should be a nearby or parent section heading.
    - Output JSON only. No extra text.
    """
    ).strip()

    s_prompt = textwrap.dedent(f"""
    {base_context}

    TASK: Create scenario-based questions JSON:
    {{
      "scenarios": [
        {{
          "id":"s_001",
          "title":"Short scenario title",
          "description":"1-2 sentence realistic situation",
          "question":"What should staff do?",
          "options":{{"A":"...","B":"...","C":"...","D":"..."}},
          "correct":"A|B|C|D",
          "explanation":"One-sentence justification from source",
          "relatedConcepts":["..."],
          "difficulty":"easy|medium|hard"
        }}
      ]
    }}
    RULES:
    - Create up to {limits['scenarios']} scenarios.
    - Situations should match the spirit and constraints of the source.
    - Output JSON only. No extra commentary.
    """
    ).strip()

    return {
        'questions': q_prompt,
        'terms': t_prompt,
        'scenarios': s_prompt,
    }

def write_prompts(slug: str, prompts: dict[str,str]) -> None:
    out_dir = ROOT / slug / 'prompts'
    out_dir.mkdir(exist_ok=True)
    for name, text in prompts.items():
        (out_dir / f'{name}.txt').write_text(text, encoding='utf-8')
    print(f"Wrote prompts to {out_dir}")

def validate_and_write(slug: str, name: str, content: str) -> None:
    # Basic validation; writes to <slug>/data/<name>.json
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise SystemExit(f"{slug} {name}: Response was not valid JSON: {e}")
    # Sanity checks
    if name == 'questions' and 'questions' not in data:
        raise SystemExit(f"{slug} {name}: Missing 'questions' key")
    if name == 'terms' and 'terms' not in data:
        raise SystemExit(f"{slug} {name}: Missing 'terms' key")
    if name == 'scenarios' and 'scenarios' not in data:
        raise SystemExit(f"{slug} {name}: Missing 'scenarios' key")

    out_dir = ROOT / slug / 'data'
    out_dir.mkdir(exist_ok=True)
    (out_dir / f'{name}.json').write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding='utf-8')
    print(f"Wrote {slug}/data/{name}.json")

def call_openai(prompt: str, model: str) -> str:
    # Lazy import to avoid dependency unless used
    try:
        from openai import OpenAI
    except Exception:
        raise SystemExit("Install openai: pip install openai")
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY in your environment.")
    client = OpenAI(api_key=api_key)
    # Use responses API to enforce JSON output
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role":"system","content":"You are a precise educational content generator. Output only JSON."},
            {"role":"user","content":prompt},
        ],
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""

def process_slug(slug: str, offline: bool, limits: dict, model: str) -> None:
    sections = read_sections(slug)
    if not sections:
        print(f"Skipping {slug}: no sections")
        return
    source = clamp_text(sections)
    prompts = build_prompts(slug, source, limits)

    if offline:
        write_prompts(slug, prompts)
        return

    # Online mode: call model and write outputs
    for name in ('questions','terms','scenarios'):
        text = call_openai(prompts[name], model=model)
        validate_and_write(slug, name, text)

def list_module_slugs() -> list[str]:
    slugs: list[str] = []
    for p in ROOT.iterdir():
        if p.is_dir() and (p / f"{p.name}.pdf").exists():
            slugs.append(p.name)
    return sorted(slugs)

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--slug', help='Single module slug to process')
    g.add_argument('--all', action='store_true', help='Process all modules')
    ap.add_argument('--offline', action='store_true', help='Write prompts instead of calling API')
    ap.add_argument('--max-questions', type=int, default=12)
    ap.add_argument('--max-terms', type=int, default=24)
    ap.add_argument('--max-scenarios', type=int, default=6)
    ap.add_argument('--model', default=os.environ.get('OPENAI_MODEL','gpt-4o-mini'))
    args = ap.parse_args()

    limits = {
        'questions': args.max_questions,
        'terms': args.max_terms,
        'scenarios': args.max_scenarios,
    }

    if args.slug:
        process_slug(args.slug, args.offline, limits, args.model)
    else:
        for slug in list_module_slugs():
            process_slug(slug, args.offline, limits, args.model)

if __name__ == '__main__':
    main()

