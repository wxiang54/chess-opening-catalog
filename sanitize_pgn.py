import json
import os
import re

import cli_util

from parse_pgn import read_headers, skip_game

### CONFIG
try:
    with open("config.json") as cfg_file:
        cfg = json.load(cfg_file)
except:
    raise OSError("ERROR: Cannot find/parse config file.")


DEBUG_MODE = cfg["DEBUG_MODE"]
EXTRA_DEBUG_MODE = cfg["EXTRA_DEBUG_MODE"]
PGN_TO_USE = "SAMPLE2"
MODE_TO_USE = "ALL" #MASTERS or ALL

HEADERS_TO_REMOVE = {"UTCDate", "UTCTime", "WhiteRatingDiff", "BlackRatingDiff", "Termination",
    "White", "Black", "WhiteTitle", "BlackTitle", "Date", "Round", "Event", "LichessURL", "Site"}
SANITIZE_REGEX = re.compile(" \{.+?\}| \$\d+| \d+\.\.\.|[?!]")

# Merged valid time-controls for blitz, rapid, and classical.
TC_BRC = set(sum([cfg["TC"][tc] for tc in ["BLITZ", "RAPID", "CLASSICAL"]], []))


def is_valid_tc(name, value):
    if name == cfg["PGN_HEADERS"]["TIME"]:
        if value not in TC_BRC:
            if DEBUG_MODE:
                print(cli_util.info(f"Invalid TC: {value}. Skipping game..."))
            return -1
        return 1
    return 0


def read_game_unsanitized(pgn_file, mode):
    lines = []
    while True:
        line = pgn_file.readline()
        if EXTRA_DEBUG_MODE:
            print(cli_util.warn(f"read_game() reading line: {line.strip()}"))
        if line == "" or line == "\n":
            if mode == "MASTERS" and len(lines) > 0:
                return "".join(lines[:-1]) + "\n"  # Slice list to skip the final space.
            return "".join(lines)
        if mode == "MASTERS":
            lines.append(line.strip("\n"))
            lines.append(" ")
        else:
            # Remove clock/eval data.
            lines.append(re.sub(SANITIZE_REGEX, '', line))


def sanitize_games(pgn_file):
    batch = []
    num_keep = 0
    num_games = 0

    src_filename = os.path.splitext(cfg["PGN_FILENAME_SRC"][PGN_TO_USE])[0]
    out_path = (cfg["PGN_DIR"] + cfg["SANITIZED_DIR"] + src_filename +
        cfg["SANITIZED_SUFFIX"] + cfg["PGN_EXT"])
    with open(out_path, 'w') as out_file:
        while True:
            try:
                headers = read_headers(pgn_file, is_valid_tc, HEADERS_TO_REMOVE)
            except EOFError:
                break

            num_games += 1
            if headers == "":   # Game was skipped.
                continue

            # Record the game.
            game = "\n".join((headers, read_game_unsanitized(pgn_file, MODE_TO_USE), ""))
            batch.append(game)

            if len(batch) >= cfg["BATCH_SIZE"]:
                num_keep += cfg["BATCH_SIZE"]
                out_file.write("".join(batch))
                batch = []

        if batch:
            num_keep += len(batch)
            out_file.write("".join(batch))

    print(cli_util.success(f"Retained and sanitized {num_keep} out of {num_games} games."))


if __name__ == "__main__":
    with open(cfg['PGN_DIR'] + cfg['SRC_DIR'] + cfg['PGN_FILENAME_SRC'][PGN_TO_USE], 'r') as f:
        sanitize_games(f)
