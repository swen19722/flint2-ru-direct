#!/usr/bin/env python3
"""Build a short Happ routing link + a compact custom geosite from the same
Russian domain list and RoutingA policy used by Flint 2. Standard library only.
No private VLESS credentials are stored or published.
"""
from __future__ import annotations

import base64
import csv
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "happ"
GEOSITE_UPSTREAM = "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat"
GEOIP_URL = "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat"
GEOSITE_URL = "https://raw.githubusercontent.com/swen19722/flint2-ru-direct/main/happ/geosite.dat"
TAG = "FLINT2-RU-DIRECT"
RULE = re.compile(r"^\s*(domain|ip)\((.+)\)\s*->\s*(direct|proxy)\s*$")
VALID = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


def varint(n: int) -> bytes:
    result = bytearray()
    while n > 127:
        result.append((n & 127) | 128)
        n >>= 7
    result.append(n)
    return bytes(result)


def read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    for shift in range(0, 70, 7):
        if pos >= len(data):
            raise ValueError("Truncated protobuf varint")
        byte = data[pos]
        pos += 1
        result |= (byte & 127) << shift
        if not (byte & 128):
            return result, pos
    raise ValueError("Invalid protobuf varint")


def fields(data: bytes):
    pos = 0
    while pos < len(data):
        tag, pos = read_varint(data, pos)
        if not tag:
            raise ValueError("Invalid protobuf field")
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            _, pos = read_varint(data, pos)
            yield number, wire, None
        elif wire == 1:
            pos += 8
            if pos > len(data):
                raise ValueError("Truncated protobuf field")
            yield number, wire, None
        elif wire == 2:
            size, pos = read_varint(data, pos)
            end = pos + size
            if end > len(data):
                raise ValueError("Truncated protobuf message")
            yield number, wire, data[pos:end]
            pos = end
        elif wire == 5:
            pos += 4
            if pos > len(data):
                raise ValueError("Truncated protobuf field")
            yield number, wire, None
        else:
            raise ValueError(f"Unknown protobuf wire type {wire}")


def bytes_field(number: int, value: bytes) -> bytes:
    return varint(number * 8 + 2) + varint(len(value)) + value


def custom_geosite(domains: list[str]) -> bytes:
    # routercommon.GeoSite{country_code:TAG, domain: [{type:RootDomain(2), value:...}]}
    entry = bytearray(bytes_field(1, TAG.encode("ascii")))
    for domain in domains:
        rule = bytes_field(2, domain.encode("ascii")) + b"\x08\x02"
        entry += bytes_field(2, rule)
    return bytes_field(1, bytes(entry))


def source_geosite() -> bytes:
    req = Request(GEOSITE_UPSTREAM, headers={"User-Agent": "flint2-happ-builder/1.0"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=60) as response:
                data = response.read(30_000_001)
            if not (100_000 < len(data) <= 30_000_000):
                raise ValueError(f"Unexpected upstream geosite size: {len(data)}")
            return data
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise RuntimeError(f"Upstream geosite unavailable: {exc}") from exc
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def policy_rules():
    result = {"direct": {"domain": [], "ip": []}, "proxy": {"domain": [], "ip": []}}
    for line in (ROOT / "ru-direct-v2raya.rules.txt").read_text(encoding="utf-8-sig").splitlines():
        match = RULE.fullmatch(line)
        if not match:
            continue
        kind, values, direction = match.groups()
        for value in next(csv.reader([values], skipinitialspace=True)):
            value = value.strip()
            if kind == "domain":
                value = re.sub(r"^(geosite|domain|full|regexp):\s*", r"\1:", value)
            if value and value not in result[direction][kind]:
                result[direction][kind].append(value)
    if len(result["proxy"]["domain"]) < 20 or "geosite:category-ru" not in result["direct"]["domain"]:
        raise ValueError("RoutingA does not contain expected RU/proxy rules")
    return result


def trimmed_geosite(upstream: bytes, groups: set[str], domains: list[str]) -> bytes:
    chosen = {}
    count = 0
    for number, wire, entry in fields(upstream):
        if number != 1 or wire != 2 or entry is None:
            continue
        count += 1
        category = next((value.decode("ascii").upper()
                         for key, w, value in fields(entry)
                         if key == 1 and w == 2 and value is not None), None)
        if category in groups:
            if category in chosen:
                raise ValueError(f"Duplicate upstream category {category}")
            chosen[category] = bytes_field(1, entry)
    if count < 100:
        raise ValueError("Unexpectedly few upstream geosite entries")
    missing = groups.difference(chosen)
    if missing:
        raise ValueError("Upstream geosite missing: " + ", ".join(sorted(missing)))
    content = b"".join(chosen[name] for name in sorted(chosen)) + custom_geosite(domains)
    if len(content) < 1000:
        raise ValueError("Unexpectedly small output")
    return content


def write_if_changed(path: Path, content: bytes) -> bool:
    if path.exists() and path.read_bytes() == content:
        return False
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(content)
    os.replace(temp, path)
    return True


def main():
    domains = [d.strip() for d in (ROOT / "ru-direct-extended.domains.txt").read_text(encoding="utf-8-sig").splitlines() if d.strip()]
    if len(domains) < 1000 or domains != sorted(set(domains)) or not all(VALID.fullmatch(d) for d in domains):
        raise ValueError("Invalid or suspiciously short RU domain list")
    rules = policy_rules()
    groups = {x.split(":", 1)[1].split("@", 1)[0].upper()
              for direction in ("direct", "proxy")
              for x in rules[direction]["domain"] if x.startswith("geosite:")}
    geodata = trimmed_geosite(source_geosite(), groups, domains)
    OUT.mkdir(parents=True, exist_ok=True)
    data_changed = write_if_changed(OUT / "geosite.dat", geodata)
    timestamp = str(int(time.time())) if data_changed else ""
    profile_path = OUT / "Happ_RU_Direct_Kazan_NL.json"
    if not data_changed and profile_path.exists():
        try:
            timestamp = str(json.loads(profile_path.read_text(encoding="utf-8")).get("LastUpdated", ""))
        except (ValueError, OSError):
            pass
    domain_set = set(domains)
    direct_sites = ["geosite:flint2-ru-direct"] + [
        value for value in rules["direct"]["domain"]
        if value.startswith("geosite:") or (value.startswith("domain:") and value[7:] not in domain_set)
    ]
    profile = {
        "Name": "RU-DIRECT-KAZAN",
        "GlobalProxy": True,
        "RouteOrder": "block-proxy-direct",
        "DomainStrategy": "IPIfNonMatch",
        "Geositeurl": GEOSITE_URL,
        "Geoipurl": GEOIP_URL,
        "LastUpdated": timestamp,
        "DirectSites": direct_sites,
        "DirectIp": rules["direct"]["ip"],
        "ProxySites": rules["proxy"]["domain"],
        "ProxyIp": rules["proxy"]["ip"],
        "BlockSites": [],
        "BlockIp": [],
    }
    text = json.dumps(profile, indent=2, ensure_ascii=False) + "\n"
    deeplink = "happ://routing/onadd/" + base64.b64encode(
        json.dumps(profile, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).decode("ascii") + "\n"
    write_if_changed(profile_path, text.encode("utf-8"))
    write_if_changed(OUT / "Happ_Import_Link.txt", deeplink.encode("ascii"))
    print(f"Happ: {len(domains)} RU domains, {len(groups)} geosite groups, {len(geodata)} bytes; link {len(deeplink)} characters")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
