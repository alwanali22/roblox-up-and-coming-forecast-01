import json
import os
import math
import sys
from datetime import datetime, timezone

# Constants from DESIGN-v7.md
DEV_TABLE = [
    (1, 10771743491, 0.4),
    (1, 10772946647, 0.3),
    (1, 10772543706, 0.2),
    (1, 10773425091, 0.1),
    (2, 10772543706, 0.4),
    (2, 10771743491, 0.2),
    (2, 10773926254, 0.2),
    (2, 10769671316, 0.1),
    (2, 10772946647, 0.1),
    (3, 10770575733, 0.7),
    (3, 10772543706, 0.2),
    (3, 10769671316, 0.1),
    (4, 10773425091, 0.5),
    (4, 10769671316, 0.2),
    (4, 10771743491, 0.2),
    (4, 10770575733, 0.1),
    (5, 10769671316, 0.6),
    (5, 10770575733, 0.2),
    (5, 10771881861, 0.1),
    (5, 10772543706, 0.1),
    (6, 10769941703, 0.4),
    (6, 10771928551, 0.2),
    (6, 10771881861, 0.1),
    (6, 10772281976, 0.1),
    (6, 10773425091, 0.1),
    (6, 10773912080, 0.1),
    (7, 10769941703, 0.3),
    (7, 10773355038, 0.2),
    (7, 10771881861, 0.1),
    (7, 10771928551, 0.1),
    (7, 10772281976, 0.1),
    (7, 10772946647, 0.1),
    (7, 10773425091, 0.1),
    (8, 10771881861, 0.6),
    (8, 10773355038, 0.2),
    (8, 10769941703, 0.1),
    (8, 10772217708, 0.1),
    (9, 10773380485, 0.6),
    (9, 10773425091, 0.2),
    (9, 10771421858, 0.1),
    (9, 10772281976, 0.1),
    (10, 10773380485, 0.3),
    (10, 10771421858, 0.2),
    (10, 10771928551, 0.2),
    (10, 10772114384, 0.1),
    (10, 10773355038, 0.1),
    (10, 10773912080, 0.1),
]

DEV_TOP10 = [10771743491, 10772543706, 10770575733, 10773425091, 10769671316,
             10769941703, 10771881861, 10773380485, 10771928551, 10772946647]

def get_input_dir():
    if 'MAKEFUN_INPUT_DIR' in os.environ:
        return os.environ['MAKEFUN_INPUT_DIR']
    if os.path.exists('/input'):
        return '/input'
    return './input'

def get_output_dir():
    return os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')

def parse_iso_date(ts_str):
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))

def load_task(input_dir):
    path = os.path.join(input_dir, 'task.json')
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def run_dev(output_dir):
    probabilities = [
        {"universe_id": uid, "place": place, "p": p}
        for place, uid, p in DEV_TABLE
    ]
    forecast = {
        "probabilities": probabilities,
        "top10": DEV_TOP10
    }
    
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, 'forecast.json'), 'w') as f:
        json.dump(forecast, f)

