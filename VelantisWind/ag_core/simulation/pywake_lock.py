# -*- coding: utf-8 -*-
"""The lock every PyWake calculation of the plugin holds (the AEP and the wake raster).

Holding this lock, the AEP and the raster never calculate at the same time, so neither can change the state of PyWake
(such as its numerical precision) while the other calculates (#75, row 5.6). Re-entrant: a calculation that nests another one (an AEP with its loss
variants) takes it again in the same thread.
"""
import threading

PYWAKE_LOCK = threading.RLock()

__all__ = ["PYWAKE_LOCK"]
