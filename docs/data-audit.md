# Data audit — Command Lab

Status: empirical audit, command baseline, response pipeline and one external response evaluation complete for this research release. Counts and validation results are generated in `models/audit.json`, not manually maintained here.

## Sources and provenance

- [OpenCommand repository](https://github.com/tomdoyo/open-command), version 1.2.0 methodology inspected on 2026-09-15. Public inferred targets are produced with `infer_targets(a, a)`: same-data fitting. Do not use them as independent held-out target labels.
- [OpenCommand dataset](https://huggingface.co/datasets/tomdoyo/open-command): 2024, 2025 and 2026 directories verified. Downloaded 2024 and 2025 target and pitch tables; source SHA256s recorded by scripts. Data is CC BY-NC-SA 4.0; attribution and noncommercial/share-alike restrictions apply. Source code from OpenCommand is inspected, not incorporated.
- [Statcast dictionary](https://baseballsavant.mlb.com/csv-docs): plate coordinates are feet, catcher perspective. The plane changes from front-of-plate through 2025 to middle-of-plate in 2026, alongside ABS-defined strike-zone bounds. Do not blindly pool 2026.

## Observations and joins

2025 files contain 660,054 target rows and 724,005 pitch rows. All target keys join one-to-one on `(game_pk, play_id)`. After regular-season, plausible-target and finite-coordinate filtering, 643,403 observations remain: 870 pitchers and 673 hitters. This snapshot differs from counts in the project README; observed file contents control this analysis.

OpenCommand `pbp_info` has pitcher/batter IDs, descriptions, trajectory and location, but lacks counts and detailed contact outcomes. Statcast supplies those. A MLB live-feed bridge maps pitch `playId` to `(game_pk, atBatIndex + 1, pitchNumber)`; the latter key joins Statcast. In game 776135, all 315 bridge pitches and all 302 target rows matched. Pitcher and batter identities agree completely; maximum horizontal coordinate difference was 0.000353 feet. This verifies one game, not every season record. Do not use fuzzy spatial joins. Independent response training on Statcast does not require every target record to be joined.

Weekly Statcast downloads hit the 25,000-row cap. They were rejected for training and replaced by three-day batches with explicit cap detection. Raw files stay outside the repository.

## Exact target schema

`game_pk`, `play_id`, `park`, `y_depth_ft`, `plate_x_in`, `plate_z_in`, `release_s`, `status`, `target_frame`, `naive_x_in`, `naive_z_in`, `plausible`, `inferred_x_in`, `inferred_z_in`.

Full pitch schema, missing fractions, pitch-type counts and observed date bounds are in the generated audit JSON. Missingness is measured before eligibility filtering. The filtering funnel, rather than an imputed target, defines command eligibility.

## Coverage and eligibility

On the usable 2025 sample, requiring 500 target observations and 10 outings yields 427 pitchers. Requiring 1,000 observed pitches yields 287 hitters; these are feasibility counts, not final serving eligibility. Production profiles must be based solely on the training period, include PA checks, and intersect with available command profiles. Report the resulting actual counts; never inflate them to fit a target.

The initial frozen release uses a 2025 training cohort. 2024 is audited for coverage but is not automatically pooled: 2025 already supports substantial coverage and older arsenals may change. Adding 2024 is a future ablation, not a demonstrated performance gain. 2026 is reserved for coordinate-harmonized external evaluation.

## Learnability and baseline

Train before July 1; select shrinkage using July; evaluate once on August onward. Command error is realized minus naive target, in inches. Bivariate Gaussian second moments are shrunk from pitcher/pitch to pitch type to league. Prior strengths 50, 100, 300 and 1,000 are compared on July likelihood. No published inferred-target coordinates enter training.

On 214,377 held-out pitches, pooled pitcher/pitch NLL is 7.26495 versus league 7.45062 and pitch-type 7.37541. Horizontal/vertical RMSE is 8.74673/10.45025 inches. Nominal 50%/80% containment is 53.35%/79.77%. This supports predictive signal beyond pitch type; it does not establish intended-target ground truth or causal benefit from changing the target. NLL units depend on inch coordinates.

## Measurement limitations

Naive targets are estimated glove positions, not verified intentions. Camera reconstruction uses trajectories and game-level information, so measurement errors may correlate with pitch endpoints and future within-game observations. Excluding inferred targets removes one clear fitting leak but does not make upstream video reconstruction a prospective independent sensor. Error variance combines execution and measurement uncertainty; it cannot be decomposed without independent target labels. Selection depends on camera quality and broadcast availability. Aggregate containment can hide player/park/pitch-specific miscalibration. Large-error tails, conditional calibration, and external-year validation are required before claiming production readiness.

## Follow-up validation

The final response pool contains 709,909 cleaned 2025 pitches. Final artifacts serve 365 pitchers and 307 hitters. A cross-fitted nonlinear value model beats the linear baseline on July selection and on a previously unused September 1–12, 2026 window (47,502 pitches, 161 games). That evaluation transports Statcast locations from the middle to the front of the plate; it does not refit on 2026 or claim the OpenCommand 2026 target schema was fully audited. Exact results are in the generated value, external and subgroup validation JSON reports.
