#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains DCC core client implementation
"""

from __future__ import print_function, division, absolute_import

import os
import sys
import time
import json
import socket
import inspect
import pkgutil
import logging
import importlib
import traceback
from collections import OrderedDict

from Qt.QtCore import Signal, QObject

from tpDcc import dcc
import tpDcc.loader
import tpDcc.libs.python
import tpDcc.libs.resources
from tpDcc.core import server, dcc as core_dcc
from tpDcc.managers import configs
from tpDcc.libs.python import python, osplatform, process, path as path_utils

if sys.version_info[0] == 2:
    from socket import error as ConnectionRefusedError

logger = logging.getLogger('tpDcc-core')


class BaseClient(QObject):

    PORT = 17344
    HEADER_SIZE = 10

    class Status(object):
        ERROR = 'error'
        WARNING = 'warning'
        SUCCESS = 'success'
        UNKNOWN = 'unknown'

    def __init__(self, timeout=20):
        super(BaseClient, self).__init__()

        self._timeout = timeout
        self._port = None
        self._discard_count = 0
        self._server = None
        self._connected = False
        self._status = dict()

    def __getattribute__(self, name):
        try:
            attr = super(BaseClient, self).__getattribute__(name)
        except AttributeError:
            def new_fn(*args, **kwargs):
                cmd = {
                    'cmd': name,
                    'args': args
                }
                cmd.update(kwargs)
                reply_dict = self.send(cmd)
                if not self.is_valid_reply(reply_dict):
                    return False
                return reply_dict['result']
            return new_fn

        return attr

    # =================================================================================================================
    # PROPERTIES
    # =================================================================================================================

    @property
    def server(self):
        return self._server

    @property
    def connected(self):
        return self._connected

    # =================================================================================================================
    # BASE
    # =================================================================================================================

    @classmethod
    def create(cls, *args, **kwargs):

        client = cls()

        return client

    @classmethod
    def create_and_connect_to_server(cls, tool_id, *args, **kwargs):

        client = cls.create(*args, **kwargs)

        client._connect()

        return client

    def set_server(self, server):
        self._server = server

    def is_valid_reply(self, reply_dict):
        if not reply_dict:
            logger.debug('Invalid reply')
            return False

        if not reply_dict['success']:
            logger.error('{} failed: {}'.format(reply_dict['cmd'], reply_dict['msg']))
            return False

        self._status = reply_dict.pop(
            'status', None) or {'msg': self.get_status_message(), 'level': self.get_status_level()}

        return True

    def ping(self):
        cmd = {
            'cmd': 'ping'
        }

        reply = self.send(cmd)

        if not self.is_valid_reply(reply):
            return False

        return True

    def get_status_message(self):
        """
        Returns current client status message
        :return: str
        """

        return self._status.get('msg', '')

    def get_status_level(self):
        """
        Returns current client status level
        :return: str
        """

        return self._status.get('level', self.Status.UNKNOWN)

    def set_status(self, status_message, status_level):
        """
        Sets current client status
        :param status_message: str
        :param status_level: str
        """

        self._status = {'msg': str(status_message), 'level': status_level}

    def send(self, cmd_dict):
        json_cmd = json.dumps(cmd_dict)

        # If we use execute the tool inside DCC we execute client/server in same process. We can just launch the
        # function in the server
        if self._server:
            reply_json = self._server._process_data(cmd_dict)
            if not reply_json:
                self._status = None
                return {'success': False}
            return json.loads(reply_json)
        else:
            if not self._connected:
                return self.send_command(cmd_dict)

            message = list()
            message.append('{0:10d}'.format(len(json_cmd.encode())))    # header (10 bytes)
            message.append(json_cmd)

            try:
                msg_str = ''.join(message)
                self._client_socket.sendall(msg_str.encode())
            except OSError as exc:
                logger.debug(exc)
                return None
            except Exception:
                logger.exception(traceback.format_exc())
                return None

            res = self.recv()
            self._status = res.pop('status', dict())

            return res

    def send_command(self, cmd_dict):
        pass

    def recv(self):
        total_data = list()
        reply_length = 0
        bytes_remaining = self.__class__.HEADER_SIZE

        start_time = time.time()
        while time.time() - start_time < self._timeout:
            try:
                data = self._client_socket.recv(bytes_remaining)
            except Exception as exc:
                time.sleep(0.01)
                print(exc)
                continue

            if data:
                total_data.append(data)
                bytes_remaining -= len(data)
                if bytes_remaining <= 0:
                    for i in range(len(total_data)):
                        total_data[i] = total_data[i].decode()

                    if reply_length == 0:
                        header = ''.join(total_data)
                        reply_length = int(header)
                        bytes_remaining = reply_length
                        total_data = list()
                    else:
                        if self._discard_count > 0:
                            self._discard_count -= 1
                            return self.recv()

                        reply_json = ''.join(total_data)
                        return json.loads(reply_json)

        self._discard_count += 1

        # If timeout is checked, before raising timeout we make sure that all remaining data is processed
        data = None
        try:
            data = self._client_socket.recv(bytes_remaining)
        except Exception as exc:
            time.sleep(0.01)
            print(exc)
        if data:
            total_data.append(data)
            bytes_remaining -= len(data)
            if bytes_remaining <= 0:
                for i in range(len(total_data)):
                    total_data[i] = total_data[i].decode()

                if reply_length == 0:
                    header = ''.join(total_data)
                    reply_length = int(header)
                else:
                    self._discard_count -= 1
                    reply_json = ''.join(total_data)
                    return json.loads(reply_json)

        raise RuntimeError('Timeout waiting for response')

    def _disconnect(self):
        try:
            self._client_socket.close()
        except Exception:
            traceback.print_exc()
            self._status = {'msg': 'Error while disconnecting client', 'level': self.Status.ERROR}
            return False

        return True

    # =================================================================================================================
    # INTERNAL
    # =================================================================================================================

    def _connect(self):

        self._port = self.PORT

        try:
            self._client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._client_socket.connect(('localhost', self._port))
            # self._client_socket.setblocking(False)
        except ConnectionRefusedError as exc:
            # LOGGER.warning(exc)
            self._status = {'msg': 'Client connection was refused.', 'level': self.Status.WARNING}
            self._connected = False
            return False
        except Exception:
            logger.exception(traceback.format_exc())
            self._status = {'msg': 'Error while connecting client', 'level': self.Status.ERROR}
            self._connected = False
            return False

        self._connected = True

        return True


class DccClient(BaseClient):
    dccDisconnected = Signal()
    callbackSended = Signal(object, str)

    def __init__(self, timeout=20, tool_id=None):
        super(DccClient, self).__init__(timeout=timeout)

        self._tool_id = tool_id or None
        self._port = core_dcc.dcc_port(self.__class__.PORT)

        self._client_sockets = dict()
        self._running_dccs = list()

    # =================================================================================================================
    # OVERRIDES
    # =================================================================================================================

    @classmethod
    def create(cls, tool_id, *args, **kwargs):

        # If a client with given ID is already registered, we return it
        client = dcc.client(tool_id, only_clients=True)
        if client:
            return client

        client = cls(tool_id=tool_id)

        return client

    def _disconnect(self):
        valid = super(DccClient, self).disconnect()
        if valid:
            self.dccDisconnected.emit()

        return valid

    # =================================================================================================================
    # BASE
    # =================================================================================================================

    @classmethod
    def _register_client(cls, tool_id, client):
        """
        Internal function that registers given client in global Dcc clients variable
        """

        if not client:
            return
        client_found = False
        current_clients = dcc._CLIENTS
        for current_client in list(current_clients.values()):
            if client == current_client():
                client_found = True
                break
        if client_found:
            return
        dcc._CLIENTS[tool_id] = client

    @classmethod
    def create_and_connect_to_server(cls, tool_id, *args, **kwargs):

        client = cls.create(tool_id, *args, **kwargs)

        parent = kwargs.get('parent', None)
        server_class_name = kwargs.get('server_name', cls.__name__.replace(
            'Client', 'Server').replace('client', 'server'))
        server_module_name = kwargs.get('server_module_name', 'server')

        if not dcc.is_standalone():
            dcc_mod_name = '{}.dccs.{}.{}'.format(tool_id.replace('-', '.'), dcc.get_name(), server_module_name)
            try:
                mod = importlib.import_module(dcc_mod_name)
                if hasattr(mod, server_class_name):
                    server = getattr(mod, server_class_name)(parent, client=client, update_paths=False)
                    client.set_server(server)
                    client.update_client(tool_id=tool_id, **kwargs)
            except Exception as exc:
                logger.warning(
                    'Impossible to launch tool server! Error while importing: {} >> {}'.format(dcc_mod_name, exc))
                try:
                    server.close_connection()
                except Exception:
                    pass
                return None
        else:
            client._connect(**kwargs)
            client.update_client(tool_id=tool_id, **kwargs)

        return client

    def update_client(self, **kwargs):
        tool_id = kwargs.get('tool_id', None)
        config_dict = configs.get_tool_config(tool_id) or dict() if tool_id else dict()
        supported_dccs = config_dict.get(
            'supported_dccs', dict()) if config_dict else kwargs.get('supported_dccs', dict())

        if not self.connected:
            self.set_status('Not connected to any DCC', self.Status.WARNING)
            return False

        if dcc.is_standalone():
            success, dcc_exe = self.update_paths()
            if not success:
                return False

            success = self.update_dcc_paths(dcc_exe)
            if not success:
                return False

            success = self.init_dcc()
            if not success:
                return False

        dcc_name, dcc_version, dcc_pid = self.get_dcc_info()
        if not dcc_name or not dcc_version:
            return False

        if dcc_name not in supported_dccs:
            self.set_status(
                'Connected DCC {} ({}) is not supported!'.format(dcc_name, dcc_version), self.Status.WARNING)
            return False

        supported_versions = supported_dccs[dcc_name]
        if dcc_version not in supported_versions:
            self.set_status(
                'Connected DCC {} is support but version {} is not!'.format(
                    dcc_name, dcc_version), self.Status.WARNING)
            return False

        msg = 'Connected to: {} {} ({})'.format(dcc_name, dcc_version, dcc_pid)
        self.set_status(msg, self.Status.SUCCESS)
        logger.info(msg)

        if tool_id:
            DccClient._register_client(tool_id, self)

    def _connect(self, **kwargs):

        def _connect(_port):
            try:
                self._client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._client_socket.connect(('localhost', _port))
                # self._client_socket.setblocking(False)
            except ConnectionRefusedError as exc:
                # LOGGER.warning(exc)
                self._status = {'msg': 'Client connection was refused.', 'level': self.Status.WARNING}
                self._connected = False
                return False
            except Exception:
                logger.exception(traceback.format_exc())
                self._status = {'msg': 'Error while connecting client', 'level': self.Status.ERROR}
                self._connected = False
                return False
            return True

        if self._server:
            self._status = {'msg': 'Client connected successfully!', 'level': self.Status.SUCCESS}
            self._connected = True
            return True

        connect_client = kwargs.pop('connect_client', True)
        if not connect_client:
            self._connected = False
            return True

        # # If we pass a port, we just connect to it
        # if port > 0:
        #     self._port = port
        #     self._connected = _connect(port)
        #     return self._connected

        supported_dccs = None
        tool_id = self._tool_id
        if tool_id:
            config_dict = configs.get_tool_config(tool_id) or dict() if tool_id else dict()
            supported_dccs = config_dict.get(
                'supported_dccs', dict()) if config_dict else dict()

        force_dcc = kwargs.get('dcc', None)
        if force_dcc and force_dcc in supported_dccs:
            self._port = core_dcc.dcc_port(self.PORT, dcc_name=force_dcc)
            self._create_callbacks_server()
            valid_connect = _connect(self._port)
            if valid_connect:
                self._connected = True
        else:
            # If no port if given, we check which DCCs are running the user machine and we try to connect
            # to those ports
            self._running_dccs = list()
            for dcc_name in core_dcc.Dccs.ALL:

                if supported_dccs and dcc_name not in supported_dccs:
                    continue

                process_name = core_dcc.Dccs.executables.get(dcc_name, dict()).get(osplatform.get_platform(), None)
                if not process_name:
                    continue
                process_running = process.check_if_process_is_running(process_name)
                if not process_running:
                    continue
                self._running_dccs.append(dcc_name)
            if not self._running_dccs:
                self._port = self.PORT
                self._connected = _connect(self._port)
            else:
                for dcc_name in self._running_dccs:
                    self._port = core_dcc.dcc_port(self.PORT, dcc_name=dcc_name)
                    self._create_callbacks_server()
                    valid_connect = _connect(self._port)
                    if valid_connect:
                        self._connected = True
                        break

        return self._connected

    def send_command(self, cmd_dict):
        cmd = cmd_dict.pop('cmd', None)
        if cmd and hasattr(dcc, cmd):
            try:
                res = getattr(dcc, cmd)(**cmd_dict)
            except TypeError:
                if python.is_python2():
                    function_kwargs = inspect.getargspec(getattr(dcc, cmd))
                    plugin_kwargs = function_kwargs.args
                    if not function_kwargs:
                        res = getattr(dcc, cmd)()
                    else:
                        valid_kwargs = dict()
                        for kwarg_name, kwarg_value in cmd_dict.items():
                            if kwarg_name in plugin_kwargs:
                                valid_kwargs[kwarg_name] = kwarg_value
                        res = getattr(dcc, cmd)(**valid_kwargs)
                else:
                    function_signature = inspect.signature(getattr(dcc, cmd))
                    if not function_signature.parameters:
                        res = getattr(dcc, cmd)()
                    else:
                        valid_kwargs = dict()
                        for kwarg_name, kwarg_value in function_signature.parameters.items():
                            if kwarg_name in cmd_dict:
                                valid_kwargs[kwarg_name] = cmd_dict[kwarg_name]
                        res = getattr(dcc, cmd)(**valid_kwargs)
            if res is not None:
                return {'success': True, 'result': res}

        return None

    def update_paths(self):

        paths_to_update = self._get_paths_to_update()

        cmd = {
            'cmd': 'update_paths',
            # NOTE: The order is SUPER important, we must load the modules in the client in the same order
            'paths': OrderedDict(paths_to_update)
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            self._status = {'msg': 'Error while connecting to Dcc: update paths ...', 'level': self.Status.ERROR}
            return False, None

        exe = reply_dict.get('exe', None)

        return reply_dict['success'], exe

    def update_dcc_paths(self, dcc_executable):
        if not dcc_executable:
            return False

        dcc_name = None
        if 'maya' in dcc_executable:
            dcc_name = core_dcc.Dccs.Maya
        elif '3dsmax' in dcc_executable:
            dcc_name = core_dcc.Dccs.Max
        elif 'houdini' in dcc_executable:
            dcc_name = core_dcc.Dccs.Houdini
        elif 'nuke' in dcc_executable:
            dcc_name = core_dcc.Dccs.Nuke
        elif 'unreal' in dcc_executable or os.path.basename(dcc_executable).startswith('UE'):
            dcc_name = core_dcc.Dccs.Unreal
        if not dcc_name:
            msg = 'Executable DCC {} is not supported!'.format(dcc_executable)
            logger.warning(msg)
            self._status = {'msg': msg, 'level': self.Status.WARNING}
            return False

        module_name = 'tpDcc.dccs.{}.loader'.format(dcc_name)
        try:
            mod = pkgutil.get_loader(module_name)
        except Exception:
            try:
                self._status = {
                    'msg': 'Error while connecting to Dcc: update dcc paths ...', 'severity': self.Status.ERROR}
                logger.error('FAILED IMPORT: {} -> {}'.format(str(module_name), str(traceback.format_exc())))
                return False
            except Exception:
                self._status = {
                    'msg': 'Error while connecting to Dcc: update dcc paths ...', 'severity': self.Status.ERROR}
                logger.error('FAILED IMPORT: {}'.format(module_name))
                return False
        if not mod:
            msg = 'Impossible to import DCC specific module: {} ({})'.format(module_name, dcc_name)
            logger.warning(msg)
            self._status = {'msg': msg, 'severity': self.Status.WARNING}
            return False

        cmd = {
            'cmd': 'update_dcc_paths',
            'paths': OrderedDict({
                'tpDcc.dccs.{}'.format(dcc_name): path_utils.clean_path(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(mod.get_filename())))))
            })
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            self._status = {
                'msg': 'Error while connecting to Dcc: update dcc paths ...', 'level': self.Status.ERROR}
            return False

        return reply_dict['success']

    def init_dcc(self):
        cmd = {
            'cmd': 'init_dcc'
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            self._status = {'msg': 'Error while connecting to Dcc: init dcc ...', 'level': self.Status.ERROR}
            return False

        return reply_dict['success']

    def get_dcc_info(self):
        cmd = {
            'cmd': 'get_dcc_info'
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            self._status = {'msg': 'Error while connecting to Dcc: get dcc info ...', 'level': self.Status.ERROR}
            return None, None, None

        return reply_dict['name'], reply_dict['version'], reply_dict['pid']

    def select_node(self, node, **kwargs):
        cmd = {
            'cmd': 'select_node',
            'node': node
        }
        cmd.update(**kwargs)

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            return False

        return reply_dict['success']

    def selected_nodes(self, full_path=True):
        cmd = {
            'cmd': 'selected_nodes',
            'full_path': full_path
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            return list()

        return reply_dict.get('result', list())

    def clear_selection(self):
        cmd = {
            'cmd': 'clear_selection'
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            return False

        return reply_dict['success']

    def get_control_colors(self):
        cmd = {
            'cmd': 'get_control_colors'
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            return list()

        return reply_dict.get('result', list())

    def get_fonts(self):
        cmd = {
            'cmd': 'get_fonts'
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            return list()

        return reply_dict.get('result', list())

    def enable_undo(self):
        cmd = {
            'cmd': 'enable_undo'
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            return list()

        return reply_dict['success']

    def disable_undo(self):
        cmd = {
            'cmd': 'disable_undo'
        }

        reply_dict = self.send(cmd)

        if not self.is_valid_reply(reply_dict):
            return list()

        return reply_dict['success']

    # =================================================================================================================
    # INTERNAL
    # =================================================================================================================

    def _get_paths_to_update(self):
        """
        Internal function that returns all the paths that DCC server should include to properly work with the client
        """

        return {
            'tpDcc.loader': path_utils.clean_path(os.path.dirname(os.path.dirname(tpDcc.loader.__file__))),
            'tpDcc.libs.python': path_utils.clean_path(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(tpDcc.libs.python.__file__))))),
            'tpDcc.libs.resources': path_utils.clean_path(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(tpDcc.libs.resources.__file__))))),
            'tpDcc.libs.qt.loader': path_utils.clean_path(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(tpDcc.libs.qt.__file__)))))
        }

    def _create_callbacks_server(self):
        self._callbacks_server = server.CallbackServer(base_port=self._port or self.PORT, parent=self)
        self._callbacks_server.callbackSended.connect(self.callbackSended.emit)


class CallbackClient(BaseClient):

    def __init__(self, base_port, timeout=20):

        self.PORT = base_port - len(core_dcc.Dccs.ALL)

        super(CallbackClient, self).__init__(timeout=timeout)

    def send_callback(self, value, callback_type):
        cmd = {
            'cmd': 'send_callback',
            'value': value,
            'callback_type': callback_type
        }

        reply = self.send(cmd)

        if not self.is_valid_reply(reply):
            return False

        return True


class ExampleClient(BaseClient):

    PORT = 17337

    def echo(self, text):
        cmd_dict = {
            'cmd': 'echo',
            'text': text
        }

        reply_dict = self.send(cmd_dict)

        if not self.is_valid_reply(reply_dict):
            return None

        return reply_dict['result']

    def set_title(self, title):
        cmd_dict = {
            'cmd': 'set_title',
            'title': title
        }

        reply_dict = self.send(cmd_dict)

        if not self.is_valid_reply(reply_dict):
            return None

        return reply_dict['result']

    def sleep(self):
        cmd_dict = {
            'cmd': 'sleep'
        }

        reply_dict = self.send(cmd_dict)

        if not self.is_valid_reply(reply_dict):
            return None

        return reply_dict['result']


if __name__ == '__main__':
    client = ExampleClient(timeout=10)
    if client._connect():
        print('Connected successfully!')

        print(client.ping())
        print(client.echo('Hello World!'))
        print(client.set_title('New Server Title'))
        print(client.sleep())

        if client._disconnect():
            print('Disconnected successfully!')
    else:
        print('Failed to connect')
