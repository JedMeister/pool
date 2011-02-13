#!/usr/bin/python
"""Get packages from pool

  If a package is specified without a version, get the newest package.
  If no packages are specified as arguments, get all the newest packages.

Options:
  -i --input <file>	file from which we read package list (- for stdin)
    
  -s --strict		fatal error on missing packages
  -q --quiet		suppress warnings about missing packages

  -t --tree		output dir is in a package tree format (like a repository)

"""
import sys
import help
import getopt

from os.path import *
import re

from pool import Pool

from common import *
from forked import forked_constructor

@help.usage(__doc__)
def usage():
    print >> sys.stderr, "Syntax: %s [-options] <output-dir> [ package[=version] ... ]" % sys.argv[0]


exitcode = 0
def warn(s):
    global exitcode
    exitcode = 1
    
    print >> sys.stderr, "warning: " + str(s)
    
def fatal(s):
    print >> sys.stderr, "error: " + str(s)
    sys.exit(1)

def read_packages(fh):
    packages = []
    for line in fh.readlines():
        line = re.sub(r'#.*', '', line)
        line = line.strip()
        if not line:
            continue
        packages.append(line)
    return packages
    
def get_treedir(pkgname):
    if pkgname.startswith("lib"):
        return join(pkgname[:4], pkgname)
    else:
        return join(pkgname[:1], pkgname)

def main():
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'i:sqt',
                                   ['input=', 'strict', 'quiet', 'tree'])
    except getopt.GetoptError, e:
        usage(e)

    if not args:
        usage()

    outputdir = args[0]
    packages = args[1:]

    input = None
    opt_strict = False
    opt_quiet = False
    opt_tree = False
    
    for opt, val in opts:
        if opt in ('-i', '--input'):
            if val == '-':
                input = sys.stdin
            else:
                input = file(val, "r")
        elif opt in ('-s', '--strict'):
            opt_strict = True
        elif opt in ('-q', '--quiet'):
            opt_quiet = True
        elif opt in ('-t', '--tree'):
            opt_tree = True


    # 1) don't drop privileges immediately because we may need root privileges
    #    in the cli process to write packages to a root owned directory
    # 2) we drop privileges in a separate process, using forked_constructor
    # 3) to minimize overhead we use forked_constructor to drop privileges
    #    only after verifying we really need to drop privileges
    pool = Pool(autosync=False, drop_privileges=False)
    if pool.drop_privileges(pretend=True):
        def f():
            pool.drop_privileges()
            return pool
        pool = forked_constructor(f, print_traceback=True)()
        
    pool.sync()
    
    if input:
        packages += read_packages(input)

    resolved = []
    unresolved = []
    for package in packages:
        if not pool.exists(package):
            if opt_strict:
                fatal("%s: no such package" % package)
            if not opt_quiet:
                warn("%s: no such package" % package)
            continue

        if '=' in package:
            resolved.append(package)
        else:
            unresolved.append(package)

    if unresolved:
        resolved += pool.resolve(unresolved)

    packages = resolved

    if not args[1:] and not input:
        # if no packages specified, get all the newest versions
        packages = pool.list()

    for package in packages:
        path_from = pool.getpath_deb(package)
        fname = basename(path_from)
        
        if opt_tree:
            package_name = package.split("=")[0]
            path_to = join(outputdir, get_treedir(package_name), fname)
            mkdir(dirname(path_to))
        else:
            path_to = join(outputdir, basename(path_from))

        if not exists(path_to):
            hardlink_or_copy(path_from, path_to)

    sys.exit(exitcode)
        
if __name__=="__main__":
    main()
