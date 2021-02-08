# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UniqueValuesViewer
                                 A QGIS plugin
 A simple plugin for displaying the unique values of an attribute of a vector layer
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2020-09-18
        copyright            : (C) 2020 by Malik Blesius
        email                : malik.blesius@foea.de
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load UniqueValuesViewer class from file UniqueValuesViewer.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .unique_values_viewer import UniqueValuesViewer
    return UniqueValuesViewer(iface)
