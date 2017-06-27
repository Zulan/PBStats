#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Installation/Setup:
#   Edit the following variables directly in this script or put
#   them into a new file called 'startPitbossEnv.py'.
# 1. CIV4BTS_PATH : Your Civ4:BTS installation directory
#    i.e "$HOME/Civ4/Beyond the Sword"
# 2. ALTROOT_BASEDIR: As default the absolute path on this folder. 
#    Edit this if you place your games at an other position, i.e.
#    $HOME/PBs.
# 3. GAMES: Hold list of games. Expand it, if you host multiple games.
#    Every entry maps to a subfolder of ALTROOT_BASEDIR.
#
# Notes:
# • Attention, backup/move your "My Games"-Folder before
#   you start the Pitboss Server with an empty ALTROOT-Folder.
#   Due a bug in the Pitboss executable your current
#   "BTS-My Games-Folder" will be moved, not copied, to the new position!
#
# • Configure the Pitboss servers over the file 'pbSettings.json' in the
#   ALTROOT-Directory of each game.
#
# • This script assumes that the wine drive 'Z:'
#   is mapped to '/' (default wine setting).
#

import sys
import os.path
import re
import glob
import json
import struct
import fileinput
import time

# Begin of configuration

# Path to Civ4:BTS folder (without executable name)
CIV4BTS_PATH = "$HOME/Civ4/Beyond the Sword"

# Folder which will be used as container for all ALTROOT directories.
# It should contains the configuration seed folder (seed)
# Set this to the subfolder '[...]/PBStats/PBs' !
# ALTROOT_BASEDIR = "$HOME/PBStats/PBs"
ALTROOT_BASEDIR = os.path.abspath(".")

# Default mod name. Can be overwritten in GAMES-dict.
# Moreover, the mod name will be changed automatically
# if the save to load contains an other mod name.
MOD = "PB Mod_v7"

# Timeout to wait a few seconds before the pitboss server restarts.
RESTART_TIMEOUT = 3

# Start command templates
START_WINDOWS = '"{CIV4BTS_EXE}" mod= "{MOD}"\" /ALTROOT={ALTROOT}'
START_LINUX = 'wine "{CIV4BTS_EXE}" mod= "{MOD}"\" /ALTROOT="{ALTROOT_W}"'

# Variant with cleaned output
UNBUFFER = False
START_LINUX_UNBUFFER = r'unbuffer wine "{CIV4BTS_EXE}" mod= "{MOD}"\"\
/ALTROOT="{ALTROOT_W} | grep -v "^FTranslator::AddText\|^fixme:"'

# (Linux only)Path for xvfb-run framebuffer.
# Screenshot available via 'xwud --id $XVFB_DIR'
XVFB = False
XVFB_DIR = "/run/shm/{GAMEID}"
XVFB_MCOOKIE = "/tmp/{GAMEID}"
XVFB_CMD = 'xvfb-run -a -e /dev/shm/xvfb.err --auth-file={COOKIE} '\
    '-s "-fbdir {DIR} -screen 0 640x480x24"'\
    'wine "{CIV4BTS_EXE}" mod= "{MOD}"\" /ALTROOT="{ALTROOT_WIN}" &'
XVFB_PRE_CMD = '$(sleep 3; xauth merge {COOKIE}) &'  #; fg'

# Seed directory
# ALTROOT_SEED = os.path.join(ALTROOT_BASEDIR, "seed")

INI = "CivilizationIV.ini"
INI_OPT = "PitbossSMTPLogin"

# End of configuration

# Put your overrides of aboves values into following file
if os.path.exists("startPitbossEnv.py"):
    print("Load local environment")
    sys.path.append(".")
    execfile(os.path.join('startPitbossEnv.py'))

####################
# List of games. Insert the names of your games here or define
# an own dict in startPitbossEnv.py
if "GAMES" not in globals():
    GAMES = {
        "1": {"name": "Pitboss 1", "mod": MOD,
              "altroot": os.path.join(ALTROOT_BASEDIR, "PB1")},
        "2": {"name": "Pitboss 2", "mod": MOD,
              "altroot": os.path.join(ALTROOT_BASEDIR, "PB2")},
    }
