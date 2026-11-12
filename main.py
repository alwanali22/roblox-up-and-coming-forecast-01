"""
This module forecasts the top 10 up-and-coming games on Roblox by modeling rank persistence using a Gaussian distribution for each chart place.
It processes historical snapshot data to calculate raw probabilities, rescales them for each rank, and computes a final score for each game to determine the top 10 forecast.
"""

import os
import json
import sys
import math
from datetime import datetime
from collections import defaultdict

# Parameters
SD = [2.0, 1.5, 1.5, 2.0, 3.0, 3.0, 2.5, 1.5, 4.0, 3.0]
SHIFT = [0.0, 2.0, 0.0, 2.0, 4.0, 0.0, 0.0, 0.0, 0.0, 2.0]
NAMED = [0.60, 0.60, 0.75, 0.85, 0.80, 0.80, 0.75, 0.75, 0.85, 0.75]
TOPK = 25

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def parse_iso_timestamp(ts_str):
    # Python 3.13 fromisoformat supports Z if it is at the end, 
    # but replacing to +00:00 is safer.
    if ts_str.endswith('Z'):
        ts_str = ts_str[:-1] + '+00:00'
    return datetime.fromisoformat(ts_str)

def get_raw_p(k, r0, sd, shift):
    # k is 1-indexed rank
    mean = r0 + shift
    # Phi((k + 0.5 - mean) / sd) - Phi((k - 0.5 - mean) / sd)
    return phi((k + 0.5 - mean) / sd) - phi((k - 0.5 - mean) / sd)

def main(argv=None):
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    
    # 1. Load task.json
    with open(os.path.join(input_dir, "task.json"), "r") as f:
        task = json.load(f)
    
    history_until = parse_iso_timestamp(task["history_until"])
    
    # 2. Read history.ndjson
    last_snapshot = None
    
    with open(os.path.join(input_dir, "history.ndjson"), "r") as f:
        for line in f:
            snapshot = json.loads(line)
            ts = parse_iso_timestamp(snapshot["at"])
            if ts <= history_until:
                if last_snapshot is None or ts > parse_iso_timestamp(last_snapshot["at"]):
                    last_snapshot = snapshot
                    
    if last_snapshot is None:
        raise ValueError("No snapshots found before history_until.")
        
    up_and_coming = last_snapshot["up_and_coming"]
    
    # Pre-calculate scores for all games
    game_scores = defaultdict(float)
    game_data = {}
    for game in up_and_coming:
        u_id = game["universe_id"]
        game_data[u_id] = game
        r0 = game["rank"]
        
        # Calculate raw score for top10 (sum over k=1..10)
        score = 0.0
        for k in range(1, 11):
            p_raw = get_raw_p(k, r0, SD[k-1], SHIFT[k-1])
            score += p_raw
        game_scores[u_id] = score
        
    # 3. Model calculations
    probabilities = []
    
    for k in range(1, 11):
        # For each place, get raw probabilities for all games
        k_probs = []
        for game in up_and_coming:
            u_id = game["universe_id"]
            r0 = game["rank"]
            p_raw = get_raw_p(k, r0, SD[k-1], SHIFT[k-1])
            k_probs.append({"universe_id": u_id, "p_raw": p_raw})
            
        # Keep TOPK games with largest p_raw
        k_probs.sort(key=lambda x: x["p_raw"], reverse=True)
        top_k_games = k_probs[:TOPK]
        
        # Rescale
        sum_p_raw = sum(game["p_raw"] for game in top_k_games)
        
        if sum_p_raw > 0:
            for game in top_k_games:
                p = (game["p_raw"] / sum_p_raw) * NAMED[k-1]
                probabilities.append({
                    "universe_id": game["universe_id"],
                    "place": k,
                    "p": round(p, 6)
                })
        # If sum_p_raw is 0, no probabilities are added for this place

    # 4. Top 10
    # Sort games by score desc, then current rank asc, then universe_id asc
    sorted_games = sorted(
        up_and_coming, 
        key=lambda g: (-game_scores[g["universe_id"]], g["rank"], g["universe_id"])
    )
    top10_ids = [game["universe_id"] for game in sorted_games[:10]]
    
    # 5. Validation
    # - top10 has exactly 10 distinct integers
    if len(set(top10_ids)) != 10:
        raise ValueError("top10 does not have 10 distinct IDs.")
        
    # - each place has at most 100 probability rows (we have 25)
    place_counts = defaultdict(int)
    for p_row in probabilities:
        place_counts[p_row["place"]] += 1
    for k in range(1, 11):
        if place_counts[k] > 100:
            raise ValueError(f"Place {k} has too many rows.")
            
    # - each place's p values sum to at most 1.0
    place_sums = defaultdict(float)
    for p_row in probabilities:
        place_sums[p_row["place"]] += p_row["p"]
        # - every p is between 0 and 1
        if not (0 <= p_row["p"] <= 1):
            raise ValueError(f"p {p_row['p']} out of range.")
            
    for k in range(1, 11):
        if place_sums[k] > 1.0000001: # allow for float precision
            raise ValueError(f"Place {k} sum {place_sums[k]} > 1.0.")
            
    # 6. Save
    output_data = {
        "probabilities": sorted(probabilities, key=lambda x: (x["place"], -x["p"], x["universe_id"])),
        "top10": top10_ids
    }
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(os.path.join(output_dir, "forecast.json"), "w") as f:
        json.dump(output_data, f, sort_keys=True, separators=(",", ":"))
        
    return 0

if __name__ == "__main__":
    sys.exit(main())

# Entry built 2026-11-12; calibrated persistence model.
