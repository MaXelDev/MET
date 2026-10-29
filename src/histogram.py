import json
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Dossiers du projet (le parent de src/)
ROOT = Path(__file__).resolve().parent.parent
JSON_DIR = ROOT / "json"
FIGURES_DIR = ROOT / "Figures"

def moyennes(fichier, champ, pas, source=None):
    with open(fichier) as f:
        data = json.load(f)
    data = [e for e in data if e.get(champ) is not None]      # on ignore timeouts / erreurs
    if source:
        data = [e for e in data if e.get("source") == source]

    jour1 = datetime.fromisoformat(data[0]["timestamp"]).date()
    jour2 = jour1 + timedelta(days=1)

    normal, refait = {}, {}                                    # {tranche: [valeurs]}
    for e in data:
        t = datetime.fromisoformat(e["timestamp"]).replace(tzinfo=None)
        minutes = (t.hour * 60 + t.minute) // pas * pas        # arrondi à la tranche
        tranche = t.replace(hour=minutes // 60, minute=minutes % 60, second=0, microsecond=0)

        if t.date() == jour2 and 9 <= t.hour < 11:             # mesure refaite le lendemain
            refait.setdefault(tranche - timedelta(days=1), []).append(e[champ])
        else:
            normal.setdefault(tranche, []).append(e[champ])

    moy = lambda d: {k: sum(v) / len(v) for k, v in d.items()}
    return moy(normal), moy(refait)

def tracer(fichier, champ, pas, titre, sortie, source=None):
    normal, refait = moyennes(fichier, champ, pas, source)
    largeur = pas / 1440 * 0.9                                 # largeur en jours

    plt.figure(figsize=(15, 6))
    plt.bar(normal.keys(), normal.values(), width=largeur, align="edge",
            color="tab:blue", edgecolor="black", label="Mesure de 24 h")
    plt.bar(refait.keys(), refait.values(), width=largeur, align="edge",
            color="red", edgecolor="black", label="Mesure refaite le lendemain (9h-11h)")

    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Hh"))
    plt.xlabel("Heure")
    plt.ylabel("RTT moyen (ms)")
    plt.title(titre)
    plt.legend()
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / sortie, dpi=200)
    plt.show()

def figures():
    # Ping : tranches de 30 min
    tracer(JSON_DIR / "ping.json", "rtt_ms", 30, "Ping - RTT moyen par tranche de 30 min", "ping.png")

    # Traceroute : tranches de 60 min, source locale uniquement
    tracer(JSON_DIR / "traceroute.json", "rtt_total_ms", 60, "Traceroute (local) - RTT total moyen par heure",
           "traceroute.png", source="local")

if __name__ == "__main__":
    figures()
