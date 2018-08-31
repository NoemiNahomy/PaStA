"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import argparse
import termios
import tty
import shutil
import subprocess
import sys

from datetime import datetime
from logging import getLogger

from .Cluster import Cluster

log = getLogger(__name__[-15:])


def get_date_selector(repo, patch_stack_definition, selector):
    # Date selector "Stack Release Date"
    if selector == 'SRD':
        date_selector = lambda x: patch_stack_definition.get_stack_of_commit(x).stack_release_date
    # Date selector "Commit Date"
    elif selector == 'CD':
        date_selector = lambda x: repo[x].commit_date
    elif selector == 'AD':
        date_selector = lambda x: repo[x].author_date
    else:
        raise NotImplementedError('Unknown date selector: ' % selector)
    return date_selector


def persist_commit_hashes(filename, commit_hashes):
    with open(filename, 'w') as f:
        f.write('\n'.join(commit_hashes) + '\n')


def load_commit_hashes(filename, ordered=True, must_exist=True):
    content = file_to_string(filename, must_exist=must_exist)
    if content is None:
        content = ''
    content = content.splitlines()

    # Filter empty lines
    content = filter(None, content)
    # Filter comment lines
    content = filter(lambda x: not x.startswith('#'), content)
    # return filtered list or set
    if ordered:
        return list(content)
    else:
        return set(content)


def file_to_string(filename, must_exist=True):
    try:
        # I HATE ENCONDING!
        # Anyway, opening a file as binary and decoding it to iso8859 solves the problem :-)
        with open(filename, 'rb') as f:
            retval = str(f.read().decode('iso8859'))
            f.close()
    except FileNotFoundError:
        print('Warning, file ' + filename + ' not found!')
        if must_exist:
            raise
        return None

    return retval


def format_date_ymd(dt):
    return dt.strftime('%Y-%m-%d')


def parse_date_ymd(ymd):
    try:
        return datetime.strptime(ymd, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError("Not a valid date: '%s'" % ymd)


def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def _ansi_clrscr():
    sys.stdout.write('\x1b[2J\x1b[H')


def fix_encoding(bstring):
    try:
        bstring = bstring.decode('utf-8')
    except:
        bstring = bstring.decode('iso8859')
    return bstring


def pager(text, enable_pager=True):
    _, lines = shutil.get_terminal_size()
    if text.count('\n') > lines and enable_pager:
        p = subprocess.Popen(['less', '-eFX'], stdin=subprocess.PIPE)
        p.stdin.write(bytes(text, 'utf-8'))
        p.stdin.close()
        p.wait()
    else:
        _ansi_clrscr()
        print(text)


def show_commit(repo, hash, enable_pager=True):
    commit = repo[hash]
    message = commit.format_message() + commit.diff.raw
    pager('\n'.join(message), enable_pager)


def show_commits(repo, left_hash, right_hash, enable_pager=True):
    def side_by_side(left, right, split_length):
        ret = []
        while len(left) or len(right):
            line = ''
            if len(left):
                line = left.pop(0).expandtabs(6)[0:split_length]
            line = line.ljust(split_length)
            line += ' | '
            if len(right):
                line += right.pop(0).expandtabs(6)[0:split_length]
            ret.append(line)
        return ret

    left_commit = repo[left_hash]
    right_commit = repo[right_hash]

    left_message = left_commit.format_message()
    right_message = right_commit.format_message()

    left_diff, left_footer = left_commit.diff.split_footer()
    right_diff, right_footer = right_commit.diff.split_footer()

    columns, _ = shutil.get_terminal_size()
    maxlen = int((columns-3)/2)

    split_length = max(map(len, left_diff + left_message))
    if split_length > maxlen:
        split_length = maxlen

    separator =\
        ['-' * (split_length + 1) + '+' + '-' * (columns - split_length - 2)]

    text = []
    text += side_by_side(left_message, right_message, split_length) + separator
    text += side_by_side(left_diff, right_diff, split_length) + separator
    text += side_by_side(left_footer, right_footer, split_length) + separator
    pager('\n'.join(text), enable_pager)


def get_first_upstream(repo, patch_groups, commit):
    tags = patch_groups.get_tagged(commit)
    if tags:
        return min(tags, key=lambda x: repo[x].commit_date)
    return None