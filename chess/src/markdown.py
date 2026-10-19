from collections import defaultdict
from urllib.parse import urlencode
import os
import re
import ast
import glob
import hashlib

import chess
import chess.svg
import yaml

with open('data/settings.yaml', 'r') as settings_file:
    settings = yaml.load(settings_file, Loader=yaml.FullLoader)


def create_link(text, link):
    return f"[{text}]({link})"

def create_issue_link(source, dest_list):
    issue_link = settings['issues']['link'].format(
        repo=os.environ["GITHUB_REPOSITORY"],
        params=urlencode(settings['issues']['move'], safe="{}"))

    ret = [create_link(dest, issue_link.format(source=source, dest=dest)) for dest in sorted(dest_list)]
    return ", ".join(ret)

def generate_top_moves():
    with open("data/top_moves.txt", 'r') as file:
        dictionary = ast.literal_eval(file.read())

    if not dictionary:
        return "\n还没有人走过棋，来当第一个吧。\n\n"

    markdown = "\n"
    markdown += "| 总步数 | 玩家 |\n"
    markdown += "| :----: | :--- |\n"

    max_entries = settings['misc']['max_top_moves']
    for key,val in sorted(dictionary.items(), key=lambda x: x[1], reverse=True)[:max_entries]:
        markdown += "| {} | {} |\n".format(val, create_link(key, "https://github.com/" + key[1:]))

    return markdown + "\n"

def generate_last_moves():
    markdown = "\n"
    markdown += "| 这一步 | 谁走的 |\n"
    markdown += "| :----: | :----- |\n"

    counter = 0

    with open("data/last_moves.txt", 'r') as file:
        for line in file.readlines():
            parts = line.rstrip().split(':')

            if not ":" in line:
                continue

            if counter >= settings['misc']['max_last_moves']:
                break

            counter += 1

            match_obj = re.search('([A-H][1-8])([A-H][1-8])', line, re.I)
            if match_obj is not None:
                source = match_obj.group(1).upper()
                dest   = match_obj.group(2).upper()

                markdown += "| `" + source + "` → `" + dest + "` | " + create_link(parts[1], "https://github.com/" + parts[1].lstrip()[1:]) + " |\n"
            else:
                markdown += "| " + ("开局" if parts[0] == "Start game" else "`" + parts[0] + "`") + " | " + create_link(parts[1], "https://github.com/" + parts[1].lstrip()[1:]) + " |\n"

    return markdown + "\n"

def generate_moves_list(board):
    # Create dictionary and fill it
    moves_dict = defaultdict(set)

    for move in board.legal_moves:
        source = chess.SQUARE_NAMES[move.from_square].upper()
        dest   = chess.SQUARE_NAMES[move.to_square].upper()

        moves_dict[source].add(dest)

    # Write everything in Markdown format
    markdown = ""

    if board.is_game_over():
        issue_link = settings['issues']['link'].format(
            repo=os.environ["GITHUB_REPOSITORY"],
            params=urlencode(settings['issues']['new_game']))

        return "\n**这一局结束了！** " + create_link("点这里", issue_link) + "开新的一局 :D\n\n"

    markdown += "\n"
    if board.is_check():
        markdown += "**将军！** 想好了再走。\n\n"

    markdown += "| 从 | 到（点一下就行） |\n"
    markdown += "| :-: | :--------------- |\n"

    for source,dest in sorted(moves_dict.items()):
        markdown += "| **" + source + "** | " + create_issue_link(source, dest) + " |\n"

    return markdown + "\n"

# Board images are written next to the bot and referenced from the README in the repo root
BOARD_DIR = 'img'
BOARD_URL = 'chess/img'

BOARD_COLORS = {
    'square light': '#a9c7a0',
    'square dark': '#5b7f56',
    'square light lastmove': '#e3c16f',
    'square dark lastmove': '#c09a3e',
    'margin': '#0b0f0c',
    'coord': '#4af626',
}

def board_to_markdown(board):
    """Render the board as one SVG, named after the position so GitHub never shows a cached one"""
    lastmove = board.peek() if board.move_stack else None
    check = board.king(board.turn) if board.is_check() else None
    svg = chess.svg.board(board, orientation=board.turn, lastmove=lastmove, check=check,
                          colors=BOARD_COLORS, size=400)
    name = 'board-' + hashlib.sha1(board.fen().encode()).hexdigest()[:10] + '.svg'

    os.makedirs(BOARD_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(BOARD_DIR, 'board-*.svg')):
        os.remove(old)
    with open(os.path.join(BOARD_DIR, name), 'w') as file:
        file.write(svg)

    if board.is_game_over():
        alt = '终局棋盘'
    else:
        alt = '当前棋盘，轮到{}走'.format('白方' if board.turn == chess.WHITE else '黑方')
    return '<img src="{}/{}" width="400" alt="{}">\n'.format(BOARD_URL, name, alt)
