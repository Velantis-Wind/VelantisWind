# -*- coding: utf-8 -*-
"""Fidelity of the arguments of the subordinate objects (#64, Q2, design 8).

Each argument offered (``subordinates.ARGS``), with the value of Q1 that changes the calculation, configured in its
position: it reaches the object the plugin builds, it is recorded as executed, and the plugin's model gives the same
effective wind speed, effective TI, AEP and iterations as PyWake built by hand with the same pieces and the same
turbines (bit for bit). With ``VELANTIS_DIAGNOSTICO=1``, the crossings that change the refusals (rotor x ground x
sum of the ground, in the deficit and the blockage; ``upstream_only`` x blockage superposition x engine; every option
of each family, by engine): validation <=> PyWake calculates.
"""
import os
import unittest
import warnings

import numpy as np

from VelantisWind.ag_core.turbines.bin_power import BIN_MEAN, simulation_wind_turbines
from VelantisWind.ag_core.wake_setup import config as cfg
from VelantisWind.ag_core.wake_setup import readers as rd
from VelantisWind.ag_core.wake_setup import subordinates as sub
from VelantisWind.ag_core.wake_setup import validation as val
from tests.test_wake_setup_factory import SITE, WT, C, build, codes, simulate, with_
from tests.test_wake_setup_factory import WS as GRID  # the grid of the bin-mean power of ``build``
from tests.test_wake_subordinates import BLOCKAGES, ENGINES, TURBULENCES, WD, WS, X, Y, probe_of

warnings.filterwarnings("ignore", module="py_wake")

from py_wake.deficit_models.gaussian import BastankhahGaussianDeficit, NiayifarGaussianDeficit  # noqa: E402
from py_wake.deficit_models.selfsimilarity import SelfSimilarityDeficit2020  # noqa: E402
from py_wake.superposition_models import LinearSum  # noqa: E402
from py_wake.turbulence_models import STF2017TurbulenceModel  # noqa: E402
from py_wake.wind_farm_models import All2AllIterative, PropagateDownwind  # noqa: E402

TURBINES = simulation_wind_turbines(WT, GRID, BIN_MEAN)


def component(arg, value):
    """The configured value and the PyWake value of a probe (a COMPONENT: an option of its family by name)."""
    if arg.kind != sub.COMPONENT:
        return value, value
    option = next(o for o in sub.options(arg) if o.name == value)
    return (None, None) if option.name is None else (C(option.name), sub.resolve_option(option)())


def config_and_direct(arg, value, engine=None):
    """The configuration of the plugin with ``arg = value`` in its position, and PyWake by hand with the same (with
    ``engine`` for the positions that are not the engine's or the blockage's: the deficit's, the superposition's, the
    turbulence's)."""
    conf, py = component(arg, value)
    if arg.kind == sub.CT2A:
        from py_wake.deficit_models.utils import ct2a_madsen, ct2a_mom1d
        conf, py = value.__name__, value
        assert py in (ct2a_madsen, ct2a_mom1d)
    owner, kw_c, kw_p = arg.owner, {arg.name: conf}, {arg.name: py}
    eff = dict(cfg.default_config().deficit.params, use_effective_ws=True)
    if owner in ENGINES:
        config = with_(cfg.default_config(owner), deficit=C("BastankhahGaussianDeficit", **eff), engine=C(owner, **kw_c),
                       blockage=C("SelfSimilarityDeficit2020", use_effective_ws=True),
                       blockage_superposition=C("LinearSum"))
        direct = sub.resolve(owner)(SITE, TURBINES, BastankhahGaussianDeficit(use_effective_ws=True),
                                    superpositionModel=LinearSum(),
                                    blockage_deficitModel=SelfSimilarityDeficit2020(use_effective_ws=True,
                                                                                    superpositionModel=LinearSum()),
                                    **kw_p)
    elif owner in ("CGIRotorAvg", "EqGridRotorAvg", "Mirror", "MultiMirror", "WeightedSum", "CumulativeWakeSum") \
            or owner in TURBULENCES or owner == "IECWeight":
        engine = engine or "PropagateDownwind"
        pud = engine == "PropagateUpDownIterative"
        position = ("rotor" if owner in ("CGIRotorAvg", "EqGridRotorAvg") else "ground" if "Mirror" in owner
                    else "superposition" if owner in ("WeightedSum", "CumulativeWakeSum") else "turbulence")
        deficit_name = "NiayifarGaussianDeficit" if position == "turbulence" else "BastankhahGaussianDeficit"
        if owner == "IECWeight":
            kw_c, kw_p = {"weight_function": C("IECWeight", **kw_c)}, {"weight_function": sub.resolve(owner)(**kw_p)}
            owner = "STF2017TurbulenceModel"
        base = cfg.default_config(engine, deficit_name)
        config = with_(base, deficit=C(deficit_name, **dict(base.deficit.params, use_effective_ws=pud)),
                       **{position: C(owner, **kw_c)})
        obj = sub.resolve(owner)(**kw_p)
        deficit_kw = {"use_effective_ws": pud, **({"rotorAvgModel": obj} if position == "rotor" else {}),
                      **({"groundModel": obj} if position == "ground" else {})}
        deficit = (NiayifarGaussianDeficit if position == "turbulence" else BastankhahGaussianDeficit)(**deficit_kw)
        engine_kw = {"superpositionModel": obj if position == "superposition" else LinearSum()}
        if position == "turbulence":
            engine_kw["turbulenceModel"] = obj
        direct = sub.resolve(engine)(SITE, TURBINES, deficit, **engine_kw)
    elif owner in BLOCKAGES:
        engine = engine or "All2AllIterative"
        pud = engine == "PropagateUpDownIterative"  # it requires the effective wind speed in both
        base = cfg.default_config(engine)
        config = with_(base, deficit=C(base.deficit.name, **dict(base.deficit.params, use_effective_ws=pud)),
                       blockage=C(owner, **dict({"use_effective_ws": True} if pud else {}, **kw_c)),
                       blockage_superposition=C("LinearSum"))
        direct = sub.resolve(engine)(SITE, TURBINES, BastankhahGaussianDeficit(use_effective_ws=pud),
                                     superpositionModel=LinearSum(),
                                     blockage_deficitModel=sub.resolve(owner)(
                                         superpositionModel=LinearSum(),
                                         **dict({"use_effective_ws": True} if pud else {}, **kw_p)))
    else:
        raise KeyError(owner)
    return config, direct


