#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains abstract definition of basic DCC progress bar
"""


class AbstractProgressBar(object):

    def set_count(self, count_number):
        pass

    def get_count(self):
        return 0

    def status(self, status_str):
        pass

    def end(self):
        pass

    def break_signaled(self):
        pass

    def set_progress(self, value):
        pass

    def inc(self, inc=1):
        pass
