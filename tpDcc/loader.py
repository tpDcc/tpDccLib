#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Initialization module for tpDcc
"""

from __future__ import print_function, division, absolute_import

import os
import logging.config

import tpDcc.config
from tpDcc.core import dcc as core_dcc
from tpDcc.libs.python import contexts
from tpDcc.managers import configs, libs, tools, callbacks
from tpDcc.libs.qt import loader as qt_loader
from tpDcc.libs.qt.managers import toolsets
from tpDcc import toolsets as dcc_toolsets

# =================================================================================

PACKAGE = 'tpDcc'

# =================================================================================


def init(dev=False):
    """
    Initializes module
    :param dev: bool, Whether tpDcc-core is initialized in dev mode or not
    """
    os.environ['TPDCC_DEV'] = str(dev) if dev else ''
    logger = create_logger(dev=dev)

    # Get DCC loader module
    dcc_loader_module = core_dcc.get_dcc_loader_module()
    logger.info('DCC loader module found: "{}"'.format(dcc_loader_module))
    if dcc_loader_module and hasattr(dcc_loader_module, 'init_dcc') and callable(dcc_loader_module.init_dcc):
        dcc_loader_module.init_dcc()

    # After that, we initialize Qt library (we must do it after tpDcc one because tpDcc-libs-qt depends on tpDcc-core)
    qt_loader.init(dev=dev)

    configs.register_package_configs(PACKAGE, os.path.dirname(tpDcc.config.__file__))
    core_config = configs.get_config('tpDcc-core', environment='development' if dev else 'production')
    if not core_config:
        logger.warning(
            'tpDcc-core configuration file not found! Make sure that you have tpDcc-config package installed!')
        return None

    libs_to_load = core_config.get('libs', list())
    tools_to_load = core_config.get('tools', list())

    with contexts.Timer('Libraries loaded', logger=logger):
        libs.LibsManager().register_package_libs(PACKAGE, libs_to_register=libs_to_load)
    #     libs.LibsManager().load_registered_libs(PACKAGE)

    with contexts.Timer('Tools loaded', logger=logger):
        tools.ToolsManager().register_package_tools(PACKAGE, tools_to_register=tools_to_load)
        # tools.ToolsManager().load_registered_tools(PACKAGE)

    # with contexts.Timer('Toolsets loaded', logger=logger):
    #     toolsets.ToolsetsManager().register_path(PACKAGE, os.path.dirname(dcc_toolsets.__file__))
    #     toolsets.ToolsetsManager().load_registered_toolsets(PACKAGE, tools_to_load=tools_to_load)

    # Callbacks
    callbacks.CallbacksManager.initialize()


def create_logger(dev=False):
    """
    Returns logger of current module
    """

    logger_directory = os.path.normpath(os.path.join(os.path.expanduser('~'), PACKAGE, 'logs'))
    if not os.path.isdir(logger_directory):
        os.makedirs(logger_directory)

    logging_config = os.path.normpath(os.path.join(os.path.dirname(__file__), '__logging__.ini'))

    logging.config.fileConfig(logging_config, disable_existing_loggers=False)
    logger = logging.getLogger('tpDcc-core')
    dev = os.getenv('TPDCC_DEV', dev)
    if dev:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    return logger


create_logger()
