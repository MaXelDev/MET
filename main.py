"""Chaîne complète : mesures -> conversion des JSON -> figures.

1. Lance les mesures (mesure.py) jusqu'à Ctrl+C
   (écriture en JSON Lines dans json/ping_ligne.json et json/traceroute_ligne.json).
2. Convertit ces fichiers en vrais JSON (json/ping.json et json/traceroute.json) avec convertJson.
3. Crée les figures (Figures/ping.png et Figures/traceroute.png) avec histogram.
"""
import mesure
from src import convertJson, histogram

JSON_DIR = convertJson.JSON_DIR


def main():
    print("Mesures en cours... Ctrl+C pour arrêter (conversion + figures ensuite).")
    mesure.main()                                   # bloque jusqu'à Ctrl+C

    convertJson.list_to_json(JSON_DIR / "ping_ligne.json", JSON_DIR / "ping.json")
    convertJson.list_to_json(JSON_DIR / "traceroute_ligne.json", JSON_DIR / "traceroute.json")

    histogram.figures()


if __name__ == "__main__":
    main()
