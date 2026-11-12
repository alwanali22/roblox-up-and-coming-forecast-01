# Roblox Up-and-Coming Forecaster v6

This model forecasts Roblox's Up-and-Coming chart.

## Design
- **Gaussian Mixture**: Two-component mixture (90% narrow, 10% wide with SD x1.25) to model place persistence.
- **Velocity Drift**: 
  - Rank velocity (0.65/0.35-weighted mean of last 2 gaps) drift.
  - Playing-velocity (mean of last 2 gaps) centre drift.
- **Occupancy Prior**: A recency-weighted place-occupancy table (halflife 8 hours, strength 0.08) added to the raw Gaussian score.
- **Climber Bonus**: Per-place bonus for top 4 climbers by log-playing velocity.

## How to Run
```bash
mkdir -p out
MAKEFUN_INPUT_DIR=../roblox/input MAKEFUN_OUTPUT_DIR=out python3 repo/main.py
```
