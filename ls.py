#!/usr/bin/env python3

import re
import sys
import os
import pwd
import grp
import stat
import datetime
import argparse
import subprocess
from pprint import pprint


COLORS = {
    'red': '\033[31m',
    'magenta': '\033[35m',
    'light_magenta': '\033[95m',
    'green': '\033[32m',
    'light_green': '\033[92m',
    'light_cyan': '\033[96m',
    'light_yellow': '\033[93m',
    'light_gray': '\033[37m',
    'dark_gray': '\033[30m',
    'light_red': '\033[91m',
    'light_blue': '\033[94m',
    'blue': '\033[34m',
    'end': '\033[0m'
}

COLOR_VALS = {
    'srcname_directory': 'light_red',
    'srcname_file': 'light_green',
    'targetname': 'light_cyan',
    'time': 'blue',
    'subfilecount': 'magenta',
    'acls': 'dark_gray',
    'owner': 'dark_gray',
    'size': 'magenta',
    'preview': 'dark_gray',
    'default': 'light_magenta'
}


PREVIEW_READ_LEN = 256
PREVIEW_TRUNC_LEN = 48


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


def getcolslisting(full=False):
    out = []
    if full:
        out.append('acls')
        out.append('owner')
    out.append('size')
    out.append('subfilecount')
    out.append('timeiso')
    out.append('srcname')
    out.append('targetname')
    if full:
        out.append('preview')
    return out


def structurecols(row, full=False):
    colslisting = getcolslisting(full=full)
    func = lambda name: makecolor(row, name)
    ret = map(func, colslisting)
    return ret


def rendercols(row, full=False):
    structcols = structurecols(row, full=full)
    ret = ''.join(['\t', '\t'.join(structcols)])
    #ret = '\t'.join(sructcols)
    return ret


def renderrows(files, full=False):
    renderer = lambda r: rendercols(r, full=full)
    out = '\n'.join(map(renderer, files))
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
        real = os.path.relpath(os.path.realpath(fname))
    else:
        real = fname
    if os.path.isdir(real):
        ret = 'directory'
    else:
        ret = 'file'
    return ret



def col_subfilecount(fname, stat_res):
    real = None
    islink = os.path.islink(fname)
    isdir = False
    if islink:
        real = os.path.relpath(os.path.realpath(fname))
    else:
        real = fname
    if not os.path.isdir(real):
        return ' '
    if not os.access(real, os.R_OK):
        return '-'
    return str(len(os.listdir(real)))


def col_preview(fname, stat_res):
    if os.path.isdir(fname):
        return ' '
    if not os.access(fname, os.R_OK):
        return ' '
    if not istextfile(fname):
        return ' '
    data = None
    with open(fname, 'rt', errors='replace') as fh:
        data = fh.read(PREVIEW_READ_LEN)
    if len(data) == 0:
        return ' '
    pat = r'(?u)[^\u0021-\u0126]+'
    cleaned = re.sub(pat, ' ', data).strip()
    truncated = cleaned[:PREVIEW_TRUNC_LEN]
    return truncated



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
    rawdata = None
    with proc() as subproc:
        rawdata = subproc.stdout.read()
    data = rawdata.decode('utf-8', errors='replace')
    pat = '(?u)[^a-zA-Z]text[^a-zA-Z]'
    check = (re.search(pat, data) is not None)
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


def run(full=False):
    files = getfiles()
    rows = renderrows(files, full=full)
    display(rows)
    return True



def getargs():
    arger = argparse.ArgumentParser(description='Replacement for ls')
    arger.add_argument(
        '-f',
        '--full',
        help='Full Output',
        dest='full',
        default=False,
        action='store_true'
    )
    args = arger.parse_args()
    return args



def main():
    args = getargs()
    run(full=args.full)
    return 0


if __name__ == '__main__':
    sys.exit(main())
