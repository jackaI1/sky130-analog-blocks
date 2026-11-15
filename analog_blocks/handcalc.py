"""Closed-form hand calculations, checked against the simulator.

Every function takes numbers that come from a simulation's operating point
(gm, gds, bias currents) or from the design values, and returns the value a
designer would get on paper. The tests compare these with ngspice results.
"""

from __future__ import annotations

import math

K_B = 1.380649e-23
Q_E = 1.602176634e-19
T_NOM_K = 300.15


def opamp_dc_gain(gm2: float, gds2: float, gds4: float,
                  gm6: float, gds6: float, gds7: float) -> float:
    """Two-stage DC gain: A = A1 * A2, with A1 = gm2/(gds2+gds4), A2 = gm6/(gds6+gds7)."""
    a1 = gm2 / (gds2 + gds4)
    a2 = gm6 / (gds6 + gds7)
    return a1 * a2


def opamp_gbw(gm2: float, cc: float) -> float:
    """Unity-gain frequency in Hz, from the input transconductance and the Miller cap."""
    return gm2 / (2 * math.pi * cc)


def opamp_phase_margin(gbw: float, gm6: float, cc: float, cl: float) -> float:
    """Phase margin (deg) with the second pole and the right-half-plane zero.

    p2 = gm6 / CL and z = gm6 / CC. Each adds about atan(GBW / f) of lag.
    The third pole from the mirror node is ignored, so the result is
    slightly optimistic.
    """
    f_p2 = gm6 / (2 * math.pi * cl)
    f_z = gm6 / (2 * math.pi * cc)
    lag = math.atan(gbw / f_p2) + math.atan(gbw / f_z)
    return 90.0 - math.degrees(lag)


def pelgrom_sigma_vth(a_vt_mv_um: float, w_um: float, l_um: float) -> float:
    """sigma(Vth) in volts for one device: A_VT / sqrt(W * L), with A_VT in mV*um."""
    return a_vt_mv_um * 1e-3 / math.sqrt(w_um * l_um)


def opamp_offset_sigma(a_vt_mv_um: float, sizes: dict[str, tuple[float, float]],
                       gm2: float, gm3: float) -> float:
    """Input-referred offset sigma (V) for the two-stage op-amp.

    The input pair (M1, M2) contributes sqrt(2) * sigma(Vth). The PMOS load
    (M3, M4) contributes the same term, scaled by (gm3/gm2) when it is
    referred to the input.
    """
    s_pair = math.sqrt(2) * pelgrom_sigma_vth(a_vt_mv_um, *sizes["M2"])
    s_load = math.sqrt(2) * pelgrom_sigma_vth(a_vt_mv_um, *sizes["M4"])
    return math.sqrt(s_pair**2 + (gm3 / gm2) ** 2 * s_load**2)


def thermal_noise_density(gm_in: float, gm_load: float, temp_k: float = T_NOM_K) -> float:
    """Input-referred thermal noise floor, V/sqrt(Hz), for a 5T-style input stage.

    S = 2 * (4kT * 2/3) / gm_in * (1 + gm_load / gm_in). Flicker noise is not
    included, so the simulated value is higher at low frequency.
    """
    s = 2 * (4 * K_B * temp_k * (2 / 3)) / gm_in * (1 + gm_load / gm_in)
    return math.sqrt(s)


def bandgap_vref(vbe: float, r2_over_r1: float, temp_c: float, area_ratio: float) -> float:
    """Vref = Vbe + (R2/R1) * (kT/q) * ln(area ratio)."""
    vt = 8.617333e-5 * (temp_c + 273.15)
    return vbe + r2_over_r1 * vt * math.log(area_ratio)


def ring_vco_frequency(i_starve: float, n_stages: int, c_node: float, vdd: float) -> float:
    """Textbook current-starved ring frequency: f = I / (N * C * VDD).

    This assumes the starve current stays at its saturation value while each
    node swings. The simulation shows that assumption is optimistic.
    """
    return i_starve / (n_stages * c_node * vdd)
