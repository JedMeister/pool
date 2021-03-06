#!/usr/bin/python
# Copyright (c) TurnKey GNU/Linux - http://www.turnkeylinux.org
#
# This file is part of Pool
#
# Pool is free software; you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.

"""Initialize a new pool"""
import os
import sys
import help
import pool

@help.usage(__doc__)
def usage():
    print >> sys.stderr, "Syntax: %s /path/to/build-chroot" % sys.argv[0]

def fatal(s):
    print >> sys.stderr, "error: " + str(s)
    sys.exit(1)

def main():
    args = sys.argv[1:]

    if not args:
        usage()

    if len(args) != 1:
        usage("bad number of arguments")

    buildroot = args[0]

    try:
        pool.Pool.init_create(os.path.abspath(buildroot))
    except pool.Error, e:
        fatal(e)

if __name__=="__main__":
    main()