###################


def init():
    # Expand environment variables
    globals()["ALTROOT_BASEDIR"] = os.path.expandvars(ALTROOT_BASEDIR).strip()
    globals()["CIV4BTS_PATH"] = os.path.expandvars(CIV4BTS_PATH).strip()
    globals()["MOD"] = os.path.expandvars(MOD).strip()
    # globals()["ALTROOT_SEED"] = os.path.expandvars(ALTROOT_SEED).strip()
    if XVFB:
        globals()["XVFB_DIR"] = os.path.expandvars(XVFB_DIR).strip()

    for g in GAMES:
        game = GAMES[g]
        for k in game:
            game[k] = os.path.expandvars(game[k]).strip()


def checkIniFile(gameid):
    """ The PitbossSMTPLogin variable had to contain the altroot path."""
    altroot = GAMES[gameid]["altroot"]
    altroot_w = getAltrootWin(altroot)
    altroot_ini = ""
    iniFn = os.path.join(altroot, INI)
    opt = INI_OPT+"="
    if os.path.isfile(iniFn):
        fp = file(iniFn, "r")
        ini = fp.readlines()
        fp.close()
    else:
        # print("%s not found." % (iniFn[iniFn.rfind(os.path.sep)+1:]))
        print("%s not found." % (iniFn))
        return None

    for line in ini:
        if line.startswith(opt):
            altroot_ini = line[line.find("=")+1:].strip()

    return altroot_ini == altroot_w


def fixIniFile(gameid):
    """ Set PitbossSMTPLogin variable on altroot path."""

    if checkIniFile(gameid):
        # Nothing to do
        return True

    altroot = GAMES[gameid]["altroot"]
    altroot_w = getAltrootWin(altroot)
    iniFn = os.path.join(altroot, INI)
    opt = INI_OPT+"="
    if os.path.isfile(iniFn):
        for line in fileinput.input(iniFn, inplace=True):
            if line.startswith(opt):
                print("%s%s" % (opt, altroot_w))
            else:
                print(line)
    else:
        print("%s not found." % (iniFn[iniFn.rfind(os.path.sep)+1:]))
        return False

    return True


def loadSettings(gameid):
    altroot = GAMES[gameid]["altroot"]
    pbFn = os.path.join(altroot, "pbSettings.json")
    if os.path.isfile(pbFn):
        fp = file(pbFn, "r")
        pbSettings = json.load(fp)
        fp.close()
    else:
        return None

    return pbSettings


def saveSettings(gameid, pbSettings):
    altroot = GAMES[gameid]["altroot"]
    pbFn = os.path.join(altroot, "pbSettings.json")
    try:
        fp = file(pbFn, "w")
        # Note that it's necessary to use the old syntax (integer value) for indent
        # argument!
        json.dump(pbSettings, fp, indent=1)
    except Exception:
        print("Write of json file fails!")


def printSelectionMenu():
    print("""\
==== Select Game/Altroot ====
ID - Description
          """)
    for g in GAMES:
        print("  %10.10s - %s" % (g, GAMES[g]["name"]))

    print("  %10.10s - %s" % ("list [game id] [save pattern]",
                              "Print out names of 20 youngest saves."))
    print("  %10.10s - %s" % ("help",
                              "Print help and exit"))


def printHelp():
    print("""Syntax: python {0} gameid [savegame] [password]

 gameid: Selects the game. Edit the GAMES-variable to define more games.
         Use the 'seed' director as template and define a different
         'altroot' directory for each game.
 savegame: If the server automatically load a save, it takes the filename
          defined in pbSettings.json.
          Use this argument to override the filename. It's not required
          to write out the full filename. The script selects the youngest file
          which match the (regular) expression.
          This is useful to load the latest save of a player.
 password: Overrides the stored password. Be careful, a wrong password traps
          the PB server in an infinite loop. The server had to be killed
          manually...
          """.format(sys.argv[0]))


