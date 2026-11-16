#!/usr/bin/env python3
"""Generate v2rayA RoutingA rules from the existing GL.iNet direct-domain list.

No network access. Only writes the new RoutingA file. The original domain list
and its generation script are left untouched.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

SOURCE_DEFAULT = Path("ru-direct-extended.domains.txt")
OUTPUT_DEFAULT = Path("ru-direct-v2raya.rules.txt")
HEADER = "# Generated RoutingA rules for v2rayA 2.5.x — DO NOT EDIT BY HAND\n# Source: ru-direct-extended.domains.txt in this repository.\n# Default: proxy; listed Russian destinations: direct.\n# Rules are evaluated top-to-bottom; specific proxy exceptions MUST stay first.\ndefault: proxy\n\n# LAN / private addresses must not be sent through VLESS\ndomain(geosite:private) -> direct\nip(geoip:private) -> direct\n\n# Russian preset: explicit proxy exceptions (keep before the RU bypass list)\n# Google / YouTube .ru domains\ndomain(domain: google.ru, domain: youtube.ru) -> proxy\n# Global services\ndomain(geosite:google, geosite:youtube) -> proxy\ndomain(geosite:telegram) -> proxy\ndomain(geosite:facebook, geosite:instagram) -> proxy\ndomain(geosite:twitter, geosite:discord) -> proxy\ndomain(geosite:openai) -> proxy\ndomain(geosite:spotify, geosite:netflix) -> proxy\ndomain(domain: whatsapp.com, domain: whatsapp.net, domain: wa.me) -> proxy\n# Telegram IPv4 networks\nip(91.108.56.0/22, 91.108.4.0/22, 91.108.8.0/22) -> proxy\nip(91.108.16.0/22, 91.108.12.0/22, 149.154.160.0/20) -> proxy\nip(91.105.192.0/23, 91.108.20.0/22, 185.76.151.0/24) -> proxy\n# Telegram IPv6 networks\nip(2001:b28:f23d::/48, 2001:b28:f23f::/48, 2001:67c:4e8::/48) -> proxy\nip(2001:b28:f23c::/48, 2a0a:f280::/32) -> proxy\n# RU-domain exceptions that need a proxy\ndomain(domain: abook-club.ru, domain: amdm.ru, domain: anime-portal.su) -> proxy\ndomain(domain: animespirit.ru, domain: anistars.ru) -> proxy\ndomain(domain: baikal-journal.ru, domain: bestchange.ru, domain: colta.ru) -> proxy\ndomain(domain: coomer.su, domain: doramalive.ru) -> proxy\ndomain(domain: ej.ru, domain: fn-volga.ru, domain: grani.ru) -> proxy\ndomain(domain: itsmycity.ru, domain: jut.su) -> proxy\ndomain(domain: kara.su, domain: kasparov.ru, domain: kemono.su) -> proxy\ndomain(domain: mangahub.ru, domain: megapeer.ru) -> proxy\ndomain(domain: moscowtimes.ru, domain: newtimes.ru, domain: novayagazeta.ru) -> proxy\ndomain(domain: ohmyswift.ru, domain: paperpaper.ru) -> proxy\ndomain(domain: pimpletv.ru, domain: polit.ru, domain: republic.ru) -> proxy\ndomain(domain: scryde.ru, domain: seasonvar.ru) -> proxy\ndomain(domain: sklatchiki.ru, domain: the-village.ru, domain: theins.ru) -> proxy\ndomain(domain: tvrain.ru, domain: zahav.ru) -> proxy\n# Ukrainian domain zone through VLESS\ndomain(domain: ua) -> proxy\n\n# Personal Russian-domain bypass list from GitHub (__COUNT__ domains)\n"
TAIL = "\n# Russian destinations from the built-in geodata\ndomain(geosite:category-ru) -> direct\nip(geoip:ru) -> direct\n# Additional Russian service domains in the preset\ndomain(domain: 1018213540.rsc.cdn77.org, domain: bitrix.info) -> direct\n# All destinations not matched above follow default: proxy\n"
VALID_DOMAIN = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
MANDATORY = {"mosoblgaz.ru", "mosenergosbyt.ru"}


def build(source: Path) -> str:
    domains = []
    for number, raw in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1):
        domain = raw.strip()
        if not VALID_DOMAIN.fullmatch(domain):
            raise ValueError(f"{source}:{number}: invalid domain {domain!r}")
        domains.append(domain)

    if len(domains) < 1000:
        raise ValueError(f"Suspiciously short source list: {len(domains)} domains")
    if domains != sorted(set(domains)):
        raise ValueError("Source list must be sorted and deduplicated")
    if not MANDATORY.issubset(domains):
        raise ValueError("Mandatory Russian direct domains are missing")

    rules = []
    for i in range(0, len(domains), 8):
        batch = domains[i:i+8]
        rules.append("domain(" + ", ".join("domain: " + item for item in batch) + ") -> direct")
    result = HEADER.replace("__COUNT__", str(len(domains))) + "\n".join(rules) + "\n" + TAIL

    # Avoid publishing a partial, malformed or unexpectedly empty policy.
    if not result.startswith("# Generated RoutingA rules") or result.count("default: proxy") < 1:
        raise ValueError("Missing RoutingA header")
    if "domain(domain: mosoblgaz.ru" not in result and "domain: mosoblgaz.ru" not in result:
        raise ValueError("Mandatory bypass rule missing")
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    p.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = p.parse_args()
    try:
        content = build(args.source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.output.with_name(args.output.name + ".tmp")
        tmp.write_text(content, encoding="utf-8", newline="\n")
        os.replace(tmp, args.output)
        print(f"OK: RoutingA {content.count(' -> direct')} direct rules -> {args.output}")
        return 0
    except (ValueError, UnicodeError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
