#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains classes to create editor tools inside Qt apps
"""

from __future__ import print_function, division, absolute_import

import os
import sys
import time
import inspect
import logging
import traceback
from functools import partial

from tpDcc import dcc
from tpDcc.dcc import window
from tpDcc.managers import resources, configs
from tpDcc.libs.python import decorators, version, modules

logger = logging.getLogger('tpDcc-core')


class DccTool(object):
    """
    Base class used by all editor tools
    """

    ID = None
    PACKAGE = None
    VERSION = None

    TOOLSET_CLASS = None

    CLIENT_CLASS = None
    SERVER_NAME = None
    SERVER_MODULE_NAME = None

    def __init__(self, settings=None, dev=False, *args, **kwargs):
        super(DccTool, self).__init__()

        self._tool = list()
        self._config = kwargs.pop('config', None)
        self._bootstrap = list()
        self._attacher = None
        self._client = None
        self._client_status = None
        self._is_frameless = True
        # self._is_frameless = self.config_dict().get('is_checked', False)
        self._settings = settings
        self._stats = ToolStats(self)
        self._dev = dev

        self._setup_client(*args, **kwargs)

        # Config is setup after the client is connected, because we need to know if we need to load app
        # DCC specific configuration or not
        self._setup_config()

    @property
    def attacher(self):
        return self._attacher

    @property
    def config(self):
        return self._config

    @property
    def settings(self):
        return self._settings

    @property
    def attacher(self):
        return self._attacher

    @property
    def stats(self):
        return self._stats

    @property
    def is_frameless(self):
        return self._is_frameless

    @property
    def dev(self):
        return self._dev

    @property
    def name(self):
        return self.config_dict().get('name')

    @property
    def default_size(self):
        return self.config_dict().get('size')

    @decorators.abstractmethod
    def launch(self, *args, **kwargs):
        """
        Launches the tool
        """

        pass

    @classmethod
    def version(cls):

        if cls.VERSION is not None:
            return cls.VERSION

        cls.VERSION = '0.0.0'

        if hasattr(cls, 'ROOT') and os.path.isdir(cls.ROOT):
            version_module_file = os.path.join(cls.ROOT, '_version.py')
            if os.path.isfile(version_module_file):
                try:
                    version_module = modules.import_module(version_module_file)
                    if version_module:
                        cls.VERSION = version.SemanticVersion.from_pep440_string(
                            version_module.get_versions()['version'])
                except Exception as exc:
                    logger.debug('Impossible to retrieve version for "{}" | {}'.format(cls.ID, exc))

        return cls.VERSION

    @staticmethod
    def creator():
        """
        Returns tool creator
        :return: str
        """

        return ''

    @staticmethod
    def icon():
        """
        Returns the icon of the tool
        :return: QIcon or None
        """

        return None

    @classmethod
    def config_dict(cls, file_name=None):
        """
        Returns internal tool configuration dictionary
        :return: dict
        """

        return {
            'name': 'DccTool',
            'id': cls.ID,
            'supported_dccs': dict(),
            'creator': 'Tomas Poveda',
            'icon': 'tpdcc',
            'tooltip': '',
            'help_url': 'www.tomipoveda.com',
            'tags': ['tpDcc', 'dcc', 'tool'],
            'is_checkable': False,
            'is_checked': False,
            'frameless': {
                'enabled': True,
                'force': False
            },
            'dock': {
                'dockable': True,
                'tabToControl': ('AttributeEditor', -1),
                'floating': False,
                'multiple_tools': False
            },
            'menu_ui': {
                'label': 'tpDcc',
                'load_on_startup': False,
                'color': '',
                'background_color': ''
            },
            'menu': [
                {
                    'type': 'menu',
                    'children': [
                        {
                            'id': 'tpDcc-tools-tool',
                            'type': 'tool'
                        }
                    ]
                }
            ],
            'shelf': [
                {
                    'name': 'tpDcc',
                    'children': [
                        {
                            'id': 'tpDcc-tools-tool',
                            'display_label': False,
                            'type': 'tool'
                        }
                    ]
                }
            ]
        }

    def unique_name(self):
        """
        Returns unique name of the tool
        When a tool is not singleton, we need to store separate data for each instance.
        We use unique identifier for that
        :return: str
        """

        return '::{}'.format(self.ID)

    def launch_frameless(self, *args, **kwargs):
        """
        Laucnhes the tool and applies frameless functionality to it
        :param args: tuple, dictionary of arguments to launch the tool
        :param kwargs: dict
        :return: dict
        """

        launch_frameless = kwargs.get('launch_frameless', None)
        frameless_active = launch_frameless if launch_frameless is not None else self._is_frameless

        tool = self.run_tool(frameless_active, kwargs)

        ret = {'tool': tool, 'bootstrap': None}
        if hasattr(tool, 'closed'):
            self._settings.set('dockable', not frameless_active)
            self._tool.append(ret)
            tool.closed.connect(partial(self._on_tool_closed, ret))

        return ret

    def run_tool(self, frameless_active=True, tool_kwargs=None, attacher_class=None):
        """
        Function that launches current tool
        :param frameless_active: bool, Whether the tool will be launch in frameless mode or not
        :param tool_kwargs: dict, dictionary of arguments to launch tool with
        :return:
        """

        tool_config_dict = self.config_dict()
        tool_name = tool_config_dict.get('name', None)
        tool_id = tool_config_dict.get('id', None)
        tool_size = tool_config_dict.get('size', None)
        if not tool_name or not tool_id:
            logger.warning('Impossible to run tool "{}" with id: "{}"'.format(tool_name, tool_id))
            return None

        toolset_class = self.TOOLSET_CLASS
        if not toolset_class:
            logger.warning('Impossible to run tool! Tool "{}" does not define a toolset class.'.format(self.ID))
            return None
        # toolset_data_copy = copy.deepcopy(self._config.data)
        # toolset_data_copy.update(toolset_class.CONFIG.data)
        # toolset_class.CONFIG.data = toolset_data_copy

        if tool_kwargs is None:
            tool_kwargs = dict()

        tool_kwargs['collapsable'] = False
        tool_kwargs['show_item_icon'] = False

        if not attacher_class:
            attacher_class = window.Window

        toolset_inst = toolset_class(**tool_kwargs)
        toolset_inst.ID = tool_id
        toolset_inst.CONFIG = tool_config_dict
        toolset_inst.initialize(client=self._client)

        # noinspection PyArgumentList
        self._attacher = attacher_class(
            id=tool_id, title=self.name, config=self.config, settings=self.settings,
            show_on_initialize=False, frameless=self.is_frameless, dockable=True, toolset=toolset_inst,
            icon=resources.icon(tool_config_dict.get('icon', 'tpdcc')))

        toolset_inst.set_attacher(self._attacher)
        # self._attacher.setWindowIcon(toolset_inst.get_icon())
        self._attacher.setWindowTitle('{} - {}'.format(self._attacher.windowTitle(), self.VERSION))
        if tool_size:
            self._attacher.resize(tool_size[0], tool_size[1])

        self._attacher.show()

        return self._attacher

    def latest_tool(self):
        """
        Returns latest added tool
        """

        try:
            return self._tool[-1]['tool']
        except IndexError:
            return None

    def set_frameless(self, tool, frameless):
        pass

    def cleanup(self):
        """
        Internal function that clears tool data
        """

        try:
            self.cleanup()
        except RuntimeError:
            logger.error('Failed to cleanup plugin: {}'.format(self.ID), exc_info=True)
        finally:
            try:
                for widget in self._bootstrap:
                    widget.close()
            except RuntimeError:
                logger.error('Tool Widget already deleted: {}'.format(self._bootstrap), exc_info=True)
            except Exception:
                logger.error('Failed to remove tool widget: {}'.format(self._bootstrap), exc_info=True)

    # =================================================================================================================
    # INTERNAL
    # =================================================================================================================

    def _setup_client(self, *args, **kwargs):
        """
        Internal function that is called to setup the client of the tool
        """

        if not self.CLIENT_CLASS:
            return False

        self._client = self.CLIENT_CLASS.create_and_connect_to_server(self.ID, *args, **kwargs)

        return True

    def _setup_config(self):
        """
        Internal function that sets the configuration of the tool
        """

        self._config = self._config or configs.get_tool_config(self.ID, self.PACKAGE)

    def _launch(self, *args, **kwargs):
        """
        Internal function for launching the tool
        :return:
        """

        self._stats.start_time = time.time()
        exc_type, exc_value, exc_tb = None, None, None
        try:
            kwargs['settings'] = self._settings
            kwargs['config'] = self._config
            kwargs['dev'] = self._dev
            tool_data = self.launch(*args, **kwargs)
            if tool_data and tool_data.get('tool') is not None:
                tool_data['tool'].ID = self.ID
                tool_data['tool'].PACKAGE = self.PACKAGE
                if self._settings.get('dockable', False):
                    uid = None
                    # TODO: Add option in settings to check if a tool can be opened multiple times or not
                    # TODO: Make this piece of code DCC agnostic
                    # if multiple_tools:
                    #     uid = "{0} [{1}]".format(self.uiData["label"], str(uuid.uuid4()))
                    ui_label = self._config.get('name', default='')
                    ui_icon = self._config.get('icon', default='tpdcc')
                    if dcc.is_maya():
                        from tpDcc.dccs.maya.ui import window
                        bootstrap_widget = window.BootStrapWidget(
                            tool_data['tool'], title=ui_label, icon=resources.icon(ui_icon), uid=uid)
                        tool_data['bootstrap'] = bootstrap_widget
                        tool_data['bootstrap'].show(
                            retain=False, dockable=True, tabToControl=('AttributeEditor', -1), floating=False)
                        self._bootstrap.append(bootstrap_widget)
        except Exception:
            exc_type, exc_value, exc_tb = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_tb)
            raise
        finally:
            tb = None
            if exc_type and exc_value and exc_tb:
                tb = traceback.format_exception(exc_type, exc_value, exc_tb)
            self._stats.finish(tb)

        return tool_data

    # =================================================================================================================
    # CALLBACKS
    # =================================================================================================================

    def _on_tool_closed(self, tool):
        """
        Internal callback function that is called when a tool is closed
        :param tool:
        :return:
        """

        pass


class ToolStats(object):
    def __init__(self, tool):
        self._tool = tool
        self._id = self._tool.ID
        self._start_time = 0.0
        self._end_time = 0.0
        self._execution_time = 0.0

        self._info = dict()

        self._init()

    @property
    def start_time(self):
        return self._start_time

    @start_time.setter
    def start_time(self, value):
        self._start_time = value

    @property
    def end_time(self):
        return self._end_time

    @end_time.setter
    def end_time(self, value):
        self._end_time = value

    @property
    def execution_time(self):
        return self._execution_time

    def _init(self):
        """
        Internal function that initializes info for the plugin and its environment
        """

        self._info.update({
            'name': self._tool.__class__.__name__,
            'creator': self._tool.creator(),
            'module': self._tool.__class__.__module__,
            'filepath': inspect.getfile(self._tool.__class__),
            'id': self._id,
            'application': dcc.client().get_name()
        })

    def start(self):
        """
        Starts the execution of the plugin
        """

        self._start_time = time.time()

    def finish(self, trace=None):
        """
        Function that is called when plugin finishes its execution
        :param trace: str or None
        """

        self._end_time = time.time()
        self._execution_time = self._end_time - self._start_time
        self._info['executionTime'] = self._execution_time
        self._info['lastUsed'] = self._end_time
        if trace:
            self._info['traceback'] = trace
