"""Run the full characterization: nominal, PVT corners and Monte Carlo.

``run_suite`` returns one dictionary with every number that goes into the
summary files and plots. It only calls ngspice through the block modules.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Callable

import numpy as np

from . import bandgap, comparator, handcalc, opamp, pdk, vco
from .spice import SpiceError

VDD_NOM = opamp.VDD_NOM
VDDS = (0.9 * VDD_NOM, VDD_NOM, 1.1 * VDD_NOM)
TEMPS = (-40.0, 27.0, 125.0)
VCTL_NOM = 1.2
BANDGAP_TEMPS = (-40.0, -25.0, -10.0, 5.0, 20.0, 27.0, 35.0, 50.0, 65.0, 80.0, 95.0, 110.0, 125.0)
VCTL_SWEEP = (1.1, 1.2, 1.3, 1.4)
VID = 0.01


def _vco_hand(point: vco.VcoPoint, vdd: float) -> float:
    return handcalc.ring_vco_frequency(point.starve_current_a, vco.N_STAGES, vco.hand_capacitance(vdd), vdd)


def nominal() -> dict:
    """Corner tt, nominal supply, 27 C. Every block once, with its hand checks."""
    op = opamp.characterize()
    noise, op_bias = opamp.input_noise()
    bg = bandgap.characterize()
    cmp_hi = comparator.decide(+VID)
    cmp_lo = comparator.decide(-VID)
    osc = vco.characterize(VCTL_NOM)
    sizes = opamp.SIZES
    a_vt = pdk.mismatch_coefficient_mV_um()
    gain_hand = handcalc.opamp_dc_gain(op.gm2, op.gds2, op.gds4, op.gm6, op.gds6, op.gds7)
    gbw_hand = handcalc.opamp_gbw(op.gm2, opamp.CC)
    pm_hand = handcalc.opamp_phase_margin(gbw_hand, op.gm6, opamp.CC, opamp.CLOAD)
    thermal = handcalc.thermal_noise_density(op.gm2, op.gm3)
    sigma_hand = handcalc.opamp_offset_sigma(a_vt, sizes, op.gm2, op.gm3)
    bg_sweep = bandgap.sweep_temperature(temps=np.array(BANDGAP_TEMPS))
    bg_pred = [handcalc.bandgap_vref(p.vbe, bandgap.R2 / bandgap.R1, p.temp, bandgap.AREA_RATIO)
               for p in bg_sweep]
    return {
        "opamp": {
            "measured": {k: v for k, v in asdict(op).items() if k != "bode"},
            "dc_gain_db": op.dc_gain_db,
            "dc_gain_hand_db": 20 * math.log10(gain_hand),
            "ugf_mhz": op.ugf_hz / 1e6,
            "gbw_hand_mhz": gbw_hand / 1e6,
            "pm_deg": op.phase_margin_deg,
            "pm_hand_deg": pm_hand,
            "noise_nv_100k": noise.at(1e5) * 1e9,
            "noise_nv_1m": noise.at(1e6) * 1e9,
            "noise_rms_uv_1hz_100mhz": noise.integrated_rms(1, 1e8) * 1e6,
            "thermal_floor_nv": thermal * 1e9,
            "bias_op": op_bias,
            "_noise_freq": noise.freq,
            "_noise_density": noise.density,
            "_bode": op.bode,
        },
        "offset": {"sigma_hand_mv": sigma_hand * 1e3, "a_vt_mv_um": a_vt},
        "bandgap": {
            "vref_27c": bg.vref,
            "vbe_27c": bg.vbe,
            "drift_ppm_per_c": bandgap.drift_ppm_per_c(bg_sweep),
            "vref_error_mv_by_temp": {
                f"{p.temp:g}": (p.vref - pred) * 1e3 for p, pred in zip(bg_sweep, bg_pred)
            },
            "_temps": [p.temp for p in bg_sweep],
            "_vref": [p.vref for p in bg_sweep],
            "_vref_hand": bg_pred,
        },
        "comparator": {
            "decide_plus_10mv_high": cmp_hi.decided_high,
            "decide_minus_10mv_high": cmp_lo.decided_high,
            "delay_ps": cmp_hi.delay_s * 1e12,
        },
        "vco": {
            "vctl": osc.vctl,
            "freq_mhz": osc.freq_hz / 1e6,
            "starve_current_ua": osc.starve_current_a * 1e6,
            "hand_freq_mhz": _vco_hand(osc, VDD_NOM) / 1e6,
            "hand_over_sim": _vco_hand(osc, VDD_NOM) / osc.freq_hz,
        },
    }


def vco_tuning() -> list[dict]:
    rows = []
    for vc in VCTL_SWEEP:
        p = vco.characterize(vc)
        rows.append({"vctl": vc, "freq_mhz": p.freq_hz / 1e6, "hand_mhz": _vco_hand(p, VDD_NOM) / 1e6,
                     "starve_ua": p.starve_current_a * 1e6})
    return rows


def pvt(progress: Callable[[str], None] | None = None) -> list[dict]:
    """Every combination of process corner, supply (+/-10%) and temperature."""
    rows = []
    for corner in pdk.CORNERS:
        for vdd in VDDS:
            for temp in TEMPS:
                if progress:
                    progress(f"pvt {corner} vdd={vdd:.3f} T={temp:g}")
                row = {"corner": corner, "vdd": round(vdd, 3), "temp": temp}
                try:
                    op = opamp.characterize(corner, vdd, temp)
                    bgp = bandgap.characterize(corner, vdd, temp)
                    hi = comparator.decide(+VID, corner, temp, vdd)
                    lo = comparator.decide(-VID, corner, temp, vdd)
                    osc = vco.characterize(VCTL_NOM, corner, temp, vdd)
                    row.update({
                        "opamp_gain_db": op.dc_gain_db,
                        "opamp_ugf_mhz": op.ugf_hz / 1e6,
                        "opamp_pm_deg": op.phase_margin_deg,
                        "bandgap_vref": bgp.vref,
                        "cmp_correct": bool(hi.decided_high and not lo.decided_high),
                        "cmp_delay_ps": hi.delay_s * 1e12,
                        "vco_freq_mhz": osc.freq_hz / 1e6,
                    })
                except (SpiceError, ValueError) as exc:
                    row["error"] = str(exc).splitlines()[0][:200]
                rows.append(row)
    return rows


def monte_carlo_offset(n: int = 100, seed: int = 2026,
                       progress: Callable[[str], None] | None = None) -> list[float]:
    """Input offset (V) for ``n`` random mismatch draws.

    Each device in MISMATCH_DEVICES gets its own Gaussian Vth error,
    sigma = A_VT / sqrt(W*L), using the PDK's coefficient. See
    docs/design.md for why the mismatch is injected per device.
    """
    a_vt = pdk.mismatch_coefficient_mV_um() * 1e-3
    sigmas = {m: a_vt / math.sqrt(opamp.SIZES[m][0] * opamp.SIZES[m][1]) for m in opamp.MISMATCH_DEVICES}
    rng = np.random.default_rng(seed)
    offsets = []
    for k in range(n):
        if progress and k % 10 == 0:
            progress(f"mc {k}/{n}")
        dvth = {m: float(rng.normal(0.0, s)) for m, s in sigmas.items()}
        offsets.append(opamp.offset_sample(dvth))
    return offsets


def run_suite(quick: bool = False, progress: Callable[[str], None] | None = None) -> dict:
    result: dict = {"nominal": nominal(), "vco_tuning": vco_tuning()}
    result["pvt"] = pvt(progress) if not quick else []
    mc_n = 20 if quick else 100
    offsets = monte_carlo_offset(mc_n, progress=progress)
    result["monte_carlo"] = {
        "n": len(offsets),
        "sigma_mv": float(np.std(offsets, ddof=1) * 1e3),
        "mean_mv": float(np.mean(offsets) * 1e3),
        "offsets_mv": [o * 1e3 for o in offsets],
    }
    return result
