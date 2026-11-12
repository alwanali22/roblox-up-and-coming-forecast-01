# Roblox Up-and-Coming Forecaster v5

This model forecasts the Roblox Up-and-Coming chart.

## Design
- Per-place Gaussian mixture (90% narrow, 10% wide at SD x1.25).
- Rank-velocity drift (clipped to [-4, 4]).
- Playing-velocity centre drift.
- Per-place playing-velocity climber bonus concentrated on the top 4 growers.
- Robustness: skippable malformed rows.

## Usage
Run with `MAKEFUN_INPUT_DIR` and `MAKEFUN_OUTPUT_DIR` set:

```bash
MAKEFUN_INPUT_DIR=/path/to/input MAKEFUN_OUTPUT_DIR=/path/to/output python3 repo/main.py
```
