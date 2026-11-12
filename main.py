import json
import math
import os
import sys
from datetime import datetime

# Per-place constants
SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]
SHIFT = [0.0, 2.0, 0.0, 2.0, 6.0, 0.0, 0.0, 0.0, 0.0, 2.0]
NAMED = [0.5, 0.4, 0.75, 0.95, 0.75, 0.75, 0.65, 0.75, 0.95, 0.7]
P_MIN = 0.0035
TOPK = 25
VEL_DRIFT = 1.25
VEL_CLIP = 4.0
CLIMBER_MASS = 0.10
CLIMBER_PLACES = (1, 2, 3, 4, 5)

def get_input_dir():
    return os.environ.get("MAKEFUN_INPUT_DIR", "/input")

def get_output_dir():
    return os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

def parse_iso(ts):
    # Python 3.13's fromisoformat should handle Z if it is ISO 8601, but just in case:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def clean_snapshot(snapshot):
    cleaned = []
    for g in snapshot:
        if isinstance(g.get("universe_id"), int) and isinstance(g.get("rank"), int):
            cleaned.append(g)
    return cleaned

def load_history(input_dir):
    history = []
    with open(os.path.join(input_dir, "history.ndjson"), "r") as f:
        for line in f:
            entry = json.loads(line)
            if "up_and_coming" in entry:
                entry["up_and_coming"] = clean_snapshot(entry["up_and_coming"])
            history.append(entry)
    # Sort just in case, though the instructions imply they are oldest first
    history.sort(key=lambda x: parse_iso(x["at"]))
    return history

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def main():
    input_dir = get_input_dir()
    output_dir = get_output_dir()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    history = load_history(input_dir)
    if len(history) < 3:
        # Instruction says if fewer than 3 reads, v_rank and v_play are 0.
        pass

    closing_chart = history[-1]["up_and_coming"]
    
    # Pre-map games for faster lookup
    # Need maps for ranks and playing counts for the last 3 reads (N-1, N-2, N-3)
    # Actually, rank velocity needs N-3, N-2, N-1.
    
    # Helper to create rank and playing maps for a given snapshot
    def get_snapshot_maps(snapshot):
        rank_map = {g["universe_id"]: g["rank"] for g in snapshot}
        playing_map = {g["universe_id"]: g["playing"] for g in snapshot}
        return rank_map, playing_map

    n = len(history)
    
    # Step 1: Rank Velocity
    # v_rank = 0.65 * v_recent + 0.35 * v_older
    # v_recent: N-2 -> N-1
    # v_older: N-3 -> N-2
    
    v_ranks = {}
    if n >= 3:
        # Maps for N-3, N-2, N-1
        rank_maps = [get_snapshot_maps(history[i]["up_and_coming"])[0] for i in [n-3, n-2, n-1]]
        times = [parse_iso(history[i]["at"]) for i in [n-3, n-2, n-1]]
        
        # Gap 1 (N-3 to N-2)
        dt1 = (times[1] - times[0]).total_seconds() / 3600
        gap1_vel = {}
        if dt1 > 0:
            for uid, rank_n2 in rank_maps[1].items():
                if uid in rank_maps[0]:
                    gap1_vel[uid] = (rank_n2 - rank_maps[0][uid]) / dt1
        
        # Gap 2 (N-2 to N-1)
        dt2 = (times[2] - times[1]).total_seconds() / 3600
        gap2_vel = {}
        if dt2 > 0:
            for uid, rank_n1 in rank_maps[2].items():
                if uid in rank_maps[1]:
                    gap2_vel[uid] = (rank_n1 - rank_maps[1][uid]) / dt2
                    
        for uid in rank_maps[2]:
            v1 = gap1_vel.get(uid)
            v2 = gap2_vel.get(uid)
            
            if v1 is not None and v2 is not None:
                v_rank = 0.65 * v2 + 0.35 * v1
            elif v2 is not None:
                v_rank = v2
            elif v1 is not None:
                v_rank = v1
            else:
                v_rank = 0.0
            
            v_ranks[uid] = max(-VEL_CLIP, min(VEL_CLIP, v_rank))
    else:
        for g in closing_chart:
            v_ranks[g["universe_id"]] = 0.0

    # Step 2: Gaussian Base Probabilities
    probabilities = []
    
    for k in range(1, 11):
        place_probs = []
        for g in closing_chart:
            uid = g["universe_id"]
            r = g["rank"]
            v_rank = v_ranks.get(uid, 0.0)
            
            c = r + v_rank * VEL_DRIFT + SHIFT[k-1]
            sd = SD[k-1]
            
            # Phi((k + 0.5 - c) / SD) - Phi((k - 0.5 - c) / SD)
            p = phi((k + 0.5 - c) / sd) - phi((k - 0.5 - c) / sd)
            place_probs.append({"universe_id": uid, "p": p})
            
        # Keep top TOPK
        place_probs.sort(key=lambda x: x["p"], reverse=True)
        top_probs = place_probs[:TOPK]
        
        T = sum(item["p"] for item in top_probs)
        if T > 0:
            for item in top_probs:
                item["p"] = item["p"] * NAMED[k-1] / T
                item["place"] = k
                probabilities.append(item)

    # Step 3: Playing-velocity climber bonus
    # v_play = plain mean of (log(p_b) - log(p_a)) / dt
    v_plays = {}
    if n >= 3:
        playing_maps = [get_snapshot_maps(history[i]["up_and_coming"])[1] for i in [n-3, n-2, n-1]]
        times = [parse_iso(history[i]["at"]) for i in [n-3, n-2, n-1]]
        
        # Gap 1 (N-3 to N-2)
        dt1 = (times[1] - times[0]).total_seconds() / 3600
        gap1_play = {}
        if dt1 > 0:
            for uid, p_n2 in playing_maps[1].items():
                if uid in playing_maps[0] and p_n2 > 0 and playing_maps[0][uid] > 0:
                    gap1_play[uid] = (math.log(p_n2) - math.log(playing_maps[0][uid])) / dt1
        
        # Gap 2 (N-2 to N-1)
        dt2 = (times[2] - times[1]).total_seconds() / 3600
        gap2_play = {}
        if dt2 > 0:
            for uid, p_n1 in playing_maps[2].items():
                if uid in playing_maps[1] and p_n1 > 0 and playing_maps[1][uid] > 0:
                    gap2_play[uid] = (math.log(p_n1) - math.log(playing_maps[1][uid])) / dt2
                    
        for uid in playing_maps[2]:
            vals = []
            if uid in gap1_play: vals.append(gap1_play[uid])
            if uid in gap2_play: vals.append(gap2_play[uid])
            
            if vals:
                v_plays[uid] = sum(vals) / len(vals)
            else:
                v_plays[uid] = 0.0
    
    # Rank closing chart games by v_play
    sorted_climbers = sorted(closing_chart, key=lambda g: v_plays.get(g["universe_id"], 0.0), reverse=True)
    climbers = sorted_climbers[:10]
    weights = {g["universe_id"]: max(v_plays.get(g["universe_id"], 0.0), 0.0) for g in climbers}
    W = sum(weights.values())
    
    if W > 0:
        for k in CLIMBER_PLACES:
            # Multiply existing by (1 - CLIMBER_MASS)
            for p in probabilities:
                if p["place"] == k:
                    p["p"] *= (1 - CLIMBER_MASS)
            
            # Add climber rows
            for g in climbers:
                uid = g["universe_id"]
                w = weights[uid]
                if w > 0:
                    p_bonus = CLIMBER_MASS * w / W
                    probabilities.append({"universe_id": uid, "place": k, "p": p_bonus})

    # Step 4: Merge, Cut, Sort
    merged = {}
    for p in probabilities:
        key = (p["universe_id"], p["place"])
        if key in merged:
            merged[key]["p"] += p["p"]
        else:
            merged[key] = p
            
    final_probs = []
    for row in merged.values():
        if row["p"] >= P_MIN:
            row["p"] = round(row["p"], 6)
            final_probs.append(row)
            
    # Sort
    final_probs.sort(key=lambda x: (x["place"], -x["p"], x["universe_id"]))
    
    # top10
    top10 = [g["universe_id"] for g in sorted(closing_chart, key=lambda g: g["rank"])[:10]]
    
    with open(os.path.join(output_dir, "forecast.json"), "w") as f:
        json.dump({"probabilities": final_probs, "top10": top10}, f)

if __name__ == "__main__":
    main()
