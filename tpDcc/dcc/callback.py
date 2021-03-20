#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains custom Dcc callback classes
"""

from __future__ import print_function, division, absolute_import

from tpDcc import dcc

from tpDcc.libs.python import decorators
from tpDcc.abstract import callback as abstract_callback


class _MetaCallback(type):
    def __call__(cls, *args, **kwargs):
        if dcc.is_maya():
            from tpDcc.dccs.maya.core import callback as maya_callback
            return maya_callback.MayaCallback
        else:
            return None


@decorators.add_metaclass(_MetaCallback)
class Callback(abstract_callback.AbstractCallback):
    pass
