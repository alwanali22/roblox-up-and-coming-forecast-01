import json
import math
import os
import sys

# Constants from DESIGN-v2.md
SD = [1.75, 1.75, 1.0, 2.0, 1.75, 1.5, 2.75, 1.25, 4.0, 3.0]
SHIFT = [0.0, 2.0, 0.0, 2.0, 6.0, 0.0, 0.0, 0.0, 0.0, 2.0]
NAMED = [0.5, 0.4, 0.75, 0.95, 0.75, 0.75, 0.65, 0.75, 0.95, 0.7]
P_MIN = 0.0035
TOPK = 25

def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    history_file = os.path.join(input_dir, "history.ndjson")
    
    closing_chart = None
    with open(history_file, 'r') as f:
        for line in f:
            entry = json.loads(line)
            if "up_and_coming" in entry and entry["up_and_coming"]:
                # Robust parsing for game rows: skip if rank or universe_id missing/non-integer
                valid_games = []
                for game in entry["up_and_coming"]:
                    try:
                        int(game["rank"])
                        int(game["universe_id"])
                        valid_games.append(game)
                    except (KeyError, ValueError, TypeError):
                        continue
                if valid_games:
                    closing_chart = valid_games

    if closing_chart is None:
        raise ValueError("Could not find closing chart")

    # Map universe_id to closing rank (1-based)
    closing_ranks = {game["universe_id"]: game["rank"] for game in closing_chart}
    
    # top10 is the closing chart's top 10 universe ids in rank order
    top10_ids = [game["universe_id"] for game in sorted(closing_chart, key=lambda x: x["rank"])[:10]]

    all_probabilities = []

    # For each place k from 1 to 10
    for k in range(1, 11):
        place_probabilities = []
        for game in closing_chart:
            r = game["rank"]
            universe_id = game["universe_id"]
            
            # Formula: Phi((k + 0.5 - (r + SHIFT[k-1])) / SD[k-1]) 
            #        - Phi((k - 0.5 - (r + SHIFT[k-1])) / SD[k-1])
            mu = r + SHIFT[k-1]
            sigma = SD[k-1]
            
            p_raw = phi((k + 0.5 - mu) / sigma) - phi((k - 0.5 - mu) / sigma)
            
            place_probabilities.append({"universe_id": universe_id, "p": p_raw})
            
        # Sort by raw score, highest first, and keep top TOPK
        place_probabilities.sort(key=lambda x: x["p"], reverse=True)
        place_probabilities = place_probabilities[:TOPK]
        
        # Rescale
        sum_p = sum(item["p"] for item in place_probabilities)
        if sum_p > 0:
            for item in place_probabilities:
                item["p"] = (item["p"] * NAMED[k-1]) / sum_p
        
        # Drop rows below P_MIN
        final_place_probabilities = [item for item in place_probabilities if item["p"] >= P_MIN]
        
        # Round and format
        for item in final_place_probabilities:
            item["p"] = round(item["p"], 6)
            item["place"] = k
            all_probabilities.append(item)

    # Sort all_probabilities by place ascending, p descending, universe_id ascending
    all_probabilities.sort(key=lambda x: (x["place"], -x["p"], x["universe_id"]))

    output_data = {
        "probabilities": all_probabilities,
        "top10": top10_ids
    }

    with open(os.path.join(output_dir, "forecast.json"), 'w') as f:
        json.dump(output_data, f, separators=(',', ':'))

if __name__ == "__main__":
    main()
