#!/usr/bin/env python3
"""Build a plain list for GL.iNet VPN Dashboard / Exclude ... / Subscription URL.

Sources: ru-direct standard + Tachyon ru_only_inside + extra-domains.txt.
On failed download or validation, do NOT overwrite the last good output.
Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen

SOURCES = (
    ("ru-direct", "https://raw.githubusercontent.com/kyoresuas/ru-direct/release/ru-standard.domains.txt", 1000),
    ("ru-only-inside", "https://raw.githubusercontent.com/Dushnilin/tachyon-lists/main/release/domains/ru_only_inside.lst", 100),
)
MANDATORY = {"mosoblgaz.ru", "mosenergosbyt.ru"}
VALID_DOMAIN = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


def parse_domains(source: str, text: str) -> set[str]:
    result: set[str] = set()
    for line_no, raw in enumerate(text.splitlines(), 1):
        domain = raw.split("#", 1)[0].strip().rstrip(".").lower()
        if not domain:
            continue
        try:
            domain = domain.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError(f"{source}:{line_no}: bad IDN: {domain!r}") from exc
        if not VALID_DOMAIN.fullmatch(domain):
            raise ValueError(f"{source}:{line_no}: invalid domain: {domain!r}")
        result.add(domain)
    return result


def fetch_source(name: str, url: str, min_size: int) -> set[str]:
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "flint2-ru-direct-builder/1.0", "Accept": "text/plain"})
            with urlopen(req, timeout=25) as response:
                content = response.read(400_001)
            if len(content) > 400_000:
                raise RuntimeError("unexpectedly large source")
            domains = parse_domains(name, content.decode("utf-8-sig"))
            if len(domains) < min_size:
                raise RuntimeError(f"too few domains: {len(domains)} < {min_size}")
            print(f"{name}: {len(domains)} unique domains")
            return domains
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            if attempt == 2:
                raise RuntimeError(f"Cannot safely update {name}: {exc}") from exc
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--custom", type=Path, default=Path("extra-domains.txt"))
    parser.add_argument("--output", type=Path, default=Path("ru-direct-extended.domains.txt"))
    args = parser.parse_args()
    try:
        merged = parse_domains(str(args.custom), args.custom.read_text(encoding="utf-8-sig"))
        for name, url, minimum in SOURCES:
            merged.update(fetch_source(name, url, minimum))
        if len(merged) < 1000 or not MANDATORY.issubset(merged):
            raise RuntimeError("Generated result missing essential domains or too small")
        output = "\n".join(sorted(merged)) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.output.with_name(args.output.name + ".tmp")
        tmp.write_text(output, encoding="utf-8", newline="\n")
        os.replace(tmp, args.output)
        print(f"OK: {len(merged)} domains -> {args.output}")
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
