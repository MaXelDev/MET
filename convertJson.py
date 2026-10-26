import json


def convertLineJson(file):
    with open(file, 'r') as f:
        liste = list()
        for line in f.readlines():
            liste.append(json.loads(line))
    return liste
            

def list_to_json(file):
    l = convertLineJson(file)
    with open(file,'w') as f:
        json.dump(l,f, indent=4)
        

if __name__ == "__main__":
    l = list_to_json("ping.json")
    l = list_to_json("traceroute.json")

