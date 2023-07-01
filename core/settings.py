# -*- coding: utf-8 -*-

from qgis.core import QgsSettings


class UVVSettings(QgsSettings):

    DEFAULTS = {
        'background_proc': 0,
        'copy_newline': 2,
        'quote_char': '\'',
        'quote_char_custom': '',
        'sep_char': ',',
        'sep_char_custom': '',
        'sync_layer': 2,
        'value_sort': 2
    }

    SEP_CHARS = {
        'None': '',
        'Space': ' ',
        'Tab': '\t',
        ',': ',',
        ';': ';',
        'Other': DEFAULTS['sep_char_custom']
    }

    QUOTE_CHARS = {
        '\'': '\'',
        '\"': '\"',
        '´': '´',
        '`': '`',
        'Space': ' ',
        'Other': DEFAULTS['quote_char_custom']
    }

    def __init__(self):
        """ Constructor."""
        super().__init__()
        self.beginGroup('UniqueValuesViewer')

    @staticmethod
    def get_setting(key: str, default: str = None) -> str:
        pass

    def get_quote_char(self):
        """ """
        return self.QUOTE_CHARS[self.value('quote_char')]

    def get_sep_char(self):
        """ """
        return self.SEP_CHARS[self.value('sep_char')]

    def restore_defaults(self):
        """ Return a dictionary of the default plugin settings """
        for key, value in self.DEFAULTS.items():
            self.setValue(key, value)

    @staticmethod
    def set_value():
        pass