def outputs(wfm, x=X, y=Y):
    """WS_eff, TI_eff, AEP and iterations in the case of the inventory (``tests.test_wake_subordinates``)."""
    sim = wfm(x, y, wd=WD, ws=WS)
    return [sim.WS_eff.values, sim.TI_eff.values, sim.aep().values, np.asarray(getattr(wfm, "iterations", 0))]


def same(a, b):
    return all(np.array_equal(u, v, equal_nan=True) for u, v in zip(a, b))


class ArgumentFidelityTest(unittest.TestCase):
    def test_each_argument_reaches_pywake_and_the_record(self):
        # The probes of Q1 in the case of Q1, where each one has an effect (checked here too, on PyWake by hand, so
        # that the comparison cannot pass with the value left out); RankineHalfBody.exclude_wake with its turbine
        # beside the half-body (fuentes_pywake.md, S§11). The positions of the deficit, the superposition and the
        # turbulence, with each engine; those of the blockage, with the two engines that take one.
        rankine = (np.array([0.0, 400.0]), np.array([0.0, 30.0]))
        for arg in sub.ARGS:
            engines = ((None,) if arg.owner in ENGINES else ENGINES[1:] if arg.owner in BLOCKAGES  # A2A and PUD
                       else ENGINES)
            value = False if (arg.owner, arg.name) == ("RankineHalfBody", "exclude_wake") else probe_of(arg)
            if arg.kind == sub.COMPONENT and arg.owner in ("GCLTurbulence", "CrespoHernandez") \
                    and arg.name == "rotorAvgModel":
                value = "CGIRotorAvg"  # AreaOverlapAvgModel by default; None has no effect in this case
            geometry = rankine if (arg.owner, arg.name) == ("RankineHalfBody", "exclude_wake") else (X, Y)
            for engine in engines:
                with self.subTest(owner=arg.owner, arg=arg.name, value=value, engine=engine):
                    config, direct = config_and_direct(arg, value, engine)
                    signature, direct_signature = config_and_direct(arg, sub.signature_default(arg)
                                                                    if arg.kind != sub.COMPONENT else
                                                                    _signature_option(arg), engine)
                    self.assertEqual(codes(config), [])
                    wfm = build(config)
                    self.assertTrue(same(outputs(wfm, *geometry), outputs(direct, *geometry)))
                    got, expected = flow_map(config, wfm), flow_map(config, direct)  # the map of the raster too
                    self.assertTrue(same([got.WS_eff.values, got.TI_eff.values],
                                         [expected.WS_eff.values, expected.TI_eff.values]))
                    self.assertFalse(same(outputs(direct, *geometry), outputs(direct_signature, *geometry)),
                                     "the probe has no effect here")
                    ex = rd.executed_config(wfm, config)
                    self.assertEqual(rd.differences_vs_selection(ex, config), [])


