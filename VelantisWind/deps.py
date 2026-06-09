"""
Dependency checker for the Velantis Wind QGIS plugin.

Se encarga de comprobar que las dependencias de Python estén instaladas.
Ahora mismo está configurado para no bloquear el plugin si faltan librerías:
si no se define ninguna dependencia en REQUIRED_PACKAGES, siempre devuelve True.

Si quieres que realmente compruebe cosas como 'py_wake', edita REQUIRED_PACKAGES.
"""

from importlib.util import find_spec

# Intenta importar las clases de Qt de QGIS (para mostrar mensajes bonitos en QGIS)
try:
    from qgis.PyQt.QtWidgets import QMessageBox
except Exception:  # Si falla (por ejemplo, ejecutando fuera de QGIS), simplemente no se usan diálogos
    QMessageBox = None


# ----------------------------------------------------------------------
# CONFIGURA AQUÍ LAS DEPENDENCIAS QUE QUIERAS COMPROBAR
# ----------------------------------------------------------------------
# Formato: ("nombre_del_módulo_para_import", "nombre_paquete_pip_para_instalar")
#
# Ejemplo si quieres comprobar py_wake y numpy:
#
# REQUIRED_PACKAGES = [
#     ("py_wake", "py_wake"),
#     ("numpy", "numpy"),
# ]
#
# De momento lo dejamos vacío para que el plugin NO se bloquee por dependencias.
REQUIRED_PACKAGES = []


def _is_module_available(module_name: str) -> bool:
    """
    Devuelve True si el módulo está disponible para importar, False en caso contrario.
    """
    return find_spec(module_name) is not None


def _show_error_message(text: str, parent=None) -> None:
    """
    Muestra un mensaje de error en una ventana de QGIS si es posible.
    Si no se puede (por ejemplo, fuera de QGIS), imprime el mensaje por consola.
    """
    if QMessageBox is not None and parent is not None:
        QMessageBox.critical(parent, "Missing dependencies", text)
    else:
        # Fallback: imprimir por consola
        print("==== MISSING DEPENDENCIES ====")
        print(text)
        print("=================================")


def ensure_dependencies(parent=None) -> bool:
    """
    Comprueba que todas las dependencias definidas en REQUIRED_PACKAGES
    estén disponibles. Si faltan, muestra un mensaje y devuelve False.

    Si REQUIRED_PACKAGES está vacío, devuelve True directamente y no hace nada.
    Esto evita que el plugin falle por este chequeo.

    Parámetros
    ----------
    parent : QWidget o None
        Ventana padre de QGIS, normalmente self.iface.mainWindow().
        Se usa para mostrar el QMessageBox dentro de QGIS.

    Retorno
    -------
    bool
        True si todas las dependencias están disponibles (o no se ha pedido comprobar ninguna).
        False si falta alguna dependencia.
    """
    # Si no se ha definido ninguna dependencia, no bloqueamos el plugin.
    if not REQUIRED_PACKAGES:
        return True

    missing = []

    for module_name, pip_name in REQUIRED_PACKAGES:
        if not _is_module_available(module_name):
            missing.append((module_name, pip_name))

    if missing:
        msg_lines = [
            "Faltan las siguientes dependencias de Python para ejecutar Velantis Wind:",
            "",
        ]
        for module_name, pip_name in missing:
            msg_lines.append(f"  - Módulo: {module_name}  (pip: {pip_name})")

        msg_lines.append("")
        msg_lines.append("Instálalas en el entorno de Python de QGIS y vuelve a intentarlo.")

        _show_error_message("\n".join(msg_lines), parent=parent)
        return False

    # Todo correcto
    return True
