import chess
import chess.pgn
import os
import json
import ujson
import itertools
import pprint

from cli_util import error, warn, success, info, header, confirm
from parse_pgn import parse_game
from analyze_sample import build_stats_path

### CONFIG
try:
    with open("config.json") as cfg_file:
        cfg = json.load(cfg_file)
except:
    raise OSError("ERROR: Cannot find/parse config file.")

DEBUG_MODE = cfg["DEBUG_MODE"]
EXTRA_DEBUG_MODE = cfg["EXTRA_DEBUG_MODE"]
OPENINGS_JSON = cfg["OPENINGS_JSON"] + cfg["JSON_EXT"]
LABELS = cfg["STAT_LABEL"]


with open(OPENINGS_JSON, 'r') as openings_file:
    OPENINGS = json.load(openings_file)

RATING = cfg["STATS_RATING"]
def get_stats():
    stats_path = build_stats_path(RATING)
    with open(stats_path, 'r') as stats_file:
        stats = json.load(stats_file)
    return stats

STATS = get_stats()


def split_moves_by_color(moves):
    return (moves[::2], moves[1::2])    # (White, Black)

def get_main_line(opening):
    return OPENINGS[opening]["main"]

def get_opening_color(opening):
    opening_obj = OPENINGS[opening]
    main_line = opening_obj["main_real"] if "main_real" in opening_obj else opening_obj["main"]
    moves = parse_game(main_line)
    return chess.BLACK if len(moves)%2 == 0 else chess.WHITE


def find_transpositions(opening, append_existing=False):
    '''Interactive CLI utility to manually identify feasible transpositions.'''
    if DEBUG_MODE:
        print(header(f"Finding transpositions for: {opening}"))

    main_line = get_main_line(opening)
    moves_main = parse_game(main_line)
    transpositions = []
    if "transpositions" in OPENINGS[opening]:
        if not append_existing:
            if DEBUG_MODE:
                print(warn(f"Skipping {opening} (trans. already present)."))
            return
        confirmed = confirm(f"Transpositions already present for {opening}. Add more?")
        if not confirmed:
            return
    else:
        OPENINGS[opening]["transpositions"] = []
    if len(moves_main) <= 2:
        if DEBUG_MODE:
            print(info(f"No transpositions possible for {opening}."))
        write_opening_stats()
        return   # No transpositions possible.

    moves_W, moves_B = split_moves_by_color(moves_main)
    perms_W = itertools.permutations(moves_W)
    perms_B = itertools.permutations(moves_B)
    all_lines = itertools.product(perms_W, perms_B)
    board = chess.Board()

    for white_moves, black_moves in all_lines:
        board.reset()
        is_legal = True
        zipped = itertools.zip_longest(white_moves, black_moves, fillvalue="")
        all_moves = list(itertools.chain.from_iterable(zipped))
        all_moves_cleaned = []
        if all_moves[-1] == '':
            all_moves.pop()
        for move in all_moves:
            try:
                all_moves_cleaned.append(board.san(board.parse_san(move)))
                board.push_san(move)
            except ValueError:
                is_legal = False
                break
        if is_legal:
            moves_str = game_to_pgn(all_moves_cleaned)
            transpositions.append(moves_str)

    for transposition in transpositions:
        if transposition in OPENINGS[opening]["transpositions"] or transposition == main_line:
            if EXTRA_DEBUG_MODE:
                print(info(f"Skipped {transposition}"))
            continue
        confirmed = confirm(f"Is [{transposition}] a plausible line?")
        if confirmed:
            OPENINGS[opening]["transpositions"].append(transposition)

    print(header("###  All Transpositions ###"))
    for line in OPENINGS[opening]["transpositions"]:
        print(" * " + line)
    write_opening_stats()


def calc_attainability_line(moves, color):
    # Calculate attainability of a single line, FOR the given color.
    # Essentially calculates chance of opposite color making their moves.
    attainability = 1
    moves = parse_game(moves)
    cur_obj = STATS
    cur_color = chess.WHITE
    for cur_move in moves:
        if cur_move not in cur_obj:
            if DEBUG_MODE:
                print(error(f"Move {cur_move} not found. Assuming zero attainability."))
            attainability = 0
            break
        cur_obj = cur_obj[cur_move]

        if cur_color != color:  # Opposite color's move
            prob = cur_obj["stats"][LABELS["MOVE%"]]
            attainability *= prob
            if EXTRA_DEBUG_MODE:
                print(info(f"{prob} chance opp. plays {cur_move}."))
        cur_color = not cur_color   # Flip color.
    if DEBUG_MODE:
        success(f"Attainability = {attainability}")
    return attainability


