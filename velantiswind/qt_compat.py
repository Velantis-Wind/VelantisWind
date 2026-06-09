# -*- coding: utf-8 -*-
"""Small Qt5/Qt6 compatibility bootstrap for VelantisWind.

The plugin keeps the classic PyQt5/QGIS 3 enum names (Qt.AlignRight,
QSizePolicy.Expanding, QDialogButtonBox.Ok, dialog.exec_(), etc.) because
that syntax is safest for existing QGIS 3 installations. QGIS 4 uses Qt6,
where many of those aliases were moved under scoped enum classes. This
module restores the old aliases when they are missing, so the same package
can run on QGIS 3/Qt5 and QGIS 4/Qt6.
"""

from qgis.PyQt import QtCore, QtGui, QtWidgets


def _copy_attr(target, old_name, enum_owner, new_name=None):
    """Copy enum_owner.new_name to target.old_name if target lacks old_name."""
    if hasattr(target, old_name):
        return
    try:
        value = getattr(enum_owner, new_name or old_name)
    except Exception:
        return
    try:
        setattr(target, old_name, value)
    except Exception:
        pass


def _patch_qvariant():
    """Provide a minimal QVariant compatibility object for Qt6/PyQt6.

    QGIS 3/PyQt5 exposes QVariant and many QGIS plugin examples use
    QVariant.String, QVariant.Double, etc. Qt6/PyQt6 removed QVariant from
    QtCore. QGIS 4 accepts QMetaType values for QgsField definitions, so this
    shim keeps the existing code source-compatible across QGIS 3 and QGIS 4.
    """
    if hasattr(QtCore, 'QVariant'):
        return
    qmt = getattr(QtCore, 'QMetaType', None)
    qmt_type = getattr(qmt, 'Type', None) if qmt is not None else None
    if qmt_type is None:
        return

    class _QVariantCompat:
        String = getattr(qmt_type, 'QString', getattr(qmt_type, 'QStringList', None))
        Double = getattr(qmt_type, 'Double', None)
        Int = getattr(qmt_type, 'Int', None)
        LongLong = getattr(qmt_type, 'LongLong', None)
        Bool = getattr(qmt_type, 'Bool', None)
        Date = getattr(qmt_type, 'QDate', None)
        Time = getattr(qmt_type, 'QTime', None)
        DateTime = getattr(qmt_type, 'QDateTime', None)

    try:
        setattr(QtCore, 'QVariant', _QVariantCompat)
    except Exception:
        pass


def _patch_qtcore():
    _patch_qvariant()
    Qt = QtCore.Qt
    groups = {
        'AlignmentFlag': ['AlignCenter', 'AlignLeft', 'AlignRight', 'AlignTop', 'AlignVCenter', 'AlignHCenter'],
        'AspectRatioMode': ['KeepAspectRatio'],
        'CheckState': ['Checked', 'Unchecked', 'PartiallyChecked'],
        'CursorShape': ['PointingHandCursor', 'CrossCursor', 'ArrowCursor'],
        'DockWidgetArea': ['LeftDockWidgetArea', 'RightDockWidgetArea'],
        'ItemDataRole': ['UserRole', 'DisplayRole', 'EditRole'],
        'ItemFlag': ['ItemIsEditable', 'ItemIsUserCheckable', 'ItemIsEnabled', 'ItemIsSelectable'],
        'Key': ['Key_Escape'],
        'MatchFlag': ['MatchFixedString'],
        'MouseButton': ['LeftButton', 'RightButton'],
        'Orientation': ['Horizontal', 'Vertical'],
        'ScrollBarPolicy': ['ScrollBarAlwaysOff', 'ScrollBarAsNeeded'],
        'SortOrder': ['DescendingOrder', 'AscendingOrder'],
        'TextElideMode': ['ElideRight'],
        'TextFormat': ['RichText', 'PlainText'],
        'TextInteractionFlag': ['TextSelectableByMouse'],
        'TransformationMode': ['SmoothTransformation'],
        'WidgetAttribute': ['WA_DeleteOnClose'],
        'WindowModality': ['NonModal', 'WindowModal'],
    }
    for enum_name, names in groups.items():
        enum_owner = getattr(Qt, enum_name, None)
        if enum_owner is None:
            continue
        for name in names:
            _copy_attr(Qt, name, enum_owner)

    # Qt6 scopes these enums under their enum classes. Keep QGIS 3 names.
    if hasattr(QtCore, 'QEvent'):
        _copy_attr(QtCore.QEvent, 'KeyPress', getattr(QtCore.QEvent, 'Type', None))
    if hasattr(QtCore, 'QEventLoop'):
        _copy_attr(QtCore.QEventLoop, 'ExcludeUserInputEvents', getattr(QtCore.QEventLoop, 'ProcessEventsFlag', None))


def _patch_qtwidgets():
    W = QtWidgets
    mappings = [
        (W.QAbstractItemView, 'EditTrigger', ['AllEditTriggers', 'NoEditTriggers']),
        (W.QAbstractItemView, 'SelectionMode', ['ExtendedSelection', 'NoSelection', 'SingleSelection']),
        (W.QAbstractItemView, 'ScrollMode', ['ScrollPerPixel']),
        (W.QAbstractItemView, 'SelectionBehavior', ['SelectRows']),
        (W.QAbstractScrollArea, 'SizeAdjustPolicy', ['AdjustIgnored']),
        (W.QComboBox, 'SizeAdjustPolicy', ['AdjustToMinimumContentsLengthWithIcon']),
        (W.QDialog, 'DialogCode', ['Accepted', 'Rejected']),
        (W.QDialogButtonBox, 'ButtonRole', ['ActionRole']),
        (W.QDialogButtonBox, 'StandardButton', ['Ok', 'Cancel', 'Close', 'Yes', 'No']),
        (W.QDockWidget, 'DockWidgetFeature', ['DockWidgetClosable', 'DockWidgetFloatable', 'DockWidgetMovable']),
        (W.QFileDialog, 'FileMode', ['Directory']),
        (W.QFileDialog, 'Option', ['DontUseNativeDialog', 'ShowDirsOnly']),
        (W.QFormLayout, 'FieldGrowthPolicy', ['AllNonFixedFieldsGrow', 'ExpandingFieldsGrow']),
        (W.QFrame, 'Shape', ['HLine', 'NoFrame', 'StyledPanel']),
        (W.QFrame, 'Shadow', ['Sunken']),
        (W.QHeaderView, 'ResizeMode', ['Interactive', 'ResizeToContents', 'Stretch']),
        (W.QLineEdit, 'EchoMode', ['Normal']),
        (W.QMessageBox, 'Icon', ['Information', 'Warning', 'Critical']),
        (W.QMessageBox, 'StandardButton', ['Ok', 'Yes', 'No', 'Cancel', 'Close']),
        (W.QPlainTextEdit, 'LineWrapMode', ['WidgetWidth']),
        (W.QSizePolicy, 'Policy', ['Expanding', 'Fixed', 'Preferred', 'Minimum', 'Maximum']),
        (W.QStyle, 'StandardPixmap', ['SP_MessageBoxInformation']),
    ]
    for cls, enum_name, names in mappings:
        enum_owner = getattr(cls, enum_name, None)
        if enum_owner is None:
            continue
        for name in names:
            _copy_attr(cls, name, enum_owner)

    # Qt6 dropped exec_ aliases; keep existing QGIS 3 code unchanged.
    for cls_name in ['QDialog', 'QMessageBox', 'QProgressDialog']:
        cls = getattr(W, cls_name, None)
        if cls is not None and not hasattr(cls, 'exec_') and hasattr(cls, 'exec'):
            try:
                setattr(cls, 'exec_', cls.exec)
            except Exception:
                pass


def _patch_qtgui():
    # QFont.Bold moved under QFont.Weight in Qt6.
    enum_owner = getattr(QtGui.QFont, 'Weight', None)
    if enum_owner is not None:
        _copy_attr(QtGui.QFont, 'Bold', enum_owner)

    # QAction moved from QtWidgets to QtGui in Qt6. Many QGIS 3 plugins import
    # it from QtWidgets, so expose the QtGui class there when needed.
    if not hasattr(QtWidgets, 'QAction') and hasattr(QtGui, 'QAction'):
        try:
            setattr(QtWidgets, 'QAction', QtGui.QAction)
        except Exception:
            pass


def apply():
    _patch_qtcore()
    _patch_qtwidgets()
    _patch_qtgui()


apply()
