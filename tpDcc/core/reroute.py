#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains tpDcc reroute decorator implementation
Decorator that reroutes the function call on runtime to specific DCC implementations of the given function
"""

from __future__ import print_function, division, absolute_import

import os
import logging
import importlib
from functools import wraps

from tpDcc import dcc

logger = logging.getLogger('tpDcc-core')

REROUTE_CACHE = dict()


def reroute_factory(module_path=None, module_name=None):
    def reroute(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):

            global REROUTE_CACHE

            current_dcc = os.getenv('REROUTE_DCC', dcc.client().get_name())
            if not current_dcc:
                return None

            mod_path = module_path
            mod_name = module_name
            if not mod_path:
                mod_path = fn.__module__
            fn_name = fn.__name__
            fn_mod_path = '{}.dccs.{}'.format(mod_path.replace('-', '.'), current_dcc)
            if mod_name:
                fn_mod_path = '{}.{}'.format(fn_mod_path, mod_name)
            fn_path = '{}.{}'.format(fn_mod_path, fn_name)

            dcc_fn = REROUTE_CACHE.get(fn_mod_path, dict()).get(fn_name, None)
            if not dcc_fn:
                fn_mod = None
                try:
                    fn_mod = importlib.import_module(fn_mod_path)
                except ImportError as exc:
                    logger.warning(
                        '{} | Function {} not implemented: {}'.format(current_dcc, fn_path, exc))
                except Exception as exc:
                    logger.warning(
                        '{} | Error while rerouting function {}: {}'.format(current_dcc, fn_path, exc))
                if fn_mod:
                    if hasattr(fn_mod, fn_name):
                        REROUTE_CACHE.setdefault(fn_mod_path, dict())
                        REROUTE_CACHE[fn_mod_path][fn_name] = getattr(fn_mod, fn_name)

            dcc_fn = REROUTE_CACHE.get(fn_mod_path, dict()).get(fn_name, None)
            if dcc_fn:
                return dcc_fn(*args, **kwargs)
            else:
                return fn(*args, **kwargs)

        return wrapper

    return reroute