def calc_attainability(opening, color):
    # If opposite color, we are finding prevalence,
    #  which is calculated slightly differently.
    opening_color = get_opening_color(opening)
    is_opposite_color = color != opening_color

    if opening not in OPENINGS:
        raise KeyError(error(f"Opening {opening} not found in json."))

    main_line = parse_game(get_main_line(opening))
    transpositions = OPENINGS[opening]["transpositions"]
    transpositions = [parse_game(line) for line in transpositions]

    # Split moves into decision tree.
    tree_root = {}
    cur_obj = tree_root
    for move in main_line:
        cur_obj[move] = {}
        cur_obj = cur_obj[move]
    for line in transpositions:
        cur_obj = tree_root
        for move in line:
            if move not in cur_obj:
                cur_obj[move] = {}
            cur_obj = cur_obj[move]

    # Recurse down the tree.
    MOVE_STACK = []     # Used for debugging.
    def calc_att_inner(tree_obj, stats_obj, cur_color):
        # tree_obj: Current object from decision tree.
        # stats_obj: Current object from stats json.
        # cur_color: Whose turn it is to move.
        # Find max of children's attainabilities multiplied by:
            # 1 if own color to move.
            # MOVE% if opposite color to move.
        if EXTRA_DEBUG_MODE:
            if MOVE_STACK:
                print(header(f"{MOVE_STACK} Calc att for {MOVE_STACK[-1]}"))

        moves = list(tree_obj.keys())
        att_base = 1
        if len(moves) > 0:
            recurse_revcolor = lambda move: calc_att_inner(tree_obj[move], stats_obj[move], not cur_color)
            if len(moves) == 1:
                move = moves[0]
                if move not in stats_obj:
                    if EXTRA_DEBUG_MODE:
                        print(error(f'No stats for {move} -> att=0'))
                    return 0    # No stats for this move.
                MOVE_STACK.append(move)
                att_base = recurse_revcolor(move)
                MOVE_STACK.pop()

            else:
                atts = {}   # Map moves to their att.
                att_max = 0     # Need to maintain this to keep track of move.
                move_max = None
                if EXTRA_DEBUG_MODE:
                    print(success(f"{MOVE_STACK} Checking P between: {moves}"))
                for move in moves:
                    if move not in stats_obj:
                        if EXTRA_DEBUG_MODE:
                            print(error(f'No stats for {move} -> Skipping'))
                        continue    # No stats for this move.
                    MOVE_STACK.append(move)
                    att = recurse_revcolor(move)
                    atts[move] = att
                    if att > att_max:
                        att_max = att
                        move_max = move
                    MOVE_STACK.pop()
                    if EXTRA_DEBUG_MODE:
                        print(success("==="))

                '''
                is_opposite_color indicates prev calc (True) or att calc (False).
                prev, same color: 1 * sum
                prev, diff color: MOVE% * weighted sum
                att, same color: 1 * sum
                att, diff color: MOVE% * max(children)
                '''
                if cur_color == color:
                    # Continuations are my opponent's: Sum P of their replies.
                    att_base = sum(atts.values())
                    if EXTRA_DEBUG_MODE:
                        print(warn(f"{MOVE_STACK} Sum att: {att_base}"))
                elif is_opposite_color:
                    # Continuations are mine, but have to normalize by weighting sum terms by move probability.
                    probs = {move: stats_obj[move]["stats"][LABELS["MOVE%"]] for move in atts}
                    denom = sum(probs.values())
                    att_base = 0
                    for move in probs:
                        att_base += atts[move] * (probs[move] / denom)

                    if EXTRA_DEBUG_MODE:
                        print(warn(f"{MOVE_STACK} Weighted sum att: {att_base}"))
                else:
                    # Continuations are mine: Find "best try" which maximizes P.
                    if move_max is None:
                        if EXTRA_DEBUG_MODE:
                            print(error(f'{MOVE_STACK} No valid continuations -> att=0'))
                        return 0
                    att_base = att_max
                    tree_obj[move_max]["best_try"] = True
                    tree_obj[move_max]["att"] = att_max
                    if EXTRA_DEBUG_MODE:
                        print(warn(f"{MOVE_STACK} Found max att: {att_max} from {move_max}"))

        if cur_color != color and tree_obj is not tree_root:
            # Opposite player's move
            att_base *= stats_obj["stats"][LABELS["MOVE%"]]

        if EXTRA_DEBUG_MODE:
            print(warn(f"{MOVE_STACK} Final att: {att_base}"))

        return att_base

    # Root = Black, so that first move flips to White.
    ret = calc_att_inner(tree_root, STATS, chess.BLACK)
    if is_opposite_color:
        return (ret, None)
    else:
        btl = generate_BTL(opening, tree_root, color, opening_color)
        if btl == "*":
            print(error(f"No BTL for {opening}"))
        return (ret, btl)

    return ret


