#!/usr/bin/env python3

import re
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
    'dark_gray': '\033[30m',
    'light_red': '\033[91m',
    'light_blue': '\033[94m',
    'end': '\033[0m'
}

COLOR_VALS = {
    'srcname_directory': 'light_red',
    'srcname_file': 'light_green',
    'targetname': 'light_cyan',
    'time': 'light_blue',
    'subfilecount': 'light_blue',
    'acls': 'light_blue',
    'owner': 'light_magenta',
    'size': 'light_magenta',
    'preview': 'dark_gray',
    'default': 'light_magenta'
}


PREVIEW_LEN = 48


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
    elif field == 'subfilecount':
        clr = 'subfilecount'
    elif field == 'acls':
        clr = 'acls'
    elif field == 'owner':
        clr = 'owner'
    elif field == 'size':
        clr = 'size'
    elif field == 'preview':
        clr = 'preview'
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
        makecolor(row, 'acls'),
        makecolor(row, 'owner'),
        makecolor(row, 'timeiso'),
        makecolor(row, 'size'),
        makecolor(row, 'subfilecount'),
        makecolor(row, 'srcname'),
        makecolor(row, 'targetname'),
        makecolor(row, 'preview')
    ]


def rendercols(row):
    #ret = ''.join(['\t', '\t'.join(structurecols(row))])
    ret = '\t'.join(structurecols(row))
    return ret


def renderrows(files):
    out = '\n'.join(map(rendercols, files))
    return out


def col_acls(fname, stat_res):
    t_no = '-'
    #all_acls_mode = str(oct(stat.S_IMODE(stat_res.st_mode)))[-3:]
    all_acls_mode = stat.filemode(stat_res.st_mode)
    me_can_read = os.access(fname, os.R_OK)
    me_can_write = os.access(fname, os.W_OK)
    me_can_exec = os.access(fname, os.X_OK)
    me_pdefs = [
        (me_can_read, 'r'),
        (me_can_write, 'w'),
        (me_can_exec, 'x')
    ]
    me_func = lambda x: x[1] if x[0] else t_no
    me_pitems = map(me_func, me_pdefs)
    me_acls_mode = ''.join(me_pitems)
    ret = ' '.join([all_acls_mode, me_acls_mode])
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
        ret = ' '
    return ret


def col_name(fname, stat_res):
    return fname


def col_ftype(fname, stat_res):
    if os.path.islink(fname):
        return 'symlink'
    elif os.path.isdir(fname):
        return 'directory'
    return 'file'



def col_subfilecount(fname, stat_res):
    real = None
    islink = os.path.islink(fname)
    isdir = False
    if islink:
        real = os.path.relpath(os.path.realpath(fname))
    else:
        real = fname
    isdir = os.path.isdir(real)
    if not isdir:
        ret = ' '
    else:
        ret = str(len(os.listdir(real)))
    return ret


def col_preview(fname, stat_res):
    if os.path.isdir(fname):
        return ' '
    if not os.access(fname, os.R_OK):
        return ' '
    if not istextfile(fname):
        return ' '
    data = None
    with open(fname, 'rt') as fh:
        data = fh.read(PREVIEW_LEN)
    if len(data) == 0:
        return ' '
    pat = r'(?u)[^\u0021-\u0126]+'
    cleaned = re.sub(pat, ' ', data).strip()
    return cleaned



def istextfile(fname):
    """
    See: http://stackoverflow.com/a/898759
    """
    proc = lambda: (
        subprocess.Popen(
            [
                'file',
                '--mime',
                '--dereference',
                fname
            ],
            stdout=subprocess.PIPE
        )
    )
    out = None
    with proc() as subproc:
        out = str(subproc.stdout.read())
    pat = '(?u)[^a-zA-Z]text[^a-zA-Z]'
    check = (re.search(pat, out) is not None)
    return check


def buildrow(fname):
    stat_res = os.lstat(fname)
    row = {
        'ftype': col_ftype(fname, stat_res),
        'acls': col_acls(fname, stat_res),
        'owner': col_owner(fname, stat_res),
        'size': col_size(fname, stat_res),
        'timeiso': col_timeiso(fname, stat_res),
        'timeepoch': col_timeepoch(fname, stat_res),
        'srcname': col_srcname(fname, stat_res),
        'targetname': col_targetname(fname, stat_res),
        'name': col_name(fname, stat_res),
        'subfilecount': col_subfilecount(fname, stat_res),
        'preview': col_preview(fname, stat_res)
    }
    return row;


def processrows(files):
    out = map(buildrow, files)
    return out


def encode_output(data):
    formatted = ''.join(['\n', data, '\n', '\n'])
    encoded = formatted.encode('utf-8')
    return encoded


def display(rows):
    encoded = encode_output(rows)
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
    rows = renderrows(files)
    display(rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
