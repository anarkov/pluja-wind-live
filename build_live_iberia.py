"""Build one PAWIND01 v1 ICON-EU field for Iberia.

Designed for both a local run and GitHub Actions. Output defaults to ``output``;
set D2R_OUTPUT_DIR to generate into an isolated staging directory.
"""
from __future__ import annotations

import bz2
import datetime as dt
import gzip
import html
import json
import os
import re
import struct
import sys
import urllib.request
from pathlib import Path
from live_selection import CompleteField, MAX_FUTURE_SECONDS, MAX_PAST_SECONDS, select_nearest_usable

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
from eccodes import codes_get_array, codes_get_values, codes_grib_new_from_file, codes_release

OUT = Path(os.environ.get("D2R_OUTPUT_DIR", ROOT / "output"))
BASE = "https://opendata.dwd.de/weather/nwp/icon-eu/grib"
RUN_HOURS = (21, 18, 15, 12, 9, 6, 3, 0)
NORTH, SOUTH, WEST, EAST = 45.0, 35.0, -11.0, 5.0
SCALE = 100.0
# ICON-EU is hourly forecast data: retain a nearby past field briefly, but do
# not publish one that is already meteorologically stale.  Keep this aligned
# with Android's IconEuLiveTimePolicy.


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "pluja-wind-live/1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def names_for(run_hour: str, component: str) -> set[str]:
    index = fetch(f"{BASE}/{run_hour}/{component.lower()}/").decode("utf-8", errors="replace")
    return set(html.unescape(value) for value in re.findall(r'href="([^"?]+\.grib2\.bz2)', index))


def discover_pair(now: dt.datetime) -> CompleteField:
    """Discover complete fields from the real directory listings, independent of UTC day boundaries."""
    candidates: list[CompleteField] = []
    expression = re.compile(r"icon-eu_europe_regular-lat-lon_single-level_(\d{8})(\d{2})_(\d{3})_U_10M\.grib2\.bz2")
    listing_failures: list[str] = []
    availability: list[dict[str, int | str]] = []
    for hour in RUN_HOURS:
        hour_text = f"{hour:02d}"
        try:
            u_names = names_for(hour_text, "u_10m")
            v_names = names_for(hour_text, "v_10m")
            t_names = names_for(hour_text, "t_2m")
        except Exception as error:
            listing_failures.append(f"{hour_text}Z:{type(error).__name__}")
            availability.append({"directoryHour": hour_text, "u10": 0, "v10": 0, "t2m": 0, "completeTriplets": 0})
            continue
        complete_for_directory = 0
        for u_name in u_names:
            match = expression.fullmatch(u_name)
            if not match:
                continue
            v_name, t_name = u_name.replace("_U_10M.", "_V_10M."), u_name.replace("_U_10M.", "_T_2M.")
            if v_name not in v_names or t_name not in t_names:
                continue
            complete_for_directory += 1
            run = f"{match.group(1)}{match.group(2)}"
            forecast_hour = int(match.group(3))
            run_at = dt.datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
            candidates.append(CompleteField(run, forecast_hour, run_at + dt.timedelta(hours=forecast_hour),
                f"{BASE}/{hour_text}/u_10m/{u_name}", f"{BASE}/{hour_text}/v_10m/{v_name}", f"{BASE}/{hour_text}/t_2m/{t_name}"))
        availability.append({"directoryHour": hour_text, "u10": len(u_names), "v10": len(v_names), "t2m": len(t_names), "completeTriplets": complete_for_directory})
    try:
        selected = select_nearest_usable(candidates, now)
    except RuntimeError as error:
        raise RuntimeError(f"{error}; completeCandidates={len(candidates)}; listingFailures={','.join(listing_failures) or 'none'}") from error
    nearby = sorted(
        (candidate for candidate in candidates if -MAX_PAST_SECONDS <= (candidate.valid - now).total_seconds() <= MAX_FUTURE_SECONDS),
        key=lambda candidate: (abs((candidate.valid - now).total_seconds()), candidate.valid < now, -candidate.valid.timestamp(), -int(candidate.run)),
    )
    print(json.dumps({"nowUtc": now.isoformat(), "directoryAvailability": availability, "completeCandidates": len(candidates),
                      "topCompleteCandidatesByDistance": [{"run": candidate.run, "forecastHour": candidate.forecast_hour, "validTime": candidate.valid.isoformat(), "deltaSeconds": int((candidate.valid - now).total_seconds()), "completeTriplet": True} for candidate in nearby[:8]],
                      "selected": {"run": selected.run, "forecastHour": selected.forecast_hour, "validTime": selected.valid.isoformat(), "deltaSeconds": int((selected.valid - now).total_seconds()), "completeTriplet": True}, "decision": "PUBLISH_CANDIDATE"}, sort_keys=True))
    return selected


