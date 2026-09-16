from contextlib import asynccontextmanager
from dataclasses import asdict
import json, secrets, time
from pathlib import Path
from threading import Lock
from typing import Literal
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from src.engine import Engine, ROOT
from src.game import Count, advance

engine = None
lock = Lock()


@asynccontextmanager
async def lifespan(app):
    global engine
    engine = Engine()
    yield


app = FastAPI(title="Command Lab", version="0.1.0", lifespan=lifespan)


class Call(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    pitcher: str
    hitter: str
    pitch: str
    balls: int = Field(default=0, ge=0, le=3)
    strikes: int = Field(default=0, ge=0, le=2)
    outs: int = Field(default=0, ge=0, le=2)
    bases: int = Field(default=0, ge=0, le=7)
    x: float = Field(default=0, ge=-1.5, le=1.5)
    z: float = Field(default=2.5, ge=0.75, le=4.25)
    mode: Literal["realistic", "perfect"] = "realistic"
    seed: int = Field(default=1729, ge=0, le=2**32 - 1)

    def context(self):
        return (
            self.pitcher,
            self.hitter,
            self.pitch,
            self.balls,
            self.strikes,
            self.outs,
            self.bases,
        )

    def validate_players(self):
        if self.pitcher not in engine.pitchers or self.hitter not in engine.hitters:
            raise HTTPException(422, "Player not in eligible training cohort")
        if self.pitch not in [
            p["type"] for p in engine.pitchers[self.pitcher]["pitches"]
        ]:
            raise HTTPException(422, "Pitch not in eligible repertoire")


@app.get("/api/health")
def health():
    return {"status": "ready" if engine else "loading", "release": "research-preview"}


@app.get("/api/players")
def players():
    return engine.players


@app.get("/api/methodology")
def methodology():
    return {
        "command": json.loads((ROOT / "models/audit.json").read_text()),
        "response": json.loads((ROOT / "models/response-validation.json").read_text()),
        "join": json.loads((ROOT / "models/join-audit.json").read_text()),
        "value": json.loads((ROOT / "models/value-validation.json").read_text()),
        "external": json.loads((ROOT / "models/external-validation.json").read_text()),
        "subgroups": engine.subgroups,
    }


@app.post("/api/analyze")
def analyze(c: Call):
    c.validate_players()
    t = time.monotonic()
    with lock:
        realistic = engine.evaluate(c.context(), [c.x, c.z])
        perfect = engine.evaluate(c.context(), [c.x, c.z], "perfect")
    return {
        "command_validation": (engine.subgroups or {})
        .get("pitcher_id", {})
        .get(c.pitcher),
        "realistic": realistic,
        "perfect": perfect,
        "command_penalty": realistic["run_value"] - perfect["run_value"],
        "elapsed_ms": round(1000 * (time.monotonic() - t)),
    }


@app.post("/api/surface")
def surface(c: Call):
    c.validate_players()
    with lock:
        rows = engine.surface(c.pitcher, c.hitter, c.balls, c.strikes, c.outs, c.bases)
    eligible = [r for r in rows if r["target_support"]["supported"]]
    if not eligible:
        raise HTTPException(
            422, "Insufficient target support for optimization in this matchup"
        )
    return {
        "cells": rows,
        "best_realistic": min(eligible, key=lambda r: r["realistic"]),
        "best_perfect": min(eligible, key=lambda r: r["perfect"]),
        "grid_note": "Searches 99 targets per pitch; recommendations require at least 20 nearby training targets. Monte Carlo: 64 common draws. Not a continuous global optimum.",
    }


@app.post("/api/throw")
def throw(c: Call):
    c.validate_players()
    rng = np.random.default_rng(c.seed)
    location = np.array([c.x, c.z]) + (
        engine.errors(c.pitcher, c.pitch, 1, c.seed)[0] if c.mode == "realistic" else 0
    )
    with lock:
        # Sample location and response separately with independent random streams.
        response = engine.evaluate(c.context(), location.tolist(), "perfect")
        expected = engine.evaluate(c.context(), [c.x, c.z], c.mode, n=64)
        grid = [
            r
            for r in engine.surface(
                c.pitcher, c.hitter, c.balls, c.strikes, c.outs, c.bases
            )
            if r["target_support"]["supported"]
        ]
        if not grid:
            raise HTTPException(
                422, "Insufficient target support for decision comparison"
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


@app.get("/")
def home():
    return FileResponse(ROOT / "app/index.html")


app.mount("/static", StaticFiles(directory=ROOT / "app"), name="static")
