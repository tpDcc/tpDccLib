#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains manager to handle libs
"""

from __future__ import print_function, division, absolute_import

import os
import re
import logging
import inspect
import traceback
from collections import OrderedDict

from tpDcc.core import library
from tpDcc.managers import resources
from tpDcc.libs.python import python, decorators, plugin, settings, path as path_utils

if python.is_python2():
    import pkgutil as loader
else:
    import importlib.util
    import importlib as loader

LOGGER = logging.getLogger('tpDcc-core')


@decorators.add_metaclass(decorators.Singleton)
class LibsManager(plugin.PluginFactory):

    REGEX_FOLDER_VALIDATOR = re.compile('^((?!__pycache__)(?!dccs).)*$')

    def __init__(self):
        super(LibsManager, self).__init__(interface=library.DccLibrary, plugin_id='ID', version_id='VERSION')

    # def load_plugin(self, pkg_name, pkg_loaders, environment, root_pkg_name=None, config_dict=None, load=True):
    #     """
    #     Implements load_plugin function
    #     Registers a plugin instance to the manager
    #     :param pkg_name: str
    #     :param pkg_loaders: plugin instance to register
    #     :param environment:
    #     :param root_pkg_name:
    #     :param config_dict:
    #     :param load:
    #     :return: Plugin
    #     """
    #
    #     from tpDcc.managers import configs
    #
    #     if not pkg_loaders:
    #         return False
    #
    #     package_loader = pkg_loaders[0] if isinstance(pkg_loaders, (list, tuple)) else pkg_loaders
    #     if not package_loader:
    #         return False
    #
    #     if hasattr(package_loader, 'loader'):
    #         if not package_loader.loader:
    #             return False
    #
    #     plugin_path = package_loader.filename if python.is_python2() else os.path.dirname(package_loader.loader.path)
    #     plugin_name = package_loader.fullname if python.is_python2() else package_loader.loader.name
    #
    #     if not config_dict:
    #         config_dict = dict()
    #
    #     config_dict.update({
    #         'join': os.path.join,
    #         'user': os.path.expanduser('~'),
    #         'filename': plugin_path,
    #         'fullname': plugin_name,
    #         'root': path_utils.clean_path(plugin_path)
    #     })
    #
    #     if pkg_name not in self._plugins:
    #         self._plugins[pkg_name] = dict()
    #
    #     libs_found = list()
    #     version_found = None
    #     init_fn = None
    #     mods_found = list()
    #     # packages_to_walk = [plugin_path] if python.is_python2() else [os.path.dirname(plugin_path)]
    #     for module_path in modules.iterate_modules(plugin_path, skip_inits=False, recursive=False):
    #         module_dot_path = modules.convert_to_dotted_path(module_path)
    #         try:
    #             mod = modules.import_module(module_dot_path)
    #             if not mod:
    #                 continue
    #         except Exception:
    #             continue
    #         if module_dot_path.endswith('__version__') and hasattr(mod, 'get_version') and callable(mod.get_version):
    #             if version_found:
    #                 LOGGER.warning('Already found version: "{}" for "{}"'.format(version_found, plugin_name))
    #             else:
    #                 version_found = getattr(mod, 'get_version')()
    #
    #         if not init_fn and module_dot_path.endswith('loader') and hasattr(mod, 'init') and callable(mod.init):
    #             init_fn = mod.init
    #
    #         mod.LOADED = load
    #         mods_found.append(mod)
    #
    #     for mod in mods_found:
    #         for cname, obj in inspect.getmembers(mod, inspect.isclass):
    #             for interface in self._interfaces:
    #                 if issubclass(obj, interface):
    #                     lib_config_dict = obj.config_dict(file_name=plugin_path) or dict()
    #                     if not lib_config_dict:
    #                         continue
    #                     lib_id = lib_config_dict.get('id', None)
    #                     tool_config_name = lib_config_dict.get('name', None)
    #                     if not lib_id:
    #                         LOGGER.warning(
    #                             'Impossible to register library "{}" because its ID is not defined!'.format(lib_id))
    #                         continue
    #                     if not tool_config_name:
    #                         LOGGER.warning(
    #                             'Impossible to register library "{}" because its name is not defined!'.format(
    #                                 tool_config_name))
    #                         continue
    #                     if root_pkg_name and root_pkg_name in self._plugins and lib_id in self._plugins[root_pkg_name]:
    #                         LOGGER.warning(
    #                             'Impossible to register library "{}" because its ID "{}" its already defined!'.format(
    #                                 tool_config_name, lib_id))
    #                         continue
    #
    #                     if not version_found:
    #                         version_found = '0.0.0'
    #                     obj.VERSION = version_found
    #                     obj.FILE_NAME = plugin_path
    #                     obj.FULL_NAME = plugin_name
    #
    #                     libs_found.append((module_path, version_found, obj))
    #                     version_found = True
    #                     break
    #
    #     if not libs_found:
    #         LOGGER.warning('No libraries found in module "{}". Skipping ...'.format(plugin_path))
    #         return False
    #     if len(libs_found) > 1:
    #         LOGGER.warning(
    #             'Multiple libraries found ({}) in module "{}". Loading first one. {} ...'.format(
    #                 len(libs_found), plugin_path, libs_found[-1]))
    #         lib_found = libs_found[-1]
    #     else:
    #         lib_found = libs_found[0]
    #     lib_loader = modules.convert_to_dotted_path(lib_found[0])
    #     lib_loader = loader.find_loader(lib_loader)
    #
    #     # # Check if DCC specific implementation for plugin exists
    #     # dcc_path = '{}.dccs.{}'.format(plugin_name, dcc.get_name())
    #     # dcc_loader = None
    #     # dcc_config = None
    #     # try:
    #     #     dcc_loader = loader.find_loader(dcc_path)
    #     # except ImportError:
    #     #     pass
    #
    #     lib_config_dict = lib_found[2].config_dict(file_name=plugin_path) or dict()
    #     lib_id = lib_config_dict['id']
    #     _tool_name = lib_config_dict['name']
    #
    #     tool_config_name = plugin_name.replace('.', '-')
    #     lib_config = configs.get_config(
    #         config_name=tool_config_name, package_name=pkg_name, root_package_name=root_pkg_name,
    #         environment=environment, config_dict=config_dict, extra_data=lib_config_dict)
    #
    #     # if dcc_loader:
    #     #     dcc_path = dcc_loader.fullname
    #     #     dcc_config = configs.get_config(
    #     #         config_name=dcc_path.replace('.', '-'), package_name=pkg_name,
    #     #         environment=environment, config_dict=config_dict)
    #     #     if not dcc_config.get_path():
    #     #         dcc_config = None
    #
    #     # Register resources
    #     def_resources_path = os.path.join(plugin_path, 'resources')
    #     # resources_path = plugin_config.data.get('resources_path', def_resources_path)
    #     resources_path = lib_config_dict.get('resources_path', None)
    #     if not resources_path or not os.path.isdir(resources_path):
    #         resources_path = def_resources_path
    #     if os.path.isdir(resources_path):
    #         resources.register_resource(resources_path, key='tools')
    #     else:
    #         pass
    #         # tp.logger.debug('No resources directory found for plugin "{}" ...'.format(_plugin_name))
    #
    #     # # Register DCC specific resources
    #     # if dcc_loader and dcc_config:
    #     #     def_resources_path = os.path.join(dcc_loader.filename, 'resources')
    #     #     resources_path = dcc_config.data.get('resources_path', def_resources_path)
    #     #     if not resources_path or not os.path.isdir(resources_path):
    #     #         resources_path = def_resources_path
    #     #     if os.path.isdir(resources_path):
    #     #         resources.register_resource(resources_path, key='plugins')
    #     #     else:
    #     #         pass
    #     #         # tp.logger.debug('No resources directory found for plugin "{}" ...'.format(_plugin_name))
    #
    #     # Create lib loggers directory
    #     default_logger_dir = os.path.normpath(os.path.join(os.path.expanduser('~'), 'tpDcc', 'logs', 'libs'))
    #     default_logging_config = os.path.join(plugin_path, '__logging__.ini')
    #     logger_dir = lib_config_dict.get('logger_dir', default_logger_dir)
    #     if not os.path.isdir(logger_dir):
    #         os.makedirs(logger_dir)
    #     logging_file = lib_config_dict.get('logging_file', default_logging_config)
    #
    #     lib_package = plugin_name
    #     lib_package_path = plugin_path
    #     # dcc_package = None
    #     # dcc_package_path = None
    #     # if dcc_loader:
    #     #     dcc_package = dcc_loader.fullname if python.is_python2() else dcc_loader.loader.path
    #     #     dcc_package_path = dcc_loader.filename if python.is_python2() else dcc_loader.loader.name
    #
    #     self._plugins[pkg_name][lib_id] = {
    #         'name': _tool_name,
    #         'package_name': pkg_name,
    #         'loader': package_loader,
    #         'config': lib_config,
    #         'config_dict': lib_config_dict,
    #         'plugin_loader': lib_loader,
    #         'plugin_package': lib_package,
    #         'plugin_package_path': lib_package_path,
    #         'version': lib_found[1] if lib_found[1] is not None else "0.0.0",
    #         # 'dcc_loader': dcc_loader,
    #         # 'dcc_package': dcc_package,
    #         # 'dcc_package_path': dcc_package_path,
    #         # 'dcc_config': dcc_config,
    #         'logging_file': logging_file,
    #         'plugin_instance': None
    #     }
    #
    #     if init_fn:
    #         try:
    #             dev = True if environment == 'development' else False
    #             init_fn(dev=dev)
    #             LOGGER.info('Library "{}" registered and initialized successfully!'.format(plugin_name))
    #         except Exception:
    #             LOGGER.warning(
    #                 'Library "{}" registered successfully but its initialization failed: {}'.format(
    #                     plugin_name, traceback.format_exc()))
    #     else:
    #         LOGGER.info('Library "{}" registered successfully!'.format(plugin_name))
    #
    #     return True

    def get_library_settings_file_path(self, library_id):
        """
        Returns the path where library settings file is located
        :param library_id:
        :return: str
        """

        settings_path = path_utils.get_user_data_dir(appname=library_id)
        settings_file = path_utils.clean_path(os.path.expandvars(os.path.join(settings_path, 'settings.cfg')))

        return settings_file
    #
    # def get_library_settings_file(self, library_id):
    #     """
    #     Returns the settings file of the given library
    #     :param library_id: str
    #     :return: settings.JSonSettings
    #     """
    #
    #     settings_file = self.get_library_settings_file_path(library_id)
    #
    #     return settings.JSONSettings(filename=settings_file)

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
            LOGGER.warning('No libraries found in package "{}"'.format(package_name))

        found_libs = list(set(found_libs))
        self.register_paths(found_libs, package_name=package_name)

        # Once plugins are registered we load them
        plugins = self.plugins(package_name=package_name)
        for plugin in plugins:
            plugin.load()
