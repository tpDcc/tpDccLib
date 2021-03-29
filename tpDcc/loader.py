#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Initialization module for tpDcc
"""

from __future__ import print_function, division, absolute_import

import os
import logging.config

from tpDcc.libs.python import contexts, path

from tpDcc.core import dcc as core_dcc
from tpDcc.managers import libs, callbacks
# from tpDcc.libs.qt.managers import toolsets
# from tpDcc import toolsets as dcc_toolsets

# =================================================================================

PACKAGE = 'tpDcc'

# =================================================================================


def init():
    """
    Initializes module
    :param dev: bool, Whether tpDcc-core is initialized in dev mode or not
    """
    logger = create_logger()

    # Get DCC loader module
    dcc_loader_module = core_dcc.get_dcc_loader_module()
    logger.info('DCC loader module found: "{}"'.format(dcc_loader_module))
    if dcc_loader_module and hasattr(dcc_loader_module, 'init_dcc') and callable(dcc_loader_module.init_dcc):
        dcc_loader_module.init_dcc()

    # configs.register_package_configs(PACKAGE, os.path.dirname(tpDcc.config.__file__))
    # core_config = configs.get_config('tpDcc-core', environment='development' if dev else 'production')
    # if not core_config:
    #     logger.warning(
    #         'tpDcc-core configuration file not found! Make sure that you have tpDcc-config package installed!')
    #     return None
    #
    # libs_to_load = core_config.get('libs', list())
    # tools_to_load = core_config.get('tools', list())

    libs_paths = [path.clean_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libs'))]
    custom_paths_env = os.environ.get('TPDCC_LIBS', '')
    custom_paths = custom_paths_env.split(';')
    for custom_path in custom_paths:
        if not custom_path or not os.path.isdir(custom_path):
            continue
        custom_path = path.clean_path(custom_path)
        if custom_path in libs_paths:
            continue
        libs_paths.append(custom_path)

    with contexts.Timer('Libraries loaded', logger=logger):
        libs.LibsManager().register_package_libs(PACKAGE, libs_paths=libs_paths)
    #     libs.LibsManager().load_registered_libs(PACKAGE)

    # with contexts.Timer('Tools loaded', logger=logger):
    #     tools.ToolsManager().register_package_tools(PACKAGE, tools_to_register=tools_to_load)
    #     # tools.ToolsManager().load_registered_tools(PACKAGE)
    #
    # # with contexts.Timer('Toolsets loaded', logger=logger):
    # #     toolsets.ToolsetsManager().register_path(PACKAGE, os.path.dirname(dcc_toolsets.__file__))
    # #     toolsets.ToolsetsManager().load_registered_toolsets(PACKAGE, tools_to_load=tools_to_load)

    # Callbacks
    callbacks.CallbacksManager.initialize()


def create_logger():
    """
    Returns logger of current module
    """

    logger_directory = os.path.normpath(os.path.join(os.path.expanduser('~'), PACKAGE, 'logs'))
    if not os.path.isdir(logger_directory):
        os.makedirs(logger_directory)

    logging_config = os.path.normpath(os.path.join(os.path.dirname(__file__), '__logging__.ini'))

    logging.config.fileConfig(logging_config, disable_existing_loggers=False)
    logger = logging.getLogger('tpDcc-core')
    dev = os.getenv('TPDCC_DEV', False)
    if dev:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    return logger


create_logger()
