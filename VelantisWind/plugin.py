# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Velantis Wind
                                 A QGIS plugin
 Wind farm pre-assessment: Energy / AEP, Noise and Shadow Flicker
                              -------------------
        version              : 0.1.10
        copyright            : (C) 2026 by VelantisWind contributors
        email                : info@velantiswind.com
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

import os.path

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt import QtCore
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from . import deps   # Dependency checks for py_wake and related packages.
# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .aep_setup_dialog import AEPSetupDialog
from .hub_dialog import VelantisHubDialog
from .i18n import install_runtime_i18n_patches, tr_text as _tr


class VelantisWindPlugin:
    """Main QGIS plugin implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        install_runtime_i18n_patches()
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'VelantisWind_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = _tr('&Velantis Wind')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

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
        return QCoreApplication.translate('VelantisWindPlugin', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action,
            )

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        # Toolbar/menu action icon (the small icon shown in QGIS toolbars).
        # Use the same icon declared in metadata.txt.
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=_tr('Velantis Wind'),
            callback=self.run,
            status_tip=_tr('Abrir el hub principal de Velantis Wind'),
            parent=self.iface.mainWindow(),
        )

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Velantis Wind'),
                action,
            )
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""

        # Check optional scientific dependencies before opening the main hub.
        if not deps.ensure_dependencies(parent=self.iface.mainWindow()):
            # The user cancelled or the dependency check failed.
            return

        # Create the hub dialog robustly.
        # Some QGIS plugin reloads may not preserve first_start/self.dlg.
        if (getattr(self, 'first_start', True) is True) or (not hasattr(self, 'dlg')) or (getattr(self, 'dlg', None) is None):
            self.first_start = False
            self.dlg = VelantisHubDialog(
                parent=self.iface.mainWindow(),
                energy_dialog_factory=lambda parent=None: AEPSetupDialog(parent=parent or self.iface.mainWindow())
            )
            # Apply the plugin icon here as well for environments that ignore dialog defaults.
            try:
                self.dlg.setWindowIcon(QIcon(os.path.join(self.plugin_dir, 'icon.png')))
            except Exception:
                pass

        # If the Energy module is already open from the hub, focus it instead of duplicating it.
        try:
            child = getattr(self.dlg, '_energy_dialog', None)
            if child is not None and child.isVisible():
                child.show()
                child.raise_()
                child.activateWindow()
                return
        except Exception:
            pass

        # Keep the hub non-modal so map tools and interactive layout editing can continue working.
        try:
            self.dlg.setModal(False)
            self.dlg.setWindowModality(QtCore.Qt.NonModal)
        except Exception:
            pass

        self.dlg.show()
        try:
            self.dlg.raise_()
            self.dlg.activateWindow()
        except Exception:
            pass
