import json
import math
import os
import sys
from datetime import datetime

def parse_iso8601(s):
    # Python 3.13 should handle Z suffix, but let's be robust
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    return datetime.fromisoformat(s)

def get_gap_hours(t1, t2):
    return (t2 - t1).total_seconds() / 3600.0

def main():
    # Setup paths
    input_dir = os.environ.get('MAKEFUN_INPUT_DIR', '/input/')
    output_dir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output/')
    
    # Read history
    history = []
    with open(os.path.join(input_dir, 'history.ndjson'), 'r') as f:
        for line in f:
            try:
                read = json.loads(line)
                if isinstance(read.get('up_and_coming'), list):
                    history.append(read)
            except json.JSONDecodeError:
                continue
            
    # Constants
    SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]
    SHIFT = [0.0, 2.0, 0.0, 2.0, 5.5, 0.0, 0.0, 0.0, 0.0, 2.0]
    NAMED = [0.5, 0.4, 0.75, 0.90, 0.75, 0.75, 0.65, 0.75, 0.85, 0.7]
    P_MIN = 0.0035
    TOPK = 25
    VEL_DRIFT = 1.25
    VEL_CLIP = 4.0
    PLAY_DRIFT = 4.0
    MIX_ALPHA = 0.9
    MIX_WIDE = 1.25
    CLIMBER_MASS = {1: 0.18, 2: 0.18, 3: 0.15, 4: 0.12, 5: 0.12, 6: 0.06, 7: 0.06, 8: 0.06, 9: 0.06, 10: 0.06}
    CLIMBER_N = 4

    # Last read
    last_read = history[-1]
    closing_chart = last_read['up_and_coming']
    
    # Process chart games
    chart_games = {}
    for row in closing_chart:
        universe_id = row.get('universe_id')
        rank = row.get('rank')
        if universe_id is None or rank is None:
            continue
        try:
            chart_games[int(universe_id)] = {'rank': int(rank), 'playing': row.get('playing', 0)}
        except ValueError:
            continue

    # Helpers
    def get_rank(read, uid):
        for game in read['up_and_coming']:
            if game.get('universe_id') == uid:
                return game.get('rank')
        return None

    def get_playing(read, uid):
        for game in read['up_and_coming']:
            if game.get('universe_id') == uid:
                return game.get('playing')
        return None

    # Step 1: Rank Velocity
    v_ranks = {}
    N = len(history)
    for uid in chart_games:
        v_gaps = []
        # Need at least 3 reads total to have 2 gaps ending at N-1
        if N >= 3:
            # Gaps: N-3 -> N-2, N-2 -> N-1
            for i in range(N-3, N-1):
                read_a = history[i]
                read_b = history[i+1]
                t1 = parse_iso8601(read_a['at'])
                t2 = parse_iso8601(read_b['at'])
                dt = get_gap_hours(t1, t2)
                
                r1 = get_rank(read_a, uid)
                r2 = get_rank(read_b, uid)
                
                if r1 is not None and r2 is not None and dt > 0:
                    v_gaps.append((r2 - r1) / dt)
        
        if not v_gaps:
            v_rank = 0.0
        elif len(v_gaps) == 1:
            v_rank = v_gaps[0]
        else:
            # 0.65 * recent + 0.35 * older
            v_recent = v_gaps[1]
            v_older = v_gaps[0]
            v_rank = 0.65 * v_recent + 0.35 * v_older
        
        v_ranks[uid] = max(-VEL_CLIP, min(VEL_CLIP, v_rank))

    # Step 2: Log Playing Velocity
    v_plays = {}
    for uid in chart_games:
        v_gaps = []
        if N >= 3:
            for i in range(N-3, N-1):
                read_a = history[i]
                read_b = history[i+1]
                t1 = parse_iso8601(read_a['at'])
                t2 = parse_iso8601(read_b['at'])
                dt = get_gap_hours(t1, t2)
                
                p1 = get_playing(read_a, uid)
                p2 = get_playing(read_b, uid)
                
                if p1 is not None and p2 is not None and p1 > 0 and p2 > 0 and dt > 0:
                    v_gaps.append((math.log(p2) - math.log(p1)) / dt)
        
        if not v_gaps:
            v_plays[uid] = 0.0
        else:
            v_plays[uid] = sum(v_gaps) / len(v_gaps)

    # Step 3: Gaussian Mixtures
    probabilities = {} # (uid, place) -> p
    
    def phi(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    for k in range(1, 11):
        place_raw = []
        for uid, data in chart_games.items():
            r = data['rank']
            c = r + v_ranks[uid] * VEL_DRIFT - v_plays[uid] * PLAY_DRIFT + SHIFT[k-1]
            
            # Narrow
            sd = SD[k-1]
            p_n = phi((k + 0.5 - c) / sd) - phi((k - 0.5 - c) / sd)
            
            # Wide
            sd_w = SD[k-1] * MIX_WIDE
            p_w = phi((k + 0.5 - c) / sd_w) - phi((k - 0.5 - c) / sd_w)
            
            p = MIX_ALPHA * p_n + (1 - MIX_ALPHA) * p_w
            place_raw.append((uid, p))
            
        # Top 25
        place_raw.sort(key=lambda x: x[1], reverse=True)
        top25 = place_raw[:TOPK]
        sum_p = sum(x[1] for x in top25)
        
        if sum_p > 0:
            for uid, p in top25:
                probabilities[(uid, k)] = p * NAMED[k-1] / sum_p

    # Step 4: Climber Bonus
    climbers = sorted(chart_games.keys(), key=lambda uid: v_plays[uid], reverse=True)[:CLIMBER_N]
    climber_weights = {uid: max(v_plays[uid], 0.0)**2 for uid in climbers}
    W = sum(climber_weights.values())
    
    if W > 0:
        for k in range(1, 11):
            mass = CLIMBER_MASS[k]
            # Multiply existing by (1 - mass)
            for (uid, place), p in list(probabilities.items()):
                if place == k:
                    probabilities[(uid, place)] = p * (1 - mass)
            
            # Add climbers
            for uid in climbers:
                w = climber_weights[uid]
                if w > 0:
                    p = mass * w / W
                    probabilities[(uid, k)] = probabilities.get((uid, k), 0) + p

    # Step 5: Finalize
    final_probs = []
    for (uid, place), p in probabilities.items():
        if p >= P_MIN:
            final_probs.append({"universe_id": uid, "place": place, "p": round(p, 6)})
            
    # Sort
    final_probs.sort(key=lambda x: (x['place'], -x['p'], x['universe_id']))
    
    # Top 10
    top10_ids = [row['universe_id'] for row in sorted(closing_chart, key=lambda x: x['rank'])][:10]
    
    # Write output
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with open(os.path.join(output_dir, 'forecast.json'), 'w') as f:
        json.dump({"probabilities": final_probs, "top10": top10_ids}, f)

if __name__ == '__main__':
    main()
