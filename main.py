import json
import math
import os
from datetime import datetime

# Constants
SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]
SHIFT = [0.0, 2.0, 0.0, 2.0, 6.0, 0.0, 0.0, 0.0, 0.0, 2.0]
NAMED = [0.5, 0.4, 0.75, 0.95, 0.75, 0.75, 0.65, 0.75, 0.95, 0.7]
P_MIN = 0.0035
TOPK = 25
VEL_DRIFT = 1.25
VEL_CLIP = 4.0
PLAY_DRIFT = 4.0
CLIMBER_MASS_TOP = 0.125
CLIMBER_MASS_LOW = 0.06
CLIMBER_N = 6

def Phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def get_dt_hours(at_a, at_b):
    dt_a = datetime.fromisoformat(at_a.replace('Z', '+00:00'))
    dt_b = datetime.fromisoformat(at_b.replace('Z', '+00:00'))
    return (dt_b - dt_a).total_seconds() / 3600.0

def main():
    input_dir = os.environ.get('MAKEFUN_INPUT_DIR', '/input')
    output_dir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    
    os.makedirs(output_dir, exist_ok=True)
    
    history = []
    with open(os.path.join(input_dir, 'history.ndjson'), 'r') as f:
        for line in f:
            read = json.loads(line)
            valid_games = []
            for g in read.get('up_and_coming', []):
                try:
                    rank = g.get('rank')
                    u_id = g.get('universe_id')
                    if isinstance(rank, int) and isinstance(u_id, int):
                        valid_games.append(g)
                except Exception:
                    continue
            read['up_and_coming'] = valid_games
            history.append(read)
            
    closing_chart = history[-1]['up_and_coming']
    # Build maps
    closing_rank = {g['universe_id']: g['rank'] for g in closing_chart}
    closing_playing = {g['universe_id']: g['playing'] for g in closing_chart}
    
    # Velocity calculation
    v_ranks = {}
    v_plays = {}
    
    if len(history) >= 3:
        read_n1 = history[-1]
        read_n2 = history[-2]
        read_n3 = history[-3]
        
        for g_id in closing_rank:
            # Rank velocity
            gap1_rank = None
            gap2_rank = None
            
            # Gap 1 (N-2 -> N-1)
            rank_n1 = next((g['rank'] for g in read_n1['up_and_coming'] if g['universe_id'] == g_id), None)
            rank_n2 = next((g['rank'] for g in read_n2['up_and_coming'] if g['universe_id'] == g_id), None)
            if rank_n1 is not None and rank_n2 is not None:
                dt1 = get_dt_hours(read_n2['at'], read_n1['at'])
                if dt1 > 0:
                    gap1_rank = (rank_n1 - rank_n2) / dt1
            
            # Gap 2 (N-3 -> N-2)
            rank_n2 = next((g['rank'] for g in read_n2['up_and_coming'] if g['universe_id'] == g_id), None)
            rank_n3 = next((g['rank'] for g in read_n3['up_and_coming'] if g['universe_id'] == g_id), None)
            if rank_n2 is not None and rank_n3 is not None:
                dt2 = get_dt_hours(read_n3['at'], read_n2['at'])
                if dt2 > 0:
                    gap2_rank = (rank_n2 - rank_n3) / dt2
            
            if gap1_rank is not None and gap2_rank is not None:
                v_rank = 0.65 * gap1_rank + 0.35 * gap2_rank
            elif gap1_rank is not None:
                v_rank = gap1_rank
            elif gap2_rank is not None:
                v_rank = gap2_rank
            else:
                v_rank = 0.0
                
            v_ranks[g_id] = max(-VEL_CLIP, min(VEL_CLIP, v_rank))
            
            # Log playing velocity
            gap1_play = None
            gap2_play = None
            
            # Gap 1 (N-2 -> N-1)
            play_n1 = next((g['playing'] for g in read_n1['up_and_coming'] if g['universe_id'] == g_id), None)
            play_n2 = next((g['playing'] for g in read_n2['up_and_coming'] if g['universe_id'] == g_id), None)
            if play_n1 is not None and play_n2 is not None and play_n1 > 0 and play_n2 > 0:
                dt1 = get_dt_hours(read_n2['at'], read_n1['at'])
                if dt1 > 0:
                    gap1_play = (math.log(play_n1) - math.log(play_n2)) / dt1
            
            # Gap 2 (N-3 -> N-2)
            play_n2 = next((g['playing'] for g in read_n2['up_and_coming'] if g['universe_id'] == g_id), None)
            play_n3 = next((g['playing'] for g in read_n3['up_and_coming'] if g['universe_id'] == g_id), None)
            if play_n2 is not None and play_n3 is not None and play_n2 > 0 and play_n3 > 0:
                dt2 = get_dt_hours(read_n3['at'], read_n2['at'])
                if dt2 > 0:
                    gap2_play = (math.log(play_n2) - math.log(play_n3)) / dt2
            
            plays = [p for p in [gap1_play, gap2_play] if p is not None]
            if plays:
                v_plays[g_id] = sum(plays) / len(plays)
            else:
                v_plays[g_id] = 0.0
    else:
        for g_id in closing_rank:
            v_ranks[g_id] = 0.0
            v_plays[g_id] = 0.0

    # Gaussian probabilities
    probs = {}
    for k in range(1, 11):
        place_probs = []
        for g_id, r in closing_rank.items():
            c = r + v_ranks.get(g_id, 0.0) * VEL_DRIFT - v_plays.get(g_id, 0.0) * PLAY_DRIFT + SHIFT[k-1]
            p = Phi((k + 0.5 - c) / SD[k-1]) - Phi((k - 0.5 - c) / SD[k-1])
            place_probs.append({'universe_id': g_id, 'p': p})
            
        place_probs.sort(key=lambda x: x['p'], reverse=True)
        place_probs = place_probs[:TOPK]
        t = sum(x['p'] for x in place_probs)
        if t > 0:
            for x in place_probs:
                x['p'] *= (NAMED[k-1] / t)
        else:
            for x in place_probs:
                x['p'] = 0.0
        
        probs[k] = place_probs

    # Climber bonus
    climbers = sorted(v_plays.items(), key=lambda x: x[1], reverse=True)[:CLIMBER_N]
    climber_weights = {g_id: max(v, 0.0)**2 for g_id, v in climbers}
    total_weight = sum(climber_weights.values())
    
    for k in range(1, 11):
        mass = CLIMBER_MASS_TOP if k <= 5 else CLIMBER_MASS_LOW
        
        # Apply mass
        for x in probs[k]:
            x['p'] *= (1 - mass)
        
        # Add climbers
        if total_weight > 0:
            for g_id, w in climber_weights.items():
                if w > 0:
                    p_climber = mass * w / total_weight
                    probs[k].append({'universe_id': g_id, 'p': p_climber})
    
    # Merge and format
    final_probs = []
    for k in range(1, 11):
        merged = {}
        for row in probs[k]:
            g_id = row['universe_id']
            merged[g_id] = merged.get(g_id, 0.0) + row['p']
        
        for g_id, p in merged.items():
            if p >= P_MIN:
                final_probs.append({'universe_id': g_id, 'place': k, 'p': round(p, 6)})
                
    top10 = [g['universe_id'] for g in sorted(closing_chart, key=lambda x: x['rank'])[:10]]
    
    final_probs.sort(key=lambda x: (x['place'], -x['p'], x['universe_id']))
    
    with open(os.path.join(output_dir, 'forecast.json'), 'w') as f:
        json.dump({'probabilities': final_probs, 'top10': top10}, f)

if __name__ == '__main__':
    main()