def read_grib(path: Path) -> dict[tuple[float, float], float]:
    with path.open("rb") as handle:
        gid = codes_grib_new_from_file(handle)
        if gid is None:
            raise RuntimeError(f"No GRIB message in {path}")
        try:
            return {(round(float(lat), 6), round(float(lon), 6)): float(value)
                for lat, lon, value in zip(codes_get_array(gid, "latitudes"), codes_get_array(gid, "longitudes"), codes_get_values(gid))
                if SOUTH <= float(lat) <= NORTH and WEST <= float(lon) <= EAST}
        finally:
            codes_release(gid)


def download_and_decode(url: str) -> dict[tuple[float, float], float]:
    compressed = OUT / Path(url).name
    compressed.write_bytes(fetch(url))
    raw_path = compressed.with_suffix("")
    with bz2.open(compressed, "rb") as source, raw_path.open("wb") as destination:
        destination.write(source.read())
    return read_grib(raw_path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    selected = discover_pair(now)
    run, forecast_hour, u_url, v_url, t_url = selected.run, selected.forecast_hour, selected.u_url, selected.v_url, selected.t_url
    u_points, v_points = download_and_decode(u_url), download_and_decode(v_url)
    t_points = download_and_decode(t_url)
    if u_points.keys() != v_points.keys() or u_points.keys() != t_points.keys() or not u_points:
        raise RuntimeError("ICON-EU U/V/T crop is incomplete or inconsistent")
    lats = sorted({latitude for latitude, _ in u_points}, reverse=True)
    lons = sorted({longitude for _, longitude in u_points})
    if len(u_points) != len(lats) * len(lons) or len(lats) < 2 or len(lons) < 2:
        raise RuntimeError("ICON-EU crop is not a complete regular Iberia grid")
    run_at = dt.datetime.strptime(run, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
    valid, generated = run_at + dt.timedelta(hours=forecast_hour), dt.datetime.now(dt.timezone.utc)
    raw = bytearray(b"PAWIND01") + bytes((1, 1, 2, forecast_hour))
    raw += struct.pack("<qqq", int(run_at.timestamp()), int(valid.timestamp()), int(generated.timestamp()))
    raw += struct.pack("<ddddddHHff", max(lats), min(lats), min(lons), max(lons), lats[0], lons[0], len(lons), len(lats), abs(lats[0] - lats[1]), SCALE)
    for latitude in lats:
        for longitude in lons:
            raw += struct.pack("<hh", round(u_points[(latitude, longitude)] * SCALE), round(v_points[(latitude, longitude)] * SCALE))
    target = OUT / "iberia.pawind.gz"
    with gzip.open(target, "wb") as output:
        output.write(raw)
    temperature_raw = bytearray(b"PATEMP01") + bytes((1, 1, 2, forecast_hour))
    temperature_raw += struct.pack("<qqq", int(run_at.timestamp()), int(valid.timestamp()), int(generated.timestamp()))
    temperature_raw += struct.pack("<ddddddHHff", max(lats), min(lats), min(lons), max(lons), lats[0], lons[0], len(lons), len(lats), abs(lats[0] - lats[1]), SCALE)
    for latitude in lats:
        for longitude in lons:
            temperature_raw += struct.pack("<h", round((t_points[(latitude, longitude)] - 273.15) * SCALE))
    temperature_target = OUT / "iberia.patemp.gz"
    with gzip.open(temperature_target, "wb") as output:
        output.write(temperature_raw)
    manifest = {
        "version": 1, "model": "ICON-EU", "run": run, "generatedAt": generated.isoformat(),
        "regions": {"iberia": {"bbox": {"north": max(lats), "south": min(lats), "west": min(lons), "east": max(lons)},
            "fields": [{"forecastHour": forecast_hour, "validTime": valid.isoformat(), "url": target.name,
                "etag": f"{run}-f{forecast_hour:03d}-v1", "size": target.stat().st_size}],
            "temperatureFields": [{"forecastHour": forecast_hour, "validTime": valid.isoformat(), "url": temperature_target.name,
                "etag": f"{run}-f{forecast_hour:03d}-t1", "size": temperature_target.stat().st_size}]}}
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run": run, "forecastHour": forecast_hour, "validTime": valid.isoformat(), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