def _signature_option(arg):
    default = sub.signature_default(arg)
    return type(default).__name__ if default is not None else None


def subordinate_configs():
    """The crossings that change the refusals (README, «Diseño de Q2», 8)."""
    out = []
    rotors = (None, C("CGIRotorAvg", n=7), C("EqGridRotorAvg", n=3))
    grounds = (None, C("Mirror")) + tuple(C(g, superpositionModel=C(sum_)) for g in ("Mirror", "MultiMirror")
                                          for sum_ in ("LinearSum", "SquaredSum", "MaxSum")) + (C("MultiMirror"),)
    sups = ("LinearSum", "SquaredSum", "MaxSum", "WeightedSum", "CumulativeWakeSum")
    for engine in ENGINES:
        for deficit in ("BastankhahGaussianDeficit", "TurboGaussianDeficit", "NOJDeficit"):
            base = cfg.default_config(engine, deficit)
            params = dict(base.deficit.params)
            if engine == "PropagateUpDownIterative" and "use_effective_ws" in params:
                params["use_effective_ws"] = True
            base = with_(base, deficit=C(deficit, **params))
            for rotor in rotors:
                for ground in grounds:
                    for sup in sups:
                        out.append(with_(base, rotor=rotor, ground=ground, superposition=C(sup)))
        for t in TURBULENCES:
            for arg in sub.args_of(t):
                if arg.kind != sub.COMPONENT:
                    continue
                for o in sub.FAMILIES[arg.family]:
                    value = None if o.name is None else C(o.name)
                    # A top-hat deficit for AreaOverlap, where the engine takes one (NOJ has no use_effective_ws, R3).
                    deficit = ("NOJDeficit" if o.name == "AreaOverlapAvgModel" and engine != "PropagateUpDownIterative"
                               else "NiayifarGaussianDeficit")
                    out.append(with_(cfg.default_config(engine, deficit), turbulence=C(t, **{arg.name: value}),
                                     deficit=C(deficit, **dict(cfg.default_config(engine, deficit).deficit.params,
                                                               use_effective_ws=True)) if engine ==
                                     "PropagateUpDownIterative" else cfg.default_config(engine, deficit).deficit))
        if engine == "PropagateDownwind":
            continue
        a = with_(cfg.default_config(engine), deficit=C("BastankhahGaussianDeficit", **dict(
            cfg.default_config().deficit.params, use_effective_ws=engine == "PropagateUpDownIterative")))
        for b_name in BLOCKAGES:
            for b_rotor in rotors:
                for b_ground in grounds:
                    for upstream in (False, True):
                        for bsup in ("LinearSum", "SquaredSum", "MaxSum"):
                            for sup in sups:
                                blockage = C(b_name, use_effective_ws=True, upstream_only=upstream,
                                             rotorAvgModel=b_rotor, groundModel=b_ground)
                                out.append(with_(a, superposition=C(sup), blockage=blockage,
                                                 blockage_superposition=C(bsup)))
    # The options offered with their rule of interaction (decision 6.1 of #64): the sums of their own a ground cannot
    # call, in the deficit and in the blockage, and the overlaps as the rotor of each blockage.
    own_sums = tuple(C(g, superpositionModel=C(s)) for g in ("Mirror", "MultiMirror")
                     for s in ("WeightedSum", "CumulativeWakeSum", "SqrMaxSum"))
    for engine in ENGINES:
        pud = engine == "PropagateUpDownIterative"
        a = with_(cfg.default_config(engine), deficit=C("BastankhahGaussianDeficit", **dict(
            cfg.default_config().deficit.params, use_effective_ws=pud)))
        out += [with_(a, ground=g, superposition=C(sup)) for g in own_sums for sup in sups]
        if engine == "PropagateDownwind":
            continue
        for b_name in BLOCKAGES:
            b = C(b_name, use_effective_ws=True)
            out += [with_(a, blockage=C(b_name, **dict(b.params, rotorAvgModel=C(r))),
                          blockage_superposition=C("LinearSum"))
                    for r in ("AreaOverlapAvgModel", "GaussianOverlapAvgModel")]
            out += [with_(a, superposition=C(sup), blockage=C(b_name, **dict(b.params, groundModel=g)),
                          blockage_superposition=C("LinearSum"))
                    for g in own_sums for sup in ("LinearSum", "CumulativeWakeSum")]
    return out


# The error of PyWake, whole (its type and its message: superposition_models.py:55).
_DECISION_8 = "AssertionError: SquaredSum only works for deficit - not speedups"


