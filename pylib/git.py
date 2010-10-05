import sys
import os
from os.path import *
import subprocess
import commands

def is_git_repository(path):
    """Return True if path is a git repository"""
    
    try:
        git = Git(path)
        return True
    except:
        return False

def setup(method):
    """Decorator that:
    1) chdirs into git.path
    2) processes arguments (only non-keywords arguments):
       stringifies them (except None, True or False)
       translates all absolute paths inside git.path to be relative to git.path
    
    """

    def wrapper(self, *args, **kws):
        orig_cwd = os.getcwd()
        os.chdir(self.path)

        def make_relative(arg):
            if arg in (None, True, False):
                return arg

            if isinstance(arg, (list, tuple)):
                return map(make_relative, arg)

            arg = str(arg)
            arg = join(realpath(dirname(arg)), basename(arg))
            if not arg.startswith(self.path):
                return arg
            return arg[len(self.path) + 1:]

        args = map(make_relative, args)
            
        try:
            ret = method(self, *args, **kws)
        finally:
            os.chdir(orig_cwd)

        return ret
        
    return wrapper

class Git(object):
    """Class for interfacing with a git repository.

    Most methods that are documented to return values raise an exception on error,
    except if the method is documented to return None on error.
    """
    class Error(Exception):
        def __str__(self):
            return str(self.args[0])

    class MergeMsg(object):
        """Magical attribute.

        Set writes to .git/MERGE_MSG
        Get reads value from .git/MERGE_MSG
        """

        def get_path(self, obj):
            return join(obj.path, ".git", "MERGE_MSG")
        
        def __get__(self, obj, type):
            path = self.get_path(obj)
            if exists(path):
                return file(path, "r").read()

            return None
        
        def __set__(self, obj, val):
            path = self.get_path(obj)
            file(path, "w").write(val)

    MERGE_MSG = MergeMsg()

    @classmethod
    def init_create(cls, path, bare=False, verbose=False):
        if not lexists(path):
            os.mkdir(path)

        init_path = path
        if not bare:
            init_path = join(init_path, ".git")

        command = "git --git-dir %s init" % commands.mkarg(init_path)
        if not verbose:
            command += " > /dev/null"
        os.system(command)

        return cls(path)

    def __init__(self, path):
        # heuristic: if the path has a .git directory in it, then its not bare
        # otherwise we assume its a bare repo if
        # 1) it ends with .git
        # 2) seems to be initialized (objects and refs directories exist)
        self.path = realpath(path)
        path_git = join(path, ".git")
        if isdir(path_git):
            self.bare = False
            self.gitdir = path_git
        elif path.endswith(".git") and \
                 isdir(join(path, "refs")) and isdir(join(path, "objects")):
            self.bare = True
            self.gitdir = path
        else:
            raise self.Error("Not a git repository `%s'" % path)

    @classmethod
    def _system(cls, command, *args):
        sys.stdout.flush()
        sys.stderr.flush()

        command = command + " ".join([commands.mkarg(arg) for arg in args])
        err = os.system(command)
        if err:
            raise cls.Error("command failed: " + command,
                            os.WEXITSTATUS(err))

    @setup
    def read_tree(self, *opts):
        """git-read-tree *opts"""
        self._system("git-read-tree", *opts)

    @setup
    def update_index(self, *paths):
        """git-update-index --remove <paths>"""

        self._system("git-update-index --remove", *paths)
        
    @setup
    def update_index_refresh(self):
        """git-update-index --refresh"""
        self._system("git-update-index -q --unmerged --refresh")

    @setup
    def update_index_all(self):
        """update all files that need update according to git-update-index --refresh"""
        err, output = commands.getstatusoutput("git-update-index --refresh")
        if not err:
            return
        output.split('\n')

        files = [ line.rsplit(':', 1)[0] for line in output.split('\n')
                  if line.endswith("needs update") ]
        self.update_index(*files)

    @setup
    def add(self, *paths):
        """git-add <path>"""
        # git-add chokes on empty directories
        self._system("git-add", *paths)

    @setup
    def checkout(self, *args):
        """git-checkout *args"""
        self._system("git-checkout", *args)
        
    @setup
    def checkout_index(self):
        """git-checkout-index -a -f"""
        self._system("git-checkout-index -a -f")

    @setup
    def update_ref(self, *args):
        """git-update-ref [ -d ] <ref> <rev> [ <oldvalue > ]"""
        self._system("git-update-ref", *args)

    @setup
    def rm_cached(self, path):
        """git-rm <path>"""
        self._system("git-rm --ignore-unmatch --cached --quiet -f -r", path)

    @setup
    def commit(self, paths=(), msg=None, update_all=False, verbose=False):
        """git-commit"""
        command = "git-commit"
        if update_all:
            command += " -a"
        if verbose:
            command += " -v"

        if msg:
            self._system(command, "-m", msg, *paths)
        else:
            self._system(command, *paths)

    @setup
    def merge(self, remote):
        """git-merge <remote>"""
        self._system("git-merge", remote)

    @setup
    def reset(self, *args):
        """git-reset"""
        self._system("git-reset", *args)

    @setup
    def branch_delete(self, branch):
        """git-branch -D <branch>"""
        self._system("git-branch -D", branch)

    @setup
    def prune(self):
        """git-prune"""
        self._system("git-prune")

    @setup
    def repack(self, *args):
        """git-repack *args"""
        self._system("git-repack", *args)
        
    @setup
    def fetch(self, repository, refspec):
        self._system("git-fetch", repository, refspec)

    @setup
    def raw(self, command, *args):
        """execute a raw git command.
        Returns:
            exit status code if command failed
            None if it was successfuly"""
        
        command = "git-" + command
        try:
            self._system(command, *args)
        except self.Error, e:
            return e[1]

    @classmethod
    def _getoutput(cls, command, *args):
        command = command + " ".join([commands.mkarg(arg) for arg in args])
        status, output = commands.getstatusoutput(command)
        if status != 0:
            raise cls.Error("command `%s' failed: %s" % (command, output))
        return output

    @setup
    def write_tree(self):
        """git-write-tree
        Returns id of written tree"""
        return self._getoutput("git-write-tree")

    @setup
    def rev_parse(self, rev):
        """git-rev-parse <rev>.
        Returns object-id of parsed rev.
        Returns None on failure.
        """
        try:
            return self._getoutput("git-rev-parse", rev)
        except self.Error:
            return None

    @setup
    def merge_base(self, a, b):
        """git-merge-base <a> <b>.
        Returns common ancestor"""
        try:
            return self._getoutput("git-merge-base", a, b)
        except self.Error:
            return None

    @setup
    def symbolic_ref(self, name, ref=None):
        """git-symbolic-ref <name> [ <ref> ]
        Returns the value of the symbolic ref.
        """
        args = ["git-symbolic-ref", name]
        if ref:
            args.append(ref)
        return self._getoutput(*args)

    @setup
    def rev_list(self, commit):
        """git-rev-list <commit>.
        Returns list of commits.
        """
        return self._getoutput("git-rev-list", commit).split('\n')
    
    @setup
    def name_rev(self, rev):
        """git-name-rev <rev>
        Returns name of rev"""
        return self._getoutput("git-name-rev", rev).split(" ")[1]

    @setup
    def show_ref(self, ref):
        """git-show-ref <rev>.
        Returns ref name if succesful
        Returns None on failure"""
        try:
            return self._getoutput("git-show-ref", ref).split(" ")[1]
        except self.Error:
            return None

    @setup
    def commit_tree(self, id, log, parents=None):
        """git-commit-tree <id> [ -p <parents> ] < <log>
        Return id of object committed"""
        args = ["git-commit-tree", id]
        if parents:
            if not isinstance(parents, (list, tuple)):
                parents = [ parents ]

            for parent in parents:
                args += ["-p", parent]

        PIPE = subprocess.PIPE

        p = subprocess.Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        try:
            p.stdin.write(log)
            p.stdin.close()
        except IOError:
            pass
        
        err = p.wait()
        if err:
            raise self.Error("git-commit-tree failed: " + p.stderr.read())

        return p.stdout.read().strip()

    @setup
    def log(self, *args):
        """git-log *args
        Return stdout pipe"""


        command = [ "git-log" ]
        command.extend(args)

        PIPE = subprocess.PIPE
        p = subprocess.Popen(command, stdout=PIPE, bufsize=1)

        return p.stdout
    
    @setup
    def status(self, *paths):
        """git-diff-index --name-status HEAD
        Returns array of (status, path) changes """

        self.update_index_refresh()
        output = self._getoutput("git-diff-index --name-status HEAD", *paths)
        if output:
            return [ line.split('\t', 1) for line in output.split('\n')]
        return []
    
    @setup
    def list_unmerged(self):
        output = self._getoutput("git-diff --name-only --diff-filter=U")
        if output:
            return output.split('\n')
        return []

    @setup
    def get_commit_log(self, committish):
        """Returns commit log text for <committish>"""

        str = self._getoutput("git-cat-file commit", committish)
        return str[str.index('\n\n') + 2:]

    @setup
    def list_changed_files(self, compared, *paths):
        """Return a list of files that changed between compared.

        If compared is tuple/list with 2 elements, we compare the
        compared[0] and compared[1] with git-diff-tree.
        
        If compared is not a tuple/list, or a tuple/list with 1 element,
        we compare compared with git-diff-index which compares a commit/treeish to
        the index."""

        self.update_index_refresh()
        if not isinstance(compared, (list, tuple)):
            compared = [ compared ]

        if len(compared) == 2:
            str = self._getoutput("git-diff-tree -r --name-only",
                                  compared[0], compared[1], *paths)
        elif len(compared) == 1:
            str = self._getoutput("git-diff-index -r --name-only",
                                  compared[0], *paths)
        else:
            raise self.Error("compared does not contain 1 or 2 elements")
            
        if str:
            return str.split('\n')
        return []

    def list_refs(self, refpath):
        """list refs in <refpath> (e.g., "heads")"""
        return os.listdir(join(self.gitdir, "refs", refpath))

    def list_heads(self):
        return self.list_refs("heads")

    def list_tags(self):
        return self.list_refs("tags")

    def remove_ref(self, ref):
        """deletes refs/<ref> from the git repository"""
        path = join(self.gitdir, "refs", ref)
        if lexists(path):
            os.remove(path)

    def set_alternates(self, git):
        """set alternates path to point to the objects path of the specified git object"""

        fh = file(join(self.gitdir, "objects/info/alternates"), "w")
        print >> fh, join(git.gitdir, "objects")
        fh.close()
