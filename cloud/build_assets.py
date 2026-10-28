#!/usr/bin/env python3
"""Build the base-path-aware Cloudflare static bundle from app/static."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "static"
OUTPUT = ROOT / "cloud" / "public"
BASE = "/demos/vedomost"
NOTICE_STYLE = """
.demo-notice {
  margin: 0;
  padding: 0.45rem 1rem;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  background: var(--surface);
  font-size: 0.78rem;
  text-align: center;
}
"""


def rewrite_html(text: str) -> str:
    # Prefix page and asset links while leaving external URLs alone.
    text = re.sub(
        r'(?P<attr>\b(?:href|src)=["\'])/(?!demos/vedomost/)(?P<path>[^"\']*)',
        lambda m: f"{m['attr']}{BASE}/{m['path']}" if m["path"] else f"{m['attr']}{BASE}/",
        text,
    )
    # Load session setup before currency.js and app.js can call the API.
    text = text.replace(
        f'<script src="{BASE}/static/i18n.js" defer></script>',
        f'<script src="{BASE}/static/i18n.js" defer></script>\n'
        f'    <script src="{BASE}/frontend.js" defer></script>',
    )
    # Replace the source notice with cloud-hosted language text before documents render.
    text = text.replace(
        f'<script src="{BASE}/static/legal-content.js" defer></script>',
        f'<script src="{BASE}/static/legal-content.js" defer></script>\n'
        f'    <script src="{BASE}/legal-content.js" defer></script>',
    )
    return text


def rewrite_asset(path: Path, content: str) -> str:
    if path.suffix in {".html", ".css", ".js"}:
        content = content.replace('"/static/', f'"{BASE}/static/')
        content = content.replace("'/static/", f"'{BASE}/static/")
    if path.suffix == ".html":
        content = rewrite_html(content)
    if path.name == "document.js":
        for route in ("openapi.json", "license.txt", "third-party-notices.txt"):
            content = content.replace(f'"/{route}"', f'"{BASE}/{route}"')
    return content


def build() -> None:
    modules = ROOT / "cloud" / "src"
    modules.mkdir(exist_ok=True)
    for filename in ("worker.py", "domain.py"):
        shutil.copy2(ROOT / "cloud" / filename, modules / filename)
    shutil.copy2(ROOT / "app" / "exchange_rates.py", modules / "fx_source.py")
    if not SOURCE.is_dir():
        raise SystemExit(f"Static source directory not found: {SOURCE}")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(SOURCE, OUTPUT)

    for path in OUTPUT.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".css", ".js"}:
            source_path = SOURCE / path.relative_to(OUTPUT)
            path.write_text(
                rewrite_asset(source_path, path.read_text(encoding="utf-8")),
                encoding="utf-8",
            )

    with (OUTPUT / "style.css").open("a", encoding="utf-8") as stylesheet:
        stylesheet.write("\n" + NOTICE_STYLE)

    shutil.copy2(ROOT / "LICENSE.txt", OUTPUT / "license.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", OUTPUT / "third-party-notices.txt")
    sys.path.insert(0, str(ROOT))
    from app.main import create_app

    schema = create_app().openapi()
    schema["servers"] = [{"url": BASE}]
    (OUTPUT / "openapi.json").write_text(json.dumps(schema), encoding="utf-8")
    shutil.copy2(ROOT / "cloud" / "frontend.js", OUTPUT / "frontend.js")
    shutil.copy2(ROOT / "cloud" / "legal-content.js", OUTPUT / "legal-content.js")
    shutil.copy2(ROOT / "app" / "exchange_rates.py", ROOT / "cloud" / "fx_source.py")
    verify()


def verify() -> None:
    """Fail the build if a generated page can escape its configured base path."""
    for path in OUTPUT.glob("*.html"):
        content = path.read_text(encoding="utf-8")
        for match in re.finditer(r'\b(?:href|src)=["\'](/[^"\']*)', content):
            value = match.group(1)
            if not value.startswith(f"{BASE}/"):
                raise SystemExit(f"Unprefixed local link in {path.name}: {value}")
        if f'src="{BASE}/frontend.js"' not in content:
            raise SystemExit(f"Missing session bootstrap in {path.name}")
        if path.name != "index.html" and f'src="{BASE}/legal-content.js"' not in content:
            raise SystemExit(f"Missing cloud legal text in {path.name}")
    if not (OUTPUT / "license.txt").is_file():
        raise SystemExit("Missing generated license.txt")
    if not (OUTPUT / "third-party-notices.txt").is_file():
        raise SystemExit("Missing generated third-party-notices.txt")
    document = (OUTPUT / "document.js").read_text(encoding="utf-8")
    for route in ("openapi.json", "license.txt", "third-party-notices.txt"):
        if f'"{BASE}/{route}"' not in document:
            raise SystemExit(f"Unprefixed generated document link: /{route}")


if __name__ == "__main__":
    build()
