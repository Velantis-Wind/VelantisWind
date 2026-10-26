# -*- coding: utf-8 -*-
"""The .owtg reader: what it accepts, what it rejects and with which message."""
import os
import tempfile
import unittest

from VelantisWind.ag_core.turbines.density_curve import TurbineCurveTable
from VelantisWind.ag_core.turbines.owtg import OwtgFormatError, load_owtg

# Tabulated from 0 m/s with zeros below the cut-in, as the format does.
WS = [0.0, 2.0, 3.0, 8.0, 15.0, 25.0]
RHO = [1.0, 1.225]
POWER = {1.0: [0.0, 0.0, 24.0, 1140.0, 3000.0, 3000.0], 1.225: [0.0, 0.0, 30.0, 1400.0, 3000.0, 3000.0]}  # kW
CT = {1.0: [0.0, 0.0, 0.81, 0.80, 0.22, 0.05], 1.225: [0.0, 0.0, 0.80, 0.79, 0.20, 0.05]}

HEAD = {
    "HubHeight": 90, "RotorDiameter": 100, "CapacityKW": 3000, "PeakOutputKW": 3000, "LowCutIn": 3,
    "HighCutOut": 25, "IEC_adjustment": 1, "TemperatureShutDownEnabled": 0, "DesignAirDensity": 1.225,
    "SwitchPowerCurvesOnIref": 0, "AdjustPowerCurvesForTI": 0, "PerformanceShiftWS": 0,
}
BLOCKS = ("HighWindHysteresis", "Derate", "Consumption", "PowerCurveAdjustment")


def turbine_table(tag, values, *, ws=WS, rho=RHO, extra=""):
    speeds = "".join(f'<Velocity{i} value="{v}"/>' for i, v in enumerate(ws))
    densities = "".join(f'<Rho{j} value="{r}"/>' for j, r in enumerate(rho))
    columns = "".join(
        f'<Rho{r:.6f}><Rows value="{len(ws)}"/>'
        + "".join(f'<v{j}-{i} value="{values[r][i]}"/>' for i in range(len(ws)))
        + f"</Rho{r:.6f}>"
        for j, r in enumerate(rho)
    )
    return (f"<{tag}><Type>TurbineTable</Type>{extra}<Velocities><Count value=\"{len(ws)}\"/>{speeds}</Velocities>"
            f"<AirDensities><Count value=\"{len(rho)}\"/>{densities}</AirDensities>"
            f"<Values><Columns value=\"{len(rho)}\"/>{columns}</Values></{tag}>")


def document(*, name="Synthetic", power=POWER, ct=CT, **head):
    fields = dict(HEAD, **head)
    values = "".join(f'<{tag} value="{value}"/>' for tag, value in fields.items() if value is not None)
    blocks = "".join(f'<{tag}><Enable value="0"/></{tag}>' for tag in BLOCKS)
    power_table = turbine_table("Power_Table0", power, extra='<TI_min value="6"/><TI_max value="12"/>')
    return (f'<?xml version="1.0" encoding="UTF-8"?><TurbineType><Name>{name}</Name>{values}'
            f'<Power_Tables><Count value="1"/>{power_table}</Power_Tables>{turbine_table("Thrust_Table", ct)}'
            f"{blocks}</TurbineType>")


def mutate(text, old, new):
    assert old in text, old
    return text.replace(old, new, 1)


class OwtgTestCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def write(self, text, name="turbine.owtg"):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def load(self, text=None):
        return load_owtg(self.write(text if text is not None else document()))

    def assertRejected(self, text, pattern):
        with self.assertRaisesRegex(OwtgFormatError, pattern) as ctx:
            self.load(text)
        template, data = ctx.exception.template_item
        self.assertEqual(template.format(**data), str(ctx.exception))
        return ctx.exception


