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

from __future__ import absolute_import
import os.path

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .unique_values_viewer_dockwidget import UniqueValuesViewerDockWidget


class UniqueValuesViewer:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'UniqueValuesViewer_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Unique Values Viewer')

        #print "** INITIALIZING UniqueValuesViewer"
        self.pluginIsActive = True

        self.dockwidget = UniqueValuesViewerDockWidget(self.iface,
                                                       self.plugin_dir)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('UniqueValuesViewer', message)

    def initGui(
        self,
        add_to_menu=True,
        add_to_toolbar=True):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/unique_values_viewer/icon.png'


        self.showHideAction = QAction(QIcon(icon_path), u'UniqueValuesViewer', self.dockwidget)
        self.showHideAction.setObjectName(u"mUniqueValuesViewer")
        self.showHideAction.setToolTip("<b>Unique Values Viewer<b>")
        self.dockwidget.setToggleVisibilityAction(self.showHideAction)

        # Insert Plugin Button before the Statistical Summary Widget
        if add_to_toolbar:
            self.iface.attributesToolBar().insertAction(self.iface.actionOpenStatisticalSummary(),
                                                        self.showHideAction)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, self.showHideAction)

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING UniqueValuesViewer"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD UniqueValuesViewer"

        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&Unique Values Viewer'),
                action)
            self.iface.removeToolBarIcon(action)
            self.iface.attributesToolBar().removeAction(action)
