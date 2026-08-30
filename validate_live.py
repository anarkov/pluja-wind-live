"""Validate PAWIND01 V1 output before it can replace a public live field."""
from __future__ import annotations

import gzip
import json
import struct
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"LIVE validation failed: {message}")


def main(directory: str) -> None:
    root = Path(directory)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        fail("manifest.json missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        assert manifest["version"] == 1
        field = manifest["regions"]["iberia"]["fields"][0]
        assert isinstance(field["forecastHour"], int)
        assert field["url"] == "iberia.pawind.gz"
        assert field["size"] > 0
    except (AssertionError, KeyError, IndexError, TypeError) as error:
        fail(f"manifest contract: {error}")
    asset = root / field["url"]
    if not asset.is_file() or asset.stat().st_size != field["size"]:
        fail("PAWIND size does not match manifest")
    try:
        raw = gzip.decompress(asset.read_bytes())
        if raw[:8] != b"PAWIND01" or raw[8:11] != bytes((1, 1, 2)):
            fail("PAWIND01 magic/version/model/encoding")
        width, height = struct.unpack_from("<HH", raw, 84)
        if width < 2 or height < 2 or len(raw) != 96 + width * height * 4:
            fail("PAWIND01 payload dimensions")
    except OSError as error:
        fail(f"gzip: {error}")
    print(f"valid PAWIND01: {width}x{height}, {asset.stat().st_size} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_live.py <directory>")
    main(sys.argv[1])
