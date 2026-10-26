# -*- coding: utf-8 -*-
import unittest
from unittest import mock

from VelantisWind import i18n
from VelantisWind.ag_core import aep_compute
from VelantisWind.ag_core.log_text import log_text


class _FakeIface:
    def __init__(self):
        self.messages = []

    def messageBar(self):
        return self

    def pushMessage(self, title, text, **_kwargs):
        self.messages.append(text)


class AepLogThreadTest(unittest.TestCase):
    def _log(self, *, from_main_thread, msg="msg", level=aep_compute.Qgis.Warning):
        main_thread = object()
        current_thread = main_thread if from_main_thread else object()
        app_cls = mock.Mock()
        app_cls.instance.return_value.thread.return_value = main_thread
        qthread_cls = mock.Mock()
        qthread_cls.currentThread.return_value = current_thread
        fake = _FakeIface()
        with mock.patch.object(aep_compute, "iface", fake), \
                mock.patch.object(aep_compute, "QCoreApplication", app_cls), \
                mock.patch.object(aep_compute, "QThread", qthread_cls), \
                mock.patch.object(aep_compute.QgsMessageLog, "logMessage") as log_message:
            aep_compute._log(msg, level)
        return fake.messages, log_message.call_count

    def test_main_thread_uses_the_message_bar(self):
        self.assertEqual(self._log(from_main_thread=True), (["msg"], 1))

    def test_worker_thread_only_writes_the_message_log(self):
        self.assertEqual(self._log(from_main_thread=False), ([], 1))

    def test_information_only_goes_to_the_message_log(self):
        self.assertEqual(self._log(from_main_thread=True, level=aep_compute.Qgis.Info), ([], 1))

    def test_warning_is_translated_from_its_template(self):
        msg = log_text("[WAsP] Movidos a '_bad_for_pywake': {n} (evita crash).", n=3)
        self.assertEqual(msg, "[WAsP] Movidos a '_bad_for_pywake': 3 (evita crash).")
        with mock.patch.object(i18n, "current_language", return_value="en"):
            shown, _ = self._log(from_main_thread=True, msg=msg)
        self.assertEqual(shown, ["[WAsP] Moved to '_bad_for_pywake': 3 (avoids a crash)."])

    def test_label_inside_a_warning_is_translated_too(self):
        msg = log_text("[SIM] La simulación requirió degradación: {label}", label=log_text("sin bloqueo"))
        self.assertEqual(msg, "[SIM] La simulación requirió degradación: sin bloqueo")
        with mock.patch.object(i18n, "current_language", return_value="fr"):
            shown, _ = self._log(from_main_thread=True, msg=msg)
        self.assertEqual(shown, ["[SIM] La simulation a nécessité une dégradation : sans blocage"])


if __name__ == "__main__":
    unittest.main()
