#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains DCC core functions an classes
"""

from __future__ import print_function, division, absolute_import

import os
import sys
import logging
import importlib
from functools import wraps
from collections import OrderedDict

from tpDcc.core import consts
from tpDcc.libs.python import osplatform

LOGGER = logging.getLogger('tpDcc-core')

main = __import__('__main__')

# Cached current DCC name.
CURRENT_DCC = None

# Cached used to store all the reroute paths done during a session.
DCC_REROUTE_CACHE = dict()


class Dccs(object):
    Standalone = 'standalone'
    Maya = 'maya'
    Max = 'max'
    MotionBuilder = 'mobu'
    Houdini = 'houdini'
    Nuke = 'nuke'
    Unreal = 'unreal'

    ALL = [
        Maya, Max, MotionBuilder, Houdini, Nuke, Unreal
    ]

    nice_names = OrderedDict([
        (Maya, 'Maya'),
        (Max, '3ds Max'),
        (MotionBuilder, 'MotionBuilder'),
        (Houdini, 'Houdini'),
        (Nuke, 'Nuke'),
        (Unreal, 'Unreal')
    ])

    packages = OrderedDict([
        ('cmds', Maya),
        ('pymxs', Max),
        ('pyfbsdk', MotionBuilder),
        ('hou', Houdini),
        ('nuke', Nuke),
        ('unreal', Unreal)
    ])

    # TODO: Add support for both MacOS and Linux
    # TODO: Add missing executables
    executables = {
        Maya: {osplatform.Platforms.Windows: 'maya.exe'},
        Max: {osplatform.Platforms.Windows: '3dsmax.exe'},
        MotionBuilder: {osplatform.Platforms.Windows: 'motionbuilder.exe'},
        Houdini: {osplatform.Platforms.Windows: 'houdinifx.exe'},
        Nuke: {},
        Unreal: {osplatform.Platforms.Windows: 'UE4Editor.exe'}
    }


class DccCallbacks(object):
    Shutdown = (consts.CallbackTypes.Shutdown, {'type': 'simple'})
    Tick = (consts.CallbackTypes.Tick, {'type': 'simple'})
    ScenePreCreated = (consts.CallbackTypes.ScenePreCreated, {'type': 'simple'})
    ScenePostCreated = (consts.CallbackTypes.ScenePostCreated, {'type': 'simple'})
    SceneNewRequested = (consts.CallbackTypes.SceneNewRequested, {'type': 'simple'})
    SceneNewFinished = (consts.CallbackTypes.SceneNewFinished, {'type': 'simple'})
    SceneSaveRequested = (consts.CallbackTypes.SceneSaveRequested, {'type': 'simple'})
    SceneSaveFinished = (consts.CallbackTypes.SceneSaveFinished, {'type': 'simple'})
    SceneOpenRequested = (consts.CallbackTypes.SceneOpenRequested, {'type': 'simple'})
    SceneOpenFinished = (consts.CallbackTypes.SceneOpenFinished, {'type': 'simple'})
    UserPropertyPreChanged = (consts.CallbackTypes.UserPropertyPreChanged, {'type': 'filter'})
    UserPropertyPostChanged = (consts.CallbackTypes.UserPropertyPostChanged, {'type': 'filter'})
    NodeSelect = (consts.CallbackTypes.NodeSelect, {'type': 'filter'})
    NodeAdded = (consts.CallbackTypes.NodeAdded, {'type': 'filter'})
    NodeDeleted = (consts.CallbackTypes.NodeDeleted, {'type': 'filter'})


def dcc_port(base_port, dcc_name=None):
    dcc = dcc_name or current_dcc()
    if not dcc:
        return base_port

    base_dcc_port = base_port
    for dcc_name in Dccs.ALL:
        base_dcc_port += 1
        if dcc_name == dcc:
            return base_dcc_port

    return base_port


def dcc_ports(base_port):
    all_ports = OrderedDict()
    all_ports['base'] = base_port
    for dcc_name in enumerate(Dccs.ALL):
        all_ports[dcc_name] = base_port + 1

    return all_ports


def current_dcc():
    global CURRENT_DCC
    if CURRENT_DCC:
        return CURRENT_DCC

    for dcc_package, dcc_name in Dccs.packages.items():
        if dcc_package in main.__dict__:
            CURRENT_DCC = dcc_name
            break
    if not CURRENT_DCC:
        try:
            import unreal
            CURRENT_DCC = Dccs.Unreal
        except ImportError:
            try:
                if os.path.splitext(os.path.basename(sys.executable))[0].lower() == 'motionbuilder':
                    import pyfbsdk
                    CURRENT_DCC = Dccs.MotionBuilder
                else:
                    CURRENT_DCC = Dccs.Standalone
            except ImportError:
                CURRENT_DCC = Dccs.Standalone

    return CURRENT_DCC


def get_dcc_loader_module(package='tpDcc.dccs'):
    """
    Checks DCC we are working on an initializes proper variables
    """

    dcc_mod = None
    for dcc_package, dcc_name in Dccs.packages.items():
        if dcc_package in main.__dict__:
            module_to_import = '{}.{}.loader'.format(package, dcc_name)
            try:
                dcc_mod = importlib.import_module(module_to_import)
            except ImportError:
                LOGGER.warning('DCC loader module {} not found!'.format(module_to_import))
                continue
            if dcc_mod:
                break
    if not dcc_mod:
        try:
            import unreal
            dcc_mod = importlib.import_module('{}.unreal.loader'.format(package))
        except Exception:
            try:
                import pyfbsdk
                dcc_mod = importlib.import_module('{}.mobu.loader'.format(package))
            except ImportError:
                pass

    return dcc_mod


def reroute(fn):
    """
    Decorator that reroutes the function call on runtime to the specific DCC implementation of the function
    Rerouted function calls are cached, and are only loaded once.
    The used DCC API will be retrieved from the current session, taking into account the current available
    implementations

    :param fn:
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):

        global DCC_REROUTE_CACHE

        dcc = current_dcc()
        if not dcc:
            return None

        # From the current function and DCC we retrieve module path where DCC implementation should be located
        fn_split = fn.__module__.split('.')
        dcc_reroute_path = '{}.{}'.format(consts.TPDCC_DCCS_NAMESPACE, dcc)
        fn_split_str = '.'.join(fn_split[3:])
        if fn_split_str:
            dcc_reroute_path = '{}.{}'.format(dcc_reroute_path, fn_split_str)
        dcc_reroute_path = '{}.dcc'.format(dcc_reroute_path)
        dcc_reroute_fn_path = '{}.{}'.format(dcc_reroute_path, fn.__name__)
        if dcc_reroute_fn_path not in DCC_REROUTE_CACHE:
            try:
                dcc_reroute_module = importlib.import_module(dcc_reroute_path)
            except ImportError as exc:
                raise NotImplementedError(
                    '{} | Function {} not implemented! {}'.format(dcc, dcc_reroute_fn_path, exc))
            except Exception as exc:
                raise exc

            # Cache reroute call, next calls to that function will use cache data
            if not hasattr(dcc_reroute_module, fn.__name__):
                raise NotImplementedError('{} | Function {} not implemented!'.format(dcc, dcc_reroute_fn_path))

            dcc_reroute_fn = getattr(dcc_reroute_module, fn.__name__)
            DCC_REROUTE_CACHE[dcc_reroute_fn_path] = dcc_reroute_fn

        return DCC_REROUTE_CACHE[dcc_reroute_fn_path](*args, **kwargs)

    return wrapper


def callbacks():
    """
    Return a full list of callbacks based on DccCallbacks dictionary
    :return: list<str>
    """

    new_list = list()
    for k, v in DccCallbacks.__dict__.items():
        if k.startswith('__') or k.endswith('__'):
            continue
        new_list.append(v[0])

    return new_list
