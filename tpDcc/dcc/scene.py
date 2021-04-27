#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains DCC scene base class implementation
"""

from __future__ import print_function, division, absolute_import

from tpDcc import dcc
from tpDcc.abstract import scene
from tpDcc.libs.python import decorators


class _MetaScene(type):
    def __call__(self, *args, **kwargs):
        if dcc.is_maya():
            from tpDcc.dccs.maya.core import scene as maya_scene
            return type.__call__(maya_scene.MayaScene, *args, **kwargs)
        else:
            return type.__call__(scene.AbstractScene, *args, **kwargs)


@decorators.add_metaclass(_MetaScene)
class Scene(scene.AbstractScene):
    pass
