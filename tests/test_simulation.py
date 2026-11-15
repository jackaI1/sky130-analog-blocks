"""Simulator tests. Each one runs ngspice on the Sky130 models and checks the result.

These are marked ``sim``. They skip on a machine with no ngspice or PDK.
CI sets ANALOG_BLOCKS_REQUIRE_SIM=1, so they must run there.
"""

import math

import pytest

from analog_blocks import bandgap, comparator, handcalc, opamp, pdk, vco
from analog_blocks.checks import all_checks
from analog_blocks.suite import monte_carlo_offset

pytestmark = pytest.mark.sim


@pytest.fixture(scope="module")
def op_nominal():
    return opamp.characterize()


def test_opamp_gain_matches_hand_calc(op_nominal):
    gain = handcalc.opamp_dc_gain(op_nominal.gm2, op_nominal.gds2, op_nominal.gds4,
                                  op_nominal.gm6, op_nominal.gds6, op_nominal.gds7)
    assert op_nominal.dc_gain_db == pytest.approx(20 * math.log10(gain), abs=1.0)
    assert op_nominal.dc_gain_db > 60


def test_opamp_unity_gain_and_phase_margin_match_hand_calc(op_nominal):
    gbw = handcalc.opamp_gbw(op_nominal.gm2, opamp.CC)
    assert op_nominal.ugf_hz == pytest.approx(gbw, rel=0.15)
    pm = handcalc.opamp_phase_margin(gbw, op_nominal.gm6, opamp.CC, opamp.CLOAD)
    assert op_nominal.phase_margin_deg == pytest.approx(pm, abs=8.0)


def test_opamp_noise_is_above_thermal_floor():
    noise, _ = opamp.input_noise()
    assert noise.at(1e6) > handcalc.thermal_noise_density(1.8e-4, 1.2e-4) * 0.8
    assert noise.at(10) > noise.at(1e5), "flicker should dominate at low frequency"


def test_opamp_offset_is_monte_carlo_distributed():
    offsets = monte_carlo_offset(n=30, seed=7)
    import numpy as np
    sigma = float(np.std(offsets, ddof=1))
    a_vt = pdk.mismatch_coefficient_mV_um() * 1e-3
    sizes = opamp.SIZES
    op = opamp.characterize()
    hand = handcalc.opamp_offset_sigma(a_vt * 1e3, sizes, op.gm2, op.gm3)
    assert sigma == pytest.approx(hand, rel=0.45)


def test_bandgap_reference_voltage_and_drift():
    point = bandgap.characterize()
    assert 1.15 < point.vref < 1.25
    temps = [-40.0, 27.0, 125.0]
    values = [bandgap.characterize(temp=t).vref for t in temps]
    drift = (max(values) - min(values)) / 165.0 / (sum(values) / 3) * 1e6
    assert drift < 100.0, f"drift {drift:.0f} ppm/C"
    hand = handcalc.bandgap_vref(point.vbe, bandgap.R2 / bandgap.R1, 27.0, bandgap.AREA_RATIO)
    assert point.vref == pytest.approx(hand, abs=0.03)


def test_comparator_decides_both_polarities():
    assert comparator.decide(+0.01).decided_high is True
    assert comparator.decide(-0.01).decided_high is False
    fast = comparator.decide(+0.01)
    assert 0 < fast.delay_s < 1e-9


def test_vco_tunes_up_with_control_voltage():
    freqs = [vco.characterize(v).freq_hz for v in (1.1, 1.3)]
    assert freqs[1] > freqs[0] * 2


def test_vco_frequency_is_below_textbook_estimate_and_scales_with_load():
    point = vco.characterize(1.2)
    hand = handcalc.ring_vco_frequency(point.starve_current_a, vco.N_STAGES,
                                       vco.hand_capacitance(), 1.8)
    ratio = point.freq_hz / hand
    assert 0.1 < ratio < 0.5, f"sim/hand = {ratio:.2f}"
    original = vco.CLOAD
    try:
        vco.CLOAD = 2 * original
        heavier = vco.characterize(1.2).freq_hz
    finally:
        vco.CLOAD = original
    assert heavier == pytest.approx(point.freq_hz * 0.53, rel=0.25)


def test_pvt_corners_change_the_oscillator():
    slow = vco.characterize(1.2, corner="ss").freq_hz
    typical = vco.characterize(1.2, corner="tt").freq_hz
    fast = vco.characterize(1.2, corner="ff").freq_hz
    assert slow < typical < fast


def test_all_checks_pass_on_quick_run(tmp_path):
    from analog_blocks.suite import run_suite
    result = run_suite(quick=True)
    failed = [c.name for c in all_checks(result) if not c.passed]
    assert failed == []
