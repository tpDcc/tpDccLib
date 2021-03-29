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

    def register_package_libs(self, package_name, libs_paths):
        """
        Registers  all libraries available in given package
        """

        if not libs_paths:
            return
        libs_to_register = python.remove_dupes(python.force_list(libs_paths))
        self.register_paths(libs_to_register, package_name=package_name)

        # Once plugins are registered we load them
        plugins = self.plugins(package_name=package_name)
        for plugin in plugins:
            plugin.load()
