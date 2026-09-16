# Build log

- Inspected full user specification; preserved it in SPECIFICATION.md.
- GitHub connector lists zero accessible repositories. Work proceeds in a local exportable repository; no remote publication claimed.
- Audited OpenCommand methodology and source. Rejected its in-sample inferred targets for independent validation.
- Downloaded actual 2024/2025 target and pitch files. Verified one-to-one 2025 identity joins and one-game exact Statcast bridge.
- Built and temporally evaluated the simplest partially pooled command baseline before UI work.
- Detected Statcast's export row cap and changed download windows from seven to three days with failure on capped responses.
- Chose frozen training-period physical profiles: actual future velocity, spin, movement and strike-zone bounds must not leak into pre-pitch inference.
- Response model selection uses July only; August onward is held out. Report player-agnostic comparisons, including any model where player effects fail to improve validation.
- Final response cohort: 709,909 cleaned observations. Frozen serving coverage: 365 pitchers and 307 hitters.
- Player effects improve swing/contact; hit-category validation selects player-agnostic fallback. RV gain remains modest and documented.
- Fixed optimizer scoring to use the same 64 common random draws for the user and grid alternatives.
- Fixed ambiguous Statcast `player_name` metadata by resolving both roles through MLB IDs; model identities were unaffected.
- Completed API/unit/model suite and browser PA, execution toggle, Pro Mode, methodology, mobile and narrow-desktop checks. No console errors observed.
- Prepared a Docker recipe and CI workflow. No Docker runtime is available; no remote repository is accessible. Neither container execution nor public deployment is claimed.

- Continued beyond preview: compared linear, nonlinear tree, additive residual tree, and game-cross-fitted stack for run value. Cross-fitted stack wins July selection.
- Evaluated frozen response models once on 47,502 previously unused 2026 pitches across 161 games, with explicit plate-plane transport. Nonlinear value improves over linear in a game-clustered bootstrap.
- Measured command subgroup calibration; exposed pitcher-level undercoverage instead of hiding it behind aggregate coverage.
- Added training-only target-support counts. Optimizer recommendations require 20 targets within 0.5 ft; sparse grid regions are faded and user estimates carry warnings.
- GitHub identifies account zaynr13, but no repositories are exposed. Browser repository creation requires sign-in; user action requested without asking for credentials.
