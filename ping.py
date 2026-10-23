"""Ping vers www.impots.gouv.fr : 1 seul ping, on recommence tant que ça échoue."""
import json
import platform
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

TARGET = "www.impots.gouv.fr"
TIMEOUT_S = 2
OUTPUT_FILE = Path(__file__).resolve().parent / "ping.json"

_lock = threading.Lock()
_RTT_RE = re.compile(r"(?:time|temps)\s*[=<]\s*([\d.,]+)\s*ms", re.IGNORECASE)
_IP_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")


def _command(target):
    system = platform.system()
    if system == "Windows":
        return ["ping", "-4", "-n", "1", "-w", str(TIMEOUT_S * 1000), target]
    if system == "Darwin":
        return ["ping", "-c", "1", "-W", str(TIMEOUT_S * 1000), target]
    return ["ping", "-4", "-c", "1", "-W", str(TIMEOUT_S), target]


def parse_ping(output):
    """Retourne (ip, rtt_ms) ou None si le ping n'a pas abouti."""
    rtt = _RTT_RE.search(output)
    ip = _IP_RE.search(output)
    if not rtt or not ip:
        return None
    return ip.group(1), float(rtt.group(1).replace(",", "."))


def ping_once(target=TARGET):
    """Un seul ping. Retourne un dict ou None en cas d'échec."""
    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    try:
        result = subprocess.run(
            _command(target), capture_output=True, text=True,
            errors="replace", timeout=TIMEOUT_S + 3,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    parsed = parse_ping(result.stdout)
    if parsed is None:
        return None
    ip, rtt = parsed
    return {"timestamp": timestamp, "ip": ip, "rtt_ms": rtt}


def ping_until_success(stop_event=None, target=TARGET):
    """Recommence (au moins 2 s entre deux essais) jusqu'à obtenir une réponse."""
    stop_event = stop_event or threading.Event()
    while not stop_event.is_set():
        start = time.monotonic()
        entry = ping_once(target)
        if entry is not None:
            return entry
        stop_event.wait(max(0.0, TIMEOUT_S - (time.monotonic() - start)))
    return None


def save(entry, path=OUTPUT_FILE):
    """Ajoute une ligne JSON (JSON Lines) et force l'écriture sur disque."""
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        # os.fsync évite de perdre la ligne en cas de crash
        import os
        os.fsync(f.fileno())


if __name__ == "__main__":
    entry = ping_until_success()
    if entry:
        save(entry)
        print(entry)