def generate_BTL(opening, tree_root, color, opening_color):
    # Generate "best-try lines" for an opening.
    is_opposite_color = color != opening_color
    if is_opposite_color:
        return ""   # No nodes got marked "best_try".
    cur_obj = tree_root
    board = chess.Board()
    game = chess.pgn.Game()

    def generate_BTL_inner(cur_obj, parent_node):
        if "best_try" in cur_obj:
            del cur_obj["best_try"]
            del cur_obj["att"]
        if len(cur_obj) == 1:
            # One move to be made. No ambiguity.
            move = next(iter(cur_obj))
            move_obj = board.push_san(move)
            node = parent_node.add_variation(move_obj)
            generate_BTL_inner(cur_obj[move], node)
            board.pop()
            return

        # More than one option to be played.
        if opening_color == board.turn:
            # My turn: Recurse on best try.
            best_try = None
            for move in cur_obj:
                if "best_try" in cur_obj[move]:
                    best_try = move
                    break
            if best_try is None:
                if DEBUG_MODE:
                    print(error(f"[Error] generate_BTL(): Could not find best try for {opening} at {board.move_stack}."))
                if EXTRA_DEBUG_MODE:
                    print(warn(f"{cur_obj}"))
                parent_node.comment = "No stats."
                return
            move_obj = board.push_san(move)
            node = parent_node.add_variation(move_obj)
            att = round(cur_obj[move]["att"], 3)
            other_moves = [k for k in cur_obj.keys() if k != best_try]
            node.comment = f'Att. = {att}, over {", ".join(other_moves)}'
            generate_BTL_inner(cur_obj[best_try], node)
            board.pop()

        else:
            # Not my turn: Provide variations for each reply.
            for move in cur_obj:
                if move in ["best_try", "att"]:
                    continue
                move_obj = board.push_san(move)
                node = parent_node.add_variation(move_obj)
                generate_BTL_inner(cur_obj[move], node)
                board.pop()

    generate_BTL_inner(tree_root, game)
    exporter = chess.pgn.StringExporter(headers=False, columns=None)
    ret = game.accept(exporter)
    return ret


def calc_winrate_line(moves_str):
    moves = parse_game(moves_str)
    cur_obj = STATS
    for move in moves:
        if move not in cur_obj:
            if DEBUG_MODE:
                print(error(f"[{moves_str}] Move '{move}' not in stats."))
            return None
        cur_obj = cur_obj[move]
    keys = [LABELS["TOTAL"], LABELS["WIN-W%"], LABELS["WIN-B%"], LABELS["DRAW%"]]
    ret = {k:cur_obj["stats"][k] for k in keys}
    return ret


def calc_winrate(opening):
    # Calculate winrate across all (feasible) transpositions of the opening.
    white_wrs = []
    black_wrs = []
    tots = []
    transpositions = OPENINGS[opening]["transpositions"]
    for line_str in itertools.chain([get_main_line(opening)], transpositions):
        wr = calc_winrate_line(line_str)
        if wr is None:
            continue
        white_wrs.append(wr[LABELS["WIN-W%"]])
        black_wrs.append(wr[LABELS["WIN-B%"]])
        tots.append(wr[LABELS["TOTAL"]])
        if EXTRA_DEBUG_MODE:
            print(info(f'[{line_str}] {wr[LABELS["WIN-W%"]]}/{wr[LABELS["WIN-B%"]]}/{wr[LABELS["DRAW%"]]} ({wr[LABELS["TOTAL"]]} games)'))
    # Calculate winrates for White/Black, then subtract from 1 to get draw rate.
    #  Because rounding errors might add up and give implausible stats.
    white_wr = 0
    black_wr = 0
    tot = sum(tots)
    for t,w,b in zip(tots, white_wrs, black_wrs):
        white_wr += w * t/tot
        black_wr += b * t/tot
    draw_rate = 1 - white_wr - black_wr
    return {
        LABELS["TOTAL"]: tot,
        LABELS["WIN-W%"]: white_wr,
        LABELS["WIN-B%"]: black_wr,
        LABELS["DRAW%"]: draw_rate
    }


