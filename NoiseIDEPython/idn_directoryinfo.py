from idn_events import Event

__author__ = 'Yaroslav Nikityshev aka IDNoise'

import os
from stat import ST_MTIME
from idn_utils import Timer, extension
import core
import wx

class DirectoryDataConfig:
    def __init__(self, root = None, recursive = None, fileMask = None, excludeDirs = None, excludePaths = None):
        self.recursive = recursive
        self.root = root
        self.fileMask = fileMask
        self.excludeDirs = excludeDirs
        self.excludePaths = excludePaths

    def CheckPath(self, path):
        if self.excludePaths and path in self.excludePaths:
            return False
        if os.path.isfile(path) and self.fileMask and extension(path) not in self.fileMask:
            return False
        if os.path.isdir(path) and self.excludeDirs and os.path.basename(path) in self.excludeDirs:
            return False
        return True

class DirectoryData:
    def __init__(self, path, config):
        self.path = path
        self.modTime = self.GetModifiedTime(self.path)
        self.config = config
        self.filesModData = {}
        self.dirsModData = {}
        self.files = []
        self.dirs = {}

    def AllFiles(self):
        return self.files + [d.AllFiles() for d in self.dirs]

    def AllDirs(self):
        return self.dirs.keys() + [d.dirs.keys() for d in self.dirs]

    def Gather(self):
       # print "gather " + self.path, "old mod: ", self.modTime, "new: ", self.GetModifiedTime(self.path)
        filesDirs = [os.path.normpath(os.path.join(self.path, f)) for f in os.listdir(self.path)]

        files = set([f for f in filesDirs if os.path.isfile(f) and self.config.CheckPath(f)])
        dirs = set([d for d in filesDirs if os.path.isdir(d) and self.config.CheckPath(d)])

        prevFiles = set(self.files)
        prevDirs = set(self.dirs)



        newFiles = list(files.difference(prevFiles))
        deletedFiles = list(prevFiles.difference(files))

        newDirs = list(dirs.difference(prevDirs))
        deletedDirs = list(prevDirs.difference(dirs))

        modifiedFiles = [f for f in files.intersection(prevFiles) if os.stat(f)[ST_MTIME] != self.filesModData[f]]
        #modifiedDirs = [f for f in files.intersection(prevDirs) if os.stat(f)[ST_MTIME] != self.dirsModData[f]]

        for f in files:
            self.filesModData[f] = os.stat(f)[ST_MTIME]
        for d in dirs:
            self.dirsModData[d] = os.stat(d)[ST_MTIME]


        for f in deletedFiles:
            self.files.remove(f)
            del self.filesModData[f]

        self.files = files

        for d in deletedDirs:
            deletedFiles += self.dirs[d].AllFiles()
        allDeletedDirs = deletedDirs[:]
        for d in deletedDirs:
            allDeletedDirs += self.dirs[d].AllDirs()

        for d in deletedDirs:
            del self.dirs[d]
            del self.dirsModData[d]
        #print "new dirs: ", newDirs
        for d in newDirs[:]:
            newData = DirectoryData(d, self.config)
            self.dirs[d] = newData
        for d in dirs:
            (nf, mf, df, nd, dd) = self.dirs[d].Gather()
            newFiles += nf
            newDirs += nd
            modifiedFiles += mf
            deletedFiles += df
            deletedDirs += dd
       # print "+++ gather " + self.path + " result: "
        #print (newFiles, modifiedFiles, deletedFiles, newDirs, allDeletedDirs)
        #print "=========="

        return (newFiles, modifiedFiles, deletedFiles, newDirs, allDeletedDirs)

    def GetModifiedTime(self, path):
        try:
            return os.stat(path)[ST_MTIME]
        except Exception, e:
            core.Log("Gather mtime info error: ", path, e)
            return 0

class DirectoryChecker:

    def __init__(self, interval, root, recursive = True, fileMask = [], excludeDirs = [], excludePaths = []):
        self.config = DirectoryDataConfig(root, recursive, fileMask, excludeDirs, excludePaths)
        self.data = DirectoryData(root, self.config)

        self.timer = Timer(interval, self.CheckDirectoryChanges)

        self.FilesCreatedEvent = Event()
        self.FilesModifiedEvent = Event()
        self.FilesDeletedEvent = Event()

        self.DirsCreatedEvent = Event()
        self.DirsDeletedEvent = Event()

    def SetInterval(self, interval):
        self.Stop()
        self.timer = Timer(interval, self.CheckDirectoryChanges)
        self.Start()

    def SetRoot(self, root):
        self.Stop()
        self.root = root
        self.Start()

    def SetFileMask(self, fileMask):
        self.Stop()
        self.fileMask = fileMask
        self.Start()

    def SetExcludePaths(self, excludePaths):
        self.Stop()
        self.excludePaths = excludePaths
        self.Start()

    def SetExcludePaths(self, excludeDirs):
        self.Stop()
        self.excludeDirs = excludeDirs
        self.Start()

    def Start(self):
        self.data.Gather()
        self.timer.Start()

    def Stop(self):
        self.timer.Stop()

    def CheckDirectoryChanges(self):
        (nf, mf, df, nd, dd) = self.data.Gather()
        print (nf, mf, df, nd, dd)
        if nd: wx.CallAfter(self.DirsCreatedEvent, nd)
        if dd: wx.CallAfter(self.DirsDeletedEvent, dd)
        if nf: wx.CallAfter(self.FilesCreatedEvent, nf)
        if mf: wx.CallAfter(self.FilesModifiedEvent, mf)
        if df: wx.CallAfter(self.FilesDeletedEvent, df)


