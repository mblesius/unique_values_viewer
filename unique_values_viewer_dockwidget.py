# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UniqueValuesViewer
                                 A QGIS plugin
 A simple plugin that allows you to display the unique values for a field of
 a vector layer in a widget. Values can be copied and corresponding features be
 selected through the widget.

 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-09-18
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Malik Blesius
        email                : malik.blesius@foea.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os, sys, warnings

try:
    import pandas as pd
except ImportError:
    warnings.warn("Couldn't import pandas package, Plugin will work correctly"
                  "and might crash QGIS!", ImportWarning)

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt, QEvent, pyqtSignal
from qgis.PyQt.QtWidgets import (QAbstractItemView,
                                 QAction,
                                 QDialog,
                                 QDialogButtonBox,
                                 QDockWidget,
                                 QListWidgetItem,
                                 QMenu,
                                 QProgressBar)

from qgis.gui import QgsFilterLineEdit, QgsDockWidget
from qgis.core import QgsVectorLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'unique_values_viewer_dockwidget_base.ui'))

# Commented providers are included in the combobox
# TODO: Make plugin able to work with classified rasters and other data providers
EXCLUDE_PROVIDERS = [
        'arcgisfeatureserver',
        'arcgismapserver',
        'DB2',
        'delimitedtext',
        'gdal',
        'geonode',
        #'gpx',
        'mdal',
        #'memory',
        'mesh_memory',
        'mssql',
        #'ogr',
        'ows',
        'postgres',
        'spatialite',
        'virtual',
        'wcs',
        'WFS',
        'wms'
    ]

class UniqueValuesViewerDockWidget(QgsDockWidget, FORM_CLASS):
    """ Widget for the plugin. """

    closingPlugin = pyqtSignal()

    @property
    def field(self):
        return self._field

    @field.setter
    def field(self, field):
        self._field = field

    @property
    def fieldType(self):
        return self._fieldType

    @fieldType.setter
    def fieldType(self, fieldType):
        self._fieldType = fieldType

    @property
    def mapLayer(self):
        """ Getter method for the current map layer of the combo box """
        return self._mapLayer

    @mapLayer.setter
    def mapLayer(self, lyr):
        """ Setter method for the current map layer of the combo box """
        self._mapLayer = lyr

    def __init__(self, iface, plugin_dir, parent=None):
        """Constructor."""
        super(UniqueValuesViewerDockWidget, self).__init__(parent)
        # TODO: Maybe improve UI by replacing QListWidget with QgsListWidget
        self.setupUi(self)
        self.iface = iface

        self.mMapLayerComboBox.setExcludedProviders(EXCLUDE_PROVIDERS)

        # init properties
        self._mapLayer = self.mMapLayerComboBox.currentLayer()
        self._field = None
        self._fieldType = None

        # TODO: convert to property
        self.unique_values = []

        self.plugin_dir = plugin_dir

        # install event filter for context menu
        self.listWidget.installEventFilter(self)

        # connect widgets to slots
        self.mMapLayerComboBox.layerChanged.connect(self.change_layer)
        self.mFieldComboBox.fieldChanged.connect(self.change_field)
        self.getValuesBtn.clicked.connect(self.update_values)
        self.clearBtn.clicked.connect(self.clear_listWidget)

        self.valueSearch.textChanged.connect(self.search_value)
        self.valueSearch.cleared.connect(self.show_values)

        self.sortValuesBtn.toggled.connect(self.change_sorting)
        self.liveUpdateBtn.toggled.connect(self.change_update_on_selection)
        self.selectedOnlyBtn.toggled.connect(self.enable_only_selected_features)

        # Clear selection of Listwidget Items when search bar is cleared
        self.valueSearch.cleared.connect(self.listWidget.clearSelection)

        # set initial field
        if self._mapLayer:
            self.change_layer()

    def add_to_selection(self):
        """ """
        expr = self.build_expression()
        self.mapLayer.selectByExpression(expr, behavior=QgsVectorLayer.AddToSelection)

    def build_expression(self):
        """ Build a selection expression based on the selected unique values
        of the current attribute field

        :param items: The selected ListWidgetItems corresponding to the unique
            values
        :returns: The expression to use in the expression builder for selection
        :rtype: str
        """
        items = self.listWidget.selectedItems()

        # build expression based on field type
        # TODO: Improve for different field types, replace i.e. ' in string fields,
        #       make the search bar work in reasonable manner according to field type
        expr = f"\"{self.field}\" in ("
        if self.fieldType.lower() == "string":
            for item in items:
                expr += f"'{item.text()}',"
        elif self.fieldType.lower() == "double":
            for item in items:
                expr += f"{item.text()},"
        elif self.fieldType.lower()  == "real":
            for item in items:
                expr += f"{item.text()},"
        elif self.fieldType.lower()  == "integer":
            for item in items:
                expr += f"{item.text()},"
        elif self.fieldType.lower()  == "integer64":
            for item in items:
                expr += f"{item.text()},"
        elif self.fieldType.lower() == 'time':
            for item in items:
                expr += f"{item.text()},"
        elif self.fieldType.lower() == 'datetime':
            for item in items:
                expr += f"{item.text()},"
        elif self.fieldType.lower() == 'boolean':
            for item in items:
                expr += f"{item.text()},"
        # other fieldtypes...
        else:
            return None

        # Close expression
        expr = expr[:-1] + ")"
        return expr

    def change_field(self):
        """ Changes the field property of the Dockwidget Plugin Class """
        self.field = self.mFieldComboBox.currentField()
        # get the typeName by fieldNameIndex, because currentField returns str not a QgsField object
        idx = self.mapLayer.dataProvider().fieldNameIndex(self.field)
        self.fieldType = self.mapLayer.fields()[idx].typeName()
        # automatic updating enabled
        if self.liveUpdateBtn.isChecked() == True:
            self.update_values()
            self.valueSearch.clearValue()
        elif self.clearValuesOnSelectBtn.isChecked() == True:
            self.clear_listWidget()

    def change_layer(self):
        """ Clears the ListWidget and adds the fields of the
            current layer to the field combo box
        """
        self.clear_listWidget()
        self.field = None
        # Try to disconnect old current layer from selection change ...
        if (self.liveUpdateBtn.isChecked() == True and
            self.selectedOnlyBtn.isChecked() == True):
            try:
                self.mapLayer.selectionChanged.disconnect()
            except TypeError:
                pass
        # ... change current layer property ...
        self.mapLayer = self.mMapLayerComboBox.currentLayer()
        # ... if no layer is for apperent in combobox return
        if self.mapLayer is None:
            return None
        else:
            # ... otherwise connect new layer if option is checked
            if (self.liveUpdateBtn.isChecked() == True and
                self.selectedOnlyBtn.isChecked() == True):
                self.mapLayer.selectionChanged.connect(self.update_values)
            # ... set layer for the field combobox
            self.mFieldComboBox.setLayer(self.mapLayer)
            if len(self.mapLayer.fields()) > 0:
                field = self.mapLayer.fields()[0]
                self.mFieldComboBox.setField(field.name())

    def change_sorting(self):
        """ Changes the sorting option for the ListWidgetItems
            based on the fieldtype """
        # TODO: improve sorting for numeric values
        if self.sortValuesBtn.isChecked() == True:
            self.listWidget.setSortingEnabled(True)
        else:
            self.listWidget.setSortingEnabled(False)

    def change_update_on_selection(self):
        """ Changes the widget to update the unique values on
            Selection change
        """
        # TODO: IMPROVE by disabling this connection when mapLayer has changed to None
        if self.mapLayer:
            if (self.liveUpdateBtn.isChecked() == True and
                self.selectedOnlyBtn.isChecked() == True):
                self.mapLayer.selectionChanged.connect(self.update_values)
            else:
                try:
                    self.mapLayer.selectionChanged.disconnect()
                except TypeError:
                    pass

    def clear_listWidget(self):
        """ Uses the native clear function to remove all list
            widget items and changes the values label
        """
        self.listWidget.clear()
        self.valuesLbl.setText("Unique values")

    def closeEvent(self, event):
        """ """
        self.closingPlugin.emit()
        event.accept()

    def copy_features(self):
        """ Copy all features with the selected unique values for the field """
        # store ids of currently selected features
        selected_ids = self.mapLayer.selectedFeatureIds()

        # get selected unique values
        items = self.listWidget.selectedItems()

        # check if all unique values are selected
        if (len(items) == self.listWidget.count() and
            self.selectedOnlyBtn.isChecked() == False):
            self.mapLayer.selectAll()
        else:
            # Build expression for selection
            expr = self.build_expression()

            # Check if 'Selected features only' is checked
            if self.selectedOnlyBtn.isChecked() == True:
                self.mapLayer.selectByExpression(expr, behavior=QgsVectorLayer.IntersectSelection)
            else:
                self.mapLayer.selectByExpression(expr)

        # Copy Features
        self.iface.setActiveLayer(self.mapLayer)
        self.iface.actionCopyFeatures().trigger()

        # Restore the orignal selection
        self.mapLayer.selectByIds(selected_ids)

    def copy_values(self):
        """ Copies the selected values of the ListWidget to the clipboard """
        # TODO improve for datatypes
        items = self.listWidget.selectedItems()
        if len(items) == 1:
            text_to_copy = items[0].text()
            df = pd.DataFrame([text_to_copy])
        else:
            values = []
            for item in items:
                values.append(item.text())
            df = pd.DataFrame(values)
        df.to_clipboard(index=False,header=False)

    def copy_values_string(self):
        """ Copies the selected values of the ListWidget to the clipboard """
        # TODO improve for datatypes
        items = self.listWidget.selectedItems()
        if len(items) == 1:
            text_to_copy = "'" + items[0].text() + "'"
            df = pd.DataFrame([text_to_copy])
        else:
            values = []
            for item in items:
                values.append("'" + item.text() + "'")
            df = pd.DataFrame(values)
        df.to_clipboard(index=False,header=False)

    def deselect_values(self):
        """ De-selects all selected values shown in the ListWidget
        """
        self.listWidget.clearSelection()

    def eventFilter(self, source, event):
        """ Creates the event filter for the ContextMenu event """
        if (event.type() == QEvent.ContextMenu and
            source is self.listWidget):
            # Get number of selected items to build context menu entries based on this
            items = self.listWidget.selectedItems()
            print(len(items))

            if items and items[0].text() != "No features selected":
                # Icon paths
                copyFeatures_ipath = self.plugin_dir + '/icons/mActionEditCopy.svg'
                selected_ipath = self.plugin_dir + '/icons/mIconSelected.svg'
                addSelect_ipath = self.plugin_dir + '/icons/mIconSelectAdd.svg'
                removeSelect_ipath = self.plugin_dir + '/icons/mIconSelectRemove.svg'
                intersectSelect_ipath = self.plugin_dir + '/icons/mIconSelectIntersect.svg'

                # Create the context menu
                contextMenu = QMenu(self.listWidget)

                # TODO: Shorten the code
                if len(items) == 1:
                    # Copy Actions
                    contextMenu.addAction(u'Copy Value', self.copy_values)
                    contextMenu.addAction(u'Copy Value as String',
                                      self.copy_values_string)
                    contextMenu.addAction(QIcon(copyFeatures_ipath),
                                      u'Copy Feature',
                                      self.copy_features)
                    contextMenu.addSeparator()
                    # Selection Actions
                    if self.selectedOnlyBtn.isChecked() == True:
                        contextMenu.addAction(QIcon(intersectSelect_ipath),
                                          u'Select Feature',
                                          self.select_features)
                        contextMenu.addAction(QIcon(removeSelect_ipath),
                                          u'Remove Feature from Selection',
                                          self.remove_from_selection)
                    else:
                        contextMenu.addAction(QIcon(selected_ipath),
                                          u'Select Feature',
                                          self.select_features)
                        contextMenu.addAction(QIcon(addSelect_ipath),
                                          u'Add Feature to Selection',
                                          self.add_to_selection)
                    contextMenu.addSeparator()
                    contextMenu.addAction(u'Select All Values',
                                          self.select_all_values)
                    contextMenu.addAction(u'Deselect Value',
                                          self.deselect_values)
                else:
                    # Copy Actions
                    contextMenu.addAction(u'Copy Values', self.copy_values)
                    contextMenu.addAction(u'Copy Values as String',
                                          self.copy_values_string)
                    contextMenu.addAction(QIcon(copyFeatures_ipath),
                                          u'Copy Features',
                                          self.copy_features)
                    contextMenu.addSeparator()
                    # Selection Actions
                    if self.selectedOnlyBtn.isChecked() == True:
                        contextMenu.addAction(QIcon(intersectSelect_ipath),
                                              u'Select Features',
                                              self.select_features)
                        contextMenu.addAction(QIcon(removeSelect_ipath),
                                              u'Remove from Selection',
                                              self.remove_from_selection)
                    else:
                        contextMenu.addAction(QIcon(selected_ipath),
                                              u'Select Features',
                                              self.select_features)
                        contextMenu.addAction(QIcon(addSelect_ipath),
                                              u'Add to Selection',
                                              self.add_to_selection)
                    contextMenu.addSeparator()
                    # Check if all values in listwidget are selected
                    if len(items) < self.listWidget.count():
                        contextMenu.addAction(u'Select All Values',
                                              self.select_all_values)
                    contextMenu.addAction(u'Deselect Values',
                                              self.deselect_values)
                contextMenu.exec_(event.globalPos())
                return True
        return super(UniqueValuesViewerDockWidget, self).eventFilter(source, event)

    def enable_only_selected_features(self):
        """ Enables functionality for updating the listwidget with the unique
            values on selection change if 'Only selected features' is checked
        """
        #self.clear_listWidget()
        # TODO: IMPROVE by disabling this connection when mapLayer has changed to 'None'
        if self.mapLayer:
            if (self.liveUpdateBtn.isChecked() == True and
                self.selectedOnlyBtn.isChecked() == True):
                self.mapLayer.selectionChanged.connect(self.update_values)
            else:
                try:
                    self.mapLayer.selectionChanged.disconnect()
                except TypeError:
                    pass
            self.update_values()

    def get_unique_values(self):
        """ Returns list of unique values for all features """
        # Get index for field
        idx = self.mapLayer.dataProvider().fieldNameIndex(self.field)
        # Get unique values by built_in function
        v_set = self.mapLayer.uniqueValues(idx)
        v_list = [ str(v) for v in v_set ]
        return v_list

    def get_unique_values_selected(self):
        """ Returns list of unique values only for selected features """
        # Get index for field
        idx = self.mapLayer.dataProvider().fieldNameIndex(self.field)
        v_set = set()
        # Get unique values from selected features
        for feat in self.mapLayer.getSelectedFeatures():
            v_set.add(str(feat.attributes()[idx]))
        return v_set

    def keyPressEvent(self, event):
        """ Cleares the searchbar when Escape was pressed """
        if self.valueSearch.hasFocus() and event.key() == Qt.Key_Escape:
            self.valueSearch.clearValue()
            self.valueSearch.clearFocus()

    def layerRefresh(self, lyr):
        """Refreshes a layer in QGIS map canvas

        :param lyr: The layer that will be refreshed
        :type lyr: QgsMapLayer
        """
        if self.iface.mapCanvas().isCachingEnabled():
            lyr.triggerRepaint()
        else:
            self.iface.mapCanvas().refresh()

    def remove_from_selection(self):
        """ """
        expr = self.build_expression()
        rm = self.mapLayer.selectByExpression(expr, behavior=QgsVectorLayer.RemoveFromSelection)
        #TODO: Improve here, only remove listwidget items which are no longer selected
        # instead of updating values
        self.update_values()

    def search_value(self):
        """ Searches ListWidget for matching values and updates it to
            only show the matching ones
        """
        text = self.valueSearch.text()
        # Only search if text is not empty
        if text:
            # TODO: Improve Search..
            # - remember which items were selected, so that search can be used to
            #   look for different values and select them one by one
            # - make it work for different field types, e.g. dates
            # - make it more efficient/improve performance
            # - add search options to the settings menu, e.g. for string/text fields
            #   'starts with', 'contains'

            # Search all items which do not contain the search value!
            text_not_contained = self.listWidget.findItems("^((?!%s).)*$"%text, Qt.MatchRegExp) #use Qt.MatchRegularExpression for Qt 5.15+
            # Search all items which do contain the search value
            text_contained = self.listWidget.findItems(text, Qt.MatchContains)

            # Hide all items which are not contained
            for item in text_not_contained:
                if item.isHidden() == False:
                    item.setHidden(True)
            # Show all items which are contained
            for item in text_contained:
                if item.isHidden() == True:
                    item.setHidden(False)

    def select_all_values(self):
        """ Selects all values shown in the ListWidget
        """
        self.listWidget.selectAll()

    def select_features(self):
        """  """
        expr = self.build_expression()
        self.mapLayer.selectByExpression(expr)
        # Update values for list widget
        if self.selectedOnlyBtn.isChecked() == True:
            self.update_values()

    def show_values(self):
        """ Shows all items of the listwidget after clearing the searchbar
            and if the items were hidden
        """
        for i in range(self.listWidget.count()):
            if self.listWidget.item(i).isHidden() == True:
                self.listWidget.item(i).setHidden(False)

    def update_values(self):
        """ Updates the values in the list widget """
        self.clear_listWidget()
        if self.listWidget.selectionMode() == QAbstractItemView.NoSelection:
            self.listWidget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listWidget.setStyleSheet("QListWidget {font-style:normal;}")
        # Get unique values, convert to list and sort
        if self.mMapLayerComboBox.currentLayer() is not None:
            self.unique_values = []

            if self.selectedOnlyBtn.isChecked() == False:
                self.unique_values = self.get_unique_values()
                self.valuesLbl.setText("Unique values [%s]"%len(self.unique_values))

            elif self.mapLayer.selectedFeatureCount() != 0:
                self.unique_values = list(self.get_unique_values_selected())
                self.valuesLbl.setText("Unique values [%s]"%len(self.unique_values))
                self.layerRefresh(self.mapLayer)
            else:
                self.unique_values = ["No features selected"]
                self.listWidget.setSelectionMode(QAbstractItemView.NoSelection)
                self.listWidget.setStyleSheet("QListWidget {font-style:italic;}")
            # Add unique values as items to list widget
            self.listWidget.addItems(self.unique_values)
