# Roblox Up-and-Coming Forecast Entry

This entry provides a forecast for the top 10 up-and-coming games on Roblox.

## The Model
The approach utilizes a per-place Gaussian rank-persistence model. For each of the top 10 places, it models the probability of a game's future rank based on its current rank ($r_0$). It calculates a raw Gaussian probability using predefined parameters:
- **SD (Standard Deviation):** `[2.0, 1.5, 1.5, 2.0, 3.0, 3.0, 2.5, 1.5, 4.0, 3.0]`
- **SHIFT:** `[0, 2, 0, 2, 4, 0, 0, 0, 0, 2]`
- **NAMED (Sum of probabilities per place):** `[0.60, 0.60, 0.75, 0.85, 0.80, 0.80, 0.75, 0.75, 0.85, 0.75]`

The model selects the top 25 candidate games for each place, rescales their raw probabilities to sum to the `NAMED` value for that place, and ranks the final top 10 based on the summed raw Gaussian probability across all 10 places.

## Importance of Honest Probabilities
The log score function penalizes over-concentration, as missed places are floored at 0.0001 probability. This forces the model to balance confidence with coverage rather than just picking the most likely candidates.

## Performance
- **Practice-window score:** -30.28
- **House baseline:** -43.51
- **Board leader:** -27.3

The "honest limit" of the model is that viral newcomers that were not on the closing chart cannot be directly predicted and are only covered by the remaining unnamed probability mass.

## Execution
The script requires no external dependencies (standard Python library only) and is deterministic.

### Setup
Ensure `MAKEFUN_INPUT_DIR` contains the input data and `MAKEFUN_OUTPUT_DIR` is set for output.

```bash
export MAKEFUN_INPUT_DIR=/path/to/input
export MAKEFUN_OUTPUT_DIR=/path/to/output
python3 main.py
```
