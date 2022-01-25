import json
import ujson
import os
import csv
import chess

from cli_util import error, warn, success, info, header, confirm
from analyze_opening import get_opening_color

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
RATINGS = cfg["RATINGS"]

OUT_FILE = cfg["STATS_DIR"] + "openings.csv"
WR_FILE = cfg["STATS_DIR"] + "winrates.csv"


def json_to_csv():
    with open(OPENINGS_JSON, 'r') as openings_file:
        OPENINGS = json.load(openings_file)
    with open(OUT_FILE, 'w', newline='') as out_file:
        csv_writer = csv.writer(out_file)

        csv_headers = ["Opening", "Color", "Main Line"]
        for rating in RATINGS:
            headers_wr = ["Num. Games", "%Win-W", "%Draw", "%Win-B"]
            csv_headers += [f"[{rating}] " + header for header in headers_wr]
        for rating in RATINGS:
            headers_stats = ["Prev.", "Inv.Prev.", "Att.", "Inv.Att."]
            csv_headers += [f"[{rating}] " + header for header in headers_stats]
        csv_writer.writerow(csv_headers)

        for opening in OPENINGS:
            opening_obj = OPENINGS[opening]
            color = get_opening_color(opening)
            color = "White" if color == chess.WHITE else "Black"
            main_line = opening_obj["main_real"] if "main_real" in opening_obj else opening_obj["main"]
            row = [opening, color, main_line]

            stats_obj = opening_obj["stats_main"] if opening_obj["stats"] == "[USE MAIN]" else opening_obj["stats"]
            fields_wr = ["TOTAL", "WIN-W%", "DRAW%", "WIN-B%"]
            fields_stats = ["PREV", "PREV_INV", "ATTAIN", "ATTAIN_INV"]
            for rating in RATINGS:
                rating_obj = stats_obj[str(rating)]
                if rating_obj:
                    row += [rating_obj[LABELS[field]] for field in fields_wr]
                else:
                    row += [""] * len(fields_wr)
            for rating in RATINGS:
                rating_obj = stats_obj[str(rating)]
                if rating_obj:
                    row += [rating_obj[LABELS[field]] for field in fields_stats]
                else:
                    row += [""] * len(fields_stats)
            csv_writer.writerow(row)


def split_wr_rating():
    '''Split stats of different ratings into their own rows (rather than columns of same row.)'''
    '''  (makes it easier for processing/filtering in Excel.)'''

    with open(OUT_FILE, 'r') as csv_file, open(WR_FILE, 'w', newline='') as out_file:
        csv_reader = csv.DictReader(csv_file)
        csv_writer = csv.writer(out_file)
        csv_headers = ["Opening", "Rating", "Num. Games", "White Wins", "Draw", "Black Wins", "White Wins or Draws", "Black Wins or Draws"]
        csv_writer.writerow(csv_headers)
        for row in csv_reader:
            opening = row["Opening"]
            wr_headers = ["[{}] Num. Games", "[{}] %Win-W", "[{}] %Draw", "[{}] %Win-B"]
            for r in RATINGS:
                wr = [row[h.format(str(r))] for h in wr_headers]
                rating = "2200+" if r == "MASTERS" else str(r)
                csv_writer.writerow([opening, rating, *wr, wr[1]+wr[2], wr[3]+wr[2]])


if __name__ == "__main__":
    json_to_csv()
    # split_wr_rating()
