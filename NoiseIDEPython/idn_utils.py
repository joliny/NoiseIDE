from threading import Thread, Event

__author__ = 'Yaroslav'

import os
import wx

def readFile(file):
    f = open(file)
    data = f.read()
    f.close()
    return data

def writeFile(file, data):
    f = open(file, 'w')
    f.write(data)
    f.flush()
    f.close()

def extension(path):
    name, ext = os.path.splitext(path)
    return ext

class Timer(Thread):
    def __init__(self, interval, function):
        Thread.__init__(self)
        self.setDaemon(True)
        self.interval = interval
        self.function = function
        self.finished = Event()

    def Start(self):
        self.start()

    def Stop(self):
        if self.isAlive():
            self.finished.set()

    def run(self):
        while not self.finished.is_set():
            self.function()
            self.finished.wait(self.interval)

def CreateButton(parent, label, handler):
    button = wx.Button(parent, label = label)
    button.Bind(wx.EVT_BUTTON, handler)
    return button


class Menu(wx.Menu):
    def AppendMenuItem(self, text, handlerObject, handler):
        item = self.Append(wx.NewId(), text, text)
        handlerObject.Bind(wx.EVT_MENU, handler, item)

    def AppendCheckMenuItem(self, text, handlerObject, handler, check = False):
        item = self.Append(wx.NewId(), text, text, wx.ITEM_CHECK)
        self.Check(item.Id, check)
        handlerObject.Bind(wx.EVT_MENU, handler, item)
