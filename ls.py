#!/usr/bin/env python3

import sys
import os
import pwd
import grp
import stat
import datetime
import subprocess
from pprint import pprint

COLORS = {
    'red': '\033[31m',
    'magenta': '\033[35m',
    'light_magenta': '\033[95m',
    'light_green': '\033[92m',
    'light_cyan': '\033[96m',
    'light_yellow': '\033[93m',
    'light_gray': '\033[37m',
    'light_red': '\033[91m',
    'end': '\033[0m'
}

COLOR_VALS = {
    'srcname_directory': 'light_red',
    'srcname_file': 'light_green',
    'targetname': 'light_cyan',
    'time': 'light_magenta',
    'default': 'light_gray'
}


def getrow(fname):
    return fname


def sortfile(row):
    fname = row['name']
    lowfname = fname.strip().lower()
    key = '0' if os.path.isdir(fname) else '1'
    out = ':'.join([key, lowfname])
    return out


def makecolor(row, field):
    if field == 'targetname':
        clr = 'targetname'
    elif field == 'srcname':
        if row['ftype'] == 'directory':
            clr = 'srcname_directory'
        else:
            clr = 'srcname_file'
    elif field == 'timeiso':
        clr = 'time'
    else:
        clr = 'default'
    clrval = COLOR_VALS[clr]
    out = addcolor(row[field], clrval)
    return out


def addcolor(text, color):
    out = text.join([COLORS[color], COLORS['end']])
    return out


def structurecols(row):
    return [
        makecolor(row, 'perms'),
        makecolor(row, 'owner'),
        makecolor(row, 'size'),
        makecolor(row, 'timeiso'),
        makecolor(row, 'srcname'),
        makecolor(row, 'targetname')
    ]


def rendercols(row):
    return '\t'.join(structurecols(row))


def renderrows(files):
    out = '\n'.join(map(rendercols, files))
    return out


def col_perms(fname, stat_res):
    ret = str(oct(stat.S_IMODE(stat_res.st_mode)))[-3:]
    return ret


def col_owner(fname, stat_res):
    owner = pwd.getpwuid(stat_res.st_uid).pw_name
    group = grp.getgrgid(stat_res.st_gid).gr_name
    ret = ':'.join([owner, group])
    return ret


def col_size(fname, stat_res):
    ret = '{:,}'.format(stat_res.st_size)
    return ret


def col_timeiso(fname, stat_res):
    dt = datetime.datetime.fromtimestamp(stat_res.st_mtime)
    ret = dt.strftime('%Y-%m-%d %H:%M:%S')
    return ret


def col_timeepoch(fname, stat_res):
    ret = str(stat_res.st_mtime)
    return ret


def col_srcname(fname, stat_res):
    isdir = os.path.isdir(fname)
    if isdir:
        target = ''.join([fname, '/'])
    else:
        target = fname
    ret = target
    return ret


def col_targetname(fname, stat_res):
    islink = os.path.islink(fname)
    if islink:
        real = os.path.relpath(os.path.realpath(fname))
        isdir = os.path.isdir(real)
        if isdir:
            target = ''.join([real, '/'])
        else:
            target = real
        ret = target
    else:
        ret = ''
    return ret


def col_name(fname, stat_res):
    return fname


def col_ftype(fname, stat_res):
    if os.path.islink(fname):
        return 'symlink'
    elif os.path.isdir(fname):
        return 'directory'
    return 'file'


def buildrow(fname):
    stat_res = os.lstat(fname)
    row = {
        'ftype': col_ftype(fname, stat_res),
        'perms': col_perms(fname, stat_res),
        'owner': col_owner(fname, stat_res),
        'size': col_size(fname, stat_res),
        'timeiso': col_timeiso(fname, stat_res),
        'timeepoch': col_timeepoch(fname, stat_res),
        'srcname': col_srcname(fname, stat_res),
        'targetname': col_targetname(fname, stat_res),
        'name': col_name(fname, stat_res)
    }
    return row;


def processrows(files):
    out = map(buildrow, files)
    return out


def display(out):
    formatted = ''.join([out, '\n'])
    encoded = formatted.encode('utf-8')
    pagedisplay(encoded)
    return True


def getfiles():
    files = os.listdir('./')
    processed = processrows(files)
    sfiles = sorted(processed, key=sortfile, reverse=False)
    return sfiles


def pagedisplay(output):
    """
    See:
        https://chase-seibert.github.io/blog
        /2012/10/31/python-fork-exec-vim-raw-input.html
    """
    proc = lambda: (
        subprocess.Popen(
            [
                'less',
                '--RAW-CONTROL-CHARS',
                '--quit-at-eof',
                '--quit-if-one-screen',
                '--no-init'
            ],
            stdin=subprocess.PIPE,
            stdout=sys.stdout
        )
    )
    with proc() as pager:
        try:
            pager.communicate(output)
            pager.stdin.close()
            pager.wait()
        except KeyboardInterrupt:
            ## TODO: Any way to stop ctrl-c from
            ## screwing up keyboard entry?
            pager.terminate()
            pager.wait()
    return True


def main():
    files = getfiles()
    out = renderrows(files)
    display(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
