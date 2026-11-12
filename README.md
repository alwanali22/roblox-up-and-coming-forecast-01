# Roblox Up-and-Coming forecast v3

This model forecasts Roblox's Up-and-Coming chart top 10 places. It uses a per-place Gaussian design, with rank-velocity drift (shifting the Gaussian centre based on recent rank movement) and a playing-velocity climber bonus (reallocating probability mass to games with accelerating player counts at places 1–5).

### Usage

```bash
mkdir -p out
MAKEFUN_INPUT_DIR=../roblox/input MAKEFUN_OUTPUT_DIR=out python3 repo-v3/main.py
```
