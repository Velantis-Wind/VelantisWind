# -*- coding: utf-8 -*-
import unittest

from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.wake_core.domain import WakeRasterTaskConfig


class WakeRasterTaskConfigTest(unittest.TestCase):
    def test_snapshot_is_detached_from_the_dialog_state(self):
        turbine = object()
        meta = {"name": "WT A", "diam": 120.0}
        points = [[1, 2], (3.5, "4.5")]
        models = [{"wt": turbine, "meta": meta, "coords_xy": points}]
        ti_paths = ["ti.tif"]

        config = WakeRasterTaskConfig(
            models=models,
            wasp_dir="",
            wrg_paths=["a.wrg", "  ", ""],
            wrg_ti_paths=ti_paths,
        )
        models[0]["name"] = "changed"
        meta["diam"] = 999.0
        points.append((5, 6))
        ti_paths.append("other.tif")

        model = config.models[0]
        self.assertIs(model["wt"], turbine)
        self.assertNotIn("name", model)
        self.assertEqual(model["meta"]["diam"], 120.0)
        self.assertEqual(model["coords_xy"], [(1.0, 2.0), (3.5, 4.5)])
        self.assertEqual(config.wrg_paths, ["a.wrg"])
        self.assertEqual(config.wrg_ti_paths, ["ti.tif"])

    def test_the_arguments_of_the_raster_of_the_configuration(self):
        physics = cfg.WakeConfig(**{**cfg.default_config("All2AllIterative").__dict__,
                                    "turbulence": cfg.Component("STF2017TurbulenceModel", {})})
        config = WakeRasterTaskConfig(models=[], wasp_dir=None, wake_config=physics, wd_target=270.0, fixed_ti=0.08,
                                      wrg_paths=["a.wrg"], wrg_direction_count=24, wd_interp="linear")
        kwargs = config.to_engine_kwargs()

        self.assertIs(kwargs["wake_config"], physics)
        self.assertEqual(kwargs["wasp_dir"], "")
        self.assertEqual((kwargs["wrg_paths"], kwargs["wrg_direction_count"], kwargs["wrg_wd_interp"]),
                         (["a.wrg"], 24, "linear"))
        self.assertEqual(kwargs["fixed_ti"], 0.08)
        self.assertEqual(kwargs["wd_target"], 270.0)
        self.assertEqual(kwargs["resolution_m"], 300.0)
        self.assertEqual(kwargs["ws_plot"], 10.0)
        self.assertFalse(kwargs["without_blockage"])
        self.assertNotIn("progress_callback", kwargs)
        self.assertEqual(WakeRasterTaskConfig(models=[], wasp_dir="").to_engine_kwargs()["wake_config"],
                         cfg.default_config())


if __name__ == "__main__":
    unittest.main()
