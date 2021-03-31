#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains implementation for DCC tools
"""

from __future__ import print_function, division, absolute_import

import os
import re
import logging

from tpDcc import dcc
from tpDcc.core import tool
from tpDcc.managers import resources, configs
from tpDcc.libs.python import python, decorators, path as path_utils
from tpDcc.libs.qt.core import contexts
from tpDcc.libs.plugin.core import factory

if python.is_python2():
    import pkgutil as loader
else:
    import importlib.util
    import importlib as loader

LOGGER = logging.getLogger('tpDcc-core')


@decorators.add_metaclass(decorators.Singleton)
class ToolsManager(factory.PluginFactory):

    REGEX_FOLDER_VALIDATOR = re.compile('^((?!__pycache__)(?!dccs).)*$')

    def __init__(self):
        super(ToolsManager, self).__init__(interface=tool.DccTool, plugin_id='ID', version_id='VERSION')

        self._loaded_tools = dict()
        self._hub_tools = list()

    def register_package_tools(self, package_name, tools_to_register=None):
        """
        Registers all tools available in given package
        """

        found_tools = list()

        if not tools_to_register:
            return
        tools_to_register = python.force_list(tools_to_register)

        tools_path = '{}.tools.{}'
        for tool_name in tools_to_register:
            pkg_path = tools_path.format(package_name, tool_name)
            if python.is_python2():
                pkg_loader = loader.find_loader(pkg_path)
            else:
                pkg_loader = importlib.util.find_spec(pkg_path)
            if not pkg_loader:
                continue

            tool_path = path_utils.clean_path(
                pkg_loader.filename if python.is_python2() else os.path.dirname(pkg_loader.origin))
            if not tool_path or not os.path.isdir(tool_path):
                continue

            found_tools.append(tool_path)

        if not found_tools:
            LOGGER.warning('No tools found in package "{}"'.format(package_name))

        found_tools = list(set(found_tools))
        self.register_paths(found_tools, package_name=package_name)

        for tool in self.plugins(package_name=package_name):
            if not tool:
                continue

            if not tool.PACKAGE:
                tool.PACKAGE = package_name

    # ============================================================================================================
    # BASE
    # ============================================================================================================

    def get_tool_settings_path(self, tool_id, package_name=None, plugin_version=None):
        """
        Returns path where tool settings are located
        :param tool_id: str
        :param package_name: str or None
        :param plugin_version: str or None
        :return: str
        """

        plugin = self.get_plugin_from_id(tool_id)
        if not plugin:
            return None

        package_name = package_name or tool_id.replace('.', '-').split('-')[0]
        plugin_version = str(plugin_version or plugin.version())

        settings_path = path_utils.get_user_data_dir(appauthor=package_name, appname=tool_id)
        settings_path = path_utils.join_path(settings_path, plugin_version)

        return settings_path

    def get_tool_settings_file_path(self, tool_id, package_name=None):
        """
        Returns the path where tool settings file is located
        :param tool_id:
        :param package_name: str
        :return: str
        """

        settings_path = self.get_tool_settings_path(tool_id, package_name=package_name)
        if not settings_path:
            return None

        settings_file = path_utils.clean_path(os.path.expandvars(os.path.join(settings_path, 'settings.cfg')))

        return settings_file

    def get_tool_settings_file(self, tool_id, package_name=None):
        """
        Returns the settings file of the given tool
        :param tool_id: str
        :return: settings.QtSettings
        :param package_name: str
        """

        from tpDcc.libs.qt.core import settings

        settings_file = self.get_tool_settings_file_path(tool_id, package_name=package_name)

        return settings.QtSettings(filename=settings_file)

    # ============================================================================================================
    # TOOLS
    # ============================================================================================================

    def launch_tool_by_id(self, tool_id, package_name=None, dev=False, *args, **kwargs):
        """
        Launches tool of a specific package by its ID
        :param tool_id: str, tool ID
        :param package_name: str
        :param dev: bool
        :param args: tuple, arguments to pass to the tool execute function
        :param kwargs: dict, keyword arguments to pas to the tool execute function
        :return: DccTool or None, executed tool instance
        """

        if not package_name:
            split_package = tool_id.replace('.', '-').split('-')[0]
            package_name = split_package if split_package != tool_id else 'tpDcc'

        tool_class = self.get_plugin_from_id(tool_id, package_name=package_name)
        if not tool_class:
            LOGGER.warning(
                'Impossible to launch tool. Tool with ID "{}" not found in package "{}"'.format(tool_id, package_name))
            return

        settings = self.get_tool_settings_file(tool_id, package_name)
        tool_inst = tool_class(settings=settings, dev=dev, *args, **kwargs)

        self.close_tool(tool_id, package_name=package_name)

        with contexts.application():

            if tool_id == 'tpDcc-tools-hub':
                tool_data = tool_inst._launch(*args, **kwargs)
                tool_ui = tool_data['tool']
                self._hub_tools.append(tool_ui)
            else:
                tool_inst._launch(*args, **kwargs)
                self._loaded_tools[tool_id] = tool_inst

        LOGGER.debug('Execution time: {}'.format(tool_inst.stats.execution_time))

        return tool_inst

    def close_tool(self, tool_id, package_name=None, force=True):
        """
        Closes tool with given ID
        :param tool_id: str
        :param package_name: str
        :param force: bool
        """

        tool_class = self.get_plugin_from_id(tool_id, package_name=package_name)
        if not tool_class or tool_id not in self._loaded_tools:
            return False

        closed_tool = False

        # NOTE: Here we do not use a client because this is only valid if the tools is being executed inside DCC
        parent = dcc.get_main_window()
        if parent:
            for child in parent.children():
                if child.objectName() == tool_id:
                    child.fade_close() if hasattr(child, 'fade_close') else child.close()
                    closed_tool = True

        tool_to_close = self._loaded_tools[tool_id].attacher
        try:
            if not closed_tool and tool_to_close:
                tool_to_close.fade_close() if hasattr(tool_to_close, 'fade_close') else tool_to_close.close()
            if force and tool_to_close:
                tool_to_close.setParent(None)
                tool_to_close.deleteLater()
        except RuntimeError:
            pass
        self._loaded_tools.pop(tool_id)

        return True

    def close_tools(self):
        """
        Closes all available tools
        :return:
        """

        for tool_id in self._loaded_tools.keys():
            self.close_tool(tool_id, force=True)

    # # ============================================================================================================
    # # HUB
    # # ============================================================================================================
    #
    # def close_hub_ui(self, hub_ui_inst):
    #     if hub_ui_inst in self._hub_tools:
    #         self._hub_tools.remove(hub_ui_inst)
    #         LOGGER.debug('Close tpDcc Hub UI: {}'.format(hub_ui_inst))
    #
    # def get_hub_uis(self):
    #     return self._hub_tools
    #
    # def get_last_focused_hub_ui(self, include_minimized=True):
    #     """
    #     Returns last focused Hub UI
    #     :param include_minimized: bool, Whether or not take into consideration Hub UIs that are minimized
    #     :return: HubUI
    #     """
    #
    #     hub_ui_found = None
    #     max_time = 0
    #
    #     all_hub_uis = self.get_hub_uis()
    #     for ui in all_hub_uis:
    #         if ui.isVisible() and ui.last_focused_time > max_time:
    #             if (not include_minimized and not ui.isMinimized()) or include_minimized:
    #                 hub_ui_found = ui
    #                 max_time = ui.last_focused_time
    #
    #     return hub_ui_found
    #
    # def get_last_opened_hub_ui(self):
    #     """
    #     Returns last opened Hub UI
    #     :return: HubUI
    #     """
    #
    #     hub_ui_found = None
    #
    #     all_hub_uis = self.get_hub_uis()
    #     for ui in all_hub_uis:
    #         if ui.isVisible():
    #             hub_ui_found = ui
    #
    #     return hub_ui_found

    # ============================================================================================================
    # CONFIGS
    # ============================================================================================================

    def get_tool_config(self, tool_id, package_name=None):
        """
        Returns config applied to given tool
        :param tool_id: str
        :param package_name: str
        :return: Theme
        """

        if not package_name:
            package_name = tool_id.replace('.', '-').split('-')[0]

        if package_name not in self._plugins:
            LOGGER.warning(
                'Impossible to retrieve tool config for "{}" in package "{}"! Package not registered.'.format(
                    tool_id, package_name))
            return None

        if tool_id not in self._plugins[package_name]:
            LOGGER.warning(
                'Impossible to retrieve tool config for "{}" in package "{}"! Tool not found'.format(
                    tool_id, package_name))
            return None

        return configs.get_tool_config(tool_id=tool_id, package_name=package_name)

    # ============================================================================================================
    # THEMES
    # ============================================================================================================

    def get_tool_theme(self, tool_id, package_name=None):
        """
        Returns theme applied to given tool
        :param tool_id: str
        :param package_name: str
        :return: Theme
        """

        tool_settings = self.get_tool_settings_file(tool_id, package_name=package_name)
        if not tool_settings:
            return None

        theme_name = tool_settings.get('theme', 'default')
        return resources.theme(theme_name)
