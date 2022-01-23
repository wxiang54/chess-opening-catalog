import os
import json
import ujson
import pprint

import cli_util
from parse_pgn import read_headers, parse_headers, read_game, parse_game

### CONFIG
try:
    with open("config.json") as cfg_file:
        cfg = json.load(cfg_file)
except:
    raise OSError("ERROR: Cannot find/parse config file.")

DEBUG_MODE = cfg["DEBUG_MODE"]
EXTRA_DEBUG_MODE = cfg["EXTRA_DEBUG_MODE"]

STATS_DEPTH = cfg["STATS_DEPTH"]    # How many half-moves deep to go.
LABELS = cfg["STAT_LABEL"]


def build_stats_path(rating, depth=cfg["STATS_DEPTH"]):
    return os.path.join(cfg["STATS_DIR"], f'{str(rating)}{cfg["DEPTH_SUFFIX"]}{depth}{cfg["JSON_EXT"]}')

def build_sample_path(rating):
    return os.path.join(cfg["PGN_DIR"], cfg["BY_ELO_DIR"], f"{rating}{cfg['PGN_EXT']}")


def init_stats_dict():
    return {
        LABELS["TOTAL"]: 0,
        LABELS["WIN-W"]: 0,
        LABELS["WIN-B"]: 0,
        LABELS["DRAW"]: 0
    }

def update_dict(d, result):
    d["stats"][LABELS["TOTAL"]] += 1
    d["stats"][LABELS[result]] += 1


def get_result(headers):
    if cfg["PGN_HEADERS"]["RESULT"] not in headers:
        raise RuntimeError(cli_util.error(f"Result not found in headers: {headers}"))
    result = headers[cfg["PGN_HEADERS"]["RESULT"]]
    if result not in cfg["RESULTS"]:
        raise RuntimeError(cli_util.error(f"Invalid result: {result}"))
    return cfg["RESULTS"][result]

def has_valid_result(name, value):
    if name == cfg["PGN_HEADERS"]["RESULT"]:
        if value not in cfg["RESULTS"]:
            if DEBUG_MODE:
                print(cli_util.info(f"Invalid result: {value}. Skipping game..."))
            return -1
        return 1
    return 0


def get_counts_by_rating(rating):
    sample_path = build_sample_path(rating)
    num_games = 0
    num_games_expected = cfg["NUM_EXPECTED_GAMES"]["RATINGS"][str(rating)]

    # Initialize counts dict.
    counts_dict = {}
    counts_dict["stats"] = init_stats_dict()

    with open(sample_path, 'r') as sample_file:
        while True:
            try:
                headers = read_headers(sample_file, cond=has_valid_result)
            except EOFError:
                break
            if headers == "":   # Game was skipped (invalid result).
                continue

            headers = parse_headers(headers)
            result = get_result(headers)
            game = parse_game(read_game(sample_file))
            if len(game) > STATS_DEPTH:
                game = game[:STATS_DEPTH]

            update_dict(counts_dict, result)
            cur_obj = counts_dict
            for move in game:
                if move not in cur_obj:
                    cur_obj[move] = {"stats": init_stats_dict()}
                new_obj = cur_obj[move]
                update_dict(new_obj, result)
                cur_obj = new_obj
            num_games += 1

    print(cli_util.success(f"{num_games} games processed."))
    return counts_dict


def construct_move_dict(move, obj, parent):
    return {
        "move": move,
        "obj": obj,
        "parent": parent
    }

def depth_first_traverse_moves(obj):
    def DFT_inner(move, obj, parent):
        yield construct_move_dict(move, obj, parent)
        child_moves = {k:obj[k] for k in obj if k != "stats"}
        for move in child_moves:
            yield from DFT_inner(move, child_moves[move], obj)
    yield from DFT_inner("", obj, None)

from collections import deque
def breadth_first_traverse_moves(obj):
    yield construct_move_dict("", obj, None)
    queue = deque()
    queue.append(obj)
    while len(queue) > 0:
        cur_obj = queue.popleft()
        child_moves = {k:cur_obj[k] for k in cur_obj if k != "stats"}
        for move in child_moves:
            yield construct_move_dict(move, child_moves[move], cur_obj)
            queue.append(child_moves[move])


def read_stats(rating):
    stats_path = build_stats_path(rating)
    with open(stats_path, 'r') as stats_file:
        root_obj = json.load(stats_file)
    return root_obj

def write_stats(root_obj, rating):
    stats_path = build_stats_path(rating)
    with open(stats_path, 'w') as stats_file:
        ujson.dump(root_obj, stats_file)
    print(cli_util.success(f"Wrote stats to {stats_path}."))
    return


def normalize_counts(root_obj):
    for d in breadth_first_traverse_moves(root_obj):
        stats = d["obj"]["stats"]
        total = stats[LABELS["TOTAL"]]

        # Set percentages for white win, black win, and draw.
        for stat in ["WIN-W", "WIN-B", "DRAW"]:
            stats[LABELS[stat+"%"]] = round(stats[LABELS[stat]] / total, 3)

        # Calculate probability of move being played.
        if d["obj"] is not root_obj:
            parent_total = d["parent"]["stats"][LABELS["TOTAL"]]
            stats[LABELS["MOVE%"]] = round(total / parent_total, 3)

    return root_obj


if __name__ == "__main__":
    rating = 1200
    root_obj = get_counts_by_rating(rating)
    root_obj = normalize_counts(root_obj)
    write_stats(root_obj, rating)
