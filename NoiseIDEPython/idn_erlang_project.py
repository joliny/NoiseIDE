__author__ = 'Yaroslav'

import os
import operator
import wx
from idn_cache import ErlangCache
from idn_colorschema import ColorSchema
from idn_config import Config
from idn_connect import CompileErrorInfo
from idn_console import ErlangIDEConsole, ErlangProjectConsole
from idn_erlang_constats import *
from idn_erlang_dialogs import ErlangDialyzerDialog
from idn_erlang_explorer import ErlangProjectExplorer
from idn_erlang_project_form import ErlangProjectFrom
from idn_erlangstc import ErlangHighlightedSTCBase, ErlangSTCReadOnly
from idn_errors_table import ErrorsTableGrid, XrefTableGrid, DialyzerTableGrid
import core
from idn_notebook import ErlangCompileOptionPanel
from idn_project import Project
from idn_utils import readFile, writeFile, pystr, Menu, GetImage
from idn_erlang_utils import IsBeam, IsInclude, IsYrl, IsModule

class ErlangProject(Project):
    IDE_MODULES_DIR = os.path.join(os.getcwd(), 'data', 'erlang', 'modules', 'noiseide', 'ebin')
    EXPLORER_TYPE = ErlangProjectExplorer

    def OnLoadProject(self):
        self.window.CheckRuntimes()

        if not self.GetErlangRuntime() or self.GetErlangRuntime() not in Config.Runtimes():
            self.userData[CONFIG_ERLANG_RUNTIME] = Config.Runtimes().keys()[0]
            self.SaveData()

        self.errors = {}
        self.consoleTabs = {}

        self.errorCount = 0
        self.warningCount = 0

        ErlangCache.Init(self)

        self.SetupDirs()
        self.AddTabs()
        self.AddConsoles()
        self.SetupProps()

        self.explorer.ProjectFilesCreatedEvent += self.OnProjectFilesCreated
        self.explorer.ProjectFilesModifiedEvent += self.OnProjectFilesModified
        self.explorer.ProjectFilesDeletedEvent += self.OnProjectFilesDeleted
        self.explorer.ProjectDirsCreatedEvent += self.OnProjectDirsCreated

    def SetupProps(self):
        if self.PltPath():
            self.GetShell().SetProp("plt", self.PltPath())
        if self.HomeDir():
            self.GetShell().SetHomeDir(self.HomeDir())

    def ErlangCacheChecked(self):
        ErlangCache.LoadCacheFromDir(os.path.join("runtimes", self.GetErlangRuntime()))

    def SetupMenu(self):
        Project.SetupMenu(self)

        self.window.projectMenu.AppendSeparator()
        self.window.projectMenu.AppendMenuItem("Rebuild project", self.window, lambda e: self.CompileProject())
        self.window.projectMenu.AppendMenuItem("XRef check", self.window, lambda e: self.StartXRef())

        self.dialyzerMenu = Menu()
        self.dialyzerMenu.AppendMenuItem("Edit Options", self.window, self.OnEditDialyzerOptions)
        self.dialyzerMenu.AppendSeparator()
        self.dialyzerMenu.AppendMenuItem("Project", self.window, lambda e: self.DialyzeProject())
        self.dialyzerMenu.AppendMenuItem("Current module", self.window, self.OnDialyzerRunModule)
        self.window.projectMenu.AppendMenu(wx.ID_ANY, "Dialyzer", self.dialyzerMenu)

        self.window.erlangMenu.AppendMenuItem("Regenerate erlang cache", self.window, lambda e: self.RegenerateErlangCache())
        self.window.erlangMenu.AppendSeparator()
        self.window.erlangMenu.AppendCheckMenuItem("Fly Compilation", self.window, self.OnCheckErlangFlyCompilation, Config.GetProp("erlang_fly_compilation", True))
        self.window.erlangMenu.AppendCheckMenuItem("Highlight whole line on error", self.window, self.OnCheckErlangHighlightErrorBackground, Config.GetProp("highlight_error_background", False))

        self.window.viewMenu.AppendMenuItem("Errors/Warnings", self.window, lambda e: self.ShowErrorsTable())
        self.window.viewMenu.AppendMenuItem("IDE Console", self.window, lambda e: self.ShowIDEConsole())
        self.window.viewMenu.AppendMenuItem("XRef Result", self.window, lambda e: self.ShowXrefTable())

        self.consoleMenu = Menu()

        self.window.viewMenu.AppendMenu(wx.ID_ANY, "Consoles", self.consoleMenu)

        self.window.toolbar.AddSeparator()
        self.rebuildT = self.window.toolbar.AddLabelTool(wx.ID_ANY, 'Rebuild project', GetImage('build.png'), shortHelp = 'Rebuild project')
        self.xrefCheckT = self.window.toolbar.AddLabelTool(wx.ID_ANY, 'XRef check', GetImage('xrefCheck.png'), shortHelp = 'XRef check')

        self.window.Bind(wx.EVT_TOOL, lambda e: self.CompileProject(), self.rebuildT)
        self.window.Bind(wx.EVT_TOOL, lambda e: self.StartXRef(), self.xrefCheckT)

        self.window.toolbar.Realize()

    def OnCheckErlangFlyCompilation(self, event):
        currentValue = Config.GetProp("erlang_fly_compilation")
        Config.SetProp("erlang_fly_compilation", not currentValue)

    def OnCheckErlangHighlightErrorBackground(self, event):
        currentValue = Config.GetProp("highlight_error_background")
        Config.SetProp("highlight_error_background", not currentValue)

    def ShowIDEConsole(self):
        if self.window.ToolMgr.FindPageIndexByWindow(self.shellConsole) == None:
            self.window.ToolMgr.AddPage(self.shellConsole, "IDE Console")
        self.window.ToolMgr.FocusOnWidget(self.shellConsole)

    def ShowConsole(self, title, consoleWidget):
        if self.window.ToolMgr.FindPageIndexByWindow(consoleWidget) == None:
            self.window.ToolMgr.AddPage(consoleWidget, "Console <{}>".format(title))
        self.window.ToolMgr.FocusOnWidget(consoleWidget)

    def ShowErrorsTable(self):
        if self.window.ToolMgr.FindPageIndexByWindow(self.errorsTable) == None:
            self.window.ToolMgr.AddPage(self.errorsTable, '')
        index = self.window.ToolMgr.FindPageIndexByWindow(self.errorsTable)
        self.window.ToolMgr.SetPageText(index, "Errors: {}, Warnings: {}".format(self.errorCount, self.warningCount))
        self.window.ToolMgr.FocusOnWidget(self.errorsTable)

    def ShowXrefTable(self):
        if self.window.ToolMgr.FindPageIndexByWindow(self.xrefTable) == None:
            self.window.ToolMgr.AddPage(self.xrefTable, 'XRef result')
        self.window.ToolMgr.FocusOnWidget(self.xrefTable)

    def OnEditProject(self, event):
        ErlangProjectFrom(self).ShowModal()

    def OnEditDialyzerOptions(self, event):
        ErlangDialyzerDialog(self.window, self).ShowModal()

    def OnDialyzerRunModule(self, event):
        editor = self.window.TabMgr.GetActiveEditor()
        if not editor:
            wx.MessageBox("No modules opened.")
            return
        if not IsModule(editor.filePath):
            wx.MessageBox("Current file is not erlang module.")
            return
        self.DialyzeModules(editor.filePath)

    def PltPath(self):
        return None if not CONFIG_PLT_FILE_PATH in self.userData else self.userData[CONFIG_PLT_FILE_PATH]

    def SetPltPath(self, path):
        self.userData[CONFIG_PLT_FILE_PATH] = path
        if not path: return
        self.GetShell().SetProp("plt", path)

    def HomeDir(self):
        return None if not CONFIG_HOME_PATH in self.userData else self.userData[CONFIG_HOME_PATH]

    def SetHomeDir(self, path):
        self.userData[CONFIG_HOME_PATH] = path
        if not path: return
        self.GetShell().SetHomeDir(path)

    def CheckPlt(self):
        if not self.PltPath():
            wx.MessageBox("Please specify plt for dialyzer. Project -> Dialyzer -> Edit Options.")
            return False
        return True

    def DialyzeApps(self, paths):
        #print paths
        if not self.CheckPlt(): return
        apps = set()
        for path in paths:
            app = self.GetApp(path)
            if not app: continue
            apps.add(self.EbinDirForApp(app))
        if len(apps) == 0:
            wx.MessageBox("No app to dialyze.")
            return
        #print apps
        self.GetShell().DialyzeApps(list(apps))

    def DialyzeProject(self):
        if not self.CheckPlt(): return
        apps = set()
        for app in self.GetApps():
            apps.add(self.EbinDirForApp(app))
        self.GetShell().DialyzeApps(list(apps))

    def EbinDirForApp(self, app):
        return os.path.join(self.AppsPath(), app, "ebin")

    def DialyzeModules(self, files):
        if not self.CheckPlt(): return
        beams = set()
        for file in files:
            if not IsModule(file): continue
            beamPath = self.GetBeamPathFromSrcPath(file)
            if not beamPath: continue
            beams.add(beamPath)
        if len(beams) == 0:
            wx.MessageBox("No modules to dialyze.")
            return
        self.GetShell().DialyzeModules(list(beams))

    def GetBeamPathFromSrcPath(self, path):
        app = self.GetApp(path)
        if not app:
            return None
        return os.path.join(self.EbinDirForApp(app), os.path.splitext(os.path.basename(path))[0] + ".beam")

    def AppsPath(self):
        if not CONFIG_APPS_DIR in self.projectData or not self.projectData[CONFIG_APPS_DIR]:
            return self.projectDir
        return os.path.join(self.projectDir, self.projectData[CONFIG_APPS_DIR])

    def GetErlangRuntime(self):
        return None if not CONFIG_ERLANG_RUNTIME in self.userData else self.userData[CONFIG_ERLANG_RUNTIME]

    def GetErlangPath(self):
        runtime = self.GetErlangRuntime()
        return Config.Runtimes()[runtime]

    def SetupDirs(self):
        projectCacheDir = os.path.join(ErlangCache.CACHE_DIR, self.ProjectName())
        if not os.path.isdir(projectCacheDir):
            os.makedirs(projectCacheDir)
        self.flyDir = os.path.join(self.window.cwd, "data", "erlang", "fly", self.ProjectName())
        if not os.path.isdir(self.flyDir):
            os.makedirs(self.flyDir)
        for file in os.listdir(self.flyDir):
            if IsModule(file):
                os.remove(os.path.join(self.flyDir, file))

    def RegenerateErlangCache(self):
        ErlangCache.CleanDir(os.path.join("runtimes", self.GetErlangRuntime()))
        self.GenerateErlangCache()

    def GenerateErlangCache(self):
        #print "generate erlang cache"
        self.GetShell().GenerateErlangCache(self.GetErlangRuntime())

    def StartXRef(self):
        filesForXref = set()
        for app in self.GetApps():
            path = os.path.join(os.path.join(self.AppsPath(), app), "src")
            for root, _, files in os.walk(path):
                for file in files:
                    file = os.path.join(root, file)
                    if IsModule(file):
                        filesForXref.add(file)
        self.xrefModules = set()
        for file in filesForXref:
            module = os.path.basename(file)[:-4]
            self.GetShell().XRef(module)
            self.xrefModules.add(module)
        #print "start xref", self.xrefModules
        self.xrefTable.Clear()
        #self.ShowXrefTable()

    def GetShell(self):
        return self.shellConsole.shell

    def GetApp(self, path):
        if os.path.isfile(path):
            path = os.path.dirname(path)
        if not path.startswith(self.AppsPath()):
            return None
        app = path.replace(self.AppsPath() + os.sep, "")
        if os.sep in app:
            return app[:app.index(os.sep)]
        return app

    def Compile(self, path):
        #print path
        hrls = set()
        erls = set()
        #yrls = set()
        def addByType(file):
            if IsInclude(file):
                hrls.add(file)
            elif IsModule(file):
                erls.add(file)
            elif IsYrl(file):
                erls.add(file)
        if isinstance(path, list):
            for p in path:
                addByType(p)
        else:
            addByType(path)
        #print hrls
        while len(hrls) > 0:
            toRemove = []
            for hrl in hrls:
                self.GetShell().GenerateFileCache(hrl)
               # print "hrl", hrl, os.path.basename(hrl), ErlangCache.GetDependentModules(os.path.basename(hrl))
                dependent = ErlangCache.GetDependentModules(os.path.basename(hrl))
                #print dependent
                for d in dependent:
                    addByType(d)
                toRemove.append(hrl)
            for h in toRemove:
                hrls.remove(h)

        #print "to compile: ", erls
        #self.GetShell().CompileYrls(yrls)
        print erls
        for erl in erls:
            app = self.GetApp(erl)
            if app in self.projectData[CONFIG_EXCLUDED_DIRS]:
                continue
            self.GetShell().Compile(erl)

    def CompileOption(self, path, option):
        if not IsModule(path): return
        self.GetShell().CompileOption(path, option)

    def OnCompileOptionResult(self, path, option, data):
        for page in self.window.TabMgr.Pages():
            if isinstance(page, ErlangSTCReadOnly):
                if page.filePath == path and page.option == option:
                    page.SetNewText(data)
                    return
        title = "'{}' {}".format(option, os.path.basename(path))
       # Log(title)
        panel = ErlangCompileOptionPanel(self.window.TabMgr, path, option, data)
        self.window.TabMgr.AddCustomPage(panel, title)

    def AddConsoles(self):
        #self.shellConsole = ErlangIDEConsole(self.window, self.IDE_MODULES_DIR)
        #self.shellConsole.Hide()
        self.SetupShellConsole()

        self.UpdatePaths()

        self.UpdateProjectConsoles()

    def OnIDEConnectionClosed(self):
        if self.shellConsole:
            index = self.window.ToolMgr.FindPageIndexByWindow(self.shellConsole)
            if index != None:
                self.window.ToolMgr.ClosePage(index)
        self.SetupShellConsole()

    def SetupShellConsole(self):
        self.connected = False
        self.shellConsole = ErlangIDEConsole(self.window.ToolMgr, self.IDE_MODULES_DIR)
        self.shellConsole.shell.SetProp("cache_dir", ErlangCache.CACHE_DIR)
        self.shellConsole.shell.SetProp("project_dir", self.AppsPath())
        self.shellConsole.shell.SetProp("project_name", self.ProjectName())
        self.shellConsole.onlyHide = True
        self.ShowIDEConsole()
        self.shellConsole.DataReceivedEvent += self.OnShellDataReceived
        self.shellConsole.shell.ClosedConnectionEvent += self.OnIDEConnectionClosed


    def OnShellDataReceived(self, text):
        if "started on:" in text:
            self.shellConsole.DataReceivedEvent -= self.OnShellDataReceived
            self.shellConsole.shell.TaskAddedEvent += self.OnTaskAdded
            self.shellConsole.shell.SocketDataReceivedEvent += self.OnSocketDataReceived
            self.shellConsole.shell.ConnectToSocket()

    def OnTaskAdded(self, task):
        #print task
        self.AddTask(task)

    def OnSocketDataReceived(self, response, js):
        #print response
        if response == "connect":
            self.connected = True
            #self.shellConsole.shell.SocketDataReceivedEvent -= self.OnSocketDataReceived
            self.OnSocketConnected()
        elif response == "compile" or response == "compile_fly":
            errorsData = js["errors"]
            path = pystr(js["path"])

            if response == "compile":
                done = (TASK_COMPILE, path.lower())
            else:
                done = (TASK_COMPILE_FLY, path.lower())
            self.TaskDone("Compiled {}".format(path), done)

            errors = []
            for error in errorsData:
                if error["line"] == "none":
                    continue
                errors.append(CompileErrorInfo(path, error["type"], error["line"], error["msg"]))
                #print "compile result: {} = {}".format(path, errors)
            self.AddErrors(path, errors)

        elif response == "xref_module":
            module = pystr(js["module"])
            if module in self.xrefModules:
                self.xrefModules.remove(module)
            if not module in ErlangCache.moduleData: return
            undefined = [((u["where_m"], u["where_f"], u["where_a"]),
                          (u["what_m"], u["what_f"], u["what_a"])) for u in js["undefined"]]
            #print "xref result", module, undefined
            self.AddXRefErrors(ErlangCache.moduleData[module].file, undefined)
            #print "result", module, self.xrefModules
            if len(self.xrefModules) == 0:
                self.ShowXrefTable()
        elif response == "dialyzer":
            warnings = js["warnings"]
            self.ShowDialyzerResult(warnings)
        elif response == "gen_file_cache":
            path = pystr(js["path"])
            cachePath = pystr(js["cache_path"])
            ErlangCache.AddToLoad(cachePath)
            self.TaskDone("Generated cache for {}".format(path), (TASK_GEN_FILE_CACHE, path.lower()))
        elif response == "gen_erlang_cache":
            self.ErlangCacheChecked()
        elif response == "compile_option":
            path = pystr(js["path"])
            option = js["option"]
            data = js["result"]
            self.OnCompileOptionResult(path, option, data)

    def OnSocketConnected(self):
        self.SetCompilerOptions()
        self.CreateProgressDialog("Compiling project")
        self.CompileProject()
        self.GenerateErlangCache()
        #print 'on connected ..'

    def UpdatePaths(self):
        dirs = ""
        for app in self.GetApps(True):
            appPath = os.path.join(self.AppsPath(), app)
            ebinDir = os.path.join(appPath, "ebin")
            self.shellConsole.shell.AddPath(ebinDir)
            dirs += ' "{}"'.format(ebinDir)
        dirs += ' "{}"'.format(self.IDE_MODULES_DIR)
        #print "new dirs", dirs
        self.dirs = dirs

    def AddXRefErrors(self, path, errors):
        self.xrefTable.AddErrors(path, errors)

    def ShowDialyzerResult(self, warnings):
        dialyzerTable = DialyzerTableGrid(self.window.ToolMgr, self)
        dialyzerTable.SetWarnings(warnings)
        self.window.ToolMgr.AddPage(dialyzerTable, "Dialyzer result")
        self.window.ToolMgr.FocusOnWidget(dialyzerTable)


    def UpdateProjectConsoles(self):
        self.consoles = {}

        consoles = self.projectData[CONFIG_CONSOLES]

        for console in self.consoleTabs:
            if console not in consoles:
                c = self.consoleTabs[console]
                c.Stop()
                index = self.window.ToolMgr.FindPageIndexByWindow(c)
                if index != None:
                    self.window.ToolMgr.DeletePage(index, True)
                id = self.consoleMenu.FindItem('Console <{}>'.format(console))
                if id != wx.NOT_FOUND:
                    self.consoleMenu.Delete(id)

        for title in consoles:
            data = consoles[title]
            params = []
            params.append("-sname " + data[CONFIG_CONSOLE_SNAME])
            params.append("-setcookie " + data[CONFIG_CONSOLE_COOKIE])
            params.append(data[CONFIG_CONSOLE_PARAMS])

            params.append("-pa " + self.dirs)

            if title in self.consoleTabs:
                self.consoleTabs[title].SetParams(params)
                self.consoleTabs[title].SetStartCommand(data[CONFIG_CONSOLE_COMMAND])
            else:
                self.consoles[title] = ErlangProjectConsole(self.window.ToolMgr, self.AppsPath(), params)
                self.consoles[title].onlyHide = True
                self.consoles[title].SetStartCommand(data[CONFIG_CONSOLE_COMMAND])
                self.consoleTabs[title] = self.consoles[title]
                self.ShowConsole(title, self.consoles[title])
                #self.window.ToolMgr.AddPage(self.consoles[title], 'Console <{}>'.format(title))

            def showConsole(title):
                return lambda e: self.ShowConsole(title, self.consoleTabs[title])
            self.consoleMenu.AppendMenuItem("Console <{}>".format(title), self.window, showConsole(title))

    def GetApps(self, all = False):
        apps = []
        for app in os.listdir(self.AppsPath()):
            if not all and app in self.projectData[CONFIG_EXCLUDED_DIRS]:
                continue
            appPath = os.path.join(self.AppsPath(), app)
            if not os.path.isdir(appPath):
                continue
            apps.append(app)
        return apps

    def AddTabs(self):
        self.errorsTable = ErrorsTableGrid(self.window.ToolMgr, self)
        self.errorsTable.onlyHide = True

        self.xrefTable = XrefTableGrid(self.window.ToolMgr, self)
        self.xrefTable.onlyHide = True
        self.xrefTable.Hide()

        self.ShowErrorsTable()

    def Close(self):
        ErlangCache.StopCheckingFolder(self.ProjectName())
        self.shellConsole.Stop()
        for title, console in self.consoles.items():
            console.Stop()

        self.window.ToolMgr.CloseAll()
        self.window.toolbar.DeleteTool(self.xrefCheckT.GetId())
        self.window.toolbar.DeleteTool(self.rebuildT.GetId())
        self.window.toolbar.DeleteToolByPos(self.window.toolbar.GetToolsCount() - 1)

        Project.Close(self)

    def OnProjectFilesModified(self, files):
        #print "modified", files, self.window.TabMgr.OpenedFiles()
        toCompile = []
        for file in files:
            editor = self.window.TabMgr.FindPageByPath(file)
            if editor:
                text = readFile(file)
                if not text: continue
                if editor.savedText != text:
                    dial = wx.MessageDialog(None,
                        'File "{}" was modified.\nDo you want to reload document?'.format(file),
                        'File modified',
                        wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
                    if dial.ShowModal() == wx.ID_YES:
                        editor.LoadFile(file)
                        toCompile.append(file)
            else:
                toCompile.append(file)
        self.Compile(toCompile)


    def FileSaved(self, file):
        #core.Log("saved", file)
        self.Compile(file)

    def OnProjectFilesDeleted(self, files):
        for file in files:
            self.AddErrors(file, [])
            self.RemoveUnusedBeams()
            if IsInclude(file):
                self.Compile(ErlangCache.GetDependentModules(os.path.basename(file)))
            self.ClearCacheForFile(file)
            editor = self.window.TabMgr.FindPageByPath(file)
            page = self.window.TabMgr.FindPageIndexByPath(file)

            if editor:
                dial = wx.MessageDialog(None,
                    'File "{}" was deleted.\nDo you want to close tab with deleted document?'.format(file),
                    "File deleted",
                    wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
                result = dial.ShowModal()
                if result == wx.ID_YES:
                    self.window.TabMgr.ClosePage(page)
                else:
                    editor.OnSavePointLeft(None)
                    editor.Changed()

    def OnProjectFilesCreated(self, files):
        #print "created", files
        self.Compile(files)

    def OnProjectDirsCreated(self, dirs):
        for dir in dirs:
            appPath = dir
            (root, app) = os.path.split(appPath)
            if root == self.AppsPath():
                self.UpdatePaths()
                self.UpdateProjectConsoles()

    def ClearCacheForFile(self, path):
        name = os.path.basename(path)
        if IsModule(name):
            name = name[:-4]
        ErlangCache.UnloadModule(name)

    def GetEditorTypes(self):
        return {".config": ErlangHighlightedSTCBase,
                ".src": ErlangHighlightedSTCBase,
                ".app": ErlangHighlightedSTCBase}

    def CompileProject(self):
        #print "compile project"
        self.CreateProgressDialog("Compiling project")
        ErlangCache.CleanDir(self.ProjectName())
        filesToCompile = set()
        filesToCache = set()
        yrlToCompile = set()
        for app in self.GetApps():
            srcPath = os.path.join(os.path.join(self.AppsPath(), app), "src")
            testPath = os.path.join(os.path.join(self.AppsPath(), app), "test")
            includePath = os.path.join(os.path.join(self.AppsPath(), app), "include")
            for path in [srcPath, includePath, testPath]:
                #if not os.path.isdir(path): continue
                for root, _, files in os.walk(path):
                    for file in files:
                        file = os.path.join(root, file)
                        if IsModule(file):
                            filesToCompile.add(file)
                        if IsYrl(file):
                            yrlToCompile.add(file)
                        elif IsInclude(file):
                            filesToCache.add(file)

        for file in list(yrlToCompile):
            (path, ext) = os.path.splitext(file)
            erl = path + ".erl"
            if erl in filesToCompile:
                filesToCompile.remove(erl)

        filesToCompile = sorted(list(filesToCompile) + list(yrlToCompile))
        filesToCache = sorted(list(filesToCache))

        #print "compile: ", filesToCompile
        #print "yrl compile: ", yrlToCompile
#        print "cache: ", filesToCache

        self.GetShell().GenerateFileCaches(filesToCache)
        self.GetShell().CompileProjectFiles(filesToCompile)
        self.RemoveUnusedBeams()

    def RemoveUnusedBeams(self):
        srcFiles = set()
        for app in self.GetApps(True):
            path = os.path.join(self.AppsPath(), app, "src")
            for root, _, files in os.walk(path):
                for fileName in files:
                    (file, ext) = os.path.splitext(fileName)
                    if IsModule(fileName):
                        srcFiles.add(file)

            path = self.EbinDirForApp(app)
            for root, _, files in os.walk(path):
                for fileName in files:
                    (file, ext) = os.path.splitext(fileName)
                    if IsBeam(fileName):
                        if file not in srcFiles:
                            os.remove(os.path.join(root, fileName))

    def IsFlyCompileEnabled(self):
        return Config.GetProp("erlang_fly_compilation", True)

    def AddErrors(self, path, errors):
        self.errors[path] = errors
        editor = self.window.TabMgr.FindPageByPath(path)
        if editor:
            editor.HighlightErrors(errors)

        self.errorsTable.AddErrors(path, errors)
        errorCount = 0
        warningCount = 0
        pathErrors = {}
        for (path, err) in self.errors.items():
            pathErrors[path] = False
            for e in err:
                if e.type == CompileErrorInfo.WARNING:
                    warningCount += 1
                else:
                    errorCount += 1
                    pathErrors[path] = True
        pathErrors = sorted(pathErrors.iteritems(), key = operator.itemgetter(1))
        self.explorer.SetPathErrors(pathErrors)
        #wx.CallAfter(self.window.TabMgr.HighlightErrorPaths, pathErrors)
        self.window.TabMgr.HighlightErrorPaths(pathErrors)
        index = self.window.ToolMgr.FindPageIndexByWindow(self.errorsTable)
        self.errorCount = errorCount
        self.warningCount = warningCount
        if index != None:
            self.ShowErrorsTable()

    def GetErrors(self, path):
        if path not in self.errors: return []
        else: return self.errors[path]

    def CompileFileFly(self, file, realPath, data):
        flyPath = os.path.join(self.flyDir, "fly_" + file)
        writeFile(flyPath, data)
        self.GetShell().CompileFileFly(realPath, flyPath)

    def CompilerOptions(self, projectData = None):
        if not projectData:
            projectData = self.projectData
        return "" if not CONFIG_COMPILER_OPTIONS in projectData else projectData[CONFIG_COMPILER_OPTIONS]

    def UpdateProject(self):
        self.UpdatePaths()
        self.UpdateProjectConsoles()
        self.SetCompilerOptions()
        self.SaveData()
        self.SaveUserData()

    def SetCompilerOptions(self):
        options = self.CompilerOptions().replace("\n", ", ")
        print options
        self.shellConsole.shell.SetProp(CONFIG_COMPILER_OPTIONS, options)
        if self.CompilerOptions() != self.CompilerOptions(self.oldProjectData):
            self.CompileProject()
