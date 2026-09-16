# Methodology

## Statistical object

The model estimates P(realized location | estimated glove target, pitcher, pitch type), then conditional response probabilities. The user click represents a glove-target proxy in catcher-view feet. Positive x follows Statcast catcher-view coordinates; no label maps it universally to arm-side without pitcher handedness. Targets in the API are bounded to x ∈ [-1.5, 1.5], z ∈ [0.75, 4.25] feet. The strike-zone drawing uses the hitter's training-period median top/bottom, not a future pitch's operator measurement.

The baseline assumes the error distribution is constant across target location within pitcher/pitch type. It is a defensible first baseline, not evidence that target/context effects are absent. The covariance contains both execution error and target measurement error. Its 50%/80% ellipses use the chi-square(2) quantile -2 log(1-p). They are predictive landing regions, not confidence intervals for the mean.

## Eligibility and confidence

Serving pitchers require at least 300 training Statcast pitches and 10 outings. A pitch requires 50 Statcast observations, at least 2% usage and at least 30 training command observations. Hitters require 500 pitches and 100 distinct game/PA keys. These rules produce 365 pitchers and 307 hitters in this frozen snapshot. They do not select players by reputation.

Command sample support is high at 600 observations, medium at 150, limited below 150. This is an explicit descriptive sample-size indicator, not a calibrated probability of model correctness. All command cells shrink toward priors, even when eligible. Hitter counts and PA support are exposed. The app does not claim calibrated per-player uncertainty, which remains a production gate.

## Features and leakage

Training-only preprocessing fits median imputation, scaling, splines and categorical encodings. Response predictors are plate coordinates, historical pitch-quality features, count, outs, base occupancy, pitch type, handedness and optional player IDs. Interactions multiply pitch-type and hitter indicators by centered x/z, x², z² and xz. Player effects are regularized across the pooled dataset.

Observed pitch locations/physics are valid inputs to the retrospective conditional response model. At serving time, location is integrated or sampled and physics uses pitcher/pitch training medians. The system does not feed observed test velocity or movement into prospective requests. It does not claim the historical conditional response validation is an end-to-end prospective matchup validation.

Never use `events`, `description`, exit velocity, launch angle, xwOBA, run-expectancy change, future-game spacing, post-pitch score or batted-ball measurements as pre-pitch inputs. These are labels or excluded fields. Realized plate location is the command dependent variable. OpenCommand inferred-target fields are excluded because source code applies fitting to the same rows. Camera reconstruction itself uses actual trajectories; residual correlated measurement errors remain acknowledged.

## Response chain

Swing probability is conditional on supported ordinary takes/swings. Called-strike probability is conditional on a supported take. Swing outcomes are whiff, foul, caught foul tip, or ball in play; a caught foul tip counts as a strike. In-play categories preserve outs, singles, doubles, triples, homers, errors and fielder's choice. Some terminal event types are excluded from the modeled population rather than coerced into fabricated outcomes. Unsupported bunts, HBP and automatic events are not simulated. This conditional scope limits real-game completeness.

Bounded ridge regressions estimate contact means. Offensive run-expectancy change uses a histogram gradient-boosted tree augmented with a player-aware ridge prediction. Five-fold GroupKFold by game produces this latent feature for training; inference uses the full training-period ridge model. Each training label is excluded from its own latent feature. The tree has 150 iterations, 15 leaves, minimum leaf size 300 and L2 penalty 30. July selects among linear, tree, additive linear/tree and cross-fitted-stack candidates. xwOBA is not substituted for run value. The RV head and event-probability chain share features but are separate fits; decision scores use the RV head, while sampled game outcomes use the probability chain. Their aggregate consistency is not guaranteed, and this is explicitly a limitation.

## Simulation and optimization

Realistic analysis averages 256 seeded multivariate-normal draws. Perfect execution evaluates one exact location. Response probabilities are combined per location before averaging, which preserves probability mass and conditional weighting. For example, whiff given swing is E[p(swing) p(whiff|swing)] / E[p(swing)]. Contact means are weighted by ball-in-play probability.

The target search evaluates 99 candidate locations per eligible pitch with 64 common random numbers. Recommendations require at least 20 training naive targets within 0.5 feet of the candidate. A general user click shows support at its nearest grid candidate, explicitly labeled as such. Unsupported targets may be explored but are excluded from recommended alternatives. It minimizes modeled offensive `delta_run_exp`. The displayed command penalty is realistic minus perfect value, positive when execution uncertainty adds offensive value. Numerical integration standard error is the sample standard deviation of predicted value over sqrt(N); it is not total predictive or epistemic uncertainty. In perfect mode it is zero by construction, not because the outcome is certain.

A pitch's decision loss is max(0, EV(user call) - EV(best grid call)), using the same 64 draws for both. Percentile is the fraction of candidate values no better for the pitcher than the user's value. The PA display averages pitch percentiles and sums decision loss. This is model-relative feedback, not an independently validated talent or coaching grade. No sequencing score is invented.

Optimization is neither a continuous global optimum nor causal policy evaluation. Spatial extrapolation, Gaussian tails, marginal uncertainty and imperfect RV prediction can all alter recommendations. No aggressive/conservative risk labels are supplied without validated objectives.

## Exact join reproduction

From the repository root, after downloading 2025 OpenCommand:

```sh
curl -L --fail 'https://statsapi.mlb.com/api/v1.1/game/776135/feed/live' -o data/raw/game-776135.json
curl -L --fail 'https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_date_gt=2025-09-28&game_date_lt=2025-09-28&group_by=name&min_pitches=0' -o data/raw/statcast-sample.csv
python scripts/verify_join.py --data data/raw --out models/join-audit.json
```

No fuzzy matching is used. The pitch number is the live-feed pitch number within the PA, not the event array index. One-game verification does not establish season-wide bridge completeness.

## Deployment boundary

The app is runnable without raw data. Fitted artifacts are small and loaded once per process. The API validates players, repertoire, finite coordinates and count bounds. Caches are bounded; inference is serialized within a process to avoid thread oversubscription and served through a synchronous threadpool route. Docker uses multiple processes and a concurrency limit. TLS, service-level rate limiting and load testing belong to a deployment and have not been claimed as completed.

## Additional external and subgroup validation

A frozen selected response artifact was evaluated once on September 1–12, 2026, 47,502 pitches across 161 games. Its SHA256 is recorded in `external-validation.json`. The script refuses to overwrite that report. Statcast's 2026 middle-plane coordinates are transported to y=17/12 feet using the velocity/acceleration trajectory, with the initial velocity reference at y=50 feet. This is an outcome-conditional response check, not a prospective policy experiment; observed 2026 physics enter the evaluation. No model was refitted on this window.

A paired bootstrap resamples complete games, rather than independent pitches, for the nonlinear-versus-linear MSE difference. The 1,000-replicate 95% interval is positive. This supports a predictive gain over that baseline in this window, not annual performance or causal targeting benefit.

Command subgroup reports require at least 200 test pitches. Across qualifying pitchers, nominal 80% coverage ranges from approximately 63.9% to 87.9%. The app exposes pitcher-level coverage, pools all the pitcher's pitch types for that diagnostic, and flags deviations greater than five percentage points. It does not retroactively recalibrate on these test observations.

To reproduce external evaluation in a separate release directory, download the specified dates with `download.py --statcast --year 2026 --start 2026-09-01 --end 2026-09-12`, then run `external_evaluation.py --data <download-directory>`. Preserve the original report; a re-evaluation is not a fresh untouched holdout.
