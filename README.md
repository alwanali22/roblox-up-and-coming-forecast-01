# v4 Roblox Up-and-Coming Forecast

This model forecasts the Roblox Up-and-Coming chart top 10 places.

## Model Design

The model uses a per-place Gaussian distribution to estimate game placement, adjusted by rank-velocity and log-playing velocity.

1.  **Rank-Velocity Drift**: Games' Gaussian centers are shifted based on their recent rank change (velocity), clipped to [-4, 4], to project rank movement.
2.  **Playing-Velocity Centre Drift**: Games' centers are further adjusted by their log-playing velocity to reflect acceleration or deceleration in player counts.
3.  **Two-Tier Climber Bonus**: A climber bonus for the top 6 games by log-playing velocity is applied at all 10 places. It concentrates bonus mass (12.5% for places 1-5, 6% for places 6-10) using squared weights (max(v, 0)^2) to prioritize fastest-growing experiences.

## Constants

- `SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]`
- `SHIFT = [0.0, 2.0, 0.0, 2.0, 6.0, 0.0, 0.0, 0.0, 0.0, 2.0]`
- `NAMED = [0.5, 0.4, 0.75, 0.95, 0.75, 0.75, 0.65, 0.75, 0.95, 0.7]`
- `P_MIN = 0.0035`

## Running

Run the model using Python 3.13:
```bash
MAKEFUN_INPUT_DIR=<input_dir> MAKEFUN_OUTPUT_DIR=<output_dir> python3 repo-v4/main.py
```
