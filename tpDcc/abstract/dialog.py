#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains DCC dialog abstract implementation
"""

from __future__ import print_function, division, absolute_import


class AbstractDialog(object):

    def __init__(self, *args, **kwargs):
        super(AbstractDialog, self).__init__(*args, **kwargs)

    def default_settings(self):
        pass

    def load_theme(self):
        pass

    def set_widget_height(self):
        pass

    def is_frameless(self):
        pass

    def set_frameless(self, flag):
        pass


class AbstractColorDialog(object):
    pass


class AbstractFileFolderDialog(object):

    def open_app_browser(self):
        pass


class AbstractNativeDialog(object):

    @staticmethod
    def open_file(title='Open File', start_directory=None, filters=None):
        """
        Function that shows open file DCC native dialog
        :param title: str
        :param start_directory: str
        :param filters: str
        :return: str
        """

        raise NotImplementedError('open_file() function is not implemented')

    @staticmethod
    def save_file(title='Save File', start_directory=None, filters=None):
        """
        Function that shows save file DCC native dialog
        :param title: str
        :param start_directory: str
        :param filters: str
        :return: str
        """

        raise NotImplementedError('save_file() function is not implemented')

    @staticmethod
    def select_folder(title='Select Folder', start_directory=None):
        """
        Function that shows select folder DCC native dialog
        :param title: str
        :param start_directory: str
        :return: str
        """

        raise NotImplementedError('select_folder() function is not implemented')
