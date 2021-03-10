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
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt, QEvent, pyqtSignal
from qgis.PyQt.QtWidgets import (QAbstractItemView,
                                 QApplication,
                                 QAction,
                                 QListWidgetItem,
                                 QMenu)
from qgis.gui import QgsFilterLineEdit, QgsDockWidget
from qgis.core import Qgis, QgsProject, QgsVectorLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'unique_values_viewer_dockwidget.ui'))

# Commented providers are included in the combobox
# TODO: Make plugin able to work with classified rasters and other data providers
EXCLUDE_PROVIDERS = [
    'arcgisfeatureserver',
    'arcgismapserver',
    'DB2',
    'delimitedtext',
    'gdal',
    'geonode',
    'mdal',
    'mesh_memory',
    'mssql',
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
    def fieldType(self, field_type):
        self._fieldType = field_type

    @property
    def mapLayer(self):
        """ Getter method for the current map layer of the combo box """
        return self._mapLayer

    @mapLayer.setter
    def mapLayer(self, lyr):
        """ Setter method for the current map layer of the combo box """
        self._mapLayer = lyr

    @property
    def project(self):
        """ Getter method for the current QGIS project instance"""
        return QgsProject.instance()

    def __init__(self, iface, plugin_dir, parent=None):
        """Constructor."""
        super(UniqueValuesViewerDockWidget, self).__init__(parent)
        # TODO: Maybe improve UI by replacing QListWidget with QgsListWidget
        self.setupUi(self)
        self.iface = iface

        self.plugin_dir = plugin_dir

        self.mMapLayerComboBox.setExcludedProviders(EXCLUDE_PROVIDERS)

        # init properties
        self._mapLayer = self.mMapLayerComboBox.currentLayer()
        self._field = None
        self._fieldType = None

        # TODO: convert to property?
        self.unique_values = []

        self.contains_null = None
        self.sorting_enabled = True
        self.no_features_selected = True
        self.null_item = QListWidgetItem("NULL [Null]")

        # install event filter for context menu
        self.listWidget.installEventFilter(self)

        self.project.cleared.connect(self.change_project) # Minimum QGIS-Version 3.2

        # connect widgets to slots
        self.clearBtn.clicked.connect(self.clear_listWidget)
        self.getValuesBtn.clicked.connect(self.update_values)
        self.mMapLayerComboBox.layerChanged.connect(self.change_layer)
        self.mFieldComboBox.fieldChanged.connect(self.change_field)

        self.liveUpdateBtn.toggled.connect(self.change_update_auto)
        self.selectedOnlyBtn.toggled.connect(self.change_only_selected_features)
        self.sortValuesBtn.toggled.connect(self.change_sorting)
        self.syncLayerBtn.toggled.connect(self.change_sync_layer)

        self.iface.currentLayerChanged.connect(self.sync_iface_layer_changed)

        self.valueSearch.textChanged.connect(self.search_values)
        self.valueSearch.cleared.connect(self.show_values)

        # Clear selection of ListWidget Items when search bar is cleared
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

        :returns: The expression to use in the expression builder for selection
        :rtype: str
        """

        null_item_was_selected = False

        # check if field contains NULL-Values through null_item of list widget
        if self.null_item.isSelected():
            self.null_item.setSelected(False)
            null_item_was_selected = True

        # List of items will be empty if only the null item was selected
        items = self.listWidget.selectedItems()

        # build expression in case only NULL-Values should be selected
        if not items:
            expr = f"\"{self.field}\" is Null"
        # build expression in case all but the NULL-Value are selected
        elif ((self.contains_null and not null_item_was_selected)
              and (len(items) == self.listWidget.count() - 1)):
            expr = f"\"{self.field}\" is not Null"
        # build expressions for any other case for field types
        else:
            # TODO: Improve for different field types
            # find a better solution for date/time fields, when
            # the display_format is different from the field_format
            # see als get_unique_values method

            expr = f"\"{self.field}\" in ("

            # string fields
            if self.fieldType.lower() == "string":
                for item in items:
                    if "'" in item.text():
                        text = item.text().replace("'", "''")
                        expr += f"'{text}',"
                    else:
                        expr += f"'{item.text()}',"
            # fields with date and time
            elif self.fieldType.lower() in {'time',
                                            'datetime',
                                            'date'}:
                for item in items:
                    expr += f"'{item.text()}',"
            # numeric fields
            elif self.fieldType.lower() in {"double",
                                            "real",
                                            "integer",
                                            "integer64"}:
                for item in items:
                    expr += f"{item.text()},"
            # boolean fields
            elif self.fieldType.lower() == 'boolean':
                # Boolean field can only hold true, false or None/NULL
                if len(items) == 1:
                    expr = f"(\"{self.field}\" is {items[0].text()} "
                elif len(items) == 2:
                    expr = f"(\"{self.field}\" is {items[0].text()}" \
                           f" or \"{self.field}\" is {items[1].text()} "
                else:
                    return None
            else:
                return None

            # Close expression for scheme "value in (...)"
            expr = expr[:-1] + ")"

            # Add expression part if NULL values should be selected
            if null_item_was_selected:
                expr += f" or \"{self.field}\" is Null"

        if null_item_was_selected:
            self.null_item.setSelected(True)
        return expr

    def change_field(self, update=False):
        """ Changes the field property of the DockWidget Plugin Class """
        self.contains_null = None
        self.field = self.mFieldComboBox.currentField()

        # get the typeName by fieldNameIndex, because currentField returns str not a QgsField object
        idx = self.mapLayer.dataProvider().fieldNameIndex(self.field)
        self.fieldType = self.mapLayer.fields()[idx].typeName()
        # automatic updating enabled
        if self.liveUpdateBtn.isChecked() == True:
            self.update_values()
            self.valueSearch.clearValue()
        elif self.clearOnChangeBtn.isChecked() == True:
            self.clear_listWidget()

    def change_layer(self):
        """ Changes the active layer for the plugin. Clears the
            ListWidget and adds the fields of the new layer, if
            present, to the field combo box
        """
        if self.clearOnChangeBtn.isChecked() == True:
            self.clear_listWidget()

        if self.mapLayer:
            try:
                # disconnect old layer from willBeDeleted
                self.mapLayer.willBeDeleted.disconnect()

                # Try to disconnect old current layer from selection change ...
                if (self.liveUpdateBtn.isChecked() == True and
                   self.selectedOnlyBtn.isChecked() == True):

                    self.mapLayer.selectionChanged.disconnect()
                    self.mapLayer.subsetStringChanged.disconnect()
            except TypeError:
                print("TypeError in change_layer")

        # ... change current layer property ...
        old_layer = self.mapLayer
        self.mapLayer = self.mMapLayerComboBox.currentLayer()

        # ... if no layer is apparent in combobox return None
        if self.mapLayer is None:
            self.field = None
            self.contains_null = None
            return None
        else:
            old_field = self.field
            # ... otherwise connect new layer if option is checked
            if (self.liveUpdateBtn.isChecked() == True and
                    self.selectedOnlyBtn.isChecked() == True):
                self.mapLayer.selectionChanged.connect(self.update_values)
                self.mapLayer.selectionChanged.connect(self.refresh_active_layer)
                self.mapLayer.subsetStringChanged.connect(self.update_values)

            self.mapLayer.willBeDeleted.connect(self.clear_connections)

            # ... then set the layer for the field combobox
            self.mFieldComboBox.setLayer(self.mapLayer)

            if len(self.mapLayer.fields()) > 0:
                # ... check if new layer has same named field
                if old_field in self.mapLayer.fields().names():
                    self.mFieldComboBox.setField(old_field)
                    self.contains_null = None
                    # trigger update_values when data source of old and new active layer is
                    # equal as for duplicated layers, because change_field is not triggered by
                    # setField in this case
                    if old_layer.source().__eq__(self.mapLayer.source()):
                        if self.liveUpdateBtn.isChecked() == True:
                            self.update_values()
                            self.valueSearch.clearValue()
                else:
                    field = self.mapLayer.fields()[0]
                    self.mFieldComboBox.setField(field.name())

    def change_project(self):
        """ """
        if self.listWidget.count() > 0:
            self.clear_listWidget()
        if self.liveUpdateBtn.isChecked() == True:
            self.liveUpdateBtn.setChecked(False)

    def change_only_selected_features(self):
        """ Enables functionality for updating the listwidget with the unique
            values on selection change if 'Only selected features' is checked
        """
        # TODO: IMPROVE by disabling this connection when mapLayer has changed to 'None'
        if self.mapLayer:
            if (self.liveUpdateBtn.isChecked() == True and
                    self.selectedOnlyBtn.isChecked() == True):
                self.mapLayer.selectionChanged.connect(self.update_values)
                self.mapLayer.selectionChanged.connect(self.refresh_active_layer)
            else:
                try:
                    self.mapLayer.selectionChanged.disconnect()
                except TypeError:
                    print("TypeError in change_only_selected_features")
            self.update_values()

    def change_sorting(self):
        """ Changes the sorting option for the ListWidgetItems """
        # Do not use the sorting functionality of QListWidget
        if self.sortValuesBtn.isChecked() == True:
            self.sorting_enabled = True
        else:
            self.sorting_enabled = False

    def change_sync_layer(self):
        """ Enables/disables synchronisation of active layer from iface
            with active layer of plugin/combo box
        """
        if self.syncLayerBtn.isChecked() == True:
            self.iface.currentLayerChanged.connect(self.sync_iface_layer_changed)
        else:
            try:
                self.iface.currentLayerChanged.disconnect()
            except TypeError:
                print("TypeError in change_sync_layer")

    def change_update_auto(self):
        """ Changes the widget to update the unique values on
            Field change and Selection change
        """
        # TODO: IMPROVE by disabling this connection when mapLayer has changed to None
        if self.mapLayer:
            if (self.liveUpdateBtn.isChecked() == True
               and self.selectedOnlyBtn.isChecked() == True):
                self.mapLayer.selectionChanged.connect(self.update_values)
                self.mapLayer.selectionChanged.connect(self.refresh_active_layer)
                self.mapLayer.subsetStringChanged.connect(self.update_values)  # minimum QGIS-Version 3.2
            else:
                try:
                    self.mapLayer.selectionChanged.disconnect()
                    self.mapLayer.subsetStringChanged.disconnect()
                except TypeError:
                    print("TypeError in change_update_auto")

    def clear_listWidget(self):
        """ Uses the native clear function to remove all list
            widget items and changes the values label
        """
        self.listWidget.clear()
        # Create a new null item, because it was deleted by line above
        self.null_item = QListWidgetItem("NULL [Null]")
        self.valuesLbl.setText("Unique values")

    def clear_connections(self):
        """  """
        self.mapLayer.selectionChanged.disconnect()
        self.mapLayer.subsetStringChanged.disconnect()  # Minimum QGIS-Version 3.2
        self.mapLayer = None
        self.change_layer()

    def clear_selection(self):
        """ Clears the selection of features from the current layer """
        self.mapLayer.removeSelection()

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

        # Restore the original selection
        self.mapLayer.selectByIds(selected_ids)

    def copy_values(self):
        """ Copies the selected values of the ListWidget to the clipboard """
        items = self.listWidget.selectedItems()
        if len(items) == 1:
            values = items[0].text()
        else:
            values = '\n'.join([item.text() for item in items])
        QApplication.clipboard().setText(values)

    def copy_values_string(self):
        """ Copies the selected values of the ListWidget as string to the clipboard """
        items = self.listWidget.selectedItems()
        if len(items) == 1:
            str_values = "'" + items[0].text() + "'"
        else:
            str_values = '\n'.join(["'" + item.text() + "'" for item in items])
        QApplication.clipboard().setText(str_values)

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

            if items:
                # Icon paths
                addSelect_ipath = self.plugin_dir + '/icons/mIconSelectAdd.svg'
                clearSelect_ipath = self.plugin_dir + '/icons/mActionDeselectActiveLayer.svg'
                copyFeatures_ipath = self.plugin_dir + '/icons/mActionEditCopy.svg'
                intersectSelect_ipath = self.plugin_dir + '/icons/mIconSelectIntersect.svg'
                removeSelect_ipath = self.plugin_dir + '/icons/mIconSelectRemove.svg'
                select_all_ipath = self.plugin_dir + '/icons/mActionSelectAll.svg'
                selected_ipath = self.plugin_dir + '/icons/mIconSelected.svg'

                # Create the context menu
                context_menu = QMenu(self.listWidget)

                # TODO: Shorten the code
                # if only one value is selected
                if len(items) == 1:
                    # Copy Actions
                    context_menu.addAction(u'Copy Value', self.copy_values)
                    context_menu.addAction(u'Copy Value as String',
                                           self.copy_values_string)
                    context_menu.addAction(QIcon(copyFeatures_ipath),
                                           u'Copy Features',
                                           self.copy_features)
                    context_menu.addSeparator()
                    # Selection Actions
                    if self.selectedOnlyBtn.isChecked() == True:
                        context_menu.addAction(QIcon(intersectSelect_ipath),
                                               u'Select Feature(s)',
                                               self.select_features)
                        context_menu.addAction(QIcon(removeSelect_ipath),
                                               u'Remove from Selection',
                                               self.remove_from_selection)
                    else:
                        context_menu.addAction(QIcon(selected_ipath),
                                               u'Select Feature(s)',
                                               self.select_features)
                        context_menu.addAction(QIcon(addSelect_ipath),
                                               u'Add to Selection',
                                               self.add_to_selection)
                    context_menu.addSeparator()
                    context_menu.addAction(u'Select All Values',
                                           self.select_all_values)
                    context_menu.addAction(u'Deselect Value',
                                           self.deselect_values)
                # when more than one value is selected
                else:
                    # Copy Actions
                    context_menu.addAction(u'Copy Values', self.copy_values)
                    context_menu.addAction(u'Copy Values as String',
                                           self.copy_values_string)
                    context_menu.addAction(QIcon(copyFeatures_ipath),
                                           u'Copy Features',
                                           self.copy_features)
                    context_menu.addSeparator()
                    # Selection Actions when all values are selected
                    if (len(items) == self.listWidget.count() and
                       self.selectedOnlyBtn.isChecked() == False):
                        if (self.mapLayer.selectedFeatureCount() ==
                           self.mapLayer.featureCount()):
                            context_menu.addAction(QIcon(clearSelect_ipath),
                                                   u'Clear Selection',
                                                   self.clear_selection)
                        else:
                            context_menu.addAction(QIcon(select_all_ipath),
                                                   u'Select All Features',
                                                   self.select_features)
                        context_menu.addSeparator()
                    # Selection Actions when all not values are selected
                    else:
                        if self.selectedOnlyBtn.isChecked() == True:
                            context_menu.addAction(QIcon(intersectSelect_ipath),
                                                   u'Select Features',
                                                   self.select_features)
                            context_menu.addAction(QIcon(removeSelect_ipath),
                                                   u'Remove from Selection',
                                                   self.remove_from_selection)
                        else:
                            context_menu.addAction(QIcon(selected_ipath),
                                                   u'Select Features',
                                                   self.select_features)
                            context_menu.addAction(QIcon(addSelect_ipath),
                                                   u'Add to Selection',
                                                   self.add_to_selection)
                        context_menu.addSeparator()
                        context_menu.addAction(u'Select All Values',
                                               self.select_all_values)
                    context_menu.addAction(u'Deselect Values',
                                           self.deselect_values)

                context_menu.exec_(event.globalPos())
                return True
        return super(UniqueValuesViewerDockWidget, self).eventFilter(source, event)

    def get_unique_values(self):
        """ Returns a list of string of unique values from the active field from all
            or only the selected features. It will return an empty list if no features are
            selected whilst the option is checked.
            :rtype: List of unique values
        """
        # Get index for field
        idx = self.mapLayer.dataProvider().fieldNameIndex(self.field)

        # not yet fully supported: json fields

        # Get unique values from all (filtered) features
        if self.selectedOnlyBtn.isChecked() == False:

            self.no_features_selected = None

            # Get unique values by built_in function
            v_set = self.mapLayer.uniqueValues(idx)

            # If field contains datetime values, then convert them to string with toString method
            # and check if Field Format in QgsEditorWidgetSetup was changed
            if self.fieldType.lower() in {'datetime', 'date'}:
                try:
                    # TODO: Implement selection for datetime fields with custom display_format!
                    # get QgsEditorWidgetSetup Config for the active Date or DateTime field
                    field_config = self.mapLayer.editorWidgetSetup(idx).config() # Vielleicht hier die property field erweitern
                    display_format = field_config["display_format"]
                    field_format = field_config["field_format"]
                    iso_format = field_config["field_iso_format"]
                # catch KeyError if QgsEditorWidgetSetup.config() returns an empty dictionary
                # or one of the required keys is missing
                except KeyError:
                    str_set = {str(v) if v.isNull() else v.toString(Qt.ISODate) for v in v_set}
                else:
                    if not field_format.__eq__(display_format):
                        str_set = {str(v) if v.isNull()
                                   else f"{v.toString(display_format)} [{v.toString(field_format)}]"
                                   for v in v_set}
                    else:
                        str_set = {str(v) if v.isNull() else v.toString(field_format) for v in v_set}
            else:
                str_set = {str(v) for v in v_set}

        # Get unique values from selected features in case at least one feature is selected
        elif self.mapLayer.selectedFeatureCount() != 0:

            self.no_features_selected = False

            # If field contains datetime values, then convert them to string with toString method
            if self.fieldType.lower() in ('datetime', 'date'):
                v_set = {feat.attributes()[idx]
                         for feat in self.mapLayer.getSelectedFeatures()}
                str_set = {str(v) if v.isNull() else v.toString(Qt.ISODate) for v in v_set}
            else:
                str_set = {str(feat.attributes()[idx])
                           for feat in self.mapLayer.getSelectedFeatures()}
        # Return an empty list in case no features were selected when option was checked
        else:
            self.no_features_selected = True
            return []

        # Check if NULL was in values
        if "NULL" in str_set:
            str_set.remove("NULL")
            self.contains_null = True
        else:
            self.contains_null = False

        # Sorting
        if self.sorting_enabled:
            if self.fieldType.lower() in {"string", "time", "date",
                                          "datetime",
                                          "boolean"}:
                return sorted(str_set)
            elif self.fieldType.lower() in {"double", "real"}:
                return sorted(str_set, key=float)
            elif self.fieldType.lower() == "integer":
                return sorted(str_set, key=int)
            elif self.fieldType.lower() == "integer64":
                return sorted(str_set, key=int)
            else:
                return sorted(str_set)
        else:
            return list(str_set)

    def keyPressEvent(self, event):
        """ Event to clear the searchbar when Escape-Key was pressed """
        if self.valueSearch.hasFocus() and event.key() == Qt.Key_Escape:
            self.valueSearch.clearValue()
            self.valueSearch.clearFocus()
        elif (self.valueSearch.hasFocus() and event.key() in
              {Qt.Key_Return, Qt.Key_Enter}):
            self.listWidget.setFocus()

    def layerRefresh(self, lyr):
        """ Refreshes a layer in QGIS map canvas

        :param lyr: The layer that will be refreshed
        :type lyr: QgsMapLayer
        """
        if self.iface.mapCanvas().isCachingEnabled():
            lyr.triggerRepaint()
        else:
            self.iface.mapCanvas().refresh()

    def refresh_active_layer(self):
        if self.iface.mapCanvas().isCachingEnabled():
            self.mapLayer.triggerRepaint()
        else:
            self.iface.mapCanvas().refresh()

    def remove_from_selection(self):
        """ """
        expr = self.build_expression()
        rm = self.mapLayer.selectByExpression(expr, behavior=QgsVectorLayer.RemoveFromSelection)
        # TODO: Improve here, only remove listwidget items which are no longer selected
        # instead of updating values
        self.update_values()

    def search_values(self):
        """ Searches ListWidget for matching values and updates it to
            only show the matching ones
        """
        text = self.valueSearch.text()

        # Only search if text is not empty
        if text:
            # TODO: Improve Search, some ideas:
            # - remember which items were selected, so that search can be used to
            #   look for different values and select them one by one with Return Key
            # - make it work for multiline fields
            # - make it more efficient/improve performance
            # - if useful add search options to the settings menu, e.g. for string/text fields
            #   'starts/ends with', 'contains' --> make them non-exclusive button group

            # Search all items which do not contain the search value!
            text_not_contained = self.listWidget.findItems('^((?!%s).)*$' % text,
                                                           Qt.MatchRegExp)  # use Qt.MatchRegularExpression for Qt 5.15+

            # Search all items which do contain the search value
            text_contained = self.listWidget.findItems(text, Qt.MatchContains)

            # Hide all items which are not contained
            for item in text_not_contained:
                if not item.isHidden():
                    item.setHidden(True)
            # Show all items which are contained
            for item in text_contained:
                if item.isHidden():
                    item.setHidden(False)

    def select_all_values(self):
        """ Selects all values shown in the ListWidget
        """
        self.listWidget.selectAll()

    def select_features(self):
        """ Select features based on unique values """
        items = self.listWidget.selectedItems()
        if (len(items) == self.listWidget.count() and
                self.selectedOnlyBtn.isChecked() == False):
            self.mapLayer.selectAll()
            print("Alle ausgewählt")
        else:
            expr = self.build_expression()
            self.mapLayer.selectByExpression(expr)
            # Update values for list widget
            if self.selectedOnlyBtn.isChecked() == True:
                self.update_values()
            print(expr)

    def show_values(self):
        """ Shows all items of the listwidget after clearing the searchbar
            and if the items were hidden
        """
        print(self.valueSearch.clearMode())
        for i in range(self.listWidget.count()):
            if self.listWidget.item(i).isHidden():
                self.listWidget.item(i).setHidden(False)

    def sync_iface_layer_changed(self, layer):
        """ Sets the new active layer of the QGIS interface, as current layer
            in the combobox if its data provider is not in list of excluded
            providers
            :param layer: The new active iface layer, automatically given
            :param type: QgsMapLayer
        """
        if layer is not None:
            # Only sync active iface layer with plugin active layer if
            # the plugin is visible for the user
            if self.isUserVisible():
                if layer.dataProvider().name() not in EXCLUDE_PROVIDERS:
                    self.mMapLayerComboBox.setLayer(layer)

    def update_values(self):
        """ Updates the values in the list widget """
        self.clear_listWidget()
        if self.listWidget.selectionMode() == QAbstractItemView.NoSelection:
            self.listWidget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listWidget.setStyleSheet("QListWidget {font-style:normal;}")

        # Get unique values, convert to list and sort
        if self.mMapLayerComboBox.currentLayer() is not None:
            print("update")
            self.unique_values = []
            try:
                values = self.get_unique_values()

                if (self.selectedOnlyBtn.isChecked() == True
                   and self.mapLayer.selectedFeatureCount() != 0):
                    pass
                    #self.layerRefresh(self.mapLayer)

                if self.no_features_selected:
                    self.listWidget.addItem(QListWidgetItem("No features selected"))
                    self.listWidget.setSelectionMode(QAbstractItemView.NoSelection)
                    self.listWidget.setStyleSheet("QListWidget {font-style:italic;}")

                elif values:
                    if self.contains_null:
                        self.listWidget.addItem(self.null_item)
                        self.valuesLbl.setText(f"Unique values [{len(values) + 1}]")
                    else:
                        self.valuesLbl.setText(f"Unique values [{len(values)}]")
                # in case an empty list or None is returned by get_unique_values
                else:
                    self.listWidget.addItem(self.null_item)
                    self.valuesLbl.setText(f"Unique values [1]")

            except SystemError:
                self.iface.messageBar().pushMessage("Error",
                                                    "An error occurred when calculating the set of unique values",
                                                    level=Qgis.Critical,
                                                    duration=2)
            #else:
            #    self.iface.messageBar().pushMessage("Error",
            #                                        "An unknown Error occurred",
            #                                        level=Qgis.Critical,
            #                                        duration=2)
            else:
                # Add unique values as items to list widget
                self.unique_values = values
                self.listWidget.addItems(self.unique_values)