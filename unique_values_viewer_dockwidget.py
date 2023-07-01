# -*- coding: utf-8 -*-
""" DockWidget for UniqueValuesViewer

"""

__author__ = 'malik@blesius.com'
__date__ = '2020-09-18'
__copyright__ = 'Copyright 2021, Malik Blesius'

import traceback
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QEvent, pyqtSignal
from qgis.PyQt.QtWidgets import (QAction,
                                 QListWidgetItem,
                                 QToolButton,
                                 QMenu)
from qgis.gui import QgsDockWidget
from qgis.core import (Qgis,
                       QgsApplication,
                       QgsMessageLog,
                       QgsProject,
                       QgsVectorLayer)

from unique_values_viewer.core.utils import (FieldTypes,
                                             match_field_type,
                                             is_expression_field,
                                             get_sort_key)
from unique_values_viewer.core.widgets import (delete_list_widget_items,
                                               NullItem)

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'unique_values_viewer_dockwidget.ui'))

# TODO: Make plugin able to work with other data providers
EXCLUDE_PROVIDERS = {
    'arcgisfeatureserver',
    'arcgismapserver',
    'DB2',
    'gdal',
    'geonode',
    'mdal',
    'mesh_memory',
    'mssql',
    'ows',
    'postgres',
    'pdal',
    'spatialite',
    'wcs',
    'WFS',
    'wms'
}


