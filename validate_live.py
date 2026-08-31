"""Validate PAWIND01 V1 output before it can replace a public live field."""
from __future__ import annotations

import gzip
import json
import struct
import sys
from datetime import datetime, timezone
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
    try:
        temperature = manifest["regions"]["iberia"]["temperatureFields"][0]
        valid = datetime.fromisoformat(field["validTime"]).astimezone(timezone.utc)
        delta = (valid - datetime.now(timezone.utc)).total_seconds()
        if not (-2 * 60 * 60 <= delta <= 90 * 60):
            fail(f"candidate is outside ICON-EU LIVE window: validTime={field['validTime']}")
    except (KeyError, IndexError, TypeError, ValueError) as error:
        fail(f"temperature/freshness contract: {error}")
    temperature_asset = root / temperature["url"]
    if temperature["url"] != "iberia.patemp.gz" or not temperature_asset.is_file() or temperature_asset.stat().st_size != temperature["size"]:
        fail("PATEMP size does not match manifest")
    if temperature.get("forecastHour") != field["forecastHour"] or temperature.get("validTime") != field["validTime"]:
        fail("wind and temperature do not share forecastHour/validTime")
    raw_temperature = gzip.decompress(temperature_asset.read_bytes())
    if raw_temperature[:8] != b"PATEMP01" or raw_temperature[8:11] != bytes((1, 1, 2)):
        fail("PATEMP01 magic/version/model/encoding")
    tw, th = struct.unpack_from("<HH", raw_temperature, 84)
    if tw != width or th != height or len(raw_temperature) != 96 + tw * th * 2:
        fail("PATEMP01 payload dimensions")
    print(f"valid PATEMP01: {tw}x{th}, {temperature_asset.stat().st_size} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_live.py <directory>")
    main(sys.argv[1])