class ReadTest(OwtgTestCase):
    def test_equivalent_to_a_hand_made_table(self):
        loaded = self.load()
        expected = TurbineCurveTable(
            name="Synthetic", diameter_m=100.0, hub_height_m=90.0, wind_speeds_ms=tuple(WS), air_densities=tuple(RHO),
            power_kw=tuple(tuple(POWER[r][i] for r in RHO) for i in range(len(WS))),
            ct=tuple(tuple(CT[r][i] for r in RHO) for i in range(len(WS))),
            default_air_density=1.225, rated_power_kw=3000.0, cut_in_ms=3.0, cut_out_ms=25.0,
        ).with_operating_band_enforced()
        for field in ("name", "diameter_m", "hub_height_m", "wind_speeds_ms", "air_densities", "power_kw", "ct",
                      "default_air_density", "rated_power_kw", "cut_in_ms", "cut_out_ms"):
            self.assertEqual(getattr(loaded, field), getattr(expected, field), field)
        self.assertEqual(loaded.source_format, "owtg")

    def test_the_declared_band_is_a_step(self):
        ws, power, ct = self.load().curve_at_density(1.225)
        below = ws.index(3.0) - 1
        self.assertAlmostEqual(ws[below], 3.0 - 1e-4)
        self.assertEqual((power[below], ct[below]), (0.0, 0.0))
        self.assertEqual((power[below + 1], ct[below + 1]), (30.0, 0.80))

    def test_a_cut_out_between_nodes_is_interpolated_with_a_note(self):
        loaded = self.load(document(HighCutOut=20))
        ws, power, ct = loaded.curve_at_density(1.225)
        self.assertEqual(power[ws.index(20.0)], 3000.0)
        self.assertAlmostEqual(ct[ws.index(20.0)], 0.2 + (0.05 - 0.2) * 5 / 10)
        self.assertEqual(power[ws.index(20.0) + 1], 0.0)
        self.assertTrue(any("Curva recortada a la banda declarada por el propio fichero (3–20 m/s)" in n for n in loaded.notes))

    def test_notes(self):
        notes = "\n".join(self.load().notes)
        self.assertIn("Densidad por defecto: la densidad de diseño del fichero (DesignAirDensity, 1.225 kg/m³).", notes)
        self.assertIn("IEC_adjustment", notes)
        self.assertIn("validez para una turbulencia entre 6 % y 12 %", notes)
        self.assertNotIn("se contradice", notes)

    def test_without_iec_adjustment_there_is_no_note(self):
        self.assertNotIn("IEC_adjustment", "\n".join(self.load(document(IEC_adjustment=0)).notes))

    def test_without_name_the_file_name_is_used(self):
        loaded = self.load(document(name=""))
        self.assertEqual(loaded.name, "turbine")
        self.assertIn("El fichero no trae Name; se usa el nombre del fichero.", loaded.notes)

    def test_two_different_rated_powers_are_read_with_a_warning(self):
        loaded = self.load(document(CapacityKW=2900, PeakOutputKW=3100))
        self.assertEqual(loaded.rated_power_kw, 2900.0)
        self.assertIn("El fichero se contradice: declara CapacityKW=2900 kW y PeakOutputKW=3100 kW. Se toma CapacityKW "
                      "como potencia nominal.", loaded.notes)

    def test_peak_output_stands_in_for_a_missing_capacity(self):
        self.assertEqual(self.load(document(CapacityKW=None, PeakOutputKW=2900)).rated_power_kw, 2900.0)

    def test_without_rated_power_the_table_maximum_is_noted(self):
        loaded = self.load(document(CapacityKW=None, PeakOutputKW=None))
        self.assertIsNone(loaded.rated_power_kw)
        self.assertIn("se toma el máximo de la tabla, 3000 kW", "\n".join(loaded.notes))

    def test_a_table_far_below_the_rated_power_is_noted(self):
        self.assertIn("menos de la mitad de los 7000 kW nominales", "\n".join(self.load(document(CapacityKW=7000)).notes))

    def test_absent_flags_are_off(self):
        text = document(TemperatureShutDownEnabled=None, PerformanceShiftWS=None, AdjustPowerCurvesForTI=None,
                        SwitchPowerCurvesOnIref=None, IEC_adjustment=None)
        for block in BLOCKS:
            text = mutate(text, f'<{block}><Enable value="0"/></{block}>', "")
        self.assertEqual(self.load(text).n_densities, 2)


