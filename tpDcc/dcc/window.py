#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains custom Dcc window classes
"""

from __future__ import print_function, division, absolute_import

from tpDcc import dcc

from tpDcc.libs.python import decorators
from tpDcc.abstract import window as abstract_window
from tpDcc.libs.qt.widgets import window


class _MetaWindow(type):
    def __call__(cls, *args, **kwargs):
        as_class = kwargs.pop('as_class', False)
        if dcc.is_maya():
            from tpDcc.dccs.maya.ui import window as maya_window
            if as_class:
                return maya_window.MayaWindow
            else:
                return type.__call__(maya_window.MayaWindow, *args, **kwargs)
        elif dcc.is_unreal():
            from tpDcc.dccs.unreal.ui import window as unreal_window
            if as_class:
                return unreal_window.UnrealWindow
            else:
                return type.__call__(unreal_window.UnrealWindow, *args, **kwargs)
        else:
            if as_class:
                return window.MainWindow
            else:
                return type.__call__(window.MainWindow, *args, **kwargs)


@decorators.add_metaclass(_MetaWindow)
class Window(abstract_window.AbstractWindow):
    pass
