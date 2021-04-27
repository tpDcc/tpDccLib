#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains base scene wrapper class implementation
"""

from __future__ import print_function, division, absolute_import

from tpDcc import dcc
from tpDcc.abstract import scenewrapper
from tpDcc.libs.python import decorators


class _MetaSceneWrapper(type):
    def __call__(self, *args, **kwargs):
        if dcc.is_maya():
            from tpDcc.dccs.maya.core import scenewrapper as maya_scenewrapper
            return maya_scenewrapper.MayaSceneWrapper
        else:
            return scenewrapper.AbstractSceneWrapper


@decorators.add_metaclass(_MetaSceneWrapper)
class SceneWrapper(scenewrapper.AbstractSceneWrapper):
    pass
