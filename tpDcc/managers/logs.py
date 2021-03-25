#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains implementation to handle DCC logs themes
"""

import logging

from tpDcc.managers import tools, libs

logger = logging.getLogger('tpDcc-core')


def get_logger(plugin_id=None):
    """
    Returns logger associated with given tool
    :param plugin_id: str
    :return:
    """

    if not plugin_id:
        return logging.getLogger('tpDcc-core')

    plugin_data = None
    if '-tools-' in plugin_id:
        plugin_data = tools.ToolsManager().get_tool_data_from_id(plugin_id)
    elif '-libs-' in plugin_id:
        plugin_data = libs.LibsManager().get_library_data_from_id(plugin_id)
    if not plugin_data:
        logger.warning('No logger found for: {}. Using tpDcc-core logger as fallback.'.format(plugin_id))
        return logging.getLogger('tpDcc-core')

    logging_file = plugin_data.get('logging_file', None)
    if not logging_file:
        return logging.getLogger('tpDcc-core')

    logging.config.fileConfig(logging_file, disable_existing_loggers=False)
    # tool_logger_level_env = '{}_LOG_LEVEL'.format(pkg_loader.fullname.replace('.', '_').upper())
    return logging.getLogger(plugin_id)
