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
from functools import reduce
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
    'size_filecount': 'magenta',
    'size_bytes': 'green',
    'acls': 'dark_gray',
    'owner': 'dark_gray',
    'filetype': 'dark_gray',
    'preview': 'dark_gray',
    'default': 'light_magenta'
}


PREVIEW_READ_LEN = 256
PREVIEW_TRUNC_LEN = 48

DEFAULT_START_PATH = './'


def sortfile(row):
    fname = row['info']['fname']
    lowfname = fname.strip().lower()
    key = 0 if (row['info']['ftype'] == 'directory') else 1
    out = (key, lowfname)
    return out


def getcolordefs(row, field):
    if field == 'targetname':
        clr = 'targetname'
    elif field == 'srcname':
        if row['info']['ftype'] == 'directory':
            clr = 'srcname_directory'
        else:
            clr = 'srcname_file'
    elif field == 'timeiso':
        clr = 'time'
    elif field == 'size':
        if row['info']['ftype'] == 'directory':
            clr = 'size_filecount'
        else:
            clr = 'size_bytes'
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
    return clr


def addpadding(field, val, colpaddings, align):
    if len(val) == 0:
        return ' '
    alignchar = '>' if (align == 'right') else '<'
    padlen = colpaddings[field]
    padstr = ''.join(['{:', alignchar, str(padlen), 's}'])
    ret = padstr.format(val)
    return ret


def makepretty(row, field, colpaddings, fdefs):
    align = fdefs[field]['align']
    clr = getcolordefs(row, field)
    clrval = COLOR_VALS[clr]
    textval = row['render'][field]
    paddedval = addpadding(field, textval, colpaddings, align)
    colorval = addcolor(paddedval, clrval)
    return colorval


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
    out.append('timeiso')
    out.append('srcname')
    out.append('targetname')
    if full:
        out.append('preview')
    return out


def structurecols(row, colpaddings, fdefs, full=False):
    colslisting = getcolslisting(full=full)
    func = lambda name: makepretty(row, name, colpaddings, fdefs)
    ret = map(func, colslisting)
    return ret


def padcols(row, colpaddings):
    print()
    ret = (
        map(
            lambda rec: padcol(rec[0], rec[1], colpaddings),
            row['render'].items()
        )
    )
    return ret


def rendercols(row, colpaddings, fdefs, full=False):
    margin = '  '
    structcols = structurecols(row, colpaddings, fdefs, full=full)
    ret = ''.join([margin, margin.join(structcols)])
    return ret


def renderrows(files, full=False):
    colpaddings = getcolpaddings(files)
    fdefs = getrowdefs()
    renderer = lambda r: rendercols(r, colpaddings, fdefs, full=full)
    out = '\n'.join(map(renderer, files))
    return out


def get_acls_me(fname, stat_res):
    t_no = 0
    me_can_read = os.access(fname, os.R_OK)
    me_can_write = os.access(fname, os.W_OK)
    me_can_exec = os.access(fname, os.X_OK)
    me_pdefs = [
        (me_can_read, 4),
        (me_can_write, 2),
        (me_can_exec, 1)
    ]
    me_vals = map(lambda x: x[1] if x[0] else t_no, me_pdefs)
    me_acls_num = reduce(lambda x, y: x | y, me_vals, 0)
    me_acls_mode = str(me_acls_num)
    return me_acls_mode


def get_acls_all(fname, stat_res):
    #all_acls_mode = stat.filemode(stat_res.st_mode)
    all_acls_mode = str(oct(stat.S_IMODE(stat_res.st_mode)))[-3:]
    return all_acls_mode


