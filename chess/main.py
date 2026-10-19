import re
import os
import os.path
import sys
import ast
import shutil
import tempfile
from enum import Enum
from datetime import datetime

import chess
import chess.pgn
import yaml
from github import Github

import src.markdown as markdown
import src.selftest as selftest
import src.mockGithub as mockGithub

# TODO: Use an image instead of a raw link to start new games

# The bot runs from chess/, the profile README lives in the repo root
README_PATH = '../README.md'

class Action(Enum):
    UNKNOWN = 0
    MOVE = 1
    NEW_GAME = 2


def update_top_moves(user):
    """Adds the given user to the top moves file"""
    with open('data/top_moves.txt', 'r') as file:
        contents = file.read()
        dictionary = ast.literal_eval(contents)

    if user not in dictionary:
        dictionary[user] = 1 # First move
    else:
        dictionary[user] += 1

    with open('data/top_moves.txt', 'w') as file:
        file.write(str(dictionary))


def update_last_moves(line):
    """Adds the given line to the last moves file"""
    with open('data/last_moves.txt', 'r+') as last_moves:
        content = last_moves.read()
        last_moves.seek(0, 0)
        last_moves.write(line.rstrip('\r\n') + '\n' + content)


def replace_text_between(original_text, marker, replacement_text):
    """Replace text between `marker['begin']` and `marker['end']` with `replacement`"""
    delimiter_a = marker['begin']
    delimiter_b = marker['end']

    if original_text.find(delimiter_a) == -1 or original_text.find(delimiter_b) == -1:
        return original_text

    leading_text = original_text.split(delimiter_a)[0]
    trailing_text = original_text.split(delimiter_b)[1]

    return leading_text + delimiter_a + replacement_text + delimiter_b + trailing_text


def parse_issue(title):
    """Parse issue title and return a tuple with (action, <move>)"""
    if title.lower() == 'chess: start new game':
        return (Action.NEW_GAME, None)

    if 'chess: move' in title.lower():
        match_obj = re.match('Chess: Move ([A-H][1-8]) to ([A-H][1-8])', title, re.I)
        if match_obj is None:
            return (Action.UNKNOWN, None)

        source = match_obj.group(1)
        dest   = match_obj.group(2)
        return (Action.MOVE, (source + dest).lower())

    return (Action.UNKNOWN, None)


