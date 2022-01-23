import os
import json

import cli_util

### CONFIG
try:
    with open("config.json") as cfg_file:
        cfg = json.load(cfg_file)
except:
    raise OSError("ERROR: Cannot find/parse config file.")

DEBUG_MODE = cfg["DEBUG_MODE"]
EXTRA_DEBUG_MODE = cfg["EXTRA_DEBUG_MODE"]

SKIPPED_GAME = False


def parse_header(header):
    header = header.strip("\n[]")
    name, value = header.split(" ", 1)
    return (name, value.strip('"'))


def parse_headers(headers):
    headers = headers.strip().split("\n")
    ret = {}
    for header in headers:
        name, value = header.strip("[]").split(" ", 1)
        ret[name] = value.strip('"')
    return ret


def default_true(name, value):
    return True

def read_headers(pgn_file, cond=default_true, headers_to_remove=None):
    # If game is valid according to cond, return str of headers.
    # Otherwise, if the game may be followed by more games, return empty string.
    # cond should return: -1 for invalid, 1 for valid, 0 for currently unsure.
    if headers_to_remove is None:
        headers_to_remove = []
    cond_fulfilled = False
    headers = []
    while True:
        line = pgn_file.readline()
        if EXTRA_DEBUG_MODE:
            print(cli_util.header(f"read_headers() reading line: {line.strip()}"))

        if line == "" or line == "\n":
            if cond_fulfilled:
                return "".join(headers)
            if line == "":
                raise EOFError
            # Reached end of headers without seeing TimeControl: skip game.
            skip_game(pgn_file)
            return ""

        if line[0] == "[":
            parsed = parse_header(line)
            name, value = parsed
            if name in headers_to_remove:
                continue
            ret = cond(name, value)
            if ret < 0:
                # Invalid game, skip to next game.
                skip_game(pgn_file, newline=False)
                return ""
            elif ret > 0:
                # print("Time control is VALID")
                cond_fulfilled = True
            headers.append(line)


def parse_game(game):
    # Expects movelist/result only, not headers.
    game = game.strip().split(" ")
    game = filter(lambda token: not token[0].isdigit(), game)
    return list(game)


def game_to_pgn(move_list):
    move_ctr = 1
    num_halfmoves = 0
    ret = []
    for move in move_list:
        if num_halfmoves % 2 == 0:
            ret.append(f"{move_ctr}.")
            move_ctr += 1
        ret.append(move)
        num_halfmoves += 1
    return " ".join(ret)


def read_game(pgn_file):
    prev_line = ""
    while True:
        line = pgn_file.readline()
        if EXTRA_DEBUG_MODE:
            print(cli_util.warn(f"read_game() reading line: {line.strip()}"))
        if line == "" or line == "\n":
            return prev_line
        prev_line = line


def skip_game(pgn_file, newline=True):
    # Skip exactly 2 blank newlines (one before game, one after game)
    #  to get to next set of headers.
    num_newline = 1 if newline else 0
    while True:
        line = pgn_file.readline()
        if EXTRA_DEBUG_MODE:
            print(cli_util.success(f"skip_game() reading line: {line.strip()}"))
        if line == "":
            raise EOFError
        if line == "\n":
            num_newline += 1
        if num_newline == 2:
            return


if __name__ == "__main__":
    print(game_to_pgn(["e4", "e5", "Nf3", "Nc6"]))
    print(game_to_pgn(["e4", "e5", "Nf3", "Nc6", "Bc4"]))
