#!/usr/bin/env python3

# pyright: strict

from typing import TypedDict, Literal, Dict, List, Callable, Any, cast, Optional
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


class StatRes:
    st_mode: int
    st_mtime: float
    st_uid: int
    st_gid: int
    st_size: int


FileType = Literal["file", "directory"]

ContentType = Literal[
    "directory",
    "binary_executable",
    "binary_other",
    "text",
    "unknown"
]


class FileRowInfo(TypedDict):
    fname: str
    ftype: FileType
    stat_res: StatRes
    contenttype: ContentType


class FileRow(TypedDict):
    info: FileRowInfo
    render: Dict[str, str]


FileRows = List[FileRow]


Align = Literal["left", "right"]


ColsType = Literal[
    "acls", "owner", "filetype", "size",
    "timeiso", "srcname", "targetname", "preview"
]


ColsTypes = List[ColsType]


class FileDef(TypedDict):
    align: Align
    name: ColsType
    onlyfull: bool
    func: Callable[[Any], str]


ColPaddings = Dict[str, int]


FileDefs = Dict[ColsType, FileDef]


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


def sortfile(row: FileRow):
    fname = row['info']['fname']
    lowfname = fname.strip().lower()
    key = 0 if (row['info']['ftype'] == 'directory') else 1
    out = (key, lowfname)
    return out


def getcolordefs(row: FileRow, field: str):
    if field == 'targetname':
        return 'targetname'
    if field == 'srcname':
        if row['info']['ftype'] == 'directory':
            return 'srcname_directory'
        return 'srcname_file'
    if field == 'timeiso':
        return 'time'
    if field == 'size':
        if row['info']['ftype'] == 'directory':
            return 'size_filecount'
        return 'size_bytes'
    if field == 'acls':
        return 'acls'
    if field == 'owner':
        return 'owner'
    if field == 'size':
        return 'size'
    if field == 'filetype':
        return 'filetype'
    if field == 'preview':
        return 'preview'
    return 'default'


def addpadding(field: str, val: str, colpaddings: ColPaddings, align: Align):
    if len(val) == 0:
        return ' '
    alignchar = '>' if (align == 'right') else '<'
    padlen = colpaddings[field]
    padstr = ''.join(['{:', alignchar, str(padlen), 's}'])
    ret = padstr.format(val)
    return ret


def makepretty(row: FileRow, field: str, colpaddings: ColPaddings, fdefs: FileDefs):
    align = fdefs[field]['align']
    clr = getcolordefs(row, field)
    clrval = COLOR_VALS[clr]
    textval = row['render'][field]
    paddedval = addpadding(field, textval, colpaddings, align)
    colorval = addcolor(paddedval, clrval)
    return colorval


def addcolor(text: str, color: str):
    return text.join([COLORS[color], COLORS['end']])
    return out


def getcolslisting(full: bool=False):
    out: ColsTypes = []
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


def structurecols(row: FileRow, colpaddings: ColPaddings, fdefs: FileDefs, full: bool=False):
    colslisting = getcolslisting(full=full)
    return map(lambda name: makepretty(row, name, colpaddings, fdefs), colslisting)


def rendercols(row: FileRow, colpaddings: ColPaddings, fdefs: FileDefs, full: bool=False):
    margin = '  '
    structcols = structurecols(row, colpaddings, fdefs, full=full)
    return ''.join([margin, margin.join(structcols)])


def getcolpaddings(rows: FileRows):
    longest: Dict[str, int] = {}
    for row in rows:
        for colname, colval in row['render'].items():
            if colname not in longest:
                longest[colname] = 0
            collen = len(colval)
            if collen > longest[colname]:
                longest[colname] = collen
    return longest


