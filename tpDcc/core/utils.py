#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains utils and classes used by tpDcc-core
"""

from __future__ import print_function, division, absolute_import

import os
import sys
import logging
import platform
import threading

PSUTIL_AVAILABLE = True
try:
    import psutil
except Exception:
    PSUTIL_AVAILABLE = False

SEPARATOR = '/'
BAD_SEPARATOR = '\\'
PATH_SEPARATOR = '//'
SERVER_PREFIX = '\\'
RELATIVE_PATH_PREFIX = './'
BAD_RELATIVE_PATH_PREFIX = '../'
WEB_PREFIX = 'https://'

logger = logging.getLogger('tpDcc-core')


def force_list(var):
    """
    Returns the given variable as list
    :param var: variant
    :return: list
    """

    if var is None:
        return []

    if type(var) is not list:
        if type(var) in [tuple]:
            var = list(var)
        else:
            var = [var]

    return var


def itersubclasses(cls, _seen=None):
    """
    http://code.activestate.com/recipes/576949-find-all-subclasses-of-a-given-class/
    Iterator to yield full inheritance from a given class, including subclasses. This
    """

    if _seen is None:
        _seen = set()
    try:
        subs = cls.__subclasses__()
    except TypeError:
        subs = cls.__subclasses__(cls)

    for sub in subs:
        if sub not in _seen:
            _seen.add(sub)
            yield sub
            for sub in itersubclasses(sub, _seen):
                yield sub


def repeater(interval, limit=-1):
    """!
    A function interval decorator based on
    http://stackoverflow.com/questions/5179467/equivalent-of-setinterval-in-python
    """

    def actual_decorator(fn):

        def wrapper(*args, **kwargs):

            class RepeaterTimerThread(threading.Thread):
                def __init__(self):
                    threading.Thread.__init__(self)
                    self._event = threading.Event()

                def run(self):
                    i = 0
                    while i != limit and not self._event.is_set():
                        self._event.wait(interval)
                        fn(*args, **kwargs)
                        i += 1
                    else:
                        if self._event:
                            self._event.set()

                def stopped(self):
                    return not self._event or self._event.is_set()

                def pause(self):
                    self._event.set()

                def resume(self):
                    self._event.clear()

                def stop(self):
                    self._event.set()
                    self.join()

            token = RepeaterTimerThread()
            token.daemon = True
            token.start()
            return token

        return wrapper

    return actual_decorator


def get_sys_platform():
    if sys.platform.startswith('java'):
        os_name = platform.java_ver()[3][0]
        if os_name.startswith('Windows'):   # "Windows XP", "Windows 7", etc.
            system = 'win32'
        elif os.name.startswith('Mac'):     # "Mac OS X", etc.
            system = 'darwin'
        else:   # "Linux", "SunOS", "FreeBSD", etc.
            # Setting this to "linux2" is not ideal, but only Windows or Mac
            # are actually checked for and the rest of the module expects
            # *sys.platform* style strings.
            system = 'linux2'
    else:
        system = sys.platform

    return system


def get_platform():

    system_platform = get_sys_platform()

    pl = 'Windows'
    if 'linux' in system_platform:
        pl = 'Linux'
    elif system_platform == 'darwin':
        pl = 'MacOS'

    return pl


def get_version():
    """
    Return current Python version used
    :return: SemanticVersion, python version
    """

    from tpDcc.libs.python import version

    py_version = sys.version_info
    current_version = version.SemanticVersion(
        major=py_version.major,
        minor=py_version.minor,
        patch=py_version.micro
    )

    return current_version


def machine_info():
    """
    Returns dictionary with information about the current machine
    :return: dict
    """

    machine_dict = {
        'pythonVersion': sys.version,
        'node': platform.node(),
        'OSRelease': platform.release(),
        'OSVersion': platform.platform(),
        'processor': platform.processor(),
        'machineType': platform.machine(),
        'env': os.environ,
        'syspaths': sys.path,
        'executable': sys.executable,
    }

    return machine_dict


def is_python2():
    """
    Returns whether or not current version is Python 2
    :return: bool
    """

    return get_version().major == 2


def check_if_process_is_running(process_name):
    """
    Returns whether or not a process with given name is running
    :param process_name: str
    :return: bool
    """

    if not PSUTIL_AVAILABLE:
        logger.warning(
            'Impossible to check is process "{}" is running because psutil is not available!'.format(process_name))
        return False

    for process in psutil.process_iter():
        try:
            if process_name.lower() in process.name().lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def normalize_path(path):
    """
    Normalizes a path to make sure that path only contains forward slashes
    :param path: str, path to normalize
    :return: str, normalized path
    """

    path = path.replace(BAD_SEPARATOR, SEPARATOR).replace(PATH_SEPARATOR, SEPARATOR)

    if is_python2():
        try:
            path = unicode(path.replace(r'\\', r'\\\\'), "unicode_escape").encode('utf-8')
        except TypeError:
            path = path.replace(r'\\', r'\\\\').encode('utf-8')

    return path.rstrip('/')


def clean_path(path):
    """
    Cleans a path. Useful to resolve problems with slashes
    :param path: str
    :return: str, clean path
    """

    if not path:
        return

    # We convert '~' Unix character to user's home directory
    path = os.path.expanduser(str(path))

    # Remove spaces from path and fixed bad slashes
    path = normalize_path(path.strip())

    # Fix server paths
    is_server_path = path.startswith(SERVER_PREFIX)
    while SERVER_PREFIX in path:
        path = path.replace(SERVER_PREFIX, PATH_SEPARATOR)
    if is_server_path:
        path = PATH_SEPARATOR + path

    # Fix web paths
    if not path.find(WEB_PREFIX) > -1:
        path = path.replace(PATH_SEPARATOR, SEPARATOR)

    return path


def add_metaclass(metaclass):
    """
    Decorators that allows to create a class using a metaclass
    https://github.com/benjaminp/six/blob/master/six.py
    :param metaclass:
    :return:
    """

    def wrapper(cls):
        orig_vars = cls.__dict__.copy()
        slots = orig_vars.get('__slots__')
        if slots is not None:
            if isinstance(slots, str):
                slots = [slots]
            for slots_var in slots:
                orig_vars.pop(slots_var)
        orig_vars.pop('__dict__', None)
        orig_vars.pop('__weakref__', None)
        if hasattr(cls, '__qualname__'):
            orig_vars['__qualname__'] = cls.__qualname__
        return metaclass(cls.__name__, cls.__bases__, orig_vars)
    return wrapper
