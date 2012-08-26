__author__ = 'Yaroslav Nikityshev aka IDNoise'

import wx
import os
from idn_utils import GetImage
from idn_cache import ErlangCache


class ErlangOutline(wx.Dialog):
    def __init__(self, parent, moduleName):
        wx.Dialog.__init__(self, parent, title = "Outline", size = (260, 600))
        self.moduleName = moduleName

        self.images = {"fun": 0, "record": 1, "macros": 2}

        il = wx.ImageList(16,16, True)
        for name in self.images.keys():
            bmp = GetImage(os.path.join("erlang", "outline", name + ".png"))
            il.Add(bmp)

        self.list = wx.ListCtrl(self, -1, style = wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_ALIGN_LEFT)# wx.LC_REPORT | wx.LC_NO_HEADER)# wx.LC_ICON | wx.LC_ALIGN_LEFT |  | wx.LC_AUTOARRANGE)

        self.list.AssignImageList(il, wx.IMAGE_LIST_SMALL)

        data = ErlangCache.moduleData[moduleName]

        self.navigation = {}

        self.list.InsertColumn(0, "data")
        self.list.SetColumnWidth(0, 250)
        i = 0
        for macros in data.macroses:
            self.list.InsertImageStringItem(i, macros.name, self.images["macros"])
            self.navigation[i] = macros.line
            i += 1

        for record in data.records:
            self.list.InsertImageStringItem(i, record.name, self.images["record"])
            self.navigation[i] = record.line
            i += 1

        for fun in data.functions:
            self.list.InsertImageStringItem(i, "{}/{}". format(fun.name, fun.arity), self.images["fun"])
            self.navigation[i] = fun.line
            i += 1

        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivate)

    def OnActivate(self, event):
        line = self.navigation[event.GetIndex()]
        self.Parent.GotoLine(line - 1)
        self.Close()