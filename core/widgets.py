# -*- coding: utf-8 -*-

__author__ = 'malik@blesius.com'
__date__ = '2021-05-04'
__copyright__ = 'Copyright 2021, Malik Blesius'

from qgis.core import QgsApplication

from qgis.PyQt.QtWidgets import (QAbstractItemView,
                                 QListWidget,
                                 QListWidgetItem)


def delete_list_widget_items(items, parent) -> None:
    """ Removes and deletes a list of ``items´´ from a ``parent´´
    listWidget as they are not deleted when using takeItem

    @param items: List of items to be removed
    @type items: List[QListWidgetItem]

    @param parent: The parent list widget containing the items
    @type parent: QListWidget
    """
    for item in items:
        del_item = parent.takeItem(parent.row(item))
        del del_item


class UVVListWidget(QListWidget):

    @property
    def no_selection(self):
        """ Getter method for no_selection"""
        return self._no_selection

    @no_selection.setter
    def no_selection(self, status):
        """ Setter method for no_selection"""
        self._no_selection = status

    @property
    def sorting_enabled(self):
        """ Getter method for sort status """
        return self._sorting_enabled

    @sorting_enabled.setter
    def sorting_enabled(self, sorting):
        """ Getter method for sort status """
        self._sorting_enabled = sorting

    def __init__(self, parent=None):
        """ Constructor."""
        super().__init__(parent)
        self._no_selection = False
        self._sorting_enabled = True

    def copy_values(self):
        """ Copies the selected values of the ListWidget to the clipboard """
        items = self.selectedItems()
        if len(items) == 1:
            values = items[0].text()
        else:
            values = '\n'.join([item.text() for item in items])
        QgsApplication.clipboard().setText(values)

    def copy_values_quoted(self):
        """ Copies the selected values of the ListWidget using wrapped with
            quoting character to the clipboard
        """
        items = self.selectedItems()
        if len(items) == 1:
            str_values = "'" + items[0].text() + "'"
        else:
            str_values = '\n'.join(["'" + item.text() + "'" for item in items])
        QgsApplication.clipboard().setText(str_values)

    def setExtendedSelection(self):
        """ """
        self.no_selection = False
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setStyleSheet("QListWidget {font-style:normal;}")

    def setNoSelection(self):
        """ """
        self.no_selection = True
        self.addItem(QListWidgetItem("No features selected"))
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setStyleSheet("QListWidget {font-style:italic;}")

    def switchSelectedItems(self) -> None:
        """ Switch selection of items in a ListWidget """
        # TODO: Improve performance, not very fast..
        # Remember which values were selected
        old_selection = self.selectedItems()
        # Select all values
        self.selectAll()
        # Deselect all values which were selected before
        for item in old_selection:
            item.setSelected(False)


class NullItem(QListWidgetItem):
    #TODO implement custom item
    pass

