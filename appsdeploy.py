import sys

if not sys.version.startswith('2.7'):
  print 'python version expected: 2.7.x'
  print '                  found: ', sys.version
  raise SystemExit

import logging
import os
import argparse
import traceback
import json
import urllib
import subprocess
import tarfile
import shutil
import datetime
import zipfile
from distutils.dir_util import copy_tree

# ------------------------------------------------- #
#  class structure space
# ------------------------------------------------- #


class DSLRepl:
    """structure for the dsl repl"""

    symtab = None
    hacfg = None
    artifile = None
    artidir = "ssoapps"
    bakdir = None

    def __init__(self, args):
        self.symtab = args
        currdatetime = datetime.datetime.now()
        self.symtab.month_name = currdatetime.strftime("%B")
        self.symtab.year = currdatetime.strftime("%Y")
        self.symtab.branchpath = os.path.join(
            args.svnurl, 'sso_' + args.branch)
        self.setup_built_artifact(args.jenkurl)

    # downloads file/dir to current directory
    def repoexport(self, itemuri, item, absolutepath=False):
        itempath = itemuri if absolutepath else os.path.join(self.symtab.branchpath, itemuri)
        logging.info('itempath: %s', itempath)
        if (self.symtab.branchpath.startswith(('http://', 'https://'))):
            logging.info('export from svn')
            retval = subprocess.call(["svn", "export", "--force", itempath])
            if (retval != 0):
                raise Exception('return code was ' + retval +
                                ' while invoking svn export ' + itempath)
        else:
            logging.info(
                'export from filesystem, itemuri: %s, item: %s', itemuri, item)
            if os.path.isdir(itempath):
                if os.path.isdir(item):
                    shutil.rmtree(item)
                copy_tree(itempath, os.path.join(os.getcwd(), item))
            if os.path.isfile(itempath):
                shutil.copy(itempath, os.getcwd())

    # download and extract built artifact bundle
    def setup_built_artifact(self, aurl):
        self.artifile = aurl.rsplit('/', 1)[-1]
        self.cleanup()
        # decide if remote or local
        if aurl.startswith(('http://', 'https://')):
            logging.info('downloading built artifact from %s', aurl)
            urllib.urlretrieve(aurl, self.artifile)
        else:
            shutil.copy(aurl, os.getcwd())
        # decompress...
        with tarfile.open(self.artifile, "r:gz" if self.artifile.endswith(".tar.gz") else "r:") as tar:
            tar.extractall()

    # cleanup artifact file and directory
    def cleanup(self):
        try:
            os.remove(self.artifile)
            shutil.rmtree(self.artidir)
        except OSError:
            pass

    def envcfg(self, params):
        """Setup environment configuration specified in environment specific haconf.json or such file"""
        if (len(params) != 1):
            raise Exception(
                'non-single param array passed to envcfg. envcfg takes only 1 param')
        itemuri = self.tok_interp(params[0])
        logging.info('envcfg: %s', itemuri)
        # export from local/remote repo
        jsonfile = itemuri.rsplit('/', 1)[-1]
        self.repoexport(itemuri, jsonfile, True)
        with open(jsonfile) as jf:
            self.hacfg = json.load(jf)
        if not self.hacfg:
            logging.error('environment configuration load failed.')
        # backup dir path gen
        currtimestamp = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')
        self.bakdir = os.path.join(self.tok_interp(self.hacfg['nasRoot']), self.tok_interp(self.hacfg['relBackupRoot']), currtimestamp) if self.symtab.relativebackup else os.path.join(
            self.tok_interp(self.hacfg['absBackupRoot']), currtimestamp)
        logging.info(
            'generated backup directory path for this session: %s', self.bakdir)

    def parseServerLoc(self, nodesrv):
        """combines node list and server information into a map"""
        parts = nodesrv.split(':')
        nodesrvmap = {}
        if len(parts) == 1:
            nodesrvmap['nodelist'] = self.hacfg['haNodes']
            nodesrvmap['server'] = nodesrv
        else:
            nodesrvmap['server'] = parts[1]
            nodesrvmap['nodelist'] = []
            for node in self.hacfg['haNodes']:
                if node['name'] == parts[0]:
                    nodesrvmap['nodelist'].append(node)
                    break
        return nodesrvmap

    def pause(self, params):
        """pause execution with a prompt"""
        prompt = ''
        if len(params) == 0:
            prompt = 'continue? (y/n): '
        else:
            for param in params:
                prompt += self.tok_interp(param) + ' '
        choice = raw_input(prompt)
        logging.debug('user choice: %s', choice)
        if choice.startswith(('n', 'N')):
            logging.debug('user chose to stop program when prompted at pause')
            raise SystemExit

    def remove(self, params):
        """remove a war file or directory from a server"""
        if not self.hacfg:
            raise Exception(
                'environment configuration is absent. cannot proceed!')
        if len(params) < 3:
            raise Exception(
                'illegal syntax: atleast 3 params must be passed to remove command')
        self.readPreposition('from', params[0])
        nodesrvmap = self.parseServerLoc(self.tok_interp(params[1]))
        targetsrv = nodesrvmap['server']
        params = params[2:]
        for node in nodesrvmap['nodelist']:
            for p in params:
                item = self.tok_interp(p)
                apppath = os.path.join(
                    self.hacfg['nasRoot'], node['relPath'], self.hacfg['relHAPaths'][targetsrv], self.hacfg['relDeployDir'], item)
                logging.info('attempting to delete item: %s', apppath)
                if os.path.isdir(apppath):
                    shutil.rmtree(apppath)
                elif os.path.isfile(apppath):
                    os.remove(apppath)
                else:
                    logging.info(
                        'location %s is neither a directory nor a file! doing nothing', apppath)

    def removecfg(self, params):
        """remove configuration directory or file from a server"""
        if not self.hacfg:
            raise Exception(
                'environment configuration is absent. cannot proceed!')
        if len(params) < 3:
            raise Exception(
                'illegal syntax: atleast 3 params must be passed to remove command')
        self.readPreposition('from', params[0])
        nodesrvmap = self.parseServerLoc(self.tok_interp(params[1]))
        targetsrv = nodesrvmap['server']
        params = params[2:]
        for node in nodesrvmap['nodelist']:
            for p in params:
                item = self.tok_interp(p)
                apppath = os.path.join(
                    self.hacfg['nasRoot'], node['relPath'], self.hacfg['relHAPaths'][targetsrv], self.hacfg['relConfigDir'], item)
                logging.info('attempting to delete item: %s', apppath)
                if os.path.isdir(apppath):
                    shutil.rmtree(apppath)
                elif os.path.isfile(apppath):
                    os.remove(apppath)
                else:
                    logging.info(
                        'location %s is neither a directory nor a file! doing nothing', apppath)

    def backup(self, params):
        """back up a particular web app war file or directory of a server or all nodes"""
        if not self.hacfg:
            raise Exception(
                'environment configuration is absent. cannot proceed!')
        if len(params) < 3:
            raise Exception(
                'illegal syntax: atleast 3 params must be passed to backup command')
        self.readPreposition('from', params[0])
        nodesrvmap = self.parseServerLoc(self.tok_interp(params[1]))
        targetsrv = nodesrvmap['server']
        params = params[2:]
        for node in nodesrvmap['nodelist']:
            bakdirpath = os.path.join(
                self.bakdir, node['name'], targetsrv, self.hacfg['relDeployDir'])
            logging.info('creating bakdir with path: %s', bakdirpath)
            os.makedirs(bakdirpath)
            for p in params:
                item = self.tok_interp(p)
                apppath = os.path.join(
                    self.hacfg['nasRoot'], node['relPath'], self.hacfg['relHAPaths'][targetsrv], self.hacfg['relDeployDir'], item)
                if os.path.isdir(apppath):
                    archivename = shutil.make_archive(
                        os.path.join(bakdirpath, item), 'zip', apppath)
                    logging.info('created archive %s in %s',
                                 archivename, bakdirpath)
                elif os.path.isfile(apppath):
                    shutil.copy(apppath, bakdirpath)
                else:
                    logging.info(
                        'location %s is neither a directory nor a file! doing nothing', apppath)

    def backupcfg(self, params):
        """back up a particular configuration directory or file of an app in a server or all nodes"""
        if not self.hacfg:
            raise Exception(
                'environment configuration is absent. cannot proceed!')
        if len(params) < 3:
            raise Exception(
                'illegal syntax: atleast 3 params must be passed to backupcfg command')
        self.readPreposition('from', params[0])
        nodesrvmap = self.parseServerLoc(self.tok_interp(params[1]))
        targetsrv = nodesrvmap['server']
        params = params[2:]
        for node in nodesrvmap['nodelist']:
            bakdirpath = os.path.join(
                self.bakdir, node['name'], targetsrv, self.hacfg['relConfigDir'])
            logging.info('creating bakdir with path: %s', bakdirpath)
            os.makedirs(bakdirpath)
            for p in params:
                item = self.tok_interp(p)
                apppath = os.path.join(
                    self.hacfg['nasRoot'], node['relPath'], self.hacfg['relHAPaths'][targetsrv], self.hacfg['relConfigDir'], item)
                if os.path.isdir(apppath):
                    archivename = shutil.make_archive(
                        os.path.join(bakdirpath, item), 'zip', apppath)
                    logging.info('created archive %s in %s',
                                 archivename, bakdirpath)
                elif os.path.isfile(apppath):
                    shutil.copy(apppath, bakdirpath)
                else:
                    logging.info(
                        'location %s is neither a directory nor a file! doing nothing', apppath)

    def readPreposition(self, prepword, target):
        if prepword != target.lower():
            raise Exception(str.format(
                'syntax error: expected preposition: %s, supplied: %s', prepword, target))

    def rootdeploy(self, params):
        """deploy an app as the tomcat root application"""
        if not self.hacfg:
            raise Exception(
                'environment configuration is absent. cannot proceed!')
        if len(params) != 3:
            raise Exception(str.format(
                'illegal syntax: rootdeploy takes exactly 3 arguments, %d supplied', len(params)))
        self.readPreposition('to', params[0])
        nodesrvmap = self.parseServerLoc(self.tok_interp(params[1]))
        tcserver = nodesrvmap['server']
        warfile = params[2]
        srcwar = os.path.join(self.artidir, warfile)
        for node in nodesrvmap['nodelist']:
            tgdir = os.path.join(self.hacfg['nasRoot'], node['relPath'], self.hacfg['relHAPaths']
                                 [tcserver], self.hacfg['relDeployDir'], self.hacfg['rootAppDirName'])
            if not os.path.isdir(tgdir):
                logging.error(
                    '[CATASTROPHIC] directory %s does not exist! aborting.')
                raise Exception(str.format(
                    'directory %s does not exist!', tgdir))
            shutil.rmtree(tgdir)
            os.mkdir(tgdir)
            with zipfile.ZipFile(srcwar) as zf:
                zf.extractall(tgdir)

    def deploy(self, params):
        """deploy an app to a server or all nodes"""
        if not self.hacfg:
            raise Exception(
                'environment configuration is absent. cannot proceed!')
        if (len(params) < 3):
            raise Exception(
                'illegal syntax: atleast 3 params must be passed to deploy command')
        self.readPreposition('to', params[0])
        nodesrvmap = self.parseServerLoc(self.tok_interp(params[1]))
        tcserver = nodesrvmap['server']
        params = params[2:]
        # remaining params are war file names
        for p in params:
            item = self.tok_interp(p)
            logging.info('deploy: %s', item)
            srcfile = os.path.join(self.artidir, item)
            if os.path.isfile(srcfile):
                for haNode in nodesrvmap['nodelist']:
                    tgdir = os.path.join(self.hacfg['nasRoot'], haNode['relPath'],
                                         self.hacfg['relHAPaths'][tcserver], self.hacfg['relDeployDir'])
                    logging.info('server: %s, path: %s', tcserver, tgdir)
                    shutil.copy(srcfile, tgdir)
            else:
                logging.error(
                    'item %s was not found in built artifacts archive. cannot deploy, skipping.', item)

    def p(self, params):
        """print something"""
        for p in params:
            item = self.tok_interp(p)
            print item

    def word(self, params):
        """create a variable (word) that will become available in the symbol table"""
        if len(params) != 2:
            raise Exception(
                'illegal syntax: exactly 2 params must be passed to word command')
        wordname = params[0]
        wordval = self.tok_interp(params[1])
        setattr(self.symtab, wordname, wordval)

    def help(self, params):
        """help function"""
        print 'available commands:'
        for k, v in self.dispatcher.iteritems():
            print '[' + k + '] : ' + v.__doc__

    def resolvecfghome(self, cfgmap, appname):
        return cfgmap[appname] if appname in cfgmap else self.hacfg['defaultCfgDir']

    def pullcfgitem(self, params):
        """pull a configuration directory or file from svn or local to a server or all nodes"""
        if not self.hacfg:
            raise Exception(
                'environment configuration is absent. cannot proceed!')
        if len(params) != 5:
            raise Exception(
                'illegal syntax: exactly 3 params must be passed to pullcfgfile command')
        cfgitem = self.tok_interp(params[0])
        self.readPreposition('from', params[1])
        appname = self.tok_interp(params[2])
        self.readPreposition('into', params[3])
        nodesrvmap = self.parseServerLoc(self.tok_interp(params[4]))
        tcserver = nodesrvmap['server']
        cfgitempath = os.path.join(self.hacfg['ssoappsHome'], appname, self.resolvecfghome(
            self.hacfg['appCfgDirs'], appname), cfgitem)
        logging.info('cfgitempath: %s', cfgitempath)
        self.repoexport(cfgitempath, cfgitem.rsplit('/', 1)[-1])
        for node in nodesrvmap['nodelist']:
            tgdir = os.path.join(self.hacfg['nasRoot'], node['relPath'],
                                 self.hacfg['relHAPaths'][tcserver], self.hacfg['relConfigDir'])
            logging.debug('cfgitem: %s', cfgitem)
            cfgitemdir, cfgitemname = cfgitem.rsplit('/', 1) if "/" in cfgitem else (cfgitem, '')
            logging.debug('cfgitemdir: %s', cfgitemdir)
            logging.debug('cfgitemname: %s', cfgitemname)
            tgpath = os.path.join(tgdir, cfgitemdir)
            logging.info('tgpath: %s', tgpath)
            if os.path.isfile(tgpath):
                os.remove(tgpath)
            if not os.path.isdir(tgpath):
                os.makedirs(tgpath)
            if cfgitemname == '':
                shutil.rmtree(tgpath)
                copy_tree(cfgitemdir, tgpath)
            elif os.path.isfile(cfgitemname):
                shutil.copy(cfgitemname, tgpath)
            elif os.path.isdir(cfgitemname):
                dstpath = os.path.join(tgpath, cfgitemname)
                if os.path.isdir(dstpath):
                    shutil.rmtree(dstpath)
                copy_tree(cfgitemname, dstpath)
            else:
                logging.error(
                    '%s is neither file nor directory! doing nothing.', cfgitempath)

    # the dispatcher
    dispatcher = {'backup': backup, 'backupcfg': backupcfg, 'deploy': deploy, 'rootdeploy': rootdeploy, 'envcfg': envcfg,
                  'p': p, 'pullcfgitem': pullcfgitem, 'remove': remove, 'removecfg': removecfg, 'help': help, 'word': word, 'pause': pause}

    # minimal token interpolation
    def tok_interp(self, tok):
        """fsm for interpolation of tokens"""
        ptok = ''
        xvar = ''
        # states
        outside_expr = 1
        dollar_encountered = 2
        inside_expr = 3
        # 3 state fsm used here, no expression nesting allowed
        curr_state = outside_expr
        for c in tok:
            if (curr_state == outside_expr and c == '$'):
                curr_state = dollar_encountered
            elif (curr_state == outside_expr and c != '$'):
                ptok += c
            elif (curr_state == dollar_encountered and c == '{'):
                curr_state = inside_expr
            elif (curr_state == dollar_encountered and c == '$'):
                ptok += c
            elif (curr_state == dollar_encountered and c not in "${"):
                ptok += '$' + c
                curr_state = outside_expr
            elif (curr_state == inside_expr and c == '}'):
                if (not hasattr(self.symtab, xvar)):
                    raise Exception('symbol table has no variable: ' + xvar)
                ptok += str(getattr(self.symtab, xvar))
                xvar = ''
                curr_state = outside_expr
            elif (curr_state == inside_expr and c != '}'):
                xvar += c
        # syntax error catch
        if (curr_state == dollar_encountered or curr_state == inside_expr):
            raise Exception(
                'token interpolation reached illegal state at end: ' + curr_state)
        # return evaluated expression
        return ptok

    def exec_cmd(self, command, params):
        """execute command supported by dslrepl"""
        cmd = self.tok_interp(command.lower())
        if (cmd in ['exit', 'quit', 'bye', 'die', 'tata', 'ciao', 'astalavista']):
            if (self.symtab.i):
                goodbye()
            sys.exit(0)
        else:
            if cmd in self.dispatcher:
                self.dispatcher[cmd](self, params)
            else:
                logging.error('command %s not found in dispatcher', cmd)

    # the actual interpreter with arguments array
    def process_line(self, line):
        """process a line"""
        sline = line.strip()
        # skip empty strings
        if sline == '' or sline.startswith('#'):
            return ''
        logging.debug('processing line [%s]', sline)
        tokens = sline.split()
        logging.debug('number of tokens [%d]', len(tokens))
        # execution
        self.exec_cmd(tokens[0], tokens[1:])

    def process_plan_file(self):
        """process a plan file"""
        fname = self.symtab.planfile
        logging.debug('processing file: %s', fname)
        with open(fname) as f:
            for line in f:
                self.process_line(line)

    def dply_repl(self):
        """the deployer repl"""
        line = ''
        while (True):
            line = raw_input('drepl-> ')
            self.process_line(line)