def decision_8(config, error):
    """The error of the calculation of decision 8: SquaredSum (the blockage superposition, or the sum of the ground of
    the blockage, «Correcciones del inventario») meets a speed-up of the blockage."""
    if error != _DECISION_8 or config.blockage is None:
        return False
    ground = config.blockage.params.get("groundModel")
    in_ground = ground is not None and getattr(ground.params.get("superpositionModel"), "name", None) == "SquaredSum"
    return config.blockage_superposition.name == "SquaredSum" or in_ground


def _by_hand(position, comp, **extra):
    """A PyWake object of ``comp`` written from its classes and values, without the factory of the plugin (the
    oracle of the crossings: a fault of the factory must not pass for a refusal of PyWake)."""
    import copy
    from VelantisWind.ag_core.wake_setup import catalog as cat
    if comp is None:
        return None
    entries = [e for e in cat.entries(position) if e.name == comp.name] if position else []
    cls = cat.resolve_class(entries[0]) if entries else sub.resolve_name(comp.name)
    kwargs = dict(extra)
    for k, v in comp.params.items():
        kwargs[k] = (_by_hand(None, v) if isinstance(v, cfg.Component)
                     else cat.resolve_ct2a(v) if k == "ct2a" and isinstance(v, str) else copy.deepcopy(v))
    return cls(**kwargs)


def by_hand(config, site=SITE, grid=GRID):
    """The wind farm model of ``config`` written by hand with PyWake (see ``_by_hand``)."""
    deficit = _by_hand("deficit", config.deficit, rotorAvgModel=_by_hand("rotor", config.rotor),
                       groundModel=_by_hand("ground", config.ground))
    kwargs = dict(superpositionModel=_by_hand("superposition", config.superposition),
                  turbulenceModel=_by_hand("turbulence", config.turbulence), **config.engine.params)
    if config.blockage is not None:
        kwargs["blockage_deficitModel"] = _by_hand(
            "blockage", config.blockage, superpositionModel=_by_hand("blockage_superposition", config.blockage_superposition))
    return sub.resolve(config.engine.name)(site, simulation_wind_turbines(WT, grid, BIN_MEAN), deficit, **kwargs)


def _stops(config, n, mapped=False):
    """Whether PyWake written by hand stops with ``config`` and the first ``n`` turbines of the case (building,
    simulating, the AEP, and, with ``mapped``, the flow map), and its error."""
    from py_wake import HorizontalGrid
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sim = by_hand(config)(X[:n], Y[:n], wd=WD, ws=WS)
            sim.aep()
            if mapped:
                sim.flow_map(HorizontalGrid(x=np.linspace(-300, 1100, 4), y=np.linspace(-200, 400, 3)),
                             wd=270.0, ws=10.0)
        return False, ""
    except Exception as exc:  # noqa: BLE001 - any error of PyWake is a stop
        return True, f"{type(exc).__name__}: {exc}"


def flow_map(config, wfm=None):
    """The flow map of the raster on a few points (``flow_map`` of PyWake; on the model written by hand unless
    ``wfm`` is given)."""
    from py_wake import HorizontalGrid
    sim = (wfm or by_hand(config))(X, Y, wd=[270.0], ws=[10.0])
    return sim.flow_map(HorizontalGrid(x=np.linspace(-300, 1100, 4), y=np.linspace(-200, 400, 3)), wd=270.0, ws=10.0)


