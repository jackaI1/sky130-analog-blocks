"""Pure-Python checks of the hand-calculation formulas. No simulator needed."""

import math

import numpy as np
import pytest

from analog_blocks import handcalc, opamp, pdk
from analog_blocks.checks import hand_drift_ppm
from analog_blocks.opamp import ugf_and_pm


def test_opamp_dc_gain_is_product_of_stage_gains():
    gain = handcalc.opamp_dc_gain(gm2=1e-3, gds2=1e-5, gds4=1e-5, gm6=2e-3, gds6=1e-5, gds7=1e-5)
    assert gain == pytest.approx((1e-3 / 2e-5) * (2e-3 / 2e-5))


def test_gbw_and_phase_margin_formulas():
    gbw = handcalc.opamp_gbw(gm2=2 * math.pi * 1e-12 * 30e6, cc=1e-12)
    assert gbw == pytest.approx(30e6)
    # With gm6 very large, the second pole and the RHP zero move far away, so PM -> 90 deg.
    assert handcalc.opamp_phase_margin(gbw, gm6=1e3, cc=1e-12, cl=1e-12) == pytest.approx(90.0, abs=0.1)
    # A smaller gm6 pushes the second pole closer and lowers the margin.
    # With gm6 = 1 mS, p2 and z sit near 159 MHz, so each adds ~10.7 deg of lag: PM ~ 68.6 deg.
    assert handcalc.opamp_phase_margin(gbw, gm6=1e-3, cc=1e-12, cl=1e-12) == pytest.approx(68.6, abs=0.5)


def test_pelgrom_sigma_matches_hand_value():
    # A_VT = 7.356 mV*um, W = 10 um, L = 0.5 um -> 7.356 / sqrt(5) = 3.29 mV
    assert handcalc.pelgrom_sigma_vth(7.356, 10, 0.5) == pytest.approx(3.29e-3, rel=1e-3)


def test_opamp_offset_sigma_combines_pair_and_load():
    sizes = {"M2": (10, 0.5), "M4": (10, 0.5)}
    sigma = handcalc.opamp_offset_sigma(7.356, sizes, gm2=1e-4, gm3=1e-4)
    expected = math.sqrt(2) * 3.29e-3 * math.sqrt(2)
    assert sigma == pytest.approx(expected, rel=1e-3)


def test_thermal_noise_floor_order_of_magnitude():
    # Values from the nominal op-amp operating point.
    s = handcalc.thermal_noise_density(gm_in=1.844e-4, gm_load=1.216e-4)
    assert 13e-9 < s < 15e-9


def test_bandgap_formula_at_room_temperature():
    # Vref = Vbe + (R2/R1) * VT * ln(8), with VT = k/q * T = 8.617333e-5 * 300.15 K
    vref = handcalc.bandgap_vref(vbe=0.7, r2_over_r1=8.4, temp_c=27.0, area_ratio=8)
    assert vref == pytest.approx(0.7 + 8.4 * 8.617333e-5 * 300.15 * math.log(8), rel=1e-9)


def test_ring_frequency_formula():
    f = handcalc.ring_vco_frequency(i_starve=100e-6, n_stages=5, c_node=20e-15, vdd=1.8)
    assert f == pytest.approx(100e-6 / (5 * 20e-15 * 1.8))


def test_ugf_and_pm_on_single_pole_amplifier():
    # A single pole at 1 kHz with DC gain 1000 crosses 0 dB at 1 MHz with a 90 deg lag.
    freq = np.logspace(0, 9, 4000)
    h = 1000 / (1 + 1j * freq / 1e3)
    mag_db = 20 * np.log10(np.abs(h))
    phase = np.angle(h)
    ugf, pm = ugf_and_pm(freq, mag_db, phase)
    assert ugf == pytest.approx(1e6, rel=0.01)
    assert pm == pytest.approx(90.0, abs=0.5)


def test_ugf_raises_when_gain_never_crosses():
    freq = np.logspace(0, 3, 10)
    with pytest.raises(ValueError):
        ugf_and_pm(freq, np.full(10, 20.0), np.zeros(10))


def test_hand_drift_box_method():
    assert hand_drift_ppm([1.0, 1.1], [0.0, 100.0]) == pytest.approx(0.1 / 100 / 1.05 * 1e6, rel=1e-9)


def test_unknown_corner_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        pdk.library_text("xx", root=tmp_path)


def test_mismatch_coefficient_is_read_from_pdk_file(tmp_path):
    cell = tmp_path / "cells" / "nfet_01v8"
    cell.mkdir(parents=True)
    (cell / "sky130_fd_pr__nfet_01v8__mismatch.corner.spice").write_text(
        ".param sky130_fd_pr__nfet_01v8__vth0_slope1=7.356e-03\n")
    assert pdk.mismatch_coefficient_mV_um(root=tmp_path) == pytest.approx(7.356)


def test_netlists_have_expected_structure():
    op = opamp.bench(analysis="ac")
    assert ".subckt ota2s" in op and "Lfb out inn" in op and "wrdata ac.txt" in op
    assert "sky130_fd_pr__nfet_01v8" in op
    from analog_blocks import bandgap, comparator, vco
    bg = bandgap.bench()
    pnp_instances = [line for line in bg.splitlines() if line.startswith("XQ")]
    assert len(pnp_instances) == 3 and "M=8" in bg
    ring = vco.bench(1.2)
    assert all(f"XMPS{i}" in ring for i in range(vco.N_STAGES))
    cmp_net = comparator.bench(0.01)
    assert ".subckt strongarm" in cmp_net and "wrdata cmp.txt" in cmp_net
