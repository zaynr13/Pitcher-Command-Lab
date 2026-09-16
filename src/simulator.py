"""Framework-independent application operations, migrated from the original API."""
from dataclasses import dataclass, asdict
import json
from threading import RLock
import numpy as np
from src.engine import Engine, ROOT
from src.game import Count, advance

@dataclass(frozen=True)
class Call:
    pitcher: str
    hitter: str
    pitch: str
    balls: int = 0
    strikes: int = 0
    outs: int = 0
    bases: int = 0
    x: float = 0.0
    z: float = 2.5
    mode: str = "realistic"
    seed: int = 1729

    def __post_init__(self):
        for name, high in [("balls",3),("strikes",2),("outs",2),("bases",7),("seed",2**32-1)]:
            v=getattr(self,name)
            if type(v) is not int or not 0 <= v <= high:
                raise ValueError(f"Invalid {name}")
        if not np.isfinite([self.x,self.z]).all() or not -1.5 <= self.x <= 1.5 or not .75 <= self.z <= 4.25:
            raise ValueError("Target outside supported controls")
        if self.mode not in ("realistic","perfect"):
            raise ValueError("Invalid execution mode")

    def context(self):
        return self.pitcher,self.hitter,self.pitch,self.balls,self.strikes,self.outs,self.bases

class Simulator:
    def __init__(self):
        self.engine=Engine()
        self.lock=RLock()

    def validate(self,c):
        if c.pitcher not in self.engine.pitchers or c.hitter not in self.engine.hitters:
            raise ValueError("Player not in eligible training cohort")
        if c.pitch not in [p["type"] for p in self.engine.pitchers[c.pitcher]["pitches"]]:
            raise ValueError("Pitch not in eligible repertoire")

    def analyze(self,c):
        self.validate(c)
        with self.lock:
            realistic=self.engine.evaluate(c.context(),[c.x,c.z])
            perfect=self.engine.evaluate(c.context(),[c.x,c.z],"perfect")
        return {"realistic":realistic,"perfect":perfect,"command_penalty":realistic["run_value"]-perfect["run_value"],
                "command_validation":(self.engine.subgroups or {}).get("pitcher_id",{}).get(c.pitcher)}

    def surface(self,c):
        self.validate(c)
        with self.lock:
            rows=self.engine.surface(c.pitcher,c.hitter,c.balls,c.strikes,c.outs,c.bases)
        eligible=[r for r in rows if r["target_support"]["supported"]]
        return {"cells":rows,"best_realistic":min(eligible,key=lambda r:r["realistic"]) if eligible else None,
                "best_perfect":min(eligible,key=lambda r:r["perfect"]) if eligible else None}

    def methodology(self):
        return {key:json.loads((ROOT/"models"/file).read_text()) for key,file in {
            "command":"audit.json","response":"response-validation.json","join":"join-audit.json",
            "value":"value-validation.json","external":"external-validation.json"}.items()}

    def throw(self,c):
        self.validate(c)
        rng = np.random.default_rng(c.seed)
        location = np.array([c.x, c.z]) + (
            self.engine.errors(c.pitcher, c.pitch, 1, c.seed)[0] if c.mode == "realistic" else 0
        )
        with self.lock:
            # Sample location and response separately with independent random streams.
            response = self.engine.evaluate(c.context(), location.tolist(), "perfect")
            expected = self.engine.evaluate(c.context(), [c.x, c.z], c.mode, n=64)
            grid = [
                r
                for r in self.engine.surface(
                    c.pitcher, c.hitter, c.balls, c.strikes, c.outs, c.bases
                )
                if r["target_support"]["supported"]
            ]
            if not grid:
                raise ValueError( "Insufficient target support for decision comparison"
                )
        probs = response["probabilities"]
        keys = list(probs)
        weights = np.array([probs[k] for k in keys])
        weights /= weights.sum()
        event = str(np.random.default_rng(c.seed ^ 0x9E3779B9).choice(keys, p=weights))
        state = advance(Count(c.balls, c.strikes), event)
        best = min(grid, key=lambda r: r[c.mode])
        value = expected["run_value"]
        loss = max(0, value - best[c.mode])
        rank = 100 * np.mean([r[c.mode] >= value for r in grid])
        return {
            "event": event,
            "state": asdict(state),
            "location": location.tolist(),
            "target": [c.x, c.z],
            "seed": c.seed,
            "expected": expected,
            "decision_loss": loss,
            "decision_percentile": float(rank),
            "optimal": best,
            "execution_value_change": response["run_value"] - value,
            "target_support": expected["target_support"],
            "note": "Decision percentile ranks modeled run value against the candidate grid; it is not a validated coaching grade.",
        }