def update_stats_main(opening):
    # Update STATS object with the following data:
    '''
    {<opening>:
        "stats_main": {
            "<rating>": {WIN-W%: _, WIN-B%: _, DRAW%: _,
                PREV: _, ATTAIN: _, PREV_INV: _, ATTAIN_INV: _}
        }
    }
    '''
    opening_obj = OPENINGS[opening]
    if "stats_main" not in opening_obj:
        opening_obj["stats_main"] = {}
    if str(RATING) not in opening_obj["stats_main"]:
        opening_obj["stats_main"][str(RATING)] = {}
    stats_main = opening_obj["stats_main"][str(RATING)]

    main = get_main_line(opening)
    if main == "[SYSTEM]":
        if DEBUG_MODE:
            print(warn(f"Skipping system opening: {opening}"))
        return

    opening_color = get_opening_color(opening)
    wr = calc_winrate_line(main)
    if wr is None:
        if DEBUG_MODE:
            print(warn(f"Skipping missing opening: {opening}"))
        return

    prev = calc_attainability_line(main, not opening_color)
    att = calc_attainability_line(main, opening_color)
    labels = ["TOTAL", "WIN-W%", "WIN-B%", "DRAW%", "PREV", "PREV_INV",
        "ATTAIN", "ATTAIN_INV"]
    values = [wr[LABELS["TOTAL"]], wr[LABELS["WIN-W%"]], wr[LABELS["WIN-B%"]],
        wr[LABELS["DRAW%"]], prev, 0 if prev==0 else round(1/prev), att, 0 if prev==0 else round(1/att)]
    for label, val in zip(labels, values):
        stats_main[LABELS[label]] = round(val, 3)
    if EXTRA_DEBUG_MODE:
        print(warn(pprint.pformat(stats_main, sort_dicts=False)))
    return


def update_stats(opening):
    # Update STATS object with the following data:
    '''
    {<opening>:
        "stats": {
            "<rating>": {WIN-W%: _, WIN-B%: _, DRAW%: _,
                PREV: _, ATTAIN: _, PREV_INV: _, ATTAIN_INV: _, BTL: _}}
        }
    }
    '''
    opening_obj = OPENINGS[opening]
    if "transpositions" in opening_obj and len(opening_obj["transpositions"]) == 0:
        # No transpositions: stats same as stats_main
        opening_obj["stats"] = "[USE MAIN]"
        return
    if "stats" not in opening_obj:
        opening_obj["stats"] = {}
    if str(RATING) not in opening_obj["stats"]:
        opening_obj["stats"][str(RATING)] = {}

    stats = opening_obj["stats"][str(RATING)]
    main = get_main_line(opening)
    if main == "[SYSTEM]":
        if DEBUG_MODE:
            print(warn(f"Skipping system opening: {opening}"))
        return

    opening_color = get_opening_color(opening)
    wr = calc_winrate(opening)
    if wr is None:
        if DEBUG_MODE:
            print(warn(f"Skipping missing opening: {opening}"))
        return

    prev, _ = calc_attainability(opening, not opening_color)
    att, btl = calc_attainability(opening, opening_color)
    labels = ["TOTAL", "WIN-W%", "WIN-B%", "DRAW%", "PREV", "PREV_INV",
        "ATTAIN", "ATTAIN_INV"]
    values = [wr[LABELS["TOTAL"]], wr[LABELS["WIN-W%"]], wr[LABELS["WIN-B%"]],
        wr[LABELS["DRAW%"]], prev, 0 if prev==0 else round(1/prev), att, 0 if prev==0 else round(1/att)]
    for label, val in zip(labels, values):
        stats[LABELS[label]] = round(val, 3)
    stats["BTL"] = btl
    return


def write_opening_stats():
    confirmed = confirm(f"Update openings.json file?")
    if confirmed:
        with open(OPENINGS_JSON, 'w') as openings_file:
            ujson.dump(OPENINGS, openings_file, indent=4)
        print(success(f"Wrote to {OPENINGS_JSON}."))


def process_all_openings(func, root_obj=OPENINGS):
    # func should update the global OPENINGS dict.
    for opening in root_obj:
        func(opening)
    write_opening_stats()


if __name__ == "__main__":
    # Actual work:
    # process_all_openings(find_transpositions)
    # process_all_openings(update_stats_main)
    process_all_openings(update_stats)

    # Test on a single opening.
    # opening = "Four Knights Game"
    # att, btl = calc_attainability(opening, chess.WHITE)
    # print(att)
    # print(btl)

    # Pretty-print the stats of main line.
    # att = calc_attainability_line(get_main_line(opening), chess.WHITE)
    # print(success(f"At elo {RATING}, attainability of {opening} is {att} (about 1 in {round(1/att)} games)."))
    # print(success(f"\tAccounting for getting right color (50/50), attainability is about 1 in {round(1/(att/2))} games."))
