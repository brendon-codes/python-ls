#!/usr/bin/env python3

import sys
import os
import pwd
import grp
import stat
import datetime
from pprint import pprint


def getrow(fname):
    return fname


def sortfile(row):
    fname = row['name']
    lowfname = fname.strip().lower()
    key = '0' if os.path.isdir(fname) else '1'
    out = ':'.join([key, lowfname])
    return out


def structurecols(row):
    return [
        row['perms'],
        row['owner'],
        row['size'],
        row['time'],
        row['printname']
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
    ret = str(stat_res.st_size)
    return ret


def col_time(fname, stat_res):
    dt = datetime.datetime.fromtimestamp(stat_res.st_mtime)
    ret = dt.strftime('%Y-%m-%d %H:%M:%S')
    return ret


def col_printname(fname, stat_res):
    islink = os.path.islink(fname)
    if islink:
        target = os.path.relpath(os.path.realpath(fname))
        ret = ' -> '.join([fname, target])
    else:
        ret = fname
    return ret


def col_name(fname, stat_res):
    return fname


def buildrow(fname):
    stat_res = os.lstat(fname)
    row = {
        'perms': col_perms(fname, stat_res),
        'owner': col_owner(fname, stat_res),
        'size': col_size(fname, stat_res),
        'time': col_time(fname, stat_res),
        'printname': col_printname(fname, stat_res),
        'name': col_name(fname, stat_res)
    }
    return row;


def processrows(files):
    out = map(buildrow, files)
    return out


def display(out):
    sys.stdout.write(out)
    sys.stdout.write('\n')
    return True


def getfiles():
    files = os.listdir('./')
    processed = processrows(files)
    sfiles = sorted(processed, key=sortfile)
    return sfiles


def main():
    files = getfiles()
    out = renderrows(files)
    display(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