@unittest.skipUnless(os.environ.get("VELANTIS_DIAGNOSTICO") == "1", "diagnóstico extenso (VELANTIS_DIAGNOSTICO=1)")
class SubordinateRulesDiagnostic(unittest.TestCase):
    def test_validation_matches_pywake_in_the_crossings(self):
        # Decision 6.1 of #64: the refusal of the plugin is where PyWake (written by hand) stops, by the number of
        # turbines: with one and two (validate + layout_issues), and in the map with one (+ map_issues); with the four
        # turbines of the case, the plugin calculates what PyWake calculates, bit for bit, map included.
        mismatches = []
        for config in subordinate_configs():
            for n, mapped in ((1, False), (2, False), (1, True)):
                refused = bool(val.validate(config, check_environment=False) or val.layout_issues(config, n)
                               or (mapped and val.map_issues(config, n)))
                stops, err = _stops(config, n, mapped)
                if refused != stops and not (stops and decision_8(config, err)):
                    mismatches.append((config.to_dict(), n, mapped, err[:120]))
            if val.validate(config, check_environment=False) or val.layout_issues(config, len(X)):
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    direct = simulate(by_hand(config))
                    direct.aep()
            except Exception as exc:
                if not decision_8(config, f"{type(exc).__name__}: {exc}"):
                    mismatches.append((config.to_dict(), len(X), False, f"{type(exc).__name__}: {exc}"[:120]))
                continue
            # What the plugin builds is what is configured, in this crossing too: the same WS_eff, TI_eff and AEP as
            # PyWake written by hand, bit for bit, and what is executed is the selection.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                wfm = build(config)
                plugin = simulate(wfm)
            if not same([plugin.WS_eff.values, plugin.TI_eff.values, plugin.aep().values],
                        [direct.WS_eff.values, direct.TI_eff.values, direct.aep().values]):
                mismatches.append((config.to_dict(), "el plugin no calcula lo mismo que PyWake a mano"))
            if rd.differences_vs_selection(rd.executed_config(wfm, config), config):
                mismatches.append((config.to_dict(), "lo ejecutado no es la selección"))
            if val.map_issues(config, len(X)):
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    expected, got = flow_map(config), flow_map(config, wfm)
            except Exception as exc:
                if not decision_8(config, f"{type(exc).__name__}: {exc}"):
                    mismatches.append((config.to_dict(), "mapa: " + f"{type(exc).__name__}: {exc}"[:110]))
                continue
            if not same([got.WS_eff.values, got.TI_eff.values], [expected.WS_eff.values, expected.TI_eff.values]):
                mismatches.append((config.to_dict(), "el mapa del plugin no es el de PyWake a mano"))
        self.assertEqual(mismatches, [])

    def test_the_diagnostic_matrix_of_the_crossings(self):
        """Each valid crossing, in a homogeneous case: finite, or non-finite only with a warning of its arguments (what
        PyWake calculates with non-finite results is warned, not refused: decision 5 of #64), and order-dependent
        only with CumulativeWakeSum (which has its warning, decision 19); whether it converged is recorded, never
        required (decision 9)."""
        from VelantisWind.ag_core.wake_setup.notices import NON_FINITE_TEXTS, argument_warnings
        from py_wake.site import UniformSite
        from VelantisWind.ag_core.wake_setup.instrumentation import ConvergenceRecorder
        site = UniformSite(p_wd=[1 / 12] * 12, ti=0.08)
        x, y = np.array([0.0, 400.0, 800.0, 1200.0, 4000.0]), np.array([0.0, 0.0, 0.0, 0.0, 3000.0])
        wd, ws = np.arange(0.0, 360.0, 30.0), np.array([5.0, 9.0, 13.0])
        problems, not_converged, warned_non_finite = [], 0, 0
        for config in subordinate_configs():
            if val.validate(config, check_environment=False) + val.layout_issues(config, len(x)):
                continue
            try:
                wfm = build_on(config, site, ws)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    with ConvergenceRecorder() as rec:
                        sim = wfm(x, y, wd=wd, ws=ws)
                    sim_r = wfm(x[::-1], y[::-1], wd=wd, ws=ws)
                aep, reverse = sim.aep().sum(["wd", "ws"]).values, sim_r.aep().sum(["wd", "ws"]).values[::-1]
                fields = [s_.WS_eff.values for s_ in (sim, sim_r)] + [s_.TI_eff.values for s_ in (sim, sim_r)]
            except Exception as exc:
                if not decision_8(config, f"{type(exc).__name__}: {exc}"):
                    problems.append((config.to_dict(), f"{type(exc).__name__}: {exc}"[:120]))
                continue
            not_converged += not all(e.get("converged") or set(e.get("states") or {}) == {"no_check"}
                                     for e in rec.summary().values())
            if not all(np.isfinite(v).all() for v in [aep, reverse] + fields):  # the AEP, WS_eff and TI_eff
                if any(t.template_item[0] in NON_FINITE_TEXTS for texts in argument_warnings(config).values()
                       for t in texts):
                    warned_non_finite += 1  # expected: a warning of a non-finite result says so
                else:
                    problems.append((config.to_dict(), "no finito sin aviso"))
            if (not np.allclose(aep, reverse, rtol=1e-9, atol=0.0, equal_nan=True)
                    and config.superposition.name != "CumulativeWakeSum"):
                problems.append((config.to_dict(), "depende del orden"))
        self.assertEqual(problems, [])
        print(f"\ncruces sin converger (registrado, no exigido): {not_converged}; no finitos con su aviso: "
              f"{warned_non_finite}")


def build_on(config, site, ws):
    from VelantisWind.ag_core.wake_setup import factory as fac
    return fac.build_wind_farm_model(config, site, WT, ws_grid=ws)


if __name__ == "__main__":
    unittest.main()