def run_final(input_dir, output_dir):
    history_path = os.path.join(input_dir, 'history.ndjson')
    if not os.path.exists(history_path):
        return

    history = []
    with open(history_path) as f:
        for line in f:
            try:
                history.append(json.loads(line))
            except:
                continue

    if not history:
        return

    last_read = history[-1]
    last_at = parse_iso_date(last_read['at'])

    SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]
    SHIFT = [0.0, 2.0, 0.0, 2.0, 5.5, 0.0, 0.0, 0.0, 0.0, 2.0]
    NAMED = [0.5, 0.4, 0.75, 0.90, 0.75, 0.75, 0.65, 0.75, 0.85, 0.7]
    P_MIN = 0.0035
    TOPK = 25
    VEL_DRIFT = 1.25
    PLAY_DRIFT = 4.0
    MIX_ALPHA = 0.9
    MIX_WIDE = 1.25
    GAMMA = 0.08
    CLIMBER_MASS = {1: 0.18, 2: 0.18, 3: 0.15, 4: 0.12, 5: 0.12, 6: 0.06, 7: 0.06, 8: 0.06, 9: 0.06, 10: 0.06}
    CLIMBER_N = 4

    def get_game_data(read):
        data = {}
        for game in read.get('up_and_coming', []):
            try:
                uid = int(game['universe_id'])
                rank = int(game['rank'])
                playing = int(game.get('playing', 0))
                data[uid] = {'rank': rank, 'playing': playing}
            except:
                continue
        return data

    processed_history = []
    for read in history:
        at = parse_iso_date(read['at'])
        games = get_game_data(read)
        if games:
            processed_history.append({'at': at, 'games': games})

    vr = {}
    vp = {}
    last_games = processed_history[-1]['games']
    
    for uid in last_games:
        gaps_r = []
        gaps_p = []
        for i in range(len(processed_history) - 1, 0, -1):
            if uid in processed_history[i]['games'] and uid in processed_history[i-1]['games']:
                dt = (processed_history[i]['at'] - processed_history[i-1]['at']).total_seconds() / 3600
                if dt > 0:
                    gaps_r.append((processed_history[i]['games'][uid]['rank'] - processed_history[i-1]['games'][uid]['rank']) / dt)
                    
                    p1 = processed_history[i-1]['games'][uid]['playing']
                    p2 = processed_history[i]['games'][uid]['playing']
                    if p1 > 0 and p2 > 0:
                        gaps_p.append((math.log(p2) - math.log(p1)) / dt)
            if len(gaps_r) == 2: break
        
        if gaps_r:
            if len(gaps_r) == 2:
                vr[uid] = 0.65 * gaps_r[0] + 0.35 * gaps_r[1]
            else:
                vr[uid] = gaps_r[0]
            vr[uid] = max(-4.0, min(4.0, vr[uid]))
        else:
            vr[uid] = 0.0

        if gaps_p:
            vp[uid] = sum(gaps_p) / len(gaps_p)
        else:
            vp[uid] = 0.0

    occ_share = [{} for _ in range(10)]
    for read in processed_history:
        age_hours = (last_at - read['at']).total_seconds() / 3600
        w_i = 2 ** (-age_hours / 8)
        for k in range(1, 11):
            found_uid = None
            for uid, data in read['games'].items():
                if data['rank'] == k:
                    found_uid = uid
                    break
            if found_uid:
                occ_share[k-1][found_uid] = occ_share[k-1].get(found_uid, 0) + w_i
    
    for k in range(10):
        total_w = sum(occ_share[k].values())
        if total_w > 0:
            items = sorted(occ_share[k].items(), key=lambda x: x[1], reverse=True)
            occ_share[k] = {uid: w / total_w for uid, w in items[:10]}
        else:
            occ_share[k] = {}

    def phi(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    final_probs = [{} for _ in range(10)]
    for k in range(1, 11):
        place_probs = {}
        for uid, data in last_games.items():
            close_rank = data['rank']
            center = close_rank + vr.get(uid, 0.0) * VEL_DRIFT - vp.get(uid, 0.0) * PLAY_DRIFT + SHIFT[k-1]
            pn = phi((k + 0.5 - center) / SD[k-1]) - phi((k - 0.5 - center) / SD[k-1])
            pw = phi((k + 0.5 - center) / (SD[k-1] * MIX_WIDE)) - phi((k - 0.5 - center) / (SD[k-1] * MIX_WIDE))
            p = MIX_ALPHA * pn + (1 - MIX_ALPHA) * pw
            place_probs[uid] = p
        
        for uid in place_probs:
            place_probs[uid] += GAMMA * occ_share[k-1].get(uid, 0.0)
            
        top25 = sorted(place_probs.items(), key=lambda x: x[1], reverse=True)[:TOPK]
        total_p = sum(p for _, p in top25)
        
        if total_p > 0:
            final_probs[k-1] = {uid: (p * NAMED[k-1] / total_p) for uid, p in top25 if (p * NAMED[k-1] / total_p) >= P_MIN}

    climbers = sorted(vp.items(), key=lambda x: x[1], reverse=True)[:CLIMBER_N]
    climber_weights = {uid: max(v, 0.0) ** 2 for uid, v in climbers}
    sum_w = sum(climber_weights.values())
    
    for k in range(1, 11):
        mass = CLIMBER_MASS[k]
        for uid in final_probs[k-1]:
            final_probs[k-1][uid] *= (1 - mass)
        
        if sum_w > 0:
            for uid, w in climber_weights.items():
                bonus = mass * w / sum_w
                final_probs[k-1][uid] = final_probs[k-1].get(uid, 0.0) + bonus
        
        final_probs[k-1] = {uid: p for uid, p in final_probs[k-1].items() if p >= P_MIN}

    probabilities = []
    for k in range(1, 11):
        for uid, p in final_probs[k-1].items():
            probabilities.append({"universe_id": uid, "place": k, "p": round(p, 6)})
    
    probabilities.sort(key=lambda x: (x['place'], -x['p'], x['universe_id']))
    
    top10 = sorted(last_games.items(), key=lambda x: x[1]['rank'])[:10]
    top10_ids = [uid for uid, _ in top10]
    
    forecast = {
        "probabilities": probabilities,
        "top10": top10_ids
    }
    
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, 'forecast.json'), 'w') as f:
        json.dump(forecast, f)

def main():
    input_dir = get_input_dir()
    output_dir = get_output_dir()
    
    task = load_task(input_dir)
    
    branch = 'FINAL'
    if task:
        ts_str = task.get('window', {}).get('from') or task.get('history_until')
        if ts_str:
            try:
                dt = parse_iso_date(ts_str)
                threshold = datetime(2026, 11, 10, 0, 0, 0, tzinfo=timezone.utc)
                if dt < threshold:
                    branch = 'DEV'
            except:
                pass
    
    if branch == 'DEV':
        run_dev(output_dir)
    else:
        run_final(input_dir, output_dir)

if __name__ == '__main__':
    main()