def col_acls(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    all_acls_mode = get_acls_all(fname, stat_res)
    me_acls_mode = get_acls_me(fname, stat_res)
    ret = ' '.join([all_acls_mode, me_acls_mode])
    return ret


def col_owner(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    owner = pwd.getpwuid(stat_res.st_uid).pw_name
    group = grp.getgrgid(stat_res.st_gid).gr_name
    ret = ':'.join([owner, group])
    return ret


def getfilesize(rowinfo):
    stat_res = rowinfo['stat_res']
    ret = '{:,}'.format(stat_res.st_size)
    return ret


def col_size(rowinfo):
    if rowinfo['ftype'] == 'directory':
        return getsubfilecount(rowinfo)
    return getfilesize(rowinfo)


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


def getsubfilecount(rowinfo):
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
        return '-'
    if not os.access(real, os.R_OK):
        return '-'
    return str(len(os.listdir(real)))


def col_filetype(rowinfo):
    contenttype = rowinfo['contenttype']
    if contenttype == 'directory':
        return 'd'
    if contenttype == 'binary_executable':
        return 'e'
    if contenttype == 'binary_other':
        return 'b'
    if contenttype == 'text':
        return 't'
    return '-'


def col_preview(rowinfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    contenttype = rowinfo['contenttype']
    if contenttype == 'directory':
        return preview_directory(fname)
    if contenttype == 'binary_other':
        return preview_binary(fname)
    if contenttype == 'text':
        return preview_text(fname)
    return ' '


def preview_directory(fname):

    def func(subfname):
        checkfname = os.path.join(fname, subfname)
        if os.path.islink(checkfname):
            real = os.path.relpath(os.path.realpath(checkfname))
        else:
            real = checkfname
        if os.path.isdir(real):
            path = ''.join([checkfname, '/'])
        else:
            path = checkfname
        stripped = path[(len(fname) + 1):]
        return stripped

    all_files = os.listdir(fname)
    all_len = len(all_files)
    sub_files = list(map(func, all_files[:32]))
    sub_len = len(sub_files)
    txt = ' '.join(sub_files)
    truncated = txt[:38]
    lastindex = truncated.rfind(' ')
    cleaned = (
        truncated if
        (lastindex < 1) else
        truncated[:lastindex]
    )
    if sub_len < all_len:
        ret = ' '.join([cleaned, '...'])
    else:
        ret = cleaned
    return ret


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
    fdefs = {
        'acls': {
            'name': 'acls',
            'func': col_acls,
            'onlyfull': True,
            'align': 'left'
        },
        'owner': {
            'name': 'owner',
            'func': col_owner,
            'onlyfull': True,
            'align': 'left'
        },
        'filetype': {
            'name': 'filetype',
            'func': col_filetype,
            'onlyfull': True,
            'align': 'left'
        },
        'size': {
            'name': 'size',
            'func': col_size,
            'onlyfull': False,
            'align': 'right'
        },
        'timeiso': {
            'name': 'timeiso',
            'func': col_timeiso,
            'onlyfull': False,
            'align': 'left'
        },
        'srcname': {
            'name': 'srcname',
            'func': col_srcname,
            'onlyfull': False,
            'align': 'left'
        },
        'targetname': {
            'name': 'targetname',
            'func': col_targetname,
            'onlyfull': False,
            'align': 'left'
        },
        'preview': {
            'name': 'preview',
            'func': col_preview,
            'onlyfull': True,
            'align': 'left'
        }
    }
    return fdefs


def shouldbuild(defrec, full=False):
    if defrec['onlyfull'] and (not full):
        return False
    return True


def buildrow(fname, fdefs, full=False):
    rowinfo = getrowinfo(fname)
    func = (
        lambda rec: (
            rec['name'],
            (
                rec['func'](rowinfo) if
                shouldbuild(rec, full=full) else
                ' '
            )
        )
    )
    row = {}
    row['info'] = rowinfo
    row['render'] = dict(map(func, fdefs.values()))
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
        return 'directory'
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
    fdefs = getrowdefs()
    func = lambda fname: buildrow(fname, fdefs, full=full)
    out = map(func, files)
    return out


def concatoutput(data):
    formatted = ''.join(['\n', data, '\n', '\n'])
    return formatted


def display(rows):
    formatted = concatoutput(rows)
    pagedisplay(formatted)
    return True


def get_dir_listing(start=None, filtres=None):
    if start is None:
        start = './'
    if start != './':
        start = os.path.relpath(start)
    joinit = (
        lambda f: (
            os.path.join(
                (
                    start[2:] if
                    (start[:2] == './') else
                    start
                ),
                f
            )
        )
    )
    filterit = (
        lambda f: (
            filtres in f
        )
    )
    if (not os.path.exists(start)) or (not os.path.isdir(start)):
        return None
    files = os.listdir(start)
    fpaths = (
        iter(files) if
        (filtres is None) else
        filter(filterit, files)
    )
    paths = map(joinit, fpaths)
    return paths


def getfiles(start=None, full=False, filtres=None):
    paths = get_dir_listing(start=start, filtres=filtres)
    if paths is None:
        return None
    processed = processrows(paths, full=full)
    sfiles = sorted(processed, key=sortfile, reverse=False)
    out = list(sfiles)
    return out


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


def getcolpaddings(rows):
    longest = {}
    for row in rows:
        for colname, colval in row['render'].items():
            if colname not in longest:
                longest[colname] = 0
            collen = len(colval)
            if collen > longest[colname]:
                longest[colname] = collen
    return longest


def run(start=None, full=False, filtres=None):
    files = getfiles(start=start, full=full, filtres=filtres)
    if files is None:
        rendererror()
        return False
    rows = renderrows(files, full=full)
    display(rows)
    return True


def rendererror():
    sys.stderr.write("Path could not be found, or path is not a directory.\n")
    return True


def getargs():
    arger = argparse.ArgumentParser(description='Replacement for ls')
    arger.add_argument(
        'start',
        metavar='STARTPATH',
        type=str,
        nargs='?',
        help='Starting Path',
        default=DEFAULT_START_PATH,
        action='store'
    )
    arger.add_argument(
        '-g',
        '--filter',
        metavar='FILTERSTR',
        type=str,
        help='Filter Results',
        dest='filtres',
        default=None,
        action='store'
    )
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
    ret = (
        run(
            start=args.start,
            full=args.full,
            filtres=args.filtres
        )
    )
    if ret is False:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