def main(issue, issue_author, repo_owner):
    action = parse_issue(issue.title)
    gameboard = chess.Board()

    with open('data/settings.yaml', 'r') as settings_file:
        settings = yaml.load(settings_file, Loader=yaml.FullLoader)

    if action[0] == Action.NEW_GAME:
        if os.path.exists('games/current.pgn') and issue_author != repo_owner:
            issue.create_comment(settings['comments']['invalid_new_game'].format(author=issue_author))
            issue.edit(state='closed')
            return False, 'ERROR: A current game is in progress. Only the repo owner can start a new game'

        issue.create_comment(settings['comments']['successful_new_game'].format(author=issue_author))
        issue.edit(state='closed')

        with open('data/last_moves.txt', 'w') as last_moves:
            last_moves.write('Start game: ' + issue_author)

        # Create new game
        game = chess.pgn.Game()
        game.headers['Event'] = repo_owner + '\'s Online Open Chess Tournament'
        game.headers['Site'] = 'https://github.com/' + os.environ['GITHUB_REPOSITORY']
        game.headers['Date'] = datetime.now().strftime('%Y.%m.%d')
        game.headers['Round'] = '1'

    elif action[0] == Action.MOVE:
        if not os.path.exists('games/current.pgn'):
            issue.create_comment(settings['comments']['no_game'].format(author=issue_author))
            issue.edit(state='closed', labels=[settings['labels']['invalid']])
            return False, 'ERROR: There is no game in progress! Start a new game first'

        # Load game from "games/current.pgn"
        with open('games/current.pgn') as pgn_file:
            game = chess.pgn.read_game(pgn_file)
            gameboard = game.board()

        with open('data/last_moves.txt') as moves:
            line = moves.readline()
            last_player = line.split(':')[1].strip()
            last_move   = line.split(':')[0].strip()

        for move in game.mainline_moves():
            gameboard.push(move)

        try:
            # Try to move with promotion to queen
            if chess.Move.from_uci(action[1] + 'q') in gameboard.legal_moves:
                action = (action[0], action[1] + 'q')

            move = chess.Move.from_uci(action[1])
        except ValueError:  # e.g. "E2 to E2" is not a move at all
            move = None

        # Check if player is moving twice in a row
        if last_player == issue_author and 'Start game' not in last_move:
            issue.create_comment(settings['comments']['consecutive_moves'].format(author=issue_author))
            issue.edit(state='closed', labels=[settings['labels']['invalid']])
            return False, 'ERROR: Two moves in a row!'

        # Check if move is valid
        if move is None or move not in gameboard.legal_moves:
            issue.create_comment(settings['comments']['invalid_move'].format(author=issue_author, move=action[1]))
            issue.edit(state='closed', labels=[settings['labels']['invalid']])
            return False, 'ERROR: Move is invalid!'

        # Check if board is valid
        if not gameboard.is_valid():
            issue.create_comment(settings['comments']['invalid_board'].format(author=issue_author))
            issue.edit(state='closed', labels=[settings['labels']['invalid']])
            return False, 'ERROR: Board is invalid!'

        issue_labels = [settings['labels']['capture']] if gameboard.is_capture(move) else []
        issue_labels += [settings['labels']['white'] if gameboard.turn == chess.WHITE else settings['labels']['black']]

        issue.create_comment(settings['comments']['successful_move'].format(author=issue_author, move=action[1]))
        issue.edit(state='closed', labels=issue_labels)

        update_last_moves(action[1] + ': ' + issue_author)
        update_top_moves(issue_author)

        # Perform move
        gameboard.push(move)
        game.end().add_main_variation(move, comment=issue_author)
        game.headers['Result'] = gameboard.result()

    elif action[0] == Action.UNKNOWN:
        issue.create_comment(settings['comments']['unknown_command'].format(author=issue_author))
        issue.edit(state='closed', labels=[settings['labels']['invalid']])
        return False, 'ERROR: Unknown action'

    # Save game to "games/current.pgn"
    print(game, file=open('games/current.pgn', 'w'), end='\n\n')

    last_moves = markdown.generate_last_moves()

    # If it is a game over, archive current game
    if gameboard.is_game_over():
        win_msg = {
            '1/2-1/2': '和棋',
            '1-0': '白方胜',
            '0-1': '黑方胜'
        }

        with open('data/last_moves.txt', 'r') as last_moves_file:
            lines = last_moves_file.readlines()
            pattern = re.compile('.*: (@[a-z\\d](?:[a-z\\d]|-(?=[a-z\\d])){0,38})', flags=re.I)
            player_list = { re.match(pattern, line).group(1) for line in lines }

        if gameboard.result() == '1/2-1/2':
            issue.add_to_labels(settings['labels']['draw'])
        else:
            issue.add_to_labels(settings['labels']['winner'])

        issue.create_comment(settings['comments']['game_over'].format(
            outcome=win_msg.get(gameboard.result(), 'UNKNOWN'),
            players=', '.join(player_list),
            num_moves=len(lines)-1,
            num_players=len(player_list)))

        os.rename('games/current.pgn', datetime.now().strftime('games/game-%Y%m%d-%H%M%S.pgn'))
        os.remove('data/last_moves.txt')

    with open(README_PATH, 'r') as file:
        readme = file.read()

    # Fill the sections directly (not with str.format), so braces elsewhere in the README stay intact
    readme = replace_text_between(readme, settings['markers']['board'], markdown.board_to_markdown(gameboard))
    readme = replace_text_between(readme, settings['markers']['moves'], markdown.generate_moves_list(gameboard))
    if gameboard.is_game_over():
        turn = '没人了，这局已经结束'
    else:
        turn = '白方' if gameboard.turn == chess.WHITE else '黑方'
    readme = replace_text_between(readme, settings['markers']['turn'], turn)
    readme = replace_text_between(readme, settings['markers']['last_moves'], last_moves)
    readme = replace_text_between(readme, settings['markers']['top_moves'], markdown.generate_top_moves())

    with open(README_PATH, 'w') as file:
        file.write(readme)

    return True, ''


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--self-test':
        # Play the test games in a scratch copy so the live game and README stay untouched
        scratch = tempfile.mkdtemp()
        shutil.copytree('.', scratch, dirs_exist_ok=True)
        shutil.copy(README_PATH, os.path.join(scratch, 'README.md'))
        os.chdir(scratch)
        README_PATH = 'README.md'
        selftest.run(main)
        sys.exit(0)

    repo = Github(os.environ['GITHUB_TOKEN']).get_repo(os.environ['GITHUB_REPOSITORY'])
    repo_owner = '@' + os.environ['REPOSITORY_OWNER']

    # Play every open chess issue, oldest first. GitHub cancels a queued run when another one
    # arrives, so the run that does execute also picks up the cancelled run's issue.
    issues = [issue for issue in repo.get_issues(state='open', sort='created', direction='asc')
              if issue.pull_request is None and issue.title.lower().startswith('chess:')]

    for issue in issues:
        try:
            ret, reason = main(issue, '@' + issue.user.login, repo_owner)
            print(f'Issue #{issue.number}: ' + ('ok' if ret else reason))
        except Exception as error:
            # Close it so one broken issue is not retried by every later run and cannot block the game
            print(f'::error::Issue #{issue.number}: {error!r}')
            try:
                issue.edit(state='closed')
            except Exception as close_error:
                print(f'::error::Issue #{issue.number} could not be closed: {close_error!r}')