def findSaves(gameid, pbSettings, reg_pattern=None, pattern="*"):
    """ Return list of tuples (path, creation_date) of given pattern. """
    print("Youngest saves for {0}:".format(reg_pattern))
    altroot = GAMES[gameid]["altroot"]

    subfolders = [pbSettings.get(
        "writefolder", os.path.join("Saves", "multi"))]
    subfolders.extend(pbSettings.get("readfolders", []))
    if not pattern.lower().endswith(".civbeyondswordsave"):
        pattern += ".CivBeyondSwordSave"

    saves = []
    for x in subfolders:
        ss1 = os.path.join(altroot, x, pattern)
        saves.extend(glob.glob(ss1))
        ss2 = os.path.join(CIV4BTS_PATH, x, pattern)
        saves.extend(glob.glob(ss2))
        # print("%s, %s" % (ss1, ss2))

    if reg_pattern:
        reg = re.compile(reg_pattern)
        saves = [x for x in saves if reg.search(x)]

    savesWithTimestamps = map(lambda x: (x, os.path.getctime(x)), saves)
    # Sort by timestamp
    savesWithTimestamps.sort(key=lambda xx: xx[1])
    # Remove oldest
    while len(savesWithTimestamps) >= 20:
        savesWithTimestamps.pop(0)

    savesWithTimestamps.reverse()
    return savesWithTimestamps


def isAutostartEnabled(pbSettings):
    # Return 1 if autostart is 'true' or '1'
    autostart = bool(pbSettings.get("autostart", False))
    noGui = bool(pbSettings.get("noGui", False))
    shell = bool(pbSettings.get("shell", {}).get("enable"))
    if not autostart and (noGui and not shell):
        print("Warning: Autostart flag is disabled, but noGui and shell "
              "flag overrides the setting.")
        autostart = True

    return autostart


def getAutostartSave(pbSettings):
    # Read current save name from pbSettings.json
    return pbSettings.get("save", {}).get("filename", None)


def replaceSave(gameid, pbSettings, save, adminpw=None):
    # Replace filename and optionally the password in pbSettings.json
    pbSettings.setdefault("save", {})["filename"] = save
    if adminpw:
        pbSettings["save"]["adminpw"] = adminpw

    saveSettings(gameid, pbSettings)


def listSaves(gameid, reg_pattern=None):
    """ Print newest saves. """
    pbSettings = loadSettings(gameid)
    lSaves = findSaves(gameid, pbSettings, reg_pattern)
    i = 0
    for tS in lSaves:
        i += 1
        ts = time.ctime(tS[1])
        name = tS[0]
        print("%2i %23.23s %s" % (i, ts, name))


def parseModName(filename):
    """ Return mod name for savegame. (Derived from FindHash.py) """

    def get_int(f):
        sx = f.read(4)
        ix = struct.unpack('<' + 'B'*len(sx), sx)
        ret = ix[0] + (ix[1] << 8) + (ix[2] << 16) + (ix[3] << 24)
        return ret

    f = open(filename, "rb")
    try:
        _ = f.read(4)
        mod_nameLen = get_int(f)
        mod_name = str(f.read(mod_nameLen))
        return mod_name

    finally:
        f.close()

    return ""


def getAltrootWin(altroot):
    """ Convert path with slashes into usable form as wine argument. """
    if os.path.sep == "/":
        return "Z:%s" % (altroot.replace("/", "\\\\"))
    else:
        return altroot


