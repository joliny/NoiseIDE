__author__ = 'Yaroslav Nikityshev aka IDNoise'

import os
import wx
import time
import shutil
import wx.lib.agw.customtreectrl as CT
from idn_utils import extension, Menu
from idn_directoryinfo import DirectoryChecker
from idn_global import GetTabMgr

ICON_SIZE = 16

wxEVT_PROJECT_FILE_CREATED = wx.NewEventType()
wxEVT_PROJECT_DIR_CREATED = wx.NewEventType()
wxEVT_PROJECT_FILE_MODIFIED = wx.NewEventType()
wxEVT_PROJECT_DIR_MODIFIED = wx.NewEventType()
wxEVT_PROJECT_FILE_DELETED = wx.NewEventType()
wxEVT_PROJECT_DIR_DELETED = wx.NewEventType()

EVT_PROJECT_FILE_CREATED = wx.PyEventBinder(wxEVT_PROJECT_FILE_CREATED, 1)
EVT_PROJECT_DIR_CREATED = wx.PyEventBinder(wxEVT_PROJECT_DIR_CREATED, 1)
EVT_PROJECT_FILE_MODIFIED = wx.PyEventBinder(wxEVT_PROJECT_FILE_MODIFIED, 1)
EVT_PROJECT_DIR_MODIFIED = wx.PyEventBinder(wxEVT_PROJECT_DIR_MODIFIED, 1)
EVT_PROJECT_FILE_DELETED = wx.PyEventBinder(wxEVT_PROJECT_FILE_DELETED, 1)
EVT_PROJECT_DIR_DELETED = wx.PyEventBinder(wxEVT_PROJECT_DIR_DELETED, 1)

class ProjectExplorerFileEvent(wx.PyCommandEvent):
    def __init__(self, evtType, evtId, file = None, **kwargs):
        """
        :param integer `evtType`: the event type;
        :param integer `evtId`: the event identifier;
        :param `file`: string path to file;
        """

        wx.PyCommandEvent.__init__(self, evtType, evtId, **kwargs)
        self.File = file

