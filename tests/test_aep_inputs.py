# -*- coding: utf-8 -*-
"""What a wake raster compares with the last AEP: the categories of inputs that differ (#36)."""
import unittest

from VelantisWind.ag_core.wake_setup.api import NOT_SET
from VelantisWind.energy_core import aep_inputs
from VelantisWind.energy_core.domain import EnergyRunConfig, TurbineModelInput

WT = object()
PHYSICS = {"version": 1, "engine": "PropagateDownwind", "deficit": "BastankhahGaussianDeficit",
           "deficit_params": {"k": 0.0324555}, "adaptations": [{"change": "rotor", "acceptance": "continue"}]}
UNIFORM = {"mode": "uniform", "reference_density_kg_m3": 1.15, "reference_altitude_m": None}


def run(**changes):
    """The configuration of an AEP with a WRG and its fixed TI."""
    values = dict(models=[TurbineModelInput(name="A", wt=WT, meta={"hh": 90.0}, coords_xy=[(1.0, 2.0)])],
                  wrg_paths=["site.wrg"], fixed_ti=0.1, wake_physics=PHYSICS, project_crs_authid="EPSG:32630",
                  wrg_direction_count=None, wrg_wd_interp="nearest", energy_ws_step=0.5, air_density_mode="uniform",
                  air_density_ref_kg_m3=1.15)
    values.update(changes)
    return EnergyRunConfig(**values)


def raster(**changes):
    """The same inputs as read by the wake raster from the dialog."""
    values = dict(models=[{"name": "A", "wt": WT, "meta": {"hh": 90.0}, "coords_xy": [(1.0, 2.0)],
                           "source_layer_id": "layer"}],
                  wasp_dir="/a/folder", wrg_paths=["site.wrg"], wrg_ti_paths=[], wrg_ti_heights_m=[], fixed_ti=0.1,
                  direction_count=None, wd_interp="nearest", wake_physics=PHYSICS, density=UNIFORM,
                  project_crs="EPSG:32630")
    values.update(changes)
    return aep_inputs.summarise(**values)


class DifferencesTest(unittest.TestCase):
    def differences(self, **changes):
        return aep_inputs.differences(aep_inputs.from_run_config(run()), raster(**changes))

    def test_the_same_inputs_differ_in_nothing(self):
        self.assertEqual(self.differences(), [])

    def test_without_a_previous_aep_nothing_is_compared(self):
        self.assertEqual(aep_inputs.differences(None, raster(density={"mode": "off"})), [])

    def test_each_category(self):
        moved = [{"name": "A", "wt": WT, "meta": {"hh": 90.0}, "coords_xy": [(1.0, 3.0)]}]
        other_turbine = [{"name": "A", "wt": object(), "meta": {"hh": 90.0}, "coords_xy": [(1.0, 2.0)]}]
        cases = {
            "turbinas y posiciones": [dict(models=moved), dict(models=other_turbine)],
            "recurso eólico y turbulencia": [dict(wrg_paths=["other.wrg"]), dict(fixed_ti=0.12),
                                             dict(wrg_ti_paths=["ti.tif"]), dict(direction_count=12),
                                             dict(wd_interp="linear"), dict(wrg_paths=None)],
            "modelo de estela": [dict(wake_physics=dict(PHYSICS, deficit_params={"k": 0.04})),
                                 dict(wake_physics=dict(PHYSICS, adaptations=[]))],
            "densidad del aire": [dict(density={"mode": "off"}), dict(density=dict(UNIFORM, reference_density_kg_m3=1.1))],
            "sistema de coordenadas del proyecto": [dict(project_crs="EPSG:25830")],
        }
        for label, changes in cases.items():
            for change in changes:
                with self.subTest(change=change):
                    self.assertEqual(self.differences(**change), [label])
        self.assertEqual(self.differences(density={"mode": "off"}, project_crs="EPSG:25830"),
                         ["densidad del aire", "sistema de coordenadas del proyecto"])

    def test_what_does_not_change_the_field_is_not_compared(self):
        # The speed step of the AEP and how an adaptation was accepted.
        previous = aep_inputs.from_run_config(run(energy_ws_step=1.0))
        saved = dict(PHYSICS, adaptations=[{"change": "rotor", "acceptance": "saved_preference"}])
        self.assertEqual(aep_inputs.differences(previous, raster(wake_physics=saved)), [])
        # The WAsP folder left in its field with a WRG, the source layer, and the TI heights without TI rasters.
        self.assertEqual(self.differences(wasp_dir="", wrg_ti_heights_m=[100.0]), [])
        # The altitude of the reference with a uniform density, which does not use it (it does per turbine).
        self.assertEqual(self.differences(density=dict(UNIFORM, reference_altitude_m=100.0)), [])
        per_turbine = dict(UNIFORM, mode="per_turbine", reference_altitude_m=90.0)
        previous = aep_inputs.from_run_config(run(air_density_mode="per_turbine", air_density_ref_altitude_m=90.0))
        self.assertEqual(aep_inputs.differences(previous, raster(density=per_turbine)), [])
        self.assertEqual(aep_inputs.differences(previous, raster(density=dict(per_turbine, reference_altitude_m=100.0))),
                         ["densidad del aire"])

    def test_empty_and_missing_values_are_the_same(self):
        previous = aep_inputs.from_run_config(run(wrg_ti_paths=None, wrg_ti_heights_m=None))
        self.assertEqual(aep_inputs.differences(previous, raster(wrg_ti_paths=None, wrg_ti_heights_m=None)), [])
        # Metadata missing or empty.
        bare = [TurbineModelInput(name="A", wt=WT, meta=None, coords_xy=[(1.0, 2.0)])]
        self.assertEqual(aep_inputs.differences(aep_inputs.from_run_config(run(models=bare)), raster(
            models=[{"name": "A", "wt": WT, "meta": {}, "coords_xy": [(1.0, 2.0)]}])), [])
        # The density switched off, whatever its values.
        off = aep_inputs.from_run_config(run(air_density_mode="off"))
        self.assertEqual(aep_inputs.differences(off, raster(density={"mode": "off", "reference_density_kg_m3": 1.2})), [])

    def test_a_configuration_without_physics_compares_its_other_inputs(self):
        # Minimal configurations (those of some tests) have no physics: nothing fails.
        previous = aep_inputs.from_run_config(run(wake_physics=NOT_SET))
        self.assertEqual(aep_inputs.differences(previous, raster(wake_physics=NOT_SET)), [])
        self.assertEqual(aep_inputs.differences(previous, raster()), ["modelo de estela"])


if __name__ == "__main__":
    unittest.main()
