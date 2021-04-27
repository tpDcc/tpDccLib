#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains DCC scene object base class implementation
"""

from __future__ import print_function, division, absolute_import

from tpDcc import dcc
from tpDcc.abstract import sceneobject
from tpDcc.libs.python import decorators


class _MetaSceneObject(type):
    def __call__(self, *args, **kwargs):
        if dcc.is_maya():
            from tpDcc.dccs.maya.core import sceneobject as maya_sceneobject
            return type.__call__(maya_sceneobject.MayaSceneObject, *args, **kwargs)
        else:
            return type.__call__(sceneobject.AbstractSceneObject, *args, **kwargs)


@decorators.add_metaclass(_MetaSceneObject)
class SceneObject(sceneobject.AbstractSceneObject):
    pass