class RejectTest(OwtgTestCase):
    def test_missing_file(self):
        with self.assertRaisesRegex(OwtgFormatError, "No existe el fichero .owtg"):
            load_owtg(os.path.join(self.folder, "missing.owtg"))

    def test_broken_xml(self):
        self.assertRejected("<TurbineType>", "No se pudo leer el XML de turbine.owtg")

    def test_other_root(self):
        self.assertRejected("<Turbine/>", r"la raíz de turbine.owtg es <Turbine> y se esperaba <TurbineType>")

    def test_a_wtg_points_to_its_own_reader(self):
        self.assertRejected('<WindTurbineGenerator><PerformanceTable AirDensity="1.225"/></WindTurbineGenerator>',
                            r"raíz <WindTurbineGenerator> y tablas <PerformanceTable>: parece un \.wtg")

    def test_missing_geometry_band_or_design_density(self):
        for tag in ("HubHeight", "RotorDiameter", "LowCutIn", "HighCutOut", "DesignAirDensity"):
            with self.subTest(tag=tag):
                self.assertRejected(document(**{tag: None}), f"falta el elemento <{tag}> en TurbineType")

    def test_empty_or_non_numeric_value(self):
        self.assertRejected(document(HubHeight=""), "TurbineType/HubHeight no tiene valor")
        self.assertRejected(document(RotorDiameter="ancho"), r"TurbineType/RotorDiameter no es un número finito: 'ancho'")
        self.assertRejected(document(CapacityKW="nan"), r"TurbineType/CapacityKW no es un número finito")

    def test_repeated_element(self):
        self.assertRejected(mutate(document(), '<HubHeight value="90"/>', '<HubHeight value="90"/><HubHeight value="120"/>'),
                            "TurbineType tiene 2 elementos <HubHeight> donde se espera uno")

    def test_non_positive_geometry(self):
        self.assertRejected(document(RotorDiameter=0), "El diámetro de rotor debe ser un número positivo")

    def test_table_type(self):
        self.assertRejected(mutate(document(), "<Type>TurbineTable</Type>", "<Type>TurbineTableTI</Type>"),
                            r"Power_Table0/Type es 'TurbineTableTI'; solo se admite 'TurbineTable'")

    def test_velocity_count_does_not_match(self):
        self.assertRejected(mutate(document(), '<Count value="6"/><Velocity0', '<Count value="7"/><Velocity0'),
                            r"Power_Table0/Velocities declara Count=7 y contiene los índices 0, 1, 2, 3, 4, 5 de <VelocityN>")

    def test_duplicated_index(self):
        self.assertRejected(mutate(document(), '<Rho1 value="1.225"/>', '<Rho1 value="1.225"/><Rho1 value="1.3"/>'),
                            r"índice duplicado <Rho1> en TurbineType/Power_Tables/Power_Table0/AirDensities")

    def test_index_gap(self):
        self.assertRejected(mutate(document(), '<Velocity5 value="25.0"/>', '<Velocity6 value="25.0"/>'),
                            r"contiene los índices 0, 1, 2, 3, 4, 6 de <VelocityN>; deben ir de 0 a 5 sin huecos")

    def test_columns_count_does_not_match(self):
        self.assertRejected(mutate(document(), '<Columns value="2"/>', '<Columns value="3"/>'),
                            r"Power_Table0/Values declara Columns=3 y contiene 2 columnas <RhoX>, pero AirDensities declara 2")

    def test_missing_column(self):
        text = document()
        start = text.index("<Rho1.225000>")
        text = text[:start] + text[text.index("</Rho1.225000>") + len("</Rho1.225000>"):]
        self.assertRejected(text, r"Columns=2 y contiene 1 columnas <RhoX>")

    def test_mislabelled_column(self):
        text = mutate(document(), "<Rho1.225000>", "<Rho1.250000>")
        self.assertRejected(mutate(text, "</Rho1.225000>", "</Rho1.250000>"),
                            r"la columna 1 de TurbineType/Power_Tables/Power_Table0/Values es <Rho1.250000>, pero "
                            r"AirDensities declara 1.225 kg/m³ en esa posición")

    def test_reordered_column(self):
        # The columns swapped, each one keeping its own tag and cells: the curves would swap in silence.
        text = document()
        first = text[text.index("<Rho1.000000>"):text.index("</Rho1.000000>") + len("</Rho1.000000>")]
        second = text[text.index("<Rho1.225000>"):text.index("</Rho1.225000>") + len("</Rho1.225000>")]
        self.assertRejected(text.replace(first + second, second + first, 1), r"la columna 0 de .* es <Rho1.225000>")

    def test_cell_in_another_column(self):
        self.assertRejected(mutate(document(), '<v1-2 value="30.0"/>', '<v0-2 value="30.0"/>'),
                            r"la celda <v0-2> está en la columna 1 de TurbineType/Power_Tables/Power_Table0/Values")

    def test_duplicated_cell(self):
        self.assertRejected(mutate(document(), '<v0-2 value="24.0"/>', '<v0-2 value="24.0"/><v0-2 value="25.0"/>'),
                            r"celda duplicada <v0-2> en TurbineType/Power_Tables/Power_Table0/Values/Rho1.000000")

    def test_missing_cell(self):
        self.assertRejected(mutate(document(), '<v0-2 value="24.0"/>', ""),
                            r"Values/Rho1.000000 declara Rows=6 y contiene las filas 0, 1, 3, 4, 5; Velocities declara 6")

    def test_rows_do_not_match(self):
        self.assertRejected(mutate(document(), '<Rho1.000000><Rows value="6"/>', '<Rho1.000000><Rows value="5"/>'),
                            r"Rho1.000000 declara Rows=5 y contiene las filas 0, 1, 2, 3, 4, 5")

    def test_thrust_grid_differs(self):
        ws = [0.0, 2.0, 3.0, 8.0, 16.0, 25.0]
        text = document()
        thrust = text[text.index("<Thrust_Table>"):text.index("</Thrust_Table>") + len("</Thrust_Table>")]
        self.assertRejected(text.replace(thrust, turbine_table("Thrust_Table", CT, ws=ws)),
                            r"las velocidades de la tabla de empuje \(6 valores\) no coinciden con las de la tabla de potencia")
        ct = {1.0: CT[1.0], 1.2: CT[1.225]}
        self.assertRejected(text.replace(thrust, turbine_table("Thrust_Table", ct, rho=[1.0, 1.2])),
                            r"las densidades de la tabla de empuje \(2 valores\) no coinciden")

    def test_curves_that_depend_on_turbulence(self):
        self.assertRejected(document(AdjustPowerCurvesForTI=1),
                            "AdjustPowerCurvesForTI=1. Las curvas de potencia dependen de la intensidad de turbulencia")
        self.assertRejected(document(SwitchPowerCurvesOnIref=1),
                            "SwitchPowerCurvesOnIref=1. Las curvas de potencia dependen de la clase de turbulencia Iref")

    def test_more_than_one_power_table(self):
        text = document()
        table = text[text.index("<Power_Table0>"):text.index("</Power_Table0>") + len("</Power_Table0>")]
        second = table.replace("Power_Table0", "Power_Table1")
        self.assertRejected(mutate(text, '<Count value="1"/>' + table, '<Count value="2"/>' + table + second),
                            r"Power_Tables declara Count=2 y contiene 2 tablas de potencia; solo se admite una")
        self.assertRejected(mutate(text, table, table + second), r"Count=1 y contiene 2 tablas de potencia")
        self.assertRejected(mutate(text, table, second), r"Count=1 y contiene las tablas 1; se espera una sola, <Power_Table0>")

    def test_active_operating_modifications(self):
        for block, what in (("HighWindHysteresis", "la histéresis de viento fuerte"),
                            ("Derate", "la reducción de potencia por temperatura y altitud"),
                            ("PowerCurveAdjustment", "el ajuste de la curva de potencia"),
                            ("Consumption", "el consumo propio de la turbina")):
            with self.subTest(block=block):
                text = mutate(document(), f'<{block}><Enable value="0"/>', f'<{block}><Enable value="1"/>')
                self.assertRejected(text, f"{block}/Enable=1 activa {what}, que este cálculo no representa")
        self.assertRejected(document(TemperatureShutDownEnabled=1), "TemperatureShutDownEnabled=1 activa la parada por temperatura")
        self.assertRejected(document(PerformanceShiftWS=0.5), "PerformanceShiftWS=0.5 activa el desplazamiento de la curva en velocidad")

    def test_a_modification_block_must_say_whether_it_is_enabled(self):
        self.assertRejected(mutate(document(), '<Derate><Enable value="0"/></Derate>', "<Derate/>"),
                            "falta el elemento <Enable> en Derate")

    def test_table_above_the_rated_power(self):
        self.assertRejected(document(CapacityKW=2800, PeakOutputKW=None),
                            r"llega a 3000, más de un 5 % por encima de la potencia nominal declarada \(CapacityKW=2800 kW\)")

    def test_table_above_the_capacity_even_if_the_peak_output_covers_it(self):
        self.assertRejected(document(CapacityKW=2800, PeakOutputKW=3000), r"\(CapacityKW=2800 kW\)")

    def test_table_above_the_peak_output_without_capacity(self):
        self.assertRejected(document(CapacityKW=None, PeakOutputKW=2800), r"\(PeakOutputKW=2800 kW\)")

    def test_table_in_watts_without_rated_power(self):
        watts = {r: [v * 1000.0 for v in POWER[r]] for r in RHO}
        self.assertRejected(document(power=watts, CapacityKW=None, PeakOutputKW=None),
                            r"llega a 3e\+06 y el fichero no declara CapacityKW ni PeakOutputKW .* parece estar en W")

    def test_zero_rated_power(self):
        self.assertRejected(document(CapacityKW=0), "La potencia nominal debe ser un número positivo")

    def test_cut_out_outside_the_table(self):
        self.assertRejected(document(HighCutOut=26),
                            r"Variante de .owtg no soportada en turbine.owtg: El cut-out declarado \(26 m/s\) queda fuera de "
                            r"las velocidades tabuladas \(0–25 m/s\)")

    def test_cut_in_not_below_cut_out(self):
        self.assertRejected(document(LowCutIn=25, HighCutOut=15), r"El cut-in \(25 m/s\) debe ser menor que el cut-out")

    def test_thrust_out_of_range_or_all_zero(self):
        ct = {r: list(CT[r]) for r in RHO}
        ct[1.0][3] = 1.3
        self.assertRejected(document(ct=ct), r"Valor de Ct fuera de rango a 8 m/s y 1 kg/m³: 1.3 > 1.2")
        ct = {r: [0.0] * len(WS) for r in RHO}
        self.assertRejected(document(ct=ct), "La curva de Ct a 1 kg/m³ es cero en todos los puntos")

    def test_negative_power(self):
        power = {r: list(POWER[r]) for r in RHO}
        power[1.225][3] = -5.0
        self.assertRejected(document(power=power), "Valor de potencia negativo a 8 m/s y 1.225 kg/m³")

    def test_no_wind_speeds_or_no_densities(self):
        def tables(**grid):
            text = document()
            for tag in ("Power_Table0", "Thrust_Table"):
                old = text[text.index(f"<{tag}>"):text.index(f"</{tag}>") + len(f"</{tag}>")]
                text = text.replace(old, turbine_table(tag, {r: [] for r in RHO}, **grid))
            return text

        self.assertRejected(tables(ws=[]), "no soportada en turbine.owtg: La curva necesita al menos 2 velocidades de viento; se recibieron 0")
        self.assertRejected(tables(rho=[]), "no soportada en turbine.owtg: La curva necesita al menos una densidad de aire")

    def test_unexpected_elements_in_the_matrix(self):
        self.assertRejected(mutate(document(), '<v0-2 value="24.0"/>', '<v0-2 value="24.0"/><v0-extra value="9999"/>'),
                            r"elemento inesperado <v0-extra> en TurbineType/Power_Tables/Power_Table0/Values/Rho1.000000")
        self.assertRejected(mutate(document(), '<Columns value="2"/>', '<Columns value="2"/><Note value="1"/>'),
                            r"elemento inesperado <Note> en TurbineType/Power_Tables/Power_Table0/Values")
        self.assertRejected(mutate(document(), '<Velocity5 value="25.0"/>', '<Velocity5 value="25.0"/><Velocity6b value="30"/>'),
                            r"elemento inesperado <Velocity6b> en TurbineType/Power_Tables/Power_Table0/Velocities")
        # A column tag that is numerically right but not written as <RhoX.XXXXXX>.
        text = mutate(document(), "<Rho1.000000>", "<Rho1e0>")
        self.assertRejected(mutate(text, "</Rho1.000000>", "</Rho1e0>"), r"elemento inesperado <Rho1e0> en TurbineType/Power_Tables/Power_Table0/Values")
        text = document()
        table = text[text.index("<Power_Table0>"):text.index("</Power_Table0>") + len("</Power_Table0>")]
        extra = table.replace("Power_Table0", "Power_Table1-extra")
        self.assertRejected(mutate(text, table, table + extra), r"elemento inesperado <Power_Table1-extra> en TurbineType/Power_Tables")

    def test_iec_adjustment_other_than_0_or_1(self):
        self.assertRejected(document(IEC_adjustment=2), r"IEC_adjustment=2; solo se admiten 0 y 1")

    def test_empty_or_non_numeric_flags(self):
        self.assertRejected(mutate(document(), '<Derate><Enable value="0"/>', '<Derate><Enable value=""/>'), "Derate/Enable no tiene valor")
        self.assertRejected(mutate(document(), '<Derate><Enable value="0"/>', '<Derate><Enable value="no"/>'),
                            r"Derate/Enable no es un número finito: 'no'")
        self.assertRejected(document(TemperatureShutDownEnabled=""), "TurbineType/TemperatureShutDownEnabled no tiene valor")
        self.assertRejected(document(AdjustPowerCurvesForTI="x"), r"TurbineType/AdjustPowerCurvesForTI no es un número finito: 'x'")

    def test_power_zero_everywhere(self):
        power = {r: [0.0] * len(WS) for r in RHO}
        self.assertRejected(document(power=power), "La curva de potencia a 1 kg/m³ es cero en todos los puntos")

    def test_decreasing_wind_speeds(self):
        text = document().replace('<Velocity3 value="8.0"/>', '<Velocity3 value="2.5"/>')  # in both tables
        self.assertRejected(text, "La lista de velocidades de viento debe ser estrictamente creciente")


if __name__ == "__main__":
    unittest.main()
