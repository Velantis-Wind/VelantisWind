# -*- coding: utf-8 -*-
"""The .wtg reader: what it accepts, what it rejects and with which message."""
import math
import os
import tempfile
import unittest

from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable
from VelantisWind.ag_core.turbines.wtg import WtgFormatError, load_wtg

WS = [3.0, 8.0, 15.0, 25.0]
# Power in W per density, as the format writes it, and Ct.
TABLES = {
    1.225: ([30000.0, 1400000.0, 3000000.0, 3000000.0], [0.80, 0.79, 0.20, 0.05]),
    1.0: ([24000.0, 1140000.0, 3000000.0, 3000000.0], [0.81, 0.80, 0.22, 0.05]),
    1.1: ([27000.0, 1260000.0, 3000000.0, 3000000.0], [0.80, 0.80, 0.21, 0.05]),
}


def point(ws, power, ct, **override):
    attrs = {"WindSpeed": ws, "PowerOutput": power, "ThrustCoEfficient": ct}
    attrs.update(override)
    return "<DataPoint " + " ".join(f'{k}="{v}"' for k, v in attrs.items() if v is not None) + "/>"


def table(rho, power, ct, *, ws=WS, band=None, comment="", extra="", points=None):
    band = band or {"LowSpeedCutOut": 3.0, "LowSpeedCutIn": 3.0, "HighSpeedCutIn": 25.0, "HighSpeedCutOut": 25.0}
    strategy = "<StartStopStrategy " + " ".join(f'{k}="{v}"' for k, v in band.items()) + "/>"
    points = points if points is not None else "".join(point(*row) for row in zip(ws, power, ct))
    density = "" if rho is None else f'AirDensity="{rho}" '
    return (f'<PerformanceTable {density}MaximumNoiseLevel="106" StationaryThrustCoEfficient="0.05"{extra}>'
            f"{strategy}<Comments>{comment}</Comments><DataTable>{points}</DataTable></PerformanceTable>")


def document(*, tables=None, root="WindTurbineGenerator", root_attrs='FormatVersion="1.01" Description="Synthetic"',
             diameter='RotorDiameter="100"', heights="<SuggestedHeights><Height>90.0</Height></SuggestedHeights>"):
    tables = tables if tables is not None else "".join(table(rho, *TABLES[rho]) for rho in TABLES)
    return f'<?xml version="1.0" encoding="UTF-8"?><{root} {root_attrs} {diameter}>{heights}{tables}</{root}>'


class WtgTestCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def write(self, text, name="turbine.wtg"):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def load(self, text=None, **kwargs):
        return load_wtg(self.write(text if text is not None else document()), **kwargs)

    def assertRejected(self, text, pattern, **kwargs):
        with self.assertRaisesRegex(WtgFormatError, pattern) as ctx:
            self.load(text, **kwargs)
        template, data = ctx.exception.template_item
        self.assertEqual(template.format(**data), str(ctx.exception))
        return ctx.exception


