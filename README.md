# unique_values_viewer
  A QGIS plugin to display and copy the unique values of a vector layer field.
  
  This plugin integrates into QGIS as a dockwidget, where it is opened on the right panel side of the QGIS interface by default.

  <img width="245" alt="UVV_Screenshot" src="https://user-images.githubusercontent.com/78353871/107248040-367cf500-6a32-11eb-920c-3e7c9a569203.png">
  
  Currently, vector Layers with provider type 'gpx', 'memory' and 'ogr' are supported. Other provider types are reasonable, but not yet tested.

## Features

  The active layer for the plugin can be selected from the top layer dropdown menu.
  The corresponding field can be selected from the dropdown menu below.
 
  By clicking on the 'Get values' button, the unique values of the selected field are calculated and
  will be displayed in the widget below.
  
  A context menu provides some functionality to copy the values or to select the corresponding features of the layer.
  
  The search bar allows for to search the values displayed in the widget. Several search options can be selected from the settings tab.
  There, some other plugin properties, like sorting and automatically updating values, can also be set.

  The "Selected features only" checkbox verifies that only the values of selected features are displayed. With the auto-update function, 
  the values will interactively change, when the selection changes.
  
## Future Improvements
  Since this is the first published and a very early version of the plugin, not all features are matured, tested and 
  running perfectly fine. Hopefully, future development will help to improve the plugin. Suggestions and ideas are gladly welcome!
  
#### Coming soon (v0.2):
* [x] Improve the search function (include NULL values, sort text in alphabetical order, optimize for different field types like 'date' or 'time')
* [x] Support for fields containing NULL-values
* [x] Better handling of different field types (especially 'date' and 'datetime')
* [x] Data type specific sorting (alphabetic vs. alphanumeric)
* [x] Shortcut enabled
* [x] Remove pandas dependency
  
#### Further ideas: 

* [ ] Add support for multiple fields / field combinations
* [ ] Enable support for other data providers, e.g. classified raster layers
* [ ] Improve the general performance, add functionality for very large datasets / fields

## License
This program is licensed under [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.html) or any later version