class UniqueValuesViewerDockWidget(QgsDockWidget, FORM_CLASS):
    """DockWidget for the plugin."""

    closingPlugin = pyqtSignal()

    @property
    def active_layer(self):
        """Getter method for the current map layer of the combo box."""
        return self._map_layer

    @active_layer.setter
    def active_layer(self, layer):
        """Setter method for the current map layer of the combo box.

        Parameters:
            layer(QgsVectorLayer): Vector layer to be set for the plugin.
        """
        self._map_layer = layer

    @property
    def active_field(self) -> str:
        return self._field

    @active_field.setter
    def active_field(self, field: str):
        if type(field) != str:
            raise TypeError
        self._field = field

    @property
    def field_type(self) -> FieldTypes:
        return self._field_type

    @field_type.setter
    def field_type(self, field_type):
        self._field_type = field_type

    @property
    def unique_values(self) -> set:
        """The unique values property saving the unique
        attribute values of the active field."""
        return self._unique_values

    @unique_values.setter
    def unique_values(self, unique_values):
        self._unique_values = set(unique_values)

    @unique_values.deleter
    def unique_values(self):
        if hasattr(self, "_unique_values"):
            del self._unique_values
        else:
            QgsMessageLog.logMessage("Unique values have already been cleared!", level=Qgis.Warning)

    @property
    def project(self):
        """Getter method for the current QGIS project instance."""
        return QgsProject.instance()

    def __init__(self, iface, plugin_dir, settings, parent=None):
        """Constructor."""
        super(UniqueValuesViewerDockWidget, self).__init__(parent)

        self.iface = iface
        self.plugin_dir = plugin_dir

        # init UI
        self.setupUi(self)
        self.settings = settings

        # init properties
        self._map_layer = self.mMapLayerComboBox.currentLayer()
        self._field = None
        self._field_type = None

        self._unique_values = set()

        self.field_contains_null = None
        self.no_features_selected = True

        # install event filter for context menu
        self.listWidget.installEventFilter(self)

        # init signal/slot connections and additional UI elements
        self._init_connections()
        self._init_sort()

        # init other connections
        self.project.cleared.connect(self.change_project)  # Minimum QGIS-Version 3.2
        self.iface.currentLayerChanged.connect(self.sync_iface_layer_changed)

        # set iface active layer to current combobox layer
        # can be None, for example if no layer is selected and
        # will result in None if the layer is not under supported providers
        self.mMapLayerComboBox.setExcludedProviders(EXCLUDE_PROVIDERS)
        self.mMapLayerComboBox.setLayer(self.iface.activeLayer())

    def _init_connections(self) -> None:
        """Sets up necessary signal/slot connections for the UI."""
        # buttons
        self.clearBtn.clicked.connect(self.clear_listWidget_button)
        self.getValuesBtn.clicked.connect(self.update_values)

        # comboboxes
        self.mMapLayerComboBox.layerChanged.connect(self.change_layer)
        self.mFieldComboBox.fieldChanged.connect(self.change_field)

        # checkboxes
        self.liveUpdateBtn.toggled.connect(self.change_live_update)
        self.selectedOnlyBtn.toggled.connect(self.change_only_selected_features)

        # search bar/filterLineEdit
        self.valueSearch.textChanged.connect(self.search_values)
        self.valueSearch.cleared.connect(self.show_items)
        self.valueSearch.cleared.connect(self.listWidget.clearSelection)

        # settings
        self.sortOptionBtn.stateChanged.connect(self.change_sorting)
        self.syncLayerBtn.stateChanged.connect(self.change_sync_layer)
        self.newLineBtn.stateChanged.connect(lambda v: self.setting_changed('copy_newline', v))
        self.quoteCharBox.currentTextChanged.connect(lambda v: self.setting_changed('quote_char', v))
        self.sepCharBox.currentTextChanged.connect(lambda v: self.setting_changed('sep_char', v))
        self.resetDefaultsBtn.clicked.connect(self.reset_settings)

    def _init_sort(self) -> None:
        """Creates the sort action for the values in the listWidget
        and inserts it into placeholder in the UI.
        """
        self.sort_action = QAction(QgsApplication.getThemeIcon('/sort-reverse.svg'),
                                   self.tr('Reverse Sorting'),
                                   self)
        self.sort_action.triggered.connect(self.sort_values)
        self.sort_action.reverse = False
        self.sortValuesBtn = QToolButton()
        self.sortValuesBtn.setDefaultAction(self.sort_action)
        self.sortBtnPlaceholder.insertWidget(-1, self.sortValuesBtn)

    def add_to_selection(self) -> None:
        """Adds values corresponding to selected list widget
        items to current selection.
        """
        expr = self.build_expression()
        self.active_layer.selectByExpression(expr, behavior=QgsVectorLayer.AddToSelection)

    def build_expression(self) -> str:
        """Builds a filter expression based on the selected unique values
        of the current attribute field. The expression can be used to set
        a subset string to filter the layer or to select features.

        Returns:
            The expression to use in the expression builder for selection.
        """

        # check if active_field contains NULL-Values through null_item of list widget
        if self.listWidget.null_item.isSelected():
            self.listWidget.null_item.setSelected(False)
            null_item_was_selected = True
        else:
            null_item_was_selected = False

        # List of items will be empty if only the null item was selected
        items = self.listWidget.selectedItems()

        # build expression in case only NULL-Values should be selected
        if not items:
            expr = f"\"{self.active_field}\" is Null"
        # build expression in case all but the NULL-Value are selected
        elif ((self.field_contains_null and not null_item_was_selected)
              and (len(items) == self.listWidget.count() - 1)):
            expr = f"\"{self.active_field}\" is not Null"
        # build expressions for any other case for field types
        else:
            # TODO: Improve for different field types
            # find a better solution for date/time fields, when
            # the display_format is different from the field_format
            # also in the calc_unique_values method

            expr = f"\"{self.active_field}\" in ("

            # string fields
            if self.field_type is FieldTypes.STRING:
                for item in items:
                    if "'" in item.text():
                        text = item.text().replace("'", "''")
                        expr += f"'{text}',"
                    else:
                        expr += f"'{item.text()}',"
            # fields with date and time
            elif (self.field_type | FieldTypes.DATE is FieldTypes.DATETIME
                  or self.field_type | FieldTypes.TIME is FieldTypes.DATETIME):
                for item in items:
                    expr += f"'{item.text()}',"
            # numeric fields
            elif (self.field_type | FieldTypes.INTEGER is FieldTypes.NUMERIC
                  or self.field_type | FieldTypes.DECIMAL is FieldTypes.NUMERIC):
                for item in items:
                    expr += f"{item.text()},"
            # boolean fields
            elif self.field_type is FieldTypes.BOOLEAN:
                # Boolean field can only hold true, false or None/NULL
                if len(items) == 1:
                    expr = f"(\"{self.active_field}\" is {items[0].text()} "
                elif len(items) == 2:
                    expr = f"(\"{self.active_field}\" is {items[0].text()}" \
                           f" or \"{self.active_field}\" is {items[1].text()} "
                else:
                    return None
            else:
                return None

            # Close expression for scheme "value in (...)"
            expr = expr[:-1] + ")"

            # Add expression part if NULL values should be selected
            if null_item_was_selected:
                expr += f" or \"{self.active_field}\" is Null"

        if null_item_was_selected:
            self.listWidget.null_item.setSelected(True)
        return expr

    def calc_unique_values(self) -> {str}:
        """Returns the unique values from the active field as set of strings,
        either calculated for all or only for the selected features.
        It will return an empty list if no features are selected while the
        option is checked.

        Returns:
            Set of unique values as str.
        """
        # Get index for active_field
        idx = self.active_layer.fields().indexFromName(self.active_field)

        # Get unique values from all (filtered) features
        if self.selectedOnlyBtn.isChecked() is False:

            self.no_features_selected = None

            if not is_expression_field(self.active_layer, self.active_field):
                # Get unique values by qgis built_in function
                v_set = self.active_layer.uniqueValues(idx)  # does not work for virtual fields

                # If field contains datetime values, then convert them to string with toString method
                # and check if Field Format in QgsEditorWidgetSetup was changed
                if (self.field_type | FieldTypes.DATE is FieldTypes.DATETIME
                        or self.field_type | FieldTypes.TIME is FieldTypes.DATETIME):

                    str_set = {str(v) if v.isNull() else v.toString(Qt.ISODate) for v in v_set}
                else:
                    str_set = {str(v) for v in v_set}

            else:
                # QgsMessageLog.logMessage("Virtual field", level=Qgis.Info)
                # Get unique values "manually" for virtual fields because built_in does not support it
                str_set = {str(feat.attributes()[idx])
                           for feat in self.active_layer.getFeatures()}

        # Get unique values from selected features in case at least one feature is selected
        elif self.active_layer.selectedFeatureCount() != 0:

            self.no_features_selected = False

            # If field contains datetime values, then convert them to string with toString method
            if (self.field_type | FieldTypes.DATE is FieldTypes.DATETIME
                    or self.field_type | FieldTypes.TIME is FieldTypes.DATETIME):
                v_set = {feat.attributes()[idx]
                         for feat in self.active_layer.getSelectedFeatures()}
                str_set = {str(v) if v.isNull() else v.toString(Qt.ISODate) for v in v_set}
            else:
                str_set = {str(feat.attributes()[idx])
                           for feat in self.active_layer.getSelectedFeatures()}

        # Return an empty set in case no features were selected when option was checked
        else:
            self.no_features_selected = True
            return set()

        # Check if NULL values were contained, None can occur for virtual fields
        if "None" in str_set:
            str_set.remove("None")
            self.field_contains_null = True
        elif "NULL" in str_set:
            str_set.remove("NULL")
            self.field_contains_null = True
        else:
            self.field_contains_null = False

        return str_set

    def change_field(self) -> None:
        """Changes the active_field property of the DockWidget Plugin Class."""
        # evaluate if new field is the same as the old field
        fields = self.active_layer.fields()
        new_field = self.mFieldComboBox.currentField()
        # do nothing (no update, etc.) if new field is same as old field
        if fields.indexFromName(self.active_field) == fields.indexFromName(new_field):
            return None
        else:
            # clear the listWidget to prevent issues when active_field changes and
            # values are not updated automatically, i.e. when sorting the values
            # from the field before
            self.clear_listWidget()

            self.active_field = new_field
            self.field_contains_null = None

            # get the typeName, because currentField returns str not a QgsField object
            idx = self.active_layer.fields().indexFromName(self.active_field)
            ftype = self.active_layer.fields()[idx].typeName()
            self.field_type = match_field_type(ftype)

            if self.field_type is FieldTypes.UNSUPPORTED:
                self.iface.messageBar().pushMessage("Unsupported field type:",
                                                    f"{ftype}",
                                                    level=Qgis.Warning,
                                                    duration=2)
                self.enable_updates(False)
            else:
                if not self.liveUpdateBtn.isChecked():
                    self.enable_updates(True)

            # if automatic updating enabled, update values
            if self.liveUpdateBtn.isChecked() is True:
                self.valueSearch.clearValue()
                self.update_values()

    def change_layer(self) -> None:
        """Changes the active layer for the plugin.

        Clears the ListWidget and adds the fields of the new layer,
        if present, to the field combo box.
        """
        new_layer = self.mMapLayerComboBox.currentLayer()
        # Check if a new layer is available in combobox ...
        if new_layer:
            # ... also check if an (old) active layer still exists ...
            if self.active_layer:
                # ... check if new and old active layer are identical
                if self.active_layer.id().__eq__(new_layer.id()):
                    return None
                else:
                    # disconnect old layer and save its properties for a
                    # later comparison of the active field
                    self.disconnect_active_layer()
                    # old_layer = self.active_layer
                    old_field = self.active_field

                    # change active layer property
                    self.connect_active_layer(new_layer)

                    # check if new layer has same named field like the old active
                    # field and set this field to be the new active field
                    if old_field in self.active_layer.fields().names():
                        self.mFieldComboBox.setField(old_field)
                        self.change_field()
                        # trigger update_values here, because change_field is not
                        # triggered by setField through mFieldComboBox.fieldChanged()
                        # when field name of old and new field are the same
                        if self.liveUpdateBtn.isChecked() is True:
                            self.update_values()
                        return None
            else:
                # change active layer property
                self.connect_active_layer(new_layer)

            if len(self.active_layer.fields()) > 0:
                field = self.active_layer.fields()[0]
                self.mFieldComboBox.setField(field.name())
                self.change_field()
            return None
        # If no new layer is available ...
        else:
            # ... check if the old active layer (still) exists ...
            if self.active_layer:
                # ... and disconnect it
                self.disconnect_active_layer()
                self.active_layer = None
                self.active_field = None
                self.field_contains_null = None
                self.enable_updates(False)
                return None
            # ... else if no new and (old) active layer exist, do nothing
            else:
                return None

    def change_project(self) -> None:
        """Triggered when the current QGIS Project is changed, cleared
         or closed."""
        self.clear_listWidget()
        self.liveUpdateBtn.setChecked(False)
        self.selectedOnlyBtn.setChecked(False)
        self.enable_updates(True)

    def change_only_selected_features(self) -> None:
        """Changes whether only selected features of active layer will be
        used for calculation of unique values.
         (Dis)Connects necessary signals to slots.
        """
        # Enable "Selected features only" only if active layer exists
        if self.active_layer is not None:
            if self.selectedOnlyBtn.isChecked() is True:
                if self.liveUpdateBtn.isChecked() is True:
                    self.active_layer.selectionChanged.connect(self.update_values)
                    # If layer has selected features then do an update of values
                    self.update_values()
            else:
                # Try to disconnect active layer from selectionChanged slots
                if self.liveUpdateBtn.isChecked() is True:
                    try:
                        self.active_layer.selectionChanged.disconnect(self.update_values)
                    except TypeError:
                        traceback.print_exc()
                    else:
                        self.update_values()

    def change_sorting(self, state: int) -> None:
        """ Changes the sorting option for the ListWidgetItems
        :param state: Checkstate of the QCheckbox that is connected
        """
        # Do not use the sorting functionality of QListWidget,
        # it will sort alphabetically
        if state == 2:  # Qt.Checked
            self.listWidget.sorting_enabled = True
            self.settings.setValue('value_sort', state)
            self.sortValuesBtn.setEnabled(True)
        elif state == 0:  # Qt.Unchecked
            self.listWidget.sorting_enabled = False
            self.settings.setValue('value_sort', state)
            self.sortValuesBtn.setEnabled(False)

    def change_sync_layer(self, state: int) -> None:
        """Enables/disables synchronisation of active layer from iface
        with active layer of plugin/combo box.
        :param state: Checkstate of the QCheckbox that is connected
        """
        if state == 2:  # Qt.Checked
            self.iface.currentLayerChanged.connect(self.sync_iface_layer_changed)
            self.settings.setValue('sync_layer', state)
        elif state == 0:  # Qt.Unchecked
            try:
                self.iface.currentLayerChanged.disconnect(self.sync_iface_layer_changed)
            except TypeError:
                traceback.print_exc()
            else:
                self.settings.setValue('sync_layer', state)

    def change_live_update(self) -> None:
        """Changes the widget to update the unique values automatically
        when active Field, Layer or Feature Selection changes.
        """
        if self.active_layer:
            if self.liveUpdateBtn.isChecked() is True:
                self.getValuesBtn.setEnabled(False)
                self.active_layer.subsetStringChanged.connect(self.update_values)  # minimum QGIS-Version 3.2
                if self.selectedOnlyBtn.isChecked() is True:
                    self.active_layer.selectionChanged.connect(self.update_values)
                    self.update_values()
            else:
                self.getValuesBtn.setEnabled(True)
                try:
                    self.active_layer.subsetStringChanged.disconnect(self.update_values)
                    if self.selectedOnlyBtn.isChecked() is True:
                        self.active_layer.selectionChanged.disconnect(self.update_values)
                except TypeError:
                    traceback.print_exc()

    def clear_listWidget(self) -> None:
        """Uses the native clear function to remove all list
        widget items and changes the values label.
        """
        self.listWidget.clear()
        self.sortValuesBtn.setEnabled(False)
        # Create a new null item, because it will be deleted by clearing
        self.listWidget.null_item = NullItem()
        self.valuesLbl.setText(self.tr("Unique values"))

    def clear_listWidget_button(self) -> None:
        """Clears the list widget when clicked on the clear button
        and deletes the unique values property. When 'Selected
        features only' is checked, then it also clears the active
        selection of the layer."""
        self.clear_listWidget()

        del self.unique_values

        if self.selectedOnlyBtn.isChecked() is True:
            # triggers self.active_layer.selectionChanged
            self.active_layer.removeSelection()

    def clear_connections(self) -> None:
        """Clears connections between active layer and dockwidget buttons."""
        if self.liveUpdateBtn.isChecked() is True:
            self.active_layer.selectionChanged.disconnect(self.update_values)
            self.active_layer.subsetStringChanged.disconnect(self.update_values)  # Minimum QGIS-Version 3.2
        self.active_layer = None
        self.change_layer()

    def closeEvent(self, event):
        """ """
        self.closingPlugin.emit()
        event.accept()

    def connect_active_layer(self, new_layer: QgsVectorLayer) -> None:
        """ Changes active layer property, connects the new
        layer with the relevant slots and sets it as layer for
        the field combo box.
        """
        self.active_layer = new_layer
        # connect new layer if option is checked
        if self.liveUpdateBtn.isChecked() is True:
            self.active_layer.subsetStringChanged.connect(self.update_values)
            if self.selectedOnlyBtn.isChecked() is True:
                self.active_layer.selectionChanged.connect(self.update_values)

        self.active_layer.willBeDeleted.connect(self.clear_connections)
        self.mFieldComboBox.setLayer(self.active_layer)

    def copy_features(self) -> None:
        """ Copy all features with the selected unique values for the field """
        # store ids of currently selected features
        selected_ids = self.active_layer.selectedFeatureIds()

        # get selected unique values
        items = self.listWidget.selectedItems()

        # check if all unique values are selected
        if (len(items) == self.listWidget.count() and
                self.selectedOnlyBtn.isChecked() is False):
            self.active_layer.selectAll()
        else:
            # Build expression for selection
            expr = self.build_expression()

            # Check if 'Selected features only' is checked
            if self.selectedOnlyBtn.isChecked() is True:
                self.active_layer.selectByExpression(expr,
                                                     behavior=QgsVectorLayer.IntersectSelection)
            else:
                self.active_layer.selectByExpression(expr)

        # Copy Features
        self.iface.setActiveLayer(self.active_layer)
        self.iface.copySelectionToClipboard(self.active_layer)

        # Restore the original selection
        self.active_layer.selectByIds(selected_ids)

    def disconnect_active_layer(self) -> None:
        """ Disconnects the active layer from all slots """
        try:
            # disconnect active layer from willBeDeleted
            self.active_layer.willBeDeleted.disconnect(self.clear_connections)
            # Try to disconnect old current layer from selection change ...
            if (self.liveUpdateBtn.isChecked() is True and
                    self.selectedOnlyBtn.isChecked() is True):
                self.active_layer.selectionChanged.disconnect()
                self.active_layer.subsetStringChanged.disconnect()
        except TypeError:
            traceback.print_exc()

    def enable_updates(self, enable: bool) -> None:
        """ Enables/disables buttons and checkboxes that allow
        to update/calculate the unique values, depending on the
        value of the variable 'enable'"""
        if enable:
            self.getValuesBtn.setEnabled(True)
            self.liveUpdateBtn.setEnabled(True)
            self.selectedOnlyBtn.setEnabled(True)
        else:
            self.getValuesBtn.setEnabled(False)
            self.liveUpdateBtn.setEnabled(False)
            self.selectedOnlyBtn.setEnabled(False)

    def eventFilter(self, source, event):
        """ Creates the event filter for the ContextMenu event """
        if (event.type() == QEvent.ContextMenu and
                source is self.listWidget):

            # Get number of selected items to build context menu entries based on this
            items = self.listWidget.selectedItems()

            if items:
                # Create the context menu
                context_menu = QMenu(self.listWidget)

                # TODO: Shorten the code
                # Actions for "only one value is selected"
                if len(items) == 1:
                    # Copy Actions
                    context_menu.addAction(self.tr('Copy Value'),
                                           self.listWidget.copy_values)
                    context_menu.addAction(self.tr('Copy Value (quoted)'),
                                           self.listWidget.copy_values_quoted)
                    context_menu.addAction(QgsApplication.getThemeIcon('/mActionEditCopy.svg'),
                                           self.tr('Copy Features'),
                                           self.copy_features)
                    context_menu.addSeparator()
                    # Selection Actions when all values are selected
                    if (len(items) == self.listWidget.count() and
                            self.selectedOnlyBtn.isChecked() is False):
                        if (self.active_layer.selectedFeatureCount() ==
                                self.active_layer.featureCount()):
                            context_menu.addAction(QgsApplication.getThemeIcon('/mActionDeselectActiveLayer.svg'),
                                                   self.tr('Clear Selection'),
                                                   self.active_layer.removeSelection)
                        else:
                            context_menu.addAction(QgsApplication.getThemeIcon('/mActionSelectAll.svg'),
                                                   self.tr('Select All Features'),
                                                   self.select_features)
                    # Feature Selection Actions for "not all values are selected"
                    else:
                        if self.selectedOnlyBtn.isChecked() is True:
                            context_menu.addAction(QgsApplication.getThemeIcon("/mIconSelectIntersect.svg"),
                                                   self.tr("Select Feature(s)"),
                                                   self.select_features)
                            context_menu.addAction(QgsApplication.getThemeIcon("/mIconSelectRemove.svg"),
                                                   self.tr("Remove from Selection"),
                                                   self.remove_from_selection)
                        else:
                            context_menu.addAction(QgsApplication.getThemeIcon("/mIconSelected.svg"),
                                                   self.tr("Select Feature(s)"),
                                                   self.select_features)
                            context_menu.addAction(QgsApplication.getThemeIcon("/mIconSelectAdd.svg"),
                                                   self.tr("Add to Selection"),
                                                   self.add_to_selection)
                    if not self.active_layer.subsetString():
                        context_menu.addSeparator()
                        context_menu.addAction(self.tr('Filter Layer by value'),
                                               self.filter_layer)
                    context_menu.addSeparator()
                    if self.listWidget.count() > 1:
                        context_menu.addAction(self.tr("Select All Values"),
                                               self.listWidget.selectAll)
                        context_menu.addAction(self.tr("Switch Selected Values"),
                                               self.listWidget.switchSelectedItems)
                    context_menu.addAction(self.tr("Deselect Value"),
                                           self.listWidget.clearSelection)
                # Actions for "more than one value is selected"
                else:
                    # Copy Actions
                    context_menu.addAction(self.tr("Copy Values"),
                                           self.listWidget.copy_values)
                    context_menu.addAction(self.tr("Copy Values (quoted)"),
                                           self.listWidget.copy_values_quoted)
                    context_menu.addAction(QgsApplication.getThemeIcon("/mActionEditCopy.svg"),
                                           self.tr("Copy Features"),
                                           self.copy_features)
                    context_menu.addSeparator()
                    # Feature Selection Actions for "all values are selected"
                    if (len(items) == self.listWidget.count() and
                            self.selectedOnlyBtn.isChecked() is False):
                        if (self.active_layer.selectedFeatureCount() ==
                                self.active_layer.featureCount()):
                            context_menu.addAction(QgsApplication.getThemeIcon("/mActionDeselectActiveLayer.svg"),
                                                   self.tr("Clear Selection"),
                                                   self.active_layer.removeSelection)
                        else:
                            context_menu.addAction(QgsApplication.getThemeIcon("/mActionSelectAll.svg"),
                                                   self.tr("Select All Features"),
                                                   self.select_features)
                        context_menu.addSeparator()
                    # Feature Selection Actions for "not all values are selected"
                    else:
                        if self.selectedOnlyBtn.isChecked() is True:
                            context_menu.addAction(QgsApplication.getThemeIcon("/mIconSelectIntersect.svg"),
                                                   self.tr("Select Features"),
                                                   self.select_features)
                            context_menu.addAction(QgsApplication.getThemeIcon("/mIconSelectRemove.svg"),
                                                   self.tr("Remove from Selection"),
                                                   self.remove_from_selection)
                        else:
                            context_menu.addAction(QgsApplication.getThemeIcon("/mIconSelected.svg"),
                                                   self.tr("Select Features"),
                                                   self.select_features)
                            context_menu.addAction(QgsApplication.getThemeIcon("/mIconSelectAdd.svg"),
                                                   self.tr("Add to Selection"),
                                                   self.add_to_selection)
                        if not self.active_layer.subsetString():
                            context_menu.addSeparator()
                            context_menu.addAction(self.tr('Filter Layer by values'),
                                                   self.filter_layer)
                        context_menu.addSeparator()
                        context_menu.addAction(self.tr("Select All Values"),
                                               self.listWidget.selectAll)
                        context_menu.addAction(self.tr("Switch Selected Values"),
                                               self.listWidget.switchSelectedItems)
                    context_menu.addAction(self.tr("Deselect Values"),
                                           self.listWidget.clearSelection)

                context_menu.exec_(event.globalPos())
                return True
        return super(UniqueValuesViewerDockWidget, self).eventFilter(source, event)

    def filter_layer(self) -> None:
        """Filter layer based on selected unique values in dockwidget."""
        expr = self.build_expression()
        self.active_layer.setSubsetString(expr)
        # Remove non-filtered values from listWidget and unique values property
        # when live update is not active
        if not self.liveUpdateBtn.isChecked() is True:
            self.valueSearch.clearValue()
            items = self.listWidget.selectedItems()
            self.listWidget.switchSelectedItems()
            delete_list_widget_items(self.listWidget.selectedItems(), self.listWidget)
            self.intersect_values(items)

    def intersect_values(self, items) -> None:
        """Intersects values corresponding to ``items´´ with unique values property
        @param items: List[QListWidgetItem]
        """
        values_to_intersect = {item.text() for item in items}
        self.unique_values &= values_to_intersect

    def keyPressEvent(self, event) -> None:
        """Event to clear the searchbar when Escape-Key was pressed."""
        if self.valueSearch.hasFocus() and event.key() == Qt.Key_Escape:
            self.valueSearch.clearValue()
            self.valueSearch.clearFocus()
        elif (self.valueSearch.hasFocus() and event.key() in
              {Qt.Key_Return, Qt.Key_Enter}):
            self.listWidget.setFocus()

    def remove_from_selection(self) -> None:
        """ Removes the selected items from the listWidget and the corresponding
        features from the feature selection of the active layer. Also removes
        corresponding values from the unique values property.
        """
        expr = self.build_expression()
        self.active_layer.selectByExpression(expr,
                                             behavior=QgsVectorLayer.RemoveFromSelection)

        items = self.listWidget.selectedItems()
        delete_list_widget_items(items, self.listWidget)
        self.remove_values(items)

    def remove_values(self, items) -> None:
        """Removes values corresponding to ``items´´ from unique values property.
        @param items: List[QListWidgetItem]
        """
        # create set of selected values from selected items
        values_to_remove = {item.text() for item in items}
        self.unique_values -= values_to_remove

    def reset_settings(self) -> None:
        """Restores the default settings."""
        self.enable_updates(False)
        self.settings.restore_defaults()

        self.sortOptionBtn.setCheckState(self.settings.value('value_sort', type=int))
        self.syncLayerBtn.setCheckState(self.settings.value('sync_layer', type=int))
        self.runTasksBtn.setCheckState(self.settings.value('background_proc', type=int))
        self.newLineBtn.setCheckState(self.settings.value('copy_newline', type=int))
        self.quoteCharBox.setCurrentText(self.settings.value('quote_char'))
        self.sepCharBox.setCurrentText(self.settings.value('sep_char'))

    def search_values(self) -> None:
        """Searches ListWidget for matching values and updates it to
        only show the matching ones."""
        text = self.valueSearch.text()

        # disable sort option while searching is active
        self.sortValuesBtn.setEnabled(False)

        # Only search if text is not empty
        if text:
            # TODO: Improve Search, some ideas:
            # - remember which items were selected, so that search can be used to
            #   look for different values and select them one by one with Return Key
            # - make it work for multiline fields
            # - make it more efficient/improve performance

            # Search all items which do not contain the search value!
            text_not_contained = self.listWidget.findItems('^((?!%s).)*$' % text,
                                                           Qt.MatchRegExp)  # use Qt.MatchRegularExpression for Qt 5.15+

            # Search all items which do contain the search value
            text_contained = self.listWidget.findItems(text, Qt.MatchContains)

            # Highly inefficient for large number of values!
            # Hide all items which are not contained
            for item in text_not_contained:
                if not item.isHidden():
                    item.setHidden(True)
            # Show all items which are contained
            for item in text_contained:
                if item.isHidden():
                    item.setHidden(False)

    def select_features(self) -> None:
        """Select features corresponding to selected values from the listWidget."""
        items = self.listWidget.selectedItems()
        # Select all features if all values are selected
        if (len(items) == self.listWidget.count() and
                self.selectedOnlyBtn.isChecked() is False):
            self.active_layer.selectAll()
        else:
            expr = self.build_expression()
            if self.selectedOnlyBtn.isChecked() is False:
                self.active_layer.selectByExpression(expr)
            else:
                self.active_layer.selectByExpression(expr,
                                                     behavior=QgsVectorLayer.IntersectSelection)
                self.listWidget.switchSelectedItems()
                delete_list_widget_items(self.listWidget.selectedItems(), self.listWidget)
                self.intersect_values(items)
            QgsMessageLog.logMessage(f"Selection Expression: {expr}", level=Qgis.Info)

    def setting_changed(self, key: str, value: str) -> None:
        """Change the setting ``key´´ to ``value´´.

        Parameters:
            key(str): The name of the QgsSetting
            value(str): The new value for the QgsSetting
        """
        self.settings.setValue(key, value)

    def sort_values(self) -> None:
        """Sorts the values in the ListWidget.
        Based on the sort button, ascending or descending sorting is used."""
        if not self.listWidget.sorting_enabled:
            return None

        elif self.unique_values and len(self.unique_values) > 1:

            sort_key = get_sort_key(self.field_type)

            # Change sort icon
            if self.sort_action.reverse:
                self.sortValuesBtn.setIcon(QgsApplication.getThemeIcon('/sort.svg'))
            else:
                self.sortValuesBtn.setIcon(QgsApplication.getThemeIcon('/sort-reverse.svg'))

            # Reverse sort order
            self.sort_action.reverse = not self.sort_action.reverse

            # Get a sorted list of unique values
            unique_values_list = sorted(self.unique_values,
                                        key=sort_key,
                                        reverse=self.sort_action.reverse)

            # Update ListWidget with sorted values
            self.clear_listWidget()
            if self.field_contains_null:
                self.listWidget.addItem(self.listWidget.null_item)
            self.listWidget.addItems(unique_values_list)
            self.valuesLbl.setText(f"Unique values [{len(self.unique_values)}]")
            self.sortValuesBtn.setEnabled(True)

    def show_items(self) -> None:
        """Makes all items of the listWidget unhidden."""
        # disable sort option while searching is active
        if self.sortOptionBtn.isChecked() is True:
            self.sortValuesBtn.setEnabled(True)

        for i in range(self.listWidget.count()):
            if self.listWidget.item(i).isHidden():
                self.listWidget.item(i).setHidden(False)

    def sync_iface_layer_changed(self, layer) -> None:
        """Sets the new active layer of the QGIS interface to be the
        current layer in the combobox if its data provider is not in
        the list of excluded providers.

        Parameters:
            layer(QgsMapLayer): The new active layer
        """
        if layer is not None:
            # Only sync active iface layer with plugin active layer if
            # the plugin is visible for the user
            if layer.dataProvider().name() not in EXCLUDE_PROVIDERS:
                self.valueSearch.clearValue()
                self.clear_listWidget()
                self.mMapLayerComboBox.setLayer(layer)

    def update_values(self) -> None:
        """Updates the values in the list widget."""
        # Only do something if the plugin widget is visible to the user
        # to prevent auto updates in the background when the iface active
        # layer is changed
        if self.isUserVisible():
            # Clear listWidget and search bar before updating values
            self.valueSearch.clearValue()
            self.clear_listWidget()

            # Reset selection mode of listWidget if it was previously changed
            # due to no features selected
            if self.listWidget.no_selection is True:
                self.listWidget.setExtendedSelection()

            # Use Get unique values, convert to list and sort if enabled
            if self.mMapLayerComboBox.currentLayer() is not None:
                QgsMessageLog.logMessage("Update Values", level=Qgis.Info)

                self.unique_values = set()
                try:
                    values = self.calc_unique_values()  # sets no_features_selected

                    # If no features are selected when ``Selected Features Only´´ is active
                    # disable selection in listWidget and add placeholder item
                    if self.no_features_selected:
                        self.listWidget.setNoSelection()

                    elif values:
                        if self.field_contains_null:
                            self.listWidget.addItem(self.listWidget.null_item)
                            self.valuesLbl.setText(f"Unique values [{len(values) + 1}]")
                        else:
                            self.valuesLbl.setText(f"Unique values [{len(values)}]")
                    # in case an empty list or None is returned by calc_unique_values
                    else:
                        self.listWidget.addItem(self.listWidget.null_item)
                        self.valuesLbl.setText(f"Unique values [1]")

                except SystemError:
                    self.iface.messageBar().pushMessage("Error",
                                                        "An error occurred when calculating the unique values",
                                                        level=Qgis.Critical,
                                                        duration=2)
                    traceback.print_exc()
                else:
                    if self.sortOptionBtn.isChecked() is True:
                        self.sortValuesBtn.setEnabled(True)

                    # Add unique values as items to listWidget
                    if self.listWidget.sorting_enabled:
                        sort_key = get_sort_key(self.field_type)
                        self.listWidget.addItems(sorted(values,
                                                        key=sort_key,
                                                        reverse=self.sort_action.reverse))
                    else:
                        self.listWidget.addItems(list(values))

                    # Update property
                    self.unique_values = values
