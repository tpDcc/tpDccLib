#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains DCC core server implementation
"""

from __future__ import print_function, division, absolute_import

import os
import sys
import time
import json
import logging
import inspect
import traceback
import importlib
from collections import OrderedDict

try:
    import __builtin__      # Do not remove
except ImportError:
    import builtins as __builtin__

from Qt.QtCore import QObject, QByteArray
from Qt.QtNetwork import QTcpServer, QHostAddress, QTcpSocket

from tpDcc import dcc
from tpDcc.core import dcc as core_dcc

LOGGER = logging.getLogger('tpDcc-core')


class DccServer(QObject, object):

    PORT = 17344           # Base port value, final one will depend on DCC
    HEADER_SIZE = 10

    def __init__(self, parent=None, client=None, update_paths=True):
        super(DccServer, self).__init__(parent)

        self._socket = None
        self._port = core_dcc.dcc_port(self.__class__.PORT)
        self._do_update_paths = update_paths
        self._modules_to_import = list()
        self._client = client
        self._server_functions = dict()
        self._dcc = dcc

        self._retrieved_data = ''
        self._bytes_remaining = -1

        server_functions = inspect.getmembers(self, predicate=inspect.ismethod) or list()
        for server_function_list in server_functions:
            server_function_name = server_function_list[0]
            if server_function_name in ['__init__'] or server_function_name.startswith('_'):
                continue
            self._server_functions[server_function_name] = server_function_list[1]

        self._init()

    # =================================================================================================================
    # PROPERTIES
    # =================================================================================================================

    @property
    def dcc(self):
        return self._dcc

    # =================================================================================================================
    # BASE
    # =================================================================================================================

    def close_connection(self):
        if not self._server:
            return

        self._server.close()

    def select_node(self, data, reply):
        node = data.get('node', None)
        add_to_selection = data.get('add_to_selection', False)
        if node:
            self._dcc.select_node(node)
        reply['success'] = True

    def selected_nodes(self, data, reply):
        full_path = data.get('full_path', True)
        selected_nodes = self._dcc.selected_nodes(full_path=full_path)
        reply['success'] = True
        reply['result'] = selected_nodes

    def clear_selection(self, data, reply):
        self._dcc.clear_selection()
        reply['success'] = True

    def get_control_colors(self, data, reply):
        control_colors = self._dcc.get_control_colors() or list()
        reply['success'] = True
        reply['result'] = control_colors

    def get_fonts(self, data, reply):
        all_fonts = self._dcc.get_all_fonts() or list()
        reply['success'] = True
        reply['result'] = all_fonts

    def enable_undo(self, data, reply):
        self._dcc.enable_undo()
        reply['success'] = True

    def disable_undo(self, data, reply):
        self._dcc.disable_undo()
        reply['success'] = True

    # =================================================================================================================
    # INTERNAL
    # =================================================================================================================

    def _init(self):
        if self._client:
            return

        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_established_connection)

        if self._listen():
            print('[LOG] Server listening on port: {}'.format(self._port))
        else:
            print('[ERROR] Server initialization failed')

    def _listen(self):
        if not self._server.isListening():
            return self._server.listen(QHostAddress.LocalHost, self._port)

        return False

    def _read(self):
        json_data = self._retrieved_data or ''

        while self._socket.bytesAvailable():

            # When no bytes are remaining, we read header from socket, so we can store the total
            # amount of data (in bytes) we expect to retrieve
            if self._bytes_remaining <= 0:
                byte_array = self._socket.read(DccServer.HEADER_SIZE)   # header (10 bytes)
                self._bytes_remaining, valid = byte_array.toInt()
                if not valid:
                    self._bytes_remaining = -1
                    self._write_error('Invalid header')
                    # purge unknown data
                    self._retrieved_data = ''
                    self._socket.readAll()
                    return

            # body (payload)
            # we read data until all expected bytes are read
            if self._bytes_remaining > 0:
                byte_array = self._socket.read(self._bytes_remaining)
                self._bytes_remaining -= len(byte_array)
                json_data += byte_array.data().decode()

                if self._bytes_remaining == 0:
                    self._bytes_remaining = -1
                    data = json.loads(json_data, object_pairs_hook=OrderedDict)
                    self._process_data(data)

                    json_data = ''

        self._retrieved_data = json_data

    def _write(self, reply_dict):

        try:
            json_reply = json.dumps(reply_dict)
        except Exception:
            msg = 'Error while serializing data: "{}"'.format(traceback.format_exc())
            LOGGER.error(msg)
            json_dict = {'result': None, 'success': False, 'msg': msg, 'cmd': reply_dict.get('cmd', 'unknown')}
            json_reply = json.dumps(json_dict)

        if self._socket and self._socket.state() == QTcpSocket.ConnectedState:
            header = '{0}'.format(len(json_reply.encode())).zfill(DccServer.HEADER_SIZE)
            data = QByteArray('{}{}'.format(header, json_reply).encode())
            self._socket.write(data)

        return json_reply

    def _write_error(self, error_msg):
        reply = {
            'success': False,
            'msg': error_msg,
            'cmd': 'unknown'
        }

        self._write(reply)

    def _process_data(self, data_dict):

        self._retrieved_data = ''

        reply = {
            'success': False,
            'msg': '',
            'result': None
        }

        do_write = True
        cmd = data_dict['cmd']
        if cmd == 'ping':
            reply['success'] = True
        elif cmd == 'update_paths':
            self._update_paths(data_dict, reply)
        elif cmd == 'update_dcc_paths':
            self._update_dcc_paths(data_dict, reply)
        elif cmd == 'init_dcc':
            self._init_dcc(data_dict, reply)
        elif cmd == 'get_dcc_info':
            self._get_dcc_info(data_dict, reply)
        else:
            try:
                self._process_command(cmd, data_dict, reply)
            except Exception:
                reply['success'] = False
                reply['msg'] = traceback.format_exc()
            if not reply['success']:
                reply['cmd'] = cmd
                if 'msg' not in reply.keys():
                    reply['msg'] = 'Unknown Error'

        if do_write:
            return self._write(reply)
        else:
            return reply

    def _update_paths(self, data, reply):

        if not self._do_update_paths:
            reply['success'] = True
            reply['exe'] = sys.executable
            return

        paths_data = data.get('paths', dict())
        if not paths_data:
            reply['success'] = False
            return

        paths = paths_data.values()

        # TODO: Remove this ASAP
        # NOTE: For now, we add the dependencies manually
        # In the final package, all dependencies libraries will be stored in a specific folder
        maya_deps_folder = r'D:\tpRigToolkit\venvs\maya_deps'
        paths.insert(0, maya_deps_folder)

        for path in paths:
            if path not in sys.path:
                print('Updating SYS.PATH: {}'.format(path))
                sys.path.append(path)

        # for path_mod in paths_data.keys():
        #     try:
        #         mod = importlib.import_module(path_mod)
        #     except Exception:
        #         try:
        #             print('FAILED IMPORT: {} -> {}'.format(str(path_mod), str(traceback.format_exc())))
        #             continue
        #         except Exception:
        #             print('FAILED IMPORT: {}'.format(path_mod))
        #             continue
        #     self._modules_to_import.append(mod)

        reply['success'] = True
        reply['exe'] = sys.executable

    def _update_dcc_paths(self, data, reply):

        if not self._do_update_paths:
            reply['success'] = True
            return

        paths_data = data.get('paths', dict())
        if not paths_data:
            reply['success'] = False
            return

        paths = paths_data.values()

        for path in paths:
            if path not in sys.path:
                print('Updating SYS.PATH: {}'.format(path))
                sys.path.append(path)

        for path_mod in paths_data.keys():
            try:
                mod = importlib.import_module(path_mod)
            except Exception:
                try:
                    print('FAILED IMPORT: {} -> {}'.format(str(path_mod), str(traceback.format_exc())))
                    continue
                except Exception:
                    print('FAILED IMPORT: {}'.format(path_mod))
                    continue
            self._modules_to_import.append(mod)

        reply['success'] = True

    def _init_dcc(self, data, reply):
        if not self._modules_to_import:
            reply['success'] = False
            return

        # modules_to_import = list()
        # clean_modules_to_import = list(set(self._modules_to_import))
        #
        # # Order modules to import (tpDcc.core, tpDcc.dccs.X, etc)
        # for module in clean_modules_to_import:
        #     if module.__name__ == 'tpDcc.loader' and module not in modules_to_import:
        #         modules_to_import.append(module)
        #         break
        # for module in clean_modules_to_import:
        #     if module.__name__.startswith('tpDcc.dccs.') and module not in modules_to_import:
        #         modules_to_import.append(module)
        # for module in clean_modules_to_import:
        #     if module not in self._modules_to_import:
        #         modules_to_import.append(module)
        #
        # for module in modules_to_import:
        #     if hasattr(module, 'init'):
        #         module.init()

        from tpDcc import dcc
        self._dcc = dcc

        reply['success'] = True

    def _get_dcc_info(self, data, reply):

        import tpDcc

        bultins_ = {'tp': tpDcc}
        for builtin in bultins_:
            try:
                exec('del(__builtin__.%s)' % builtin)
            except Exception:
                pass
            builtin_value = bultins_[builtin]
            exec('__builtin__.%s = builtin_value' % builtin)

        # NOTE: tp is imported dynamically
        dcc_name = self._dcc.get_name()
        dcc_version = self._dcc.get_version_name()

        reply['success'] = True
        reply['name'] = dcc_name
        reply['version'] = dcc_version
        reply['pid'] = os.getpid()

    def _process_command(self, command_name, data_dict, reply_dict):
        if command_name in self._server_functions:
            self._server_functions[command_name](data_dict, reply_dict)
        elif self._dcc and hasattr(self._dcc, command_name):
            reply_dict['success'] = True
            dcc_fn = getattr(self._dcc, command_name)
            args, varargs, varkw, defaults = inspect.getargspec(dcc_fn)
            if not varkw:
                reply_dict['result'] = getattr(self._dcc, command_name)()
            else:
                data_dict.pop('cmd', None)
                args = data_dict.pop('args', list())
                try:
                    reply_dict['result'] = getattr(self._dcc, command_name)(*args, **data_dict)
                except Exception as exc:
                    print(exc)
                except TypeError:
                    try:
                        reply_dict['result'] = getattr(self._dcc, command_name)(**data_dict)
                    except TypeError:
                        try:
                            reply_dict['result'] = getattr(self._dcc, command_name)(*args)
                        except TypeError:
                            reply_dict['result'] = getattr(self._dcc, command_name)()
        else:
            reply_dict['msg'] = 'Invalid command ({})'.format(command_name)

    # =================================================================================================================
    # CALLBACKS
    # =================================================================================================================

    def _on_established_connection(self):
        self._socket = self._server.nextPendingConnection()
        if self._socket.state() == QTcpSocket.ConnectedState:
            self._socket.disconnected.connect(self._on_disconnected)
            self._socket.readyRead.connect(self._read)
            print('[LOG] Connection established')

    def _on_disconnected(self):
        self._socket.disconnected.disconnect()
        self._socket.readyRead.disconnect()
        self._socket.deleteLater()
        print('[LOG] Connection disconnected')


class ExampleServer(DccServer, object):

    PORT = 17337

    def __init__(self, parent_window):
        super(ExampleServer, self).__init__(parent_window)

        self._window = parent_window

    def _process_command(self, command_name, data_dict, reply_dict):
        if command_name == 'echo':
            self.echo(data_dict, reply_dict)
        elif command_name == 'set_title':
            self.set_title(data_dict, reply_dict)
        elif command_name == 'sleep':
            self.sleep(data_dict, reply_dict)
        else:
            super(ExampleServer, self)._process_command(command_name, data_dict, reply_dict)

    def echo(self, data_dict, reply_dict):
        reply_dict['result'] = data_dict['text']
        reply_dict['success'] = True

    def set_title(self, data_dict, reply_dict):
        self._window.setWindowTitle(data_dict['title'])
        reply_dict['result'] = True
        reply_dict['success'] = True

    def sleep(self, data_dict, reply_dict):
        for i in range(6):
            print('Sleeping {}'.format(i))
            time.sleep(1)

        reply_dict['result'] = True
        reply_dict['success'] = True


if __name__ == '__main__':
    from Qt.QtWidgets import QApplication, QDialog, QPlainTextEdit

    app = QApplication(sys.argv)
    window = QDialog()
    window.setWindowTitle('Example Base')
    window.setFixedSize(240, 150)
    QPlainTextEdit(window)
    server = ExampleServer(window)
    window.show()
    app.exec_()
