"""Exact ID bridge; never fuzzy-match pitches by coordinates."""

import json, argparse
from pathlib import Path
import pandas as pd


def bridge(feed):
    rows = []
    game = feed["gamePk"]
    for pa in feed["liveData"]["plays"]["allPlays"]:
        for e in pa["playEvents"]:
            if e.get("isPitch") and e.get("playId"):
                rows.append(
                    dict(
                        game_pk=game,
                        play_id=e["playId"],
                        at_bat_number=pa["about"]["atBatIndex"] + 1,
                        pitch_number=e["pitchNumber"],
                    )
                )
    return pd.DataFrame(rows)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--data", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a = a.parse_args()
    b = bridge(json.loads((a.data / "game-776135.json").read_text()))
    s = pd.read_csv(a.data / "statcast-sample.csv")
    t = pd.read_csv(a.data / "targets-2025.csv.gz")
    p = pd.read_csv(a.data / "pbp-2025.csv.gz")
    k = ["game_pk", "at_bat_number", "pitch_number"]
    assert (
        not b.duplicated(k).any()
        and not b.duplicated(["game_pk", "play_id"]).any()
        and not s.duplicated(k).any()
    )
    m = b.merge(s, on=k, validate="one_to_one", how="left", indicator=True)
    o = t[t.game_pk == 776135].merge(
        m, on=["game_pk", "play_id"], validate="one_to_one", how="left"
    )
    q = p[p.game_pk == 776135].merge(
        m, on=["game_pk", "play_id"], validate="one_to_one", suffixes=("_oc", "_sc")
    )
    report = {
        "game_pk": 776135,
        "bridge_pitches": len(b),
        "matched_statcast": int((m["_merge"] == "both").sum()),
        "target_rows": len(o),
        "targets_matched_statcast": int(o.pitch_number.notna().sum()),
        "pitcher_id_agreement": float((q.pitcher_id == q.pitcher_sc).mean()),
        "batter_id_agreement": float((q.batter_id == q.batter).mean()),
        "max_plate_difference_feet": float((q.plate_x_oc - q.plate_x_sc).abs().max()),
        "note": "One-game identity bridge verified; rounding and source trajectory differences require audit. Season-wide join not yet verified.",
    }
    a.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
