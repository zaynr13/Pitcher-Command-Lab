# Command Lab — project report

## Delivered

Functional local research web application; reproducible data ingestion and model training; temporally evaluated model artifacts; tests; README; methodology; data audit; build log; Docker recipe; GitHub Actions workflow. No public deployment or remote GitHub repository has been created.

## Data

| Dataset | Observations | Pitchers | Hitters |
|---|---:|---:|---:|
| 2024 usable regular-season OpenCommand (audit only) | 658,215 | 852 | 651 |
| 2025 usable regular-season OpenCommand | 643,403 | 870 | 673 |
| 2025 cleaned Statcast response training/validation/test pool | 709,909 | See frozen serving cohort | See frozen serving cohort |
| Frozen serving cohort | Training-only profiles | 365 | 307 |

The response pool splits into 369,171 training, 106,883 validation and 233,855 test observations. Outcome-specific sample sizes are smaller and recorded per head. The command test contains 214,377 observations. These pools overlap; never sum them as unique MLB pitches.

2024 is audited but not pooled into this model release. 2026 is not used for training. A previously unused September 1–12 window is evaluated externally after converting its plate coordinates to the 2025 reference plane; ABS and behavioral changes remain.

## Models and validation

Command: partially pooled bivariate Gaussian target-to-location error. Held-out 80% region coverage 79.77%, horizontal/vertical RMSE 8.75/10.45 inches. Predictor uses estimated glove targets, not independent intention labels.

Response: regularized logistic heads with spatial interactions; held-out swing log loss 0.4811 versus 0.4962 without player effects. Conditional contact log loss 1.0358 versus 1.0498. Hit category selected the player-agnostic model. Contact-quality heads are bounded ridge regressions. Run value now uses boosted trees with a game-cross-fitted player-aware linear feature: 2025 test RMSE 0.22395 versus linear 0.22624 and mean-only 0.22755. The external 2026 window contains 47,502 pitches across 161 games, with RMSE 0.22784 versus linear 0.23039. A paired game bootstrap gives a positive MSE-reduction interval. This supports predictive improvement, not causal policy improvement.

Model selection uses July; August onward is held out, with initial solver convergence diagnostics inspected and corrected. The separate 12-day 2026 window was evaluated once after final response-model selection; broader external coverage is still needed. This release does not establish production-grade accuracy.

## Product and performance

Game mode includes pitcher/hitter search, eligible repertoire, count/base situation, clickable and keyboard-controlled targets, execution toggle, simulated outcomes and complete PA review. Pro Mode compares pitch-specific target surfaces. Methodology exposes model selection and actual evaluation values. All these views share the fitted inference engine.

21 automated tests passed. Browser acceptance testing completed the Cease–Guerrero flow, execution toggle, optimizer and methodology. The 390px mobile and 1108px desktop checks showed no page-width overflow. No console errors were observed. One local in-process timing measured 24 ms per analysis and 308 ms for the uncached 297-candidate Cease search. No load test or cloud latency guarantee is implied.

## Exploratory finding

For the frozen Cease–Guerrero model at 2–1, two outs and a runner on first, the candidate search preferred a four-seam at (0, 3.20) feet in perfect mode and a slider at (-0.375, 2.50) feet in realistic mode. The location difference is approximately 0.794 feet, and pitch type also changes. This is one model illustration, not a league-wide finding or a demonstrated tactical advantage. Exact outputs and timings are in `models/research-example.json`.

## Main limits

Unverified target intent; correlated camera/trajectory measurement errors; constant-error baseline within pitcher/pitch type; incomplete subgroup calibration; modest RV improvement; separate event and value heads; historical cohort; no injury/arsenal drift model; unsupported HBP/bunt/automatic events; no causal or held-out policy improvement; no validated sequencing or catastrophic-miss score.

## Deployment and next work

Public release remains gated by independent target-quality validation, broader external evaluation, uncertainty beyond numerical integration, and tested hosting. Nonlinear baselines, one external-year window, subgroup diagnostics and support-aware target restrictions are now implemented. Docker is unavailable in this environment, so the included container recipe has not been built. The connected GitHub account returned no accessible repositories, and no destination URL was supplied.

Accurate project facts suitable for a future description: built a real-data pitch-calling research app for 365 pitchers and 307 hitters, audited over 640,000 usable 2025 command observations, implemented temporally evaluated partially pooled command and hitter models, verified a 315-pitch exact identity bridge, and tested a full interactive plate appearance. Do not describe this work as a publicly deployed, causally validated, or production-accurate system.
