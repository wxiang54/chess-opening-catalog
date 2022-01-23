import os
import json
import random

import cli_util

from parse_pgn import read_headers, read_game, skip_game

### CONFIG
try:
    with open("config.json") as cfg_file:
        cfg = json.load(cfg_file)
except:
    raise OSError("ERROR: Cannot find/parse config file.")

DEBUG_MODE = cfg["DEBUG_MODE"]
EXTRA_DEBUG_MODE = cfg["EXTRA_DEBUG_MODE"]

PGN_TO_USE = "SAMPLE2"
PGN_PATH = os.path.join(cfg["PGN_DIR"], cfg["SANITIZED_DIR"],
    os.path.splitext(cfg["PGN_FILENAME_SRC"][PGN_TO_USE])[0] +
        cfg["SANITIZED_SUFFIX"] + cfg["PGN_EXT"])

MODE_TO_USE = "ALL" # "MASTERS" or "ALL"

FIRST_PLAYER_VALID = False  # Must reset to False after each game.
CUR_RATING = 0


def players_in_rating(name, value):
    global FIRST_PLAYER_VALID, CUR_RATING
    if name in (cfg["PGN_HEADERS"]["ELO-W"], cfg["PGN_HEADERS"]["ELO-B"]):
        if value.isdigit() and CUR_RATING-cfg["RATING_DEV"] <= int(value) <= CUR_RATING+cfg["RATING_DEV"]:
            if cfg["DEBUG_MODE"]:
                print(cli_util.info(f"elo within range: {value}"))
            if FIRST_PLAYER_VALID:
                FIRST_PLAYER_VALID = False
                return 1
            FIRST_PLAYER_VALID = True
            return 0
        FIRST_PLAYER_VALID = False
        return -1
    return 0


def separate_by_elo(rating):
    # Create a new pgn file for specified elo.
    # sanitized --> by-elo
    global FIRST_PLAYER_VALID, CUR_RATING
    CUR_RATING = rating
    ratings_dict = cfg["NUM_EXPECTED_GAMES"]["RATINGS"]

    out_path = os.path.join(cfg["PGN_DIR"], cfg["BY_ELO_DIR"], str(rating)+cfg["PGN_EXT"])
    cnt = 0
    cnt_total = 0
    batch = []
    with open(PGN_PATH, 'r') as pgn_file, open(out_path, 'w') as out_file:
        while True:
            FIRST_PLAYER_VALID = False
            try:
                headers = read_headers(pgn_file, cond=players_in_rating)
            except EOFError:
                break

            cnt_total += 1
            if headers == "":   # Game was skipped.
                continue

            # Record the game.
            game = "\n".join((headers, read_game(pgn_file), ""))
            batch.append(game)
            if len(batch) >= cfg["BATCH_SIZE"]:
                cnt += cfg["BATCH_SIZE"]
                out_file.write("".join(batch))
                batch = []
        if batch:
            cnt += len(batch)
            out_file.write("".join(batch))

    print(cli_util.success(f"Wrote {cnt} games to {out_path} (out of {cnt_total})."))
    return


if __name__ == "__main__":
    separate_by_elo(1200)
