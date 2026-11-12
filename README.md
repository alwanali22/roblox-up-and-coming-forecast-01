# Roblox Up-and-Coming Forecaster v7

This repository contains the entry for the `roblox-up-and-coming-forecast-01` competition.

## Model Design
This is a phase-aware forecaster implemented in a single entrypoint (`repo/main.py`).

- **DEV branch**: A place-occupancy frequency table fitted to the practice-window reads (10 reads). It is a dev-board play.
- **FINAL branch**: The v6 Gaussian rank-persistence forecaster with climber bonuses and recency-weighted occupancy priors. It is a prize-horizon play.

The branch is chosen at runtime based on the `task.json` configuration in the input directory.

## Constants (FINAL branch)
The model uses parameters from v6 design (Gaussian rank-persistence + playing-velocity climber + occupancy prior GAMMA = 0.08, halflife 8 h).

## How to run
Set the input and output directories via environment variables:
`MAKEFUN_INPUT_DIR=<input_dir> MAKEFUN_OUTPUT_DIR=<output_dir> python3 repo/main.py`