class ReadTest(WtgTestCase):
    def test_valid_turbine_with_internal_dtd_is_accepted(self):
        xml = document().replace(
            "?><WindTurbineGenerator", "?>\n<!DOCTYPE WindTurbineGenerator [<!ELEMENT WindTurbineGenerator ANY>]>\n<WindTurbineGenerator", 1
        )
        loaded = self.load(xml)
        self.assertEqual(loaded.source_format, "wtg")

    def test_entity_declaration_in_turbine_dtd_is_rejected(self):
        xml = document().replace(
            "?><WindTurbineGenerator", "?>\n<!DOCTYPE WindTurbineGenerator [<!ENTITY payload 'ATTACK'>]>\n<WindTurbineGenerator", 1
        )
        self.assertRejected(xml, "EntitiesForbidden")

    def test_rejects_xml_entity_declarations(self):
        dangerous = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY payload "ATTACK">]><x>&payload;</x>'
        self.assertRejected(dangerous, "No se pudo leer el XML")

    def test_equivalent_to_a_hand_made_table(self):
        loaded = self.load()
        rho = sorted(TABLES)
        expected = TurbineCurveTable(
            name="Synthetic", diameter_m=100.0, hub_height_m=90.0, wind_speeds_ms=tuple(WS), air_densities=tuple(rho),
            power_kw=tuple(tuple(TABLES[r][0][i] / 1000.0 for r in rho) for i in range(len(WS))),
            ct=tuple(tuple(TABLES[r][1][i] for r in rho) for i in range(len(WS))),
            default_air_density=1.225, cut_in_ms=3.0, cut_out_ms=25.0,
        )
        for field in ("name", "diameter_m", "hub_height_m", "wind_speeds_ms", "air_densities", "power_kw", "ct",
                      "default_air_density", "cut_in_ms", "cut_out_ms"):
            self.assertEqual(getattr(loaded, field), getattr(expected, field), field)
        self.assertIsNone(loaded.rated_power_kw)
        self.assertEqual(loaded.source_format, "wtg")

    def test_first_table_density_is_the_default_even_if_it_is_not_the_lowest(self):
        loaded = self.load()
        self.assertEqual(loaded.air_densities, (1.0, 1.1, 1.225))
        self.assertEqual(loaded.default_air_density, 1.225)
        self.assertTrue(any("primera tabla (1.225 kg/m³)" in note for note in loaded.notes))

    def test_a_single_table_is_valid(self):
        loaded = self.load(document(tables=table(1.225, *TABLES[1.225])))
        self.assertFalse(loaded.is_density_dependent)

    def test_notes_separate_physical_consequences_from_unused_data(self):
        notes = "\n".join(self.load().notes)
        self.assertIn("StationaryThrustCoEfficient", notes)
        self.assertIn("afecta a las estelas", notes)
        self.assertIn("No se usan estos atributos de las tablas: MaximumNoiseLevel", notes)
        self.assertIn("FormatVersion del fichero: 1.01", notes)

    def test_other_version_or_root_is_read_with_a_note(self):
        loaded = self.load(document(root_attrs='FormatVersion="2.0" Description="Synthetic"'))
        self.assertTrue(any("FormatVersion del fichero: 2.0" in note for note in loaded.notes))
        for root in ("TurbineData", "TurbineType"):
            with self.subTest(root=root):
                loaded = self.load(document(root=root))
                self.assertEqual(loaded.air_densities, (1.0, 1.1, 1.225))
                self.assertTrue(any(f"<{root}>" in note for note in loaded.notes))

    def test_name_falls_back_to_the_file_name(self):
        loaded = load_wtg(self.write(document(root_attrs='FormatVersion="1.01"'), name="My turbine.wtg"))
        self.assertEqual(loaded.name, "My turbine")
        self.assertTrue(any("nombre del fichero" in note for note in loaded.notes))

    def test_the_declared_band_wins_with_a_note(self):
        band = {"LowSpeedCutIn": 3.0, "HighSpeedCutOut": 20.0}
        loaded = self.load(document(tables="".join(table(rho, *TABLES[rho], band=band) for rho in TABLES)))
        self.assertEqual(loaded.cut_out_ms, 20.0)
        self.assertEqual(loaded.power_kw[-1], (0.0, 0.0, 0.0))
        self.assertTrue(any("fuera de la banda declarada" in note for note in loaded.notes))

    def test_implausible_power_coefficient_is_a_note_not_a_rejection(self):
        # Power written in kW instead of W.
        tables = "".join(table(rho, [p / 1000.0 for p in TABLES[rho][0]], TABLES[rho][1]) for rho in TABLES)
        loaded = self.load(document(tables=tables))
        self.assertTrue(any("Cp implícito máximo" in note and "sospechosos" in note for note in loaded.notes))
        self.assertFalse(any("Cp implícito" in note for note in self.load().notes))

    def test_a_wind_speed_close_to_zero_does_not_break_the_power_coefficient(self):
        points = "".join(point(w, p, c) for w, p, c in zip([1e-110] + WS[1:], *TABLES[1.0]))
        band = {"LowSpeedCutIn": 1e-110, "HighSpeedCutOut": 25.0}
        self.assertEqual(self.load(document(tables=table(1.0, *TABLES[1.0], points=points, band=band))).cut_in_ms, 1e-110)

    def test_one_of_several_heights_is_chosen_explicitly(self):
        heights = "<SuggestedHeights><Height>80.0</Height><Height>94.0</Height></SuggestedHeights>"
        error = self.assertRejected(document(heights=heights), r"varias alturas de buje \(80 m, 94 m\): hay que elegir")
        self.assertEqual(error.suggested_heights, (80.0, 94.0))
        self.assertEqual(self.load(document(heights=heights), hub_height_m=94.0).hub_height_m, 94.0)
        self.assertRejected(document(heights=heights), r"altura elegida \(90 m\) no es una de las alturas", hub_height_m=90.0)


