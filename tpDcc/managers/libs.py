#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains manager to handle libs
"""

from __future__ import print_function, division, absolute_import

import os
import re
import logging

from tpDcc.core import library
from tpDcc.libs.python import python, decorators, path as path_utils
from tpDcc.libs.plugin.core import factory

if python.is_python2():
    import pkgutil as loader
else:
    import importlib.util
    import importlib as loader

logger = logging.getLogger('tpDcc-core')


@decorators.add_metaclass(decorators.Singleton)
class LibsManager(factory.PluginFactory):

    REGEX_FOLDER_VALIDATOR = re.compile('^((?!__pycache__)(?!dccs).)*$')

    def __init__(self):
        super(LibsManager, self).__init__(interface=library.DccLibrary, plugin_id='ID', version_id='VERSION')

    def get_library_settings_file_path(self, library_id):
        """
        Returns the path where library settings file is located
        :param library_id:
        :return: str
        """

        settings_path = path_utils.get_user_data_dir(appname=library_id)
        settings_file = path_utils.clean_path(os.path.expandvars(os.path.join(settings_path, 'settings.cfg')))

        return settings_file

    def register_package_libs(self, package_name, libs_to_register=None):
        """
        Registers  all libraries available in given package
        """

        found_libs = list()

        if not libs_to_register:
            return
        libs_to_register = python.force_list(libs_to_register)

        libs_path = '{}.libs.{}'
        for lib_name in libs_to_register:
            pkg_path = libs_path.format(package_name, lib_name)
            if python.is_python2():
                pkg_loader = loader.find_loader(pkg_path)
            else:
                pkg_loader = importlib.util.find_spec(pkg_path)
            if not pkg_loader:
                continue

            lib_path = path_utils.clean_path(
                pkg_loader.filename if python.is_python2() else os.path.dirname(pkg_loader.origin))
            if not lib_path or not os.path.isdir(lib_path):
                continue

            found_libs.append(lib_path)

        if not found_libs:
            logger.warning('No libraries found in package "{}"'.format(package_name))

        found_libs = list(set(found_libs))
        self.register_paths(found_libs, package_name=package_name)

        # Once plugins are registered we load them
        plugins = self.plugins(package_name=package_name)
        for plugin in plugins:
            plugin.load()
