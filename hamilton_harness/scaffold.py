"""Write a starter pack for a new company.

The starter is a small pack that already validates and already passes its own
fake customers, so the first edit a business makes is to a working rep.
"""

from __future__ import annotations

import json
from pathlib import Path

from hamilton_harness.pack.loader import PackError

TEMPLATE = Path(__file__).parent / "templates" / "starter"


def _fill(text: str, *, company: str, rep: str, quoted: bool) -> str:
    """Put the company and rep names into one template file."""

    def value(raw: str) -> str:
        # A JSON string is a valid YAML string, so a name with a colon or a quote is safe.
        return json.dumps(raw, ensure_ascii=False) if quoted else raw

    lines = {
        "__DISCLOSURE__": f"I'm {rep}, {company}'s AI assistant. I can get a person any time.",
        "__OFF_TOPIC__": f"I can only help with {company}. What do you need?",
        "__GREETING__": f"Hi, I'm {rep} from {company}. How can I help?",
        "__COMPANY__": company,
        "__REP__": rep,
    }
    for placeholder, raw in lines.items():
        text = text.replace(placeholder, value(raw))
    # Inside a block of prose the name is written as it is, never quoted.
    return text.replace("__COMPANY_PLAIN__", company)


def write_starter_pack(dest: str | Path, *, company: str, rep: str = "Sam") -> list[Path]:
    """Create a starter pack at `dest` and return the files written."""
    company, rep = company.strip(), rep.strip()
    if not company:
        raise PackError("a starter pack needs a company name")
    if not rep:
        raise PackError("a starter pack needs a name for the rep")
    for name in (company, rep):
        if "\n" in name or "__" in name:
            raise PackError(f"{name!r} cannot be used as a name")

    root = Path(dest).expanduser()
    if root.exists() and not root.is_dir():
        raise PackError(f"{root} exists and is not a folder")
    if root.is_dir() and any(root.iterdir()):
        raise PackError(f"{root} is not empty, so nothing was written")

    written: list[Path] = []
    for source in sorted(TEMPLATE.rglob("*")):
        if not source.is_file():
            continue
        target = root / source.relative_to(TEMPLATE)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8")
        quoted = source.suffix == ".yaml"
        target.write_text(_fill(text, company=company, rep=rep, quoted=quoted), encoding="utf-8")
        written.append(target)
    return written