def getrowdefs():
    ret: FileDefs = {
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
    return ret


def renderrows(rows: FileRows, full: bool=False):
    colpaddings = getcolpaddings(rows)
    fdefs = getrowdefs()
    rendered = map(lambda r: rendercols(r, colpaddings, fdefs, full=full), rows)
    out = '\n'.join(rendered)
    return out


def get_acls_me(fname: str, stat_res: StatRes):
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


def get_acls_all(fname: str, stat_res: StatRes):
    return str(oct(stat.S_IMODE(stat_res.st_mode)))[-3:]


def col_acls(rowinfo: FileRowInfo):
    fname = rowinfo['fname']
    stat_res = rowinfo['stat_res']
    all_acls_mode = get_acls_all(fname, stat_res)
    me_acls_mode = get_acls_me(fname, stat_res)
    return ' '.join([all_acls_mode, me_acls_mode])


def col_owner(rowinfo: FileRowInfo):
    stat_res = rowinfo['stat_res']
    owner = pwd.getpwuid(stat_res.st_uid).pw_name
    group = grp.getgrgid(stat_res.st_gid).gr_name
    ret = ':'.join([owner, group])
    return ret


def getfilesize(rowinfo: FileRowInfo):
    stat_res = rowinfo['stat_res']
    ret = '{:,}'.format(stat_res.st_size)
    return ret


def col_size(rowinfo: FileRowInfo):
    if rowinfo['ftype'] == 'directory':
        return getsubfilecount(rowinfo)
    return getfilesize(rowinfo)


def col_timeiso(rowinfo: FileRowInfo):
    stat_res = rowinfo['stat_res']
    dt = datetime.datetime.fromtimestamp(stat_res.st_mtime)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def col_srcname(rowinfo: FileRowInfo):
    fname = rowinfo['fname']
    isdir = rowinfo['ftype'] == 'directory'
    return ''.join([fname, '/']) if isdir else fname


def col_targetname(rowinfo: FileRowInfo):
    fname = rowinfo['fname']
    islink = os.path.islink(fname)
    if islink:
        real = os.path.relpath(os.path.realpath(fname))
        isdir = rowinfo['ftype'] == 'directory'
        return ''.join([real, '/']) if isdir else real
    return ' '


def getsubfilecount(rowinfo: FileRowInfo):
    fname = rowinfo['fname']
    islink = os.path.islink(fname)
    real = os.path.relpath(os.path.realpath(fname)) if islink else fname
    if not os.path.isdir(real):
        return '-'
    if not os.access(real, os.R_OK):
        return '-'
    return str(len(os.listdir(real)))


def col_filetype(rowinfo: FileRowInfo):
    contenttype = rowinfo['contenttype']
    if contenttype == 'directory':
        return 'd'
    if contenttype == 'binary_executable':
        return 'e'
    if contenttype == 'binary_other':
        return 'b'
    if contenttype == 'text':
        return 't'
    return 'u'


def col_preview(rowinfo: FileRowInfo):
    fname = rowinfo['fname']
    contenttype = rowinfo['contenttype']
    if contenttype == 'directory':
        return preview_directory(fname)
    if contenttype == 'binary_other':
        return preview_binary(fname)
    if contenttype == 'text':
        return preview_text(fname)
    return ' '


def preview_directory(fname: str):

    def _func(subfname: str):
        checkfname = os.path.join(fname, subfname)
        real = (
            os.path.relpath(os.path.realpath(checkfname)) if
            os.path.islink(checkfname) else
            checkfname
        )
        path = (
            ''.join([checkfname, '/']) if
            os.path.isdir(real) else
            checkfname
        )
        stripped = path[(len(fname) + 1):]
        return stripped

    all_files = os.listdir(fname)
    all_len = len(all_files)
    sub_files = list(map(_func, all_files[:32]))
    sub_len = len(sub_files)
    txt = ' '.join(sub_files)
    truncated = txt[:38]
    lastindex = truncated.rfind(' ')
    cleaned = (
        truncated if
        (lastindex < 1) else
        truncated[:lastindex]
    )
    return ' '.join([cleaned, '...']) if sub_len < all_len else cleaned


def preview_binary(fname: str):
    def _inrange(a: int):
        return (
            (a >= 0x0021 and a <= 0x007E) or
            (a >= 0x0009 and a <= 0x000D)
        )

    data: bytes
    with open(fname, 'rb') as fh:
        data = fh.read(PREVIEW_READ_LEN)
    if len(data) == 0:
        return ' '
    newdata = ''.join(map(chr, filter(_inrange, data)))
    stripped = newdata.strip()
    cleaned = re.sub(r"(?u)[\s]+", ' ', stripped)
    return cleaned[:PREVIEW_TRUNC_LEN]


def preview_text(fname: str):
    data: str
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
    return cleaned[:PREVIEW_TRUNC_LEN]


def getfileinfo(fname: str):
    """
    See: http://stackoverflow.com/a/898759
    """
    def _proc():
        return (
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

    rawdata: Optional[bytes]
    with _proc() as subproc:
        rawdata = None if subproc.stdout is None else subproc.stdout.read()
    if rawdata is None:
        return cast(ContentType, "unknown")
    data = rawdata.decode('utf-8', errors='replace')
    ##
    ## First check if text
    ##
    if (re.search('(?u)[^a-zA-Z]text[^a-zA-Z]', data) is not None):
        return cast(ContentType, 'text')
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
        return cast(ContentType, 'binary_executable')
    ##
    ## Some other binary file such as an image
    ##
    return cast(ContentType, 'binary_other')



def shouldbuild(defrec: FileDef, full: bool=False):
    if defrec['onlyfull'] and (not full):
        return False
    return True


def buildrow(fname: str, fdefs: FileDefs, full: bool=False):
    rowinfo = getrowinfo(fname)

    def _func(rec: FileDef):
        return (
            rec['name'],
            (
                rec['func'](rowinfo) if
                shouldbuild(rec, full=full) else
                ' '
            )
        )

    ret: FileRow = {
        'info': rowinfo,
        'render': dict(map(_func, fdefs.values()))
    }
    return ret


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


def info_timeepoch(fname: str, stat_res: StatRes):
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


def getrowinfo(fname: str):
    stat_res = cast(StatRes, os.lstat(fname))
    ret: FileRowInfo = {
        'fname': fname,
        'stat_res': stat_res,
        'ftype': info_ftype(fname, stat_res),
        'contenttype': info_contenttype(fname, stat_res),
        'timeepoch': info_timeepoch(fname, stat_res)
    }
    return ret


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
