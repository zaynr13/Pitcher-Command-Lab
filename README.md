# Command Lab

Call the pitch. Pick the target. Live with the miss.

A native Streamlit baseball simulator for exploring how pitcher command and hitter response change a pitch call. Includes fitted profiles for 365 pitchers and 307 hitters.

- Searchable matchups, observed repertoires, count, outs and runners.
- Interactive targeting, landing distributions, and realistic versus perfect execution.
- Full plate appearances, reproducible pitch seeds and decision reviews.
- Expected outcomes, command penalties and repertoire-wide target maps.
- Held-out validation results and model limitations inside the app.

## Run

Use **Python 3.12** and install the pinned dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

On Windows, activate with `.venv\Scripts\activate`.

For **Streamlit Community Cloud**, select this repository, branch `main`, and main file **`streamlit_app.py`**. Choose Python **3.12** in Advanced settings. No credentials or separate backend service are required.

## Methodology

The app loads the bundled fitted models directly. Partially pooled, two-dimensional Gaussian errors describe execution around estimated glove targets. Existing feature engineering and fitted probability heads predict swing, called strikes, contact and hit outcomes. Run value uses a boosted tree with a cross-fitted player-aware linear feature. Integration over possible pitch locations yields realistic predictions; exact target locations yield perfect-execution predictions.

Optimization compares 99 targets per pitch using common random draws and excludes regions with fewer than 20 nearby training targets. The original model assets, feature transformations and seeded simulation calculations are preserved.

Profiles are frozen at July 1, 2025. Glove position is an estimate of intent, not verified intent. Historical predictions do not establish causal coaching value. The simulation ends at a plate appearance; sequencing, injuries, bunts, hit-by-pitch and automatic balls are not modeled. Validation includes a limited September 2026 external window; full results and caveats are in Methodology.

## Repository

```text
streamlit_app.py      interface, controls and session state
.streamlit/          product theme
src/                 inference, simulation and chart presentation
models/              required fitted model, player profiles and displayed validation
tests/              model, state and interface regression checks
```

Run checks with `python -m unittest discover -s tests`.

The required fitted model is approximately 466 KiB; no raw season downloads or training step are needed. Only load trusted model artifacts.

Sources: [OpenCommand / Tom Kim](https://github.com/tomdoyo/open-command) and [MLB Statcast](https://baseballsavant.mlb.com/csv-docs). Source code is MIT; OpenCommand-derived profiles retain CC BY-NC-SA 4.0 noncommercial/share-alike terms. See [LICENSE.md](LICENSE.md). Not affiliated with MLB.