class ProjectExplorer(CT.CustomTreeCtrl):
    FILE, DIRECTORY_OPEN, DIRECTORY_CLOSED = range(3)
    INTERVAL = 1
    def __init__(self, parent):
        style = wx.TR_MULTIPLE | wx.DIRCTRL_3D_INTERNAL | wx.TR_HAS_BUTTONS

        CT.CustomTreeCtrl.__init__(self, parent, agwStyle = style)

        self.root = None
        self.mask = self.DefaultMask()
        self.excludeDirs = self.DefaultExcludeDirs()
        self.excludePaths = self.DefaultExcludePaths()
        self.hiddenPaths = set()
        self.showHidden = False
        self.dirChecker = None

        self.SetupIcons()

        self.Bind(CT.EVT_TREE_ITEM_MENU, self.ShowMenu)
        self.Bind(CT.EVT_TREE_ITEM_ACTIVATED, self.OnActivateItem)

    def SetupIcons(self):
        self.imageList = wx.ImageList(ICON_SIZE, ICON_SIZE)
        self.iconIndex = {}
        self.AddIconFromArt(self.FILE, wx.ART_NORMAL_FILE)
        self.AddIconFromArt(self.DIRECTORY_OPEN, wx.ART_FILE_OPEN)
        self.AddIconFromArt(self.DIRECTORY_CLOSED, wx.ART_FOLDER)
        self.SetImageList(self.imageList)

    def AppendDir(self, parentNode, path):
        if (path in self.excludePaths or
            (not self.showHidden and path in self.hiddenPaths) or
            os.path.basename(path) in self.excludeDirs):
            return False
        dir = self.AppendItem(parentNode, os.path.basename(path))
        self.SetItemHasChildren(dir, True)
        self.SetPyData(dir, path)
        self.SetItemImage(dir, self.iconIndex[self.DIRECTORY_CLOSED], wx.TreeItemIcon_Normal)
        self.SetItemImage(dir, self.iconIndex[self.DIRECTORY_OPEN], wx.TreeItemIcon_Expanded)
        if path in self.hiddenPaths:
            self.SetAttrsForHiddenItem(dir)
        self.Load(dir, path)
        return True

    def AppendFile(self, parentNode, path):
        file = os.path.basename(path)
        if (path in self.excludePaths or
            (not self.showHidden and path in self.hiddenPaths) or
            self.mask and extension(file) not in self.mask):
            return False
        icon = self.GetIconIndex(path)
        file = self.AppendItem(parentNode, file)
        self.SetItemImage(file, icon, wx.TreeItemIcon_Normal)
        if path in self.hiddenPaths:
            self.SetAttrsForHiddenItem(file)
        self.SetPyData(file, path)
        return True

    def SetupChecker(self):
        if self.dirChecker:
            self.dirChecker.Stop()
        self.dirChecker = DirectoryChecker(self.INTERVAL, self.root, True, self.mask, self.excludeDirs, self.excludePaths)
        self.dirChecker.AddHandler(DirectoryChecker.HANDLER_FILE_CREATED, self.FileCreated)
        self.dirChecker.AddHandler(DirectoryChecker.HANDLER_FILE_MODIFIED, self.FileModified)
        self.dirChecker.AddHandler(DirectoryChecker.HANDLER_FILE_DELETED, self.FileDeleted)
        self.dirChecker.AddHandler(DirectoryChecker.HANDLER_DIR_CREATED, self.DirCreated)
        self.dirChecker.AddHandler(DirectoryChecker.HANDLER_DIR_MODIFIED, self.DirModified)
        self.dirChecker.AddHandler(DirectoryChecker.HANDLER_DIR_DELETED, self.DirDeleted)
        self.dirChecker.Start()

    def SetRoot(self, root):
        self.root = root
        self.SetupChecker()
        rootNode = self.AddRoot(root)
        self.SetItemHasChildren(rootNode, True)
        self.SetItemImage(rootNode, self.iconIndex[self.DIRECTORY_CLOSED], wx.TreeItemIcon_Normal)
        self.SetItemImage(rootNode, self.iconIndex[self.DIRECTORY_OPEN], wx.TreeItemIcon_Expanded)
        self.SetPyData(rootNode, root)

        self.Load(rootNode, root)
        self.Expand(rootNode)

    def SetMask(self, mask):
        self.mask = mask
        self.DeleteAllItems()
        self.SetRoot(self.root)

    def AddMask(self, mask):
        self.SetMask(self.mask + mask)

    def SetHiddenList(self, list):
        self.hiddenPaths = list
        self.DeleteAllItems()
        self.SetRoot(self.root)

    def AddIcon(self, id, path):
        try:
            if os.path.exists(path):
                key = self.imageList.Add(wx.Bitmap(path, wx.BITMAP_TYPE_PNG))
                self.iconIndex[id] = key
        except Exception, e:
            print e

    def AddIconFromArt(self, id, image):
        icon = wx.ArtProvider_GetBitmap(image, wx.ART_OTHER, (ICON_SIZE, ICON_SIZE))
        key = self.imageList.Add(icon)
        self.iconIndex[id] = key

    def Load(self, node, dir):
        if not os.path.isdir(dir):
            raise Exception("{} is not a valid directory".format(dir))

        files = os.listdir(dir)
        for f in files:
            path = os.path.join(dir, f)
            if os.path.isdir(path):
                self.AppendDir(node, path)
            else:
                self.AppendFile(node, path)

    def GetIconIndex(self, fileName):
        ext = extension(fileName)
        if ext in self.iconIndex:
            return self.iconIndex[ext]
        else:
            try:
                fileType = wx.TheMimeTypesManager.GetFileTypeFromExtension(ext)
                if hasattr(fileType, 'GetIconInfo'):
                    info = fileType.GetIconInfo()

                    if info is not None:
                        icon = info[0]
                        if icon.Ok():
                            key = self.imageList.AddIcon(icon)
                            self.iconIndex[ext] = key
                            self.SetImageList(self.imageList)
                            return iconkey
            finally:
                return self.iconIndex[self.FILE]

    def StopTrackingProject(self):
        self.dirChecker.Stop()

    def FileCreated(self, file):
        id = self.FindItemByPath(file)
        if self.AppendFile(id, file):
            e = ProjectExplorerFileEvent(wxEVT_PROJECT_FILE_CREATED , self.GetId(), file)
            self.GetEventHandler().ProcessEvent(e)

    def FileModified(self, file):
        if self.mask and extension(file) not in self.mask: return
        e = ProjectExplorerFileEvent(wxEVT_PROJECT_FILE_MODIFIED , self.GetId(), file)
        self.GetEventHandler().ProcessEvent(e)

    def FileDeleted(self, file):
        if self.mask and extension(file) not in self.mask: return
        id = self.GetIdByPath(file)
        e = ProjectExplorerFileEvent(wxEVT_PROJECT_FILE_DELETED , self.GetId(), file)
        self.GetEventHandler().ProcessEvent(e)
        self.Delete(id)

    def DirCreated(self, dir):
        id = self.FindItemByPath(os.path.dirname(dir))
        self.AppendDir(id, dir)

        e = ProjectExplorerFileEvent(wxEVT_PROJECT_DIR_CREATED, self.GetId(), dir)
        self.GetEventHandler().ProcessEvent(e)

    def DirModified(self, dir):
        e = ProjectExplorerFileEvent(wxEVT_PROJECT_DIR_MODIFIED, self.GetId(), dir)
        self.GetEventHandler().ProcessEvent(e)

    def DirDeleted(self, dir):
        id = self.FindItemByPath(dir)
        if self.GetPyData(id) == dir:
            e = ProjectExplorerFileEvent(wxEVT_PROJECT_DIR_DELETED , self.GetId(), dir)
            self.GetEventHandler().ProcessEvent(e)
            self.Delete(id)

    def FindItemByPath(self, path):
        id = self.GetRootItem()
        items = self.SplitOnItemsFromRoot(path)
        for item in items:
            id = self.FindItem(id, item)
        return id

    def SplitOnItemsFromRoot(self, path):
        items = []
        if os.path.isfile(path):
            path = os.path.dirname(path)
        while path != self.root:
            (path, folder) = os.path.split(path)
            items.append(folder)

        return reversed(items)

    def ShowMenu(self, event):
        self.popupItemIds = self.GetSelections()#event.GetItem()
        self.popupItemId = event.GetItem()
        menu = Menu()
        if len(self.popupItemIds) > 1 and self.GetRootItem() not in self.popupItemIds:
            menu.AppendMenuItem("Delete", self, self.OnMenuDelete)
            menu.AppendCheckMenuItem("Hide", self, self.OnMenuHide,
                self.GetPyData(self.popupItemIds[0]) in self.hiddenPaths)
        else:
            if self.ItemHasChildren(self.popupItemId):
                newMenu = Menu()
                newMenu.AppendMenuItem("New Dir", self, self.OnMenuNewDir)
                newMenu.AppendSeparator()
                self.FillNewSubMenu(newMenu)
                menu.AppendMenu(wx.NewId(), "New", newMenu)
            if self.popupItemId != self.GetRootItem():
                menu.AppendMenuItem("Delete", self, self.OnMenuDelete)
                menu.AppendSeparator()
                menu.AppendCheckMenuItem("Hide", self, self.OnMenuHide,
                    self.GetPyData(self.popupItemId) in self.hiddenPaths)
            if self.popupItemId == self.GetRootItem():
                menu.AppendCheckMenuItem("Show hidden", self, self.OnMenuShowHide, self.showHidden)

        self.PopupMenu(menu)

    def FillNewSubMenu(self, newMenu):
        pass

    def DefaultMask(self):
        return []

    def DefaultExcludeDirs(self):
        return [".git", ".svn"]

    def DefaultExcludePaths(self):
        return []

    def OnMenuNewDir(self, event):
        #print "on menu new dir", self.GetPyData(self.popupItemId)
        dialog = wx.TextEntryDialog(None, "Enter dir name",
            "New Directory", "new_dir", style=wx.OK | wx.CANCEL)
        if dialog.ShowModal() == wx.ID_OK:
            newDir = os.path.join(self.GetPyData(self.popupItemId), dialog.GetValue())
            if not os.path.isdir(newDir):
                os.mkdir(newDir)
        dialog.Destroy()

    def OnMenuDelete(self, event):
        for id in self.popupItemIds:
            path = self.GetPyData(id)
            if os.path.isdir(path):
                shutil.rmtree(path, True)
            else:
                os.remove(path)

    def GetIdByPath(self, path):
        if os.path.isdir(path):
            return self.FindItemByPath(path)
        else:
            parentId = self.FindItemByPath(path)
            return self.FindItem(parentId, os.path.basename(path))

    def OnMenuHide(self, event):
        if self.GetPyData(self.popupItemIds[0]) in self.hiddenPaths:
            for id in self.popupItemIds:
                path = self.GetPyData(id)
                self.hiddenPaths.remove(path)
                self.ClearHiddenAttrs(id)
        else:
            for id in self.popupItemIds:
                path = self.GetPyData(id)
                self.hiddenPaths.add(path)
                self.SetAttrsForHiddenItem(id)
                if not self.showHidden:
                    self.Delete(id)

    def SetAttrsForHiddenItem(self, id):
        self.SetItemTextColour(id, wx.Colour(60, 60, 200))
        self.SetItemItalic(id, True)

    def ClearHiddenAttrs(self, id):
        rootId = self.GetRootItem()
        self.SetItemTextColour(id, self.GetItemTextColour(rootId))
        self.SetItemItalic(id, False)

    def OnMenuShowHide(self, event):
        if self.showHidden == True:
            self.showHidden = False
            for path in self.hiddenPaths:
                self.DeleteItemByPath(path)
        else:
            self.showHidden = True
            for path in sorted(self.hiddenPaths):
                if os.path.dirname(path) in self.hiddenPaths: continue
                if os.path.isdir(path):
                    id = self.FindItemByPath(os.path.dirname(path))
                    self.AppendDir(id, path)
                else:
                    id = self.FindItemByPath(path)
                    self.AppendFile(id, path)
                if id:
                    self.SortChildren(id)

    def DeleteItemByPath(self, path):
        if os.path.isfile(path):
            parentId = self.FindItemByPath(path)
            id = self.FindItem(parentId, os.path.basename(path))
        else:
            id = self.FindItemByPath(path)
        if self.GetPyData(id) == path:
            self.Delete(id)

    def OnActivateItem(self, event):
        path = self.GetPyData(event.GetItem())
        if os.path.isfile(path):
            GetTabMgr().LoadFile(path)
        else:
            event.Skip()


    def GetAllFiles(self):
        id = self.GetRootItem()
        return self._GetFiles(id)

    def _GetFiles(self, item):
        #self.SelectAll()
        result = []
        if item:
            if item.HasChildren():
                for id in item.GetChildren():
                    result += self._GetFiles(id)
            else:
                result.append(self.GetPyData(item))
        return result

class PythonProjectExplorer(ProjectExplorer):
    def FillNewSubMenu(self, newMenu):
        newMenu.AppendMenuItem("New File", self, self.OnMenuNewFile)

    def DefaultMask(self):
        return [".py", ".yaml"]

    def OnMenuNewFile(self, event):
        print "on menu new file", self.GetPyData(self.popupItemId)

class ErlangProjectExplorer(ProjectExplorer):
    def FillNewSubMenu(self, newMenu):
        newMenu.AppendMenuItem("New Module", self, self.OnMenuNewModule)
        newMenu.AppendMenuItem("New Header", self, self.OnMenuNewHeader)

    def DefaultMask(self):
        return [".erl", ".hrl", ".config", "*.c", "*.cpp"]

    def OnMenuNewModule(self, event):
        print "on menu new module"

    def OnMenuNewHeader(self, event):
        print "on menu new header"

    def DefaultExcludeDirs(self):
        return ProjectExplorer.DefaultExcludeDirs(self) + ["ebin", ".settings"]