def setupGame(gameid, save_pat=None, password=None):
    """ Check input and starts the game.

    If save_pat is given, the script search the youngest file with the
    regular pattern 'save_pat'.  The case will be ignored.

    If password is given, the saved one will be replaced.
    Nevertheless, the startup stops if neither the new password or
    one of the passwords in pbPasswords.json not matches with
    the save password. (TODO)
    """
    print("\n==== Start %s ====\n" % GAMES[gameid]["name"])

    pbSettings = loadSettings(gameid)
    if save_pat:
        lSaves = findSaves(gameid, pbSettings, save_pat)
        if len(lSaves) > 0:
            newest_save = lSaves[0][0]  # [0][1] is timestamp
            replaceSave(gameid, pbSettings, newest_save, password)
    else:
        save_pat = pbSettings.get("save", {}).get("filename", "")
        lSaves = findSaves(gameid, pbSettings, save_pat)

    autostart = isAutostartEnabled(pbSettings)
    if autostart:
        print("Autostart {0}".format(
            (pbSettings.get("save", {}).get("filename", "?"))))

    if autostart and len(lSaves) == 0:
        print("No save found for pattern '%s'." % (save_pat))
        return -1

    if autostart:
        mod_name = parseModName(lSaves[0][0])
    else:
        mod_name = GAMES[gameid]["mod"]

    print "Mod name: %s" % (mod_name)

    # Check if patched executable is available
    if os.path.exists(os.path.join(CIV4BTS_PATH,
                                   "Civ4BeyondSword_PitBoss2014.exe")):
        civ4bts_exe = os.path.join(CIV4BTS_PATH,
                                   "Civ4BeyondSword_PitBoss2014.exe")
    else:
        civ4bts_exe = os.path.join(CIV4BTS_PATH,
                                   "Civ4BeyondSword_PitBoss.exe")

    altroot = GAMES[gameid]["altroot"]
    altroot_w = getAltrootWin(altroot)

    if not os.path.exists(civ4bts_exe):
        print("Executeable not found. Is the path correctly?\n'%s'\n" %
              (civ4bts_exe))
        return

    if not os.path.exists(altroot):
        print("Altroot directory found. Is the path correctly?\n'%s'\n"\
              "Copy 'seed' if you want create a new game." % (altroot))
        return

    if XVFB:
        xvfb_dir = XVFB_DIR.format(GAMEID=gameid)
        xvfb_mcookie = XVFB_MCOOKIE.format(GAMEID=gameid)
        xvfb_cmd = XVFB_CMD.format(COOKIE=xvfb_mcookie,
                                   DIR=xvfb_dir, MOD=mod_name,
                                   CIV4BTS_EXE=civ4bts_exe,
                                   ALTROOT_WIN=altroot_w)
        xvfb_pre_cmd = XVFB_PRE_CMD.format(COOKIE=xvfb_mcookie)
        if not os.path.exists(xvfb_dir):
            print("Create directory for XV framebuffer.")
            from os import mkdir
            mkdir(xvfb_dir)

    # Generate start command pipe
    pre_start_cmd = None
    if os.path.sep == "\\":  # Windows
        start_cmd = START_WINDOWS.format(
            CIV4BTS_EXE=civ4bts_exe,
            MOD=mod_name,
            ALTROOT=altroot)
    else:
        if XVFB:
            pre_start_cmd = xvfb_pre_cmd
            start_cmd = xvfb_cmd
        elif UNBUFFER:
            start_cmd = START_LINUX_UNBUFFER.format(
                CIV4BTS_EXE=civ4bts_exe,
                MOD=mod_name,
                ALTROOT_W=altroot_w)
        else:
            start_cmd = START_LINUX.format(
                CIV4BTS_EXE=civ4bts_exe,
                MOD=mod_name,
                ALTROOT_W=altroot_w)

    print("Start Command:\n%s" % (start_cmd,))

    # Start infinite loop for the selected game
    os.chdir(CIV4BTS_PATH)

    try:
        while True:
            if pre_start_cmd:
                os.system(pre_start_cmd)

            os.system(start_cmd)

            sys.stdout.write("\nRestart server in %i seconds." % RESTART_TIMEOUT)
            sys.stdout.flush()
            for _ in range(RESTART_TIMEOUT):
                time.sleep(1)
                sys.stdout.write(".")
                sys.stdout.flush()

            sys.stdout.write("\n")
            break
    except KeyboardInterrupt:
        print("\nQuit script")

if __name__ == "__main__":
    args = list(sys.argv[1:])

    init()
    if len(args) == 0:
        printSelectionMenu()
        args.extend(raw_input().split(" "))

    # Add dummies for optional arguments
    args.append(None)
    args.append(None)
    args = args[0:3]

    if args[0] == "help":
        printHelp()
    elif args[0] == "list":
        listSaves(args[1], args[2])
    else:
        if not fixIniFile(args[0]):
            print("Error: The option '%s' in '%s' contain not the altroot path "
                  "and the automated fix failed." % (INI_OPT, INI))
        else:
            setupGame(*args)