class RejectionTest(WtgTestCase):
    def test_missing_file_and_broken_xml(self):
        with self.assertRaisesRegex(WtgFormatError, "No existe el fichero"):
            load_wtg(os.path.join(self.folder, "none.wtg"))
        self.assertRejected("<WindTurbineGenerator><", "No se pudo leer el XML de turbine.wtg")

    def test_owtg_root_without_wtg_fields(self):
        self.assertRejected("<TurbineType><Name>X</Name></TurbineType>", r"parece un \.owtg")

    def test_no_performance_table(self):
        self.assertRejected(document(tables=""), r"no soportada: turbine\.wtg no tiene ningún <PerformanceTable> \(raíz <WindTurbineGenerator>\)")

    def test_rotor_diameter(self):
        self.assertRejected(document(diameter=""), "falta el atributo RotorDiameter en la raíz")
        self.assertRejected(document(diameter='RotorDiameter="ancho"'), r"@RotorDiameter no es un número finito: 'ancho'")
        self.assertRejected(document(diameter='RotorDiameter="0"'), "RotorDiameter debe ser positivo")

    def test_suggested_heights(self):
        self.assertRejected(document(heights=""), "falta el elemento <SuggestedHeights> en la raíz")
        twice = "<SuggestedHeights><Height>90</Height></SuggestedHeights>" * 2
        self.assertRejected(document(heights=twice), "tiene 2 elementos <SuggestedHeights> donde se espera uno")
        self.assertRejected(document(heights="<SuggestedHeights/>"), "no contiene ningún <Height>")
        self.assertRejected(document(heights="<SuggestedHeights><Height>-5</Height></SuggestedHeights>"),
                            r"Height\[1\] no es una altura positiva")

    def test_air_density(self):
        self.assertRejected(document(tables=table(None, *TABLES[1.0])), r"falta el atributo AirDensity en PerformanceTable\[1\]")
        self.assertRejected(document(tables=table("nan", *TABLES[1.0])), r"PerformanceTable\[1\]/@AirDensity no es un número finito")
        self.assertRejected(document(tables=table(0, *TABLES[1.0])), r"PerformanceTable\[1\]/@AirDensity debe ser positiva")

    def test_repeated_density_is_ambiguous(self):
        tables = table(1.225, *TABLES[1.225]) + table(1.0, *TABLES[1.0]) + table(1.225, *TABLES[1.225])
        self.assertRejected(document(tables=tables), r"tablas 1 y 3 tienen la misma densidad \(1\.225 kg/m³\).*ambiguo")

    def test_different_modes_in_the_comments(self):
        for first, second in (("Noise Mode 0", "Noise Mode 2"), ("Noise Mode 0", "Power Mode 0"), ("Noise Mode 0", ""),
                              ("Noise Mode 0", "Noise Mode 0 / Noise Mode 1")):
            with self.subTest(second=second):
                tables = table(1.0, *TABLES[1.0], comment=first) + table(1.1, *TABLES[1.1], comment=second)
                self.assertRejected(document(tables=tables), "nombran modos de operación distintos")

    def test_the_same_mode_with_other_annotations_is_read(self):
        tables = (table(1.0, *TABLES[1.0], comment="Noise Mode 0 | rev. A")
                  + table(1.1, *TABLES[1.1], comment="noise mode 0, measured"))
        loaded = self.load(document(tables=tables))
        self.assertTrue(any("mismo modo en sus comentarios: Noise Mode 0" in note for note in loaded.notes))

    def test_start_stop_strategy(self):
        no_strategy = table(1.0, *TABLES[1.0]).replace('<StartStopStrategy LowSpeedCutOut="3.0" LowSpeedCutIn="3.0" HighSpeedCutIn="25.0" HighSpeedCutOut="25.0"/>', "")
        self.assertRejected(document(tables=no_strategy), r"falta el elemento <StartStopStrategy> en PerformanceTable\[1\]")
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0], band={"HighSpeedCutOut": 25.0})),
                            r"falta el atributo LowSpeedCutIn en PerformanceTable\[1\]/StartStopStrategy")
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0], band={"LowSpeedCutIn": 25.0, "HighSpeedCutOut": 3.0})),
                            "LowSpeedCutIn=25 y HighSpeedCutOut=3")

    def test_hysteresis_is_rejected(self):
        for band, name in (({"LowSpeedCutOut": 2.5, "LowSpeedCutIn": 3.0, "HighSpeedCutOut": 25.0}, "LowSpeedCutOut=2.5"),
                           ({"LowSpeedCutIn": 3.0, "HighSpeedCutIn": 22.0, "HighSpeedCutOut": 25.0}, "HighSpeedCutIn=22")):
            with self.subTest(name=name):
                self.assertRejected(document(tables=table(1.0, *TABLES[1.0], band=band)), rf"histéresis \({name}")

    def test_data_table(self):
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0]).replace("<DataTable>", "<DataTable></DataTable><DataTable>")),
                            "tiene 2 elementos <DataTable>")
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0], points=point(3.0, 1000.0, 0.8))),
                            r"PerformanceTable\[1\]/DataTable tiene 1 DataPoint; hacen falta al menos 2")

    def test_data_points(self):
        cases = (
            (point(8.0, 1000.0, None), r"falta el atributo ThrustCoEfficient en PerformanceTable\[1\]/DataTable/DataPoint\[2\]"),
            (point(8.0, "1,4e6", 0.8), r"DataPoint\[2\]/@PowerOutput no es un número finito: '1,4e6'"),
            (point(8.0, 1000.0, "nan"), r"DataPoint\[2\]/@ThrustCoEfficient no es un número finito"),
            (point(8.0, -1.0, 0.8), r"DataPoint\[2\]/@PowerOutput es negativa"),
            (point(2.0, 1000.0, 0.8), r"DataPoint\[2\]/@WindSpeed=2 no es mayor que la velocidad anterior"),
        )
        for second, pattern in cases:
            with self.subTest(pattern=pattern):
                points = point(3.0, 30000.0, 0.8) + second + point(25.0, 3000000.0, 0.05)
                self.assertRejected(document(tables=table(1.0, *TABLES[1.0], points=points)), pattern)
        points = point(-1.0, 0.0, 0.0) + point(3.0, 30000.0, 0.8)
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0], points=points)), r"DataPoint\[1\]/@WindSpeed=-1")

    def test_grid_and_band_must_match_between_tables(self):
        other_ws = [3.0, 8.5, 15.0, 25.0]
        tables = table(1.0, *TABLES[1.0]) + table(1.1, *TABLES[1.1], ws=other_ws)
        self.assertRejected(document(tables=tables), r"tabla 2 \(1\.1 kg/m³\) no tiene las mismas velocidades")
        tables = table(1.0, *TABLES[1.0]) + table(1.1, *TABLES[1.1], band={"LowSpeedCutIn": 3.0, "HighSpeedCutOut": 20.0})
        self.assertRejected(document(tables=tables), r"tabla 2 \(1\.1 kg/m³\) declara la banda 3–20 m/s")

    def test_shared_validation_is_reported_for_the_file(self):
        band = {"LowSpeedCutIn": 3.0, "HighSpeedCutOut": 26.0}
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0], band=band)),
                            r"Variante de \.wtg no soportada en turbine\.wtg: El cut-out declarado \(26 m/s\) queda fuera de las velocidades tabuladas")
        power, ct = TABLES[1.1]
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0]) + table(1.1, power, [0.8, 1.3, 0.2, 0.05])),
                            r"Variante de \.wtg no soportada en turbine\.wtg: Valor de Ct fuera de rango a 8 m/s y 1\.1 kg/m³: 1\.3 > 1\.2")
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0]) + table(1.1, [0.0] * 4, ct)),
                            r"Variante de \.wtg no soportada en turbine\.wtg: La curva de potencia a 1\.1 kg/m³ es cero en todos los puntos")
        self.assertRejected(document(tables=table(1.0, *TABLES[1.0]) + table(1.1, power, [0.0] * 4)),
                            r"Variante de \.wtg no soportada en turbine\.wtg: La curva de Ct a 1\.1 kg/m³ es cero en todos los puntos")


if __name__ == "__main__":
    unittest.main()
