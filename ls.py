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
    'filetype': 'dark_gray',
    'size': 'magenta',
    'preview': 'dark_gray',
    'default': 'light_magenta'
}


PREVIEW_READ_LEN = 256
PREVIEW_TRUNC_LEN = 48


def sortfile(row):
    fname = row['info']['fname']
    lowfname = fname.strip().lower()
    key = 0 if (row['info']['ftype'] == 'directory') else 1
    out = (key, lowfname)
    return out


def makecolor(row, field):
    if field == 'targetname':
        clr = 'targetname'
    elif field == 'srcname':
        if row['info']['ftype'] == 'directory':
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
    elif field == 'filetype':
        clr = 'filetype'
    elif field == 'preview':
        clr = 'preview'
    else:
        clr = 'default'
    clrval = COLOR_VALS[clr]
    out = addcolor(row['render'][field], clrval)
    return out


def addcolor(text, color):
    out = text.join([COLORS[color], COLORS['end']])
    return out


def getcolslisting(full=False):
    out = []
    if full:
        out.append('acls')
        out.append('owner')
        out.append('filetype')
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


def col_acls(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
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


def col_owner(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    owner = pwd.getpwuid(stat_res.st_uid).pw_name
    group = grp.getgrgid(stat_res.st_gid).gr_name
    ret = ':'.join([owner, group])
    return ret


def col_size(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    ret = '{:,}'.format(stat_res.st_size)
    return ret


def col_timeiso(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    dt = datetime.datetime.fromtimestamp(stat_res.st_mtime)
    ret = dt.strftime('%Y-%m-%d %H:%M:%S')
    return ret


def col_srcname(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    isdir = rowinfo['ftype'] == 'directory'
    if isdir:
        target = ''.join([fname, '/'])
    else:
        target = fname
    ret = target
    return ret


def col_targetname(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    islink = os.path.islink(fname)
    if islink:
        real = os.path.relpath(os.path.realpath(fname))
        isdir = rowinfo['ftype'] == 'directory'
        if isdir:
            target = ''.join([real, '/'])
        else:
            target = real
        ret = target
    else:
        ret = ' '
    return ret


def col_subfilecount(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
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


def col_filetype(rowinfo):
    contenttype = rowinfo['contenttype']
    if contenttype == 'binary_executable':
        return 'exe'
    if contenttype == 'binary_other':
        return 'bin'
    if contenttype == 'text':
        return 'txt'
    return '---'


def col_preview(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    contenttype = rowinfo['contenttype']
    if contenttype == 'binary_other':
        return preview_binary(fname)
    if contenttype == 'text':
        return preview_text(fname)
    return ' '


def preview_binary(fname):
    inrange = (
        lambda a: (
            (a >= 0x0021 and a <= 0x007E) or
            (a >= 0x0009 and a <= 0x000D)
        )
    )
    data = None
    with open(fname, 'rb') as fh:
        data = fh.read(PREVIEW_READ_LEN)
    if len(data) == 0:
        return ' '
    newdata = ''.join(map(chr, filter(inrange, data)))
    stripped = newdata.strip()
    cleaned = re.sub('(?u)[\s]+', ' ', stripped)
    truncated = cleaned[:PREVIEW_TRUNC_LEN]
    return truncated


def preview_text(fname):
    data = None
    with open(fname, 'rt', errors='replace') as fh:
        data = fh.read(PREVIEW_READ_LEN)
    if len(data) == 0:
        return ' '
    ##
    ## Match
    ##
    ## * First 32 characters of ascii
    ## * The DEL character
    ## * Anything that is a whitespace
    ##
    pat = r'(?u)[\u0000-\u0020\u0127\s]+'
    cleaned = re.sub(pat, ' ', data).strip()
    truncated = cleaned[:PREVIEW_TRUNC_LEN]
    return truncated



def getfileinfo(fname):
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
    ##
    ## First check if text
    ##
    if (re.search('(?u)[^a-zA-Z]text[^a-zA-Z]', data) is not None):
        return 'text'
    ##
    ## Executable binary file such as ELF
    ##
    if (
            re.search(
                '(?u)[^a-zA-Z]x-(executable|sharedlib)[^a-zA-Z]',
                data
            )
            is not None
    ):
        return 'binary_executable'
    ##
    ## Some other binary file such as an image
    ##
    return 'binary_other'


def getrowdefs():
    fdefs = [
        {
            'name': 'acls',
            'func': col_acls,
            'onlyfull': True
        },
        {
            'name': 'owner',
            'func': col_owner,
            'onlyfull': True
        },
        {
            'name': 'filetype',
            'func': col_filetype,
            'onlyfull': True
        },
        {
            'name': 'size',
            'func': col_size,
            'onlyfull': False
        },
        {
            'name': 'timeiso',
            'func': col_timeiso,
            'onlyfull': False
        },
        {
            'name': 'srcname',
            'func': col_srcname,
            'onlyfull': False
        },
        {
            'name': 'targetname',
            'func': col_targetname,
            'onlyfull': False
        },
        {
            'name': 'subfilecount',
            'func': col_subfilecount,
            'onlyfull': False
        },
        {
            'name': 'preview',
            'func': col_preview,
            'onlyfull': True
        }
    ]
    return fdefs


def shouldbuild(defrec, full=False):
    if defrec['onlyfull'] and (not full):
        return False
    return True


def buildrow(fname, full=False):
    rowinfo = getrowinfo(fname)
    fdefs = getrowdefs()
    func = (
        lambda rec: (
            rec['name'],
            (
                rec['func'](rowinfo) if
                shouldbuild(rec, full=full) else
                None
            )
        )
    )
    row = {}
    row['info'] = rowinfo
    row['render'] = dict(map(func, fdefs))
    return row;


def info_ftype(fname, stat_res):
    if os.path.islink(fname):
        real = os.path.relpath(os.path.realpath(fname))
    else:
        real = fname
    if os.path.isdir(real):
        ret = 'directory'
    else:
        ret = 'file'
    return ret


def info_timeepoch(fname, stat_res):
    ret = str(stat_res.st_mtime)
    return ret


def info_contenttype(fname, stat_res):
    if os.path.isdir(fname):
        return 'not_applicable'
    if not os.access(fname, os.R_OK):
        return 'not_readable'
    if stat_res.st_size == 0:
        return 'empty'
    fileinfo = getfileinfo(fname)
    ##
    ## Binary Executable such as ELF
    ##
    if fileinfo == 'binary_executable':
        return 'binary_executable'
    ##
    ## Some other binary such as image
    ##
    if fileinfo == 'binary_other':
        return 'binary_other'
    ##
    ## If is text
    ##
    if fileinfo == 'text':
        return 'text'
    ##
    ## Something else
    ##
    return 'other'


def getrowinfo(fname):
    stat_res = os.lstat(fname)
    info = {}
    info['fname'] = fname
    info['stat_res'] = stat_res
    info['ftype'] = info_ftype(fname, stat_res)
    info['contenttype'] = info_contenttype(fname, stat_res)
    info['timeepoch'] = info_timeepoch(fname, stat_res)
    return info


def processrows(files, full=False):
    func = lambda fname: buildrow(fname, full=full)
    out = map(func, files)
    return out


def concatoutput(data):
    formatted = ''.join(['\n', data, '\n', '\n'])
    return formatted


def display(rows):
    formatted = concatoutput(rows)
    pagedisplay(formatted)
    return True


def getfiles(full=False):
    files = os.listdir('./')
    processed = processrows(files, full=full)
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
    encoded = output.encode('utf-8')
    with proc() as pager:
        try:
            pager.communicate(encoded)
            pager.stdin.close()
            pager.wait()
        except KeyboardInterrupt:
            ## TODO: Any way to stop ctrl-c from
            ## screwing up keyboard entry?
            pager.terminate()
            pager.wait()
    return True


def run(full=False):
    files = getfiles(full=full)
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
