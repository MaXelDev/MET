import json
from pathlib import Path

# Dossier du projet (le parent de src/) : les chemins ne dépendent plus du dossier courant
ROOT = Path(__file__).resolve().parent.parent
JSON_DIR = ROOT / "json"


def convertLineJson(file):
    with open(file, 'r') as f:
        liste = list()
        for line in f.readlines():
            liste.append(json.loads(line))
    return liste
            

def list_to_json(file, dest=None):
    """Lit un fichier JSON Lines (file) et écrit un vrai JSON dans dest (par défaut : file)."""
    l = convertLineJson(file)
    with open(dest or file,'w') as f:
        json.dump(l,f, indent=4)
        

if __name__ == "__main__":
    l = list_to_json(JSON_DIR / "ping_ligne.json", JSON_DIR / "ping.json")
    l = list_to_json(JSON_DIR / "traceroute_ligne.json", JSON_DIR / "traceroute.json")

