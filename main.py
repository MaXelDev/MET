"""Ping toutes les 20 s + traceroutes (local et Globalping) toutes les heures."""
import threading
import time

import ping
import traceroute

PING_INTERVAL_S = 20
TRACEROUTE_INTERVAL_S = 3600


def ping_loop(stop):
    while not stop.is_set():
        entry = ping.ping_until_success(stop)
        if entry is None:
            break
        ping.save(entry)
        print(f"[ping] {entry['ip']} {entry['rtt_ms']} ms")
        # 20 s comptées à partir du ping réussi
        stop.wait(PING_INTERVAL_S)


def traceroute_loop(stop):
    next_run = time.monotonic()
    while not stop.is_set():
        try:
            traceroute.run_all(stop)
        except Exception as exc:
            print(f"[traceroute] erreur : {exc}")
        next_run += TRACEROUTE_INTERVAL_S
        stop.wait(max(0.0, next_run - time.monotonic()))


def main():
    stop = threading.Event()
    threads = [
        threading.Thread(target=ping_loop, args=(stop,), daemon=True),
        threading.Thread(target=traceroute_loop, args=(stop,), daemon=True),
    ]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Arrêt...")
        stop.set()
        for t in threads:
            t.join(timeout=5)


if __name__ == "__main__":
    main()
