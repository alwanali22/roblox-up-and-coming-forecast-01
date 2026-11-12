# Roblox Up-and-Coming forecaster v2

This model forecasts the Roblox Up-and-Coming chart top 10 places.

## Model Design
- The model reads the last chart from the history.
- For each place k (1-10), it computes Gaussian-based probabilities for each game.
- Each place has specific `SD` (spread), `SHIFT` (drift), and `NAMED` (named-mass budget) constants.
- It keeps the top 25 games per place, rescales to the `NAMED` budget, and drops probabilities below `P_MIN` (0.0035).
- It outputs a forecast with `probabilities` and `top10` (the last read's top 10).

## Constants
- `SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]`
- `SHIFT = [0.0, 2.0, 0.0, 2.0, 6.0, 0.0, 0.0, 0.0, 0.0, 2.0]`
- `NAMED = [0.5, 0.4, 0.75, 0.95, 0.75, 0.75, 0.65, 0.75, 0.95, 0.7]`
- `P_MIN = 0.0035`
- `TOPK = 25`

## Running
Run with `python3 repo-v2/main.py`.
It reads history from `MAKEFUN_INPUT_DIR` (or `/input/`) and writes forecast to `MAKEFUN_OUTPUT_DIR` (or `/output/`).
