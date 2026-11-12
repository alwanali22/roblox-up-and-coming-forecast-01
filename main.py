import json
import os
import math
import sys
from datetime import datetime

# Constants
NAMED = [0.5, 0.4, 0.75, 0.90, 0.75, 0.75, 0.65, 0.75, 0.85, 0.7]
SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]
SHIFT = [0, 2, 0, 2, 5.5, 0, 0, 0, 0, 2]
PD = 4.0
VD = 1.25
PMIN = 0.0035
TOPK = 25
GAMMA = 0.08
HALFLIFE_HOURS = 8

def get_dt_hours(t1, t2):
    return (t1 - t2).total_seconds() / 3600.0

def load_data():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "input")
    history_file = os.path.join(input_dir, "history.ndjson")
    
    reads = []
    with open(history_file, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                if 'up_and_coming' not in data or not isinstance(data['up_and_coming'], list):
                    continue
                
                # Parse timestamp
                try:
                    at = datetime.fromisoformat(data['at'].replace('Z', '+00:00'))
                except (ValueError, TypeError, KeyError):
                    continue
                
                games = []
                for row in data['up_and_coming']:
                    if 'rank' not in row or 'universe_id' not in row:
                        continue
                    try:
                        games.append({
                            'rank': int(row['rank']),
                            'universe_id': int(row['universe_id']),
                            'playing': int(row.get('playing', 0))
                        })
                    except ValueError:
                        continue
                
                reads.append({'at': at, 'games': games})
            except json.JSONDecodeError:
                continue
    
    return reads

def compute_velocities(reads):
    if len(reads) < 2:
        return {}, {}
    
    last_idx = len(reads) - 1
    last_games = {g['universe_id']: g for g in reads[last_idx]['games']}
    
    vr = {uid: 0.0 for uid in last_games}
    vp = {uid: 0.0 for uid in last_games}
    
    # Pre-map games for faster lookup
    read_games = []
    for r in reads:
        read_games.append({g['universe_id']: g for g in r['games']})

    for uid in last_games:
        # Rank velocity: 2 gaps ending at last_read
        v_recent = None
        v_older = None
        
        # Gap 1 (most recent): last_idx-1 -> last_idx
        i = last_idx
        g_curr = read_games[i].get(uid)
        g_prev = read_games[i-1].get(uid)
        if g_curr and g_prev:
            dt = get_dt_hours(reads[i]['at'], reads[i-1]['at'])
            if dt > 0:
                v_recent = (g_curr['rank'] - g_prev['rank']) / dt
                
        # Gap 2 (older): last_idx-2 -> last_idx-1
        if last_idx >= 2:
            i = last_idx - 1
            g_curr = read_games[i].get(uid)
            g_prev = read_games[i-1].get(uid)
            if g_curr and g_prev:
                dt = get_dt_hours(reads[i]['at'], reads[i-1]['at'])
                if dt > 0:
                    v_older = (g_curr['rank'] - g_prev['rank']) / dt
        
        if v_recent is not None and v_older is not None:
            vr[uid] = max(-4.0, min(4.0, 0.65 * v_recent + 0.35 * v_older))
        elif v_recent is not None:
            vr[uid] = max(-4.0, min(4.0, v_recent))
        elif v_older is not None:
            vr[uid] = max(-4.0, min(4.0, v_older))
        else:
            vr[uid] = 0.0
            
        # Playing velocity: last 2 gaps ending at last_read
        play_gaps = []
        for i in range(last_idx, max(0, last_idx - 2), -1):
            g_curr = read_games[i].get(uid)
            g_prev = read_games[i-1].get(uid)
            
            if g_curr and g_prev:
                p_curr = g_curr['playing']
                p_prev = g_prev['playing']
                dt = get_dt_hours(reads[i]['at'], reads[i-1]['at'])
                if dt > 0 and p_curr > 0 and p_prev > 0:
                    play_gaps.append((math.log(p_curr) - math.log(p_prev)) / dt)
        
        if play_gaps:
            vp[uid] = sum(play_gaps) / len(play_gaps)
            
    return vr, vp

def compute_occupancy(reads):
    if not reads:
        return {}
    
    t_last = reads[-1]['at']
    occ = {k: {} for k in range(1, 11)} # place: {uid: weight_sum}
    
    for r in reads:
        age = get_dt_hours(t_last, r['at'])
        weight = 2 ** (-age / HALFLIFE_HOURS)
        
        for g in r['games']:
            k = g['rank']
            if 1 <= k <= 10:
                uid = g['universe_id']
                occ[k][uid] = occ[k].get(uid, 0.0) + weight
                
    # Normalize and keep top 10 per place
    final_occ = {k: {} for k in range(1, 11)}
    for k in range(1, 11):
        total_w = sum(occ[k].values())
        if total_w > 0:
            # Sorted by weight descending
            sorted_uids = sorted(occ[k].items(), key=lambda x: x[1], reverse=True)
            for uid, w in sorted_uids[:10]:
                final_occ[k][uid] = w / total_w
    return final_occ

def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def main():
    reads = load_data()
    if not reads:
        return
    
    vr, vp = compute_velocities(reads)
    occ = compute_occupancy(reads)
    
    last_read = reads[-1]
    
    # Gaussian mixture
    probs = [] # list of {"universe_id": uid, "place": k, "p": prob}
    
    for k in range(1, 11):
        place_probs = {}
        for g in last_read['games']:
            uid = g['universe_id']
            rank = g['rank']
            
            center = rank + vr.get(uid, 0.0)*VD - vp.get(uid, 0.0)*PD + SHIFT[k-1]
            
            # Narrow
            sd = SD[k-1]
            p_narrow = phi((k+0.5-center)/sd) - phi((k-0.5-center)/sd)
            
            # Wide
            sd_wide = sd * 1.25
            p_wide = phi((k+0.5-center)/sd_wide) - phi((k-0.5-center)/sd_wide)
            
            p = 0.9 * p_narrow + 0.1 * p_wide
            
            # Add occupancy prior
            p += GAMMA * occ[k].get(uid, 0.0)
            
            place_probs[uid] = p
            
        # Keep top TOPK
        sorted_games = sorted(place_probs.items(), key=lambda x: x[1], reverse=True)
        top_k = sorted_games[:TOPK]
        
        total_p = sum(p for _, p in top_k)
        if total_p > 0:
            for uid, p in top_k:
                probs.append({"universe_id": uid, "place": k, "p": p * NAMED[k-1] / total_p})

    # Climber bonus
    climbers = sorted([g for g in last_read['games'] if vp.get(g['universe_id'], 0.0) > 0], 
                      key=lambda x: vp.get(x['universe_id'], 0.0), reverse=True)[:4]
    
    if climbers:
        mass = {1: 0.18, 2: 0.18, 3: 0.15, 4: 0.12, 5: 0.12, 6: 0.06, 7: 0.06, 8: 0.06, 9: 0.06, 10: 0.06}
        climber_weights = {g['universe_id']: max(vp.get(g['universe_id'], 0.0), 0)**2 for g in climbers}
        total_cw = sum(climber_weights.values())
        
        # Merge duplicates
        merged_probs = {} # (uid, place) -> p
        for row in probs:
            merged_probs[(row['universe_id'], row['place'])] = merged_probs.get((row['universe_id'], row['place']), 0) + row['p']
            
        # Apply bonus
        for k in range(1, 11):
            m = mass[k]
            
            # Shrink existing probabilities for place k
            for (uid, place), p in list(merged_probs.items()):
                if place == k:
                    merged_probs[(uid, place)] = p * (1.0 - m)
            
            # Now add the bonus mass
            for uid in climber_weights:
                bonus = (climber_weights[uid] / total_cw) * m
                merged_probs[(uid, k)] = merged_probs.get((uid, k), 0) + bonus
                
        # Drop and reformat
        final_probs = []
        for (uid, k), p in merged_probs.items():
            if p >= PMIN:
                final_probs.append({"universe_id": uid, "place": k, "p": round(p, 6)})
        probs = final_probs
    else:
        # Just round
        for row in probs:
            row['p'] = round(row['p'], 6)

    # Prepare top10
    top10 = [g['universe_id'] for g in sorted(last_read['games'], key=lambda x: x['rank'])[:10]]
    
    # Sort
    probs.sort(key=lambda x: (x['place'], -x['p'], x['universe_id']))
    
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(os.path.join(output_dir, "forecast.json"), 'w') as f:
        json.dump({"probabilities": probs, "top10": top10}, f)

if __name__ == "__main__":
    main()
