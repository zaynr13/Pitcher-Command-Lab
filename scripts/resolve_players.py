import argparse, json, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--players", type=Path, required=True)
a = ap.parse_args()
d = json.loads(a.players.read_text())
ids = sorted({p["id"] for p in d["hitters"] + d["pitchers"]})
names = {}
for start in range(0, len(ids), 100):
    url = "https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(
        ids[start : start + 100]
    )
    with urllib.request.urlopen(url, timeout=60) as r:
        for p in json.load(r)["people"]:
            names[str(p["id"])] = p["fullName"]
for p in d["hitters"] + d["pitchers"]:
    p["name"] = names.get(p["id"], p["name"])
a.players.write_text(json.dumps(d, allow_nan=False))
print("Resolved", len(names), "player names")