# ------------------------------------------------- #
#  function space
# ------------------------------------------------- #


def greeting():
    print '''
  ------------------------------------------------
        __   __   __   __   ___  __        __
   /\  |__) |__) /__` |  \ |__  |__) |    /  \ \ /
  /~~\ |    |    .__/ |__/ |___ |    |___ \__/  |

  ------------------------------------------------
  '''


def goodbye():
    print '''
  --------------------------------------
   __   __   __   __   __       ___   /
  / _` /  \ /  \ |  \ |__) \ / |__   /
  \__> \__/ \__/ |__/ |__)  |  |___ .

  --------------------------------------
  '''


def digest_args():
    """argument parser"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-u', '--jenkurl', help='jenkins url for the artifact (mandatory)', required=True)
    parser.add_argument(
        '-b', '--branch', help='svn branch number (mandatory)', required=True)
    parser.add_argument(
        '-e', '--env', help='execution environment (mandatory)', required=True)
    parser.add_argument(
        '--i', help='start interactive repl', action='store_true')
    parser.add_argument('-l', '--loglevel',
                        help='logging level', required=True)
    parser.add_argument(
        '-s', '--svnurl', help='svn url for repository', required=True)
    parser.add_argument('-r', '--relativebackup',
                        help='use relative path for backing up files', action='store_true')
    parser.add_argument('-j', '--jiraticket',
                        help='jira ticket number for deployment', required=True)
    parser.add_argument('planfile', nargs='?',
                        help='.plan file that is the deployment program')
    return parser.parse_args()


def init_logging(args):
    """initialize logging for the program"""
    logformat = '[%(levelname)s] {%(asctime)s} -> %(message)s'
    loglevel = getattr(logging, args.loglevel)
    logging.basicConfig(level=loglevel, filename='appsdeploy.' +
                        datetime.datetime.today().strftime('%Y%m%d_%H%M%S') + '.log', filemode='w', format=logformat)
    # adding console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(loglevel)
    ch.setFormatter(logging.Formatter(logformat))
    logging.getLogger().addHandler(ch)

# ------------------------------------------------- #
#  flow begins
# ------------------------------------------------- #


args = digest_args()
init_logging(args)

if (args.i):
    greeting()
    logging.info('starting deploy repl...')
    repl = DSLRepl(args)
    repl.dply_repl()
elif (args.planfile):
    logging.info('executing plan file: %s', args.planfile)
    repl = DSLRepl(args)
    repl.process_plan_file()
else:
    logging.info(
        'nothing to do! this program does not accept piped input through stdin as of now. exiting!')
