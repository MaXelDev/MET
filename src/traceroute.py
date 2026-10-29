"""Traceroute vers www.impots.gouv.fr : depuis ce PC puis via l'API Globalping."""
import json
import os
import platform
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

TARGET = "www.impots.gouv.fr"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "json" / "traceroute_ligne.json"

GLOBALPING_URL = "https://api.globalping.io/v1/measurements"
GLOBALPING_TOKEN = os.environ.get("GLOBALPING_TOKEN")  # facultatif
GLOBALPING_LOCATIONS = {
    "Toulouse": {"country": "FR", "city": "Toulouse"},
    "Reunion": {"country": "RE"},
    "Nouvelle-Caledonie": {"country": "NC"},
}
GLOBALPING_TIMEOUT_S = 120
GLOBALPING_POLL_S = 2

_lock = threading.Lock()
_IP_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")
_HOP_RE = re.compile(r"^\s*(\d+)\s+(.*)$")
_MS_RE = re.compile(r"<?\s*(\d+(?:[.,]\d+)?)\s*ms", re.IGNORECASE)
_DEST_RE = re.compile(r"[\[(](\d{1,3}(?:\.\d{1,3}){3})[\])]")


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def save(entry, path=OUTPUT_FILE):
    """Ajoute une ligne JSON (JSON Lines) et force l'écriture sur disque."""
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _round(x):
    return None if x is None else round(x, 3)


def build_result(source, destination_ip, raw_hops, **extra):
    """raw_hops : liste de (ip ou None, [rtt_ms, ...]) dans l'ordre des sauts."""
    hops = []
    previous_rtt = 0.0  # la source est à 0 ms
    for number, (ip, rtts) in enumerate(raw_hops, start=1):
        rtt = sum(rtts) / len(rtts) if rtts else None
        delta = None
        if rtt is not None:
            delta = rtt - previous_rtt
            previous_rtt = rtt
        hops.append({
            "hop": number,
            "ip": ip,
            "rtt_ms": _round(rtt),
            "delta_ms": _round(delta),
        })
    reached = bool(
        destination_ip and hops and hops[-1]["ip"] == destination_ip
        and hops[-1]["rtt_ms"] is not None
    )
    return {
        "timestamp": now_iso(),
        "source": source,
        "target": TARGET,
        "destination_ip": destination_ip,
        "reached": reached,
        "rtt_total_ms": hops[-1]["rtt_ms"] if reached else None,
        "hops": hops,
        **extra,
    }


# ---------- Traceroute local ----------

def _local_command(target):
    if platform.system() == "Windows":
        return ["tracert", "-d", "-4", "-h", "30", "-w", "2000", target]
    return ["traceroute", "-n", "-4", "-m", "30", "-q", "3", "-w", "2", target]


def parse_traceroute(output):
    """Parse la sortie de tracert / traceroute. Retourne (destination_ip, raw_hops)."""
    destination_ip = None
    raw_hops = []
    for line in output.splitlines():
        match = _HOP_RE.match(line)
        if not match:
            if destination_ip is None:
                dest = _DEST_RE.search(line)
                if dest:
                    destination_ip = dest.group(1)
            continue
        rest = match.group(2)
        ips = _IP_RE.findall(rest)
        rtts = [float(v.replace(",", ".")) for v in _MS_RE.findall(rest)]
        raw_hops.append((ips[0] if ips else None, rtts))
    return destination_ip, raw_hops


def local_traceroute(target=TARGET):
    result = subprocess.run(
        _local_command(target), capture_output=True, text=True,
        errors="replace", timeout=300,
    )
    destination_ip, raw_hops = parse_traceroute(result.stdout)
    if not raw_hops:
        raise RuntimeError("Sortie traceroute vide : " + (result.stderr.strip() or "?"))
    return build_result("local", destination_ip, raw_hops)


# ---------- Globalping ----------

def _headers():
    headers = {"User-Agent": "SDR-Traceroute"}
    if GLOBALPING_TOKEN:
        headers["Authorization"] = f"Bearer {GLOBALPING_TOKEN}"
    return headers


def globalping_traceroute(name, location, target=TARGET):
    body = {
        "type": "traceroute",
        "target": target,
        "limit": 1,
        "locations": [location],
        "measurementOptions": {"protocol": "ICMP", "ipVersion": 4},
    }
    resp = requests.post(GLOBALPING_URL, json=body, headers=_headers(), timeout=30)
    resp.raise_for_status()
    measurement_id = resp.json()["id"]

    deadline = time.monotonic() + GLOBALPING_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(GLOBALPING_POLL_S)
        resp = requests.get(f"{GLOBALPING_URL}/{measurement_id}", headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "in-progress":
            break
    else:
        raise TimeoutError("Mesure Globalping trop longue")

    if not data.get("results"):
        raise RuntimeError("Aucune sonde Globalping pour " + name)
    item = data["results"][0]
    probe, result = item["probe"], item["result"]
    if result.get("status") != "finished":
        raise RuntimeError(f"Mesure en échec : {result.get('status')}")

    raw_hops = []
    for hop in result.get("hops", []):
        rtts = [t["rtt"] for t in hop.get("timings", []) if t.get("rtt") is not None]
        raw_hops.append((hop.get("resolvedAddress"), rtts))
    return build_result(
        f"globalping:{name}", result.get("resolvedAddress"), raw_hops,
        probe={
            "country": probe.get("country"),
            "city": probe.get("city"),
            "asn": probe.get("asn"),
            "network": probe.get("network"),
        },
        globalping_id=measurement_id,
    )


# ---------- Orchestration ----------

def run_all(stop_event=None):
    """Lance tous les traceroutes ; chaque résultat est enregistré dès qu'il arrive."""
    stop_event = stop_event or threading.Event()
    jobs = [("local", local_traceroute)] + [
        (name, lambda n=name, loc=loc: globalping_traceroute(n, loc))
        for name, loc in GLOBALPING_LOCATIONS.items()
    ]
    for name, job in jobs:
        if stop_event.is_set():
            return
        try:
            entry = job()
        except Exception as exc:
            entry = {"timestamp": now_iso(), "source": name, "target": TARGET,
                     "error": f"{type(exc).__name__}: {exc}"}
        save(entry)
        print(f"[traceroute] {name}: " + ("erreur" if "error" in entry
              else f"{len(entry['hops'])} sauts, RTT total {entry['rtt_total_ms']} ms"))


if __name__ == "__main__":
    run_all()
