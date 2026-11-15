"""Current-starved five-stage ring oscillator (a voltage-controlled oscillator).

Each inverter has a series "starve" transistor above (PMOS) and below
(NMOS). The control voltage ``vctl`` sets the NMOS starve gate, and
``vdd - vctl`` sets the PMOS starve gate. Those set the current I that
charges and discharges every node, so the frequency rises with vctl.

Hand formula used for the check (textbook ring oscillator):

    t_d = C * VDD / (2 * I)        delay per stage
    f   = 1 / (2 * N * t_d) = I / (N * C * VDD)

Here I is the starve transistor's saturation current, read from a DC sweep
of that device. C is the explicit load plus the gate capacitance of the
next stage. Oxide capacitance is taken from the PDK's oxide thickness.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import opamp, pdk
from .spice import simulate

N_STAGES = 5
CLOAD = 20e-15
W_INV_N, W_INV_P = 1.0, 2.0
W_STARVE_N = 4.0
W_STARVE_P = 12.0  # PMOS is about 3x weaker per width, so it gets 3x the width
L_INV = 0.15
L_STARVE = 0.5
C_OX = 3.9 * 8.854e-12 / 4.148e-9  # F/m^2, from the PDK's toxm


def _ring_lines(vdd: float) -> str:
    lines = []
    for i in range(N_STAGES):
        inp = f"n{N_STAGES if i == 0 else i}"
        out = f"n{i + 1}"
        lines += [
            f"XMPS{i} p{i} vbp vdd vdd {pdk.PFET} W={W_STARVE_P} L={L_STARVE} nf=1 m=1",
            f"XMP{i} {out} {inp} p{i} vdd {pdk.PFET} W={W_INV_P} L={L_INV} nf=1 m=1",
            f"XMN{i} {out} {inp} s{i} vss {pdk.NFET} W={W_INV_N} L={L_INV} nf=1 m=1",
            f"XMNS{i} s{i} vbn vss vss {pdk.NFET} W={W_STARVE_N} L={L_STARVE} nf=1 m=1",
            f"CLOAD{i} {out} vss {CLOAD}",
        ]
    return "\n".join(lines)


def bench(vctl: float, corner: str = "tt", temp: float = 27.0, vdd: float = opamp.VDD_NOM,
          tstop: float = 150e-9) -> str:
    return (
        "* current-starved ring oscillator testbench\n"
        ".option scale=1e-6\n"
        f".temp {temp}\n"
        + pdk.library_text(corner)
        + f"""
VDD vdd 0 {vdd}
Vbn vbn 0 DC {vctl}
Vbp vbp 0 DC {vdd - vctl}
VSS vss 0 0
{_ring_lines(vdd)}
.ic v(n1)=0 v(n2)={vdd} v(n3)=0 v(n4)={vdd} v(n5)=0
.control
tran 10p {tstop} uic
wrdata osc.txt v(n1)
.endc
.end
"""
    )


def starve_current_bench(vctl: float, corner: str = "tt", temp: float = 27.0,
                         vdd: float = opamp.VDD_NOM) -> str:
    """One starve NMOS with its drain held at VDD/2 (a saturation current probe)."""
    return (
        "* starve transistor current probe\n"
        ".option scale=1e-6\n"
        f".temp {temp}\n"
        + pdk.library_text(corner)
        + f"""
VDS d 0 {vdd / 2}
Vbn g 0 DC {vctl}
XMNS d g 0 0 {pdk.NFET} W={W_STARVE_N} L={L_STARVE} nf=1 m=1
.control
op
let idn = @m.xmns.m{pdk.NFET}[id]
print idn
.endc
.end
"""
    )


def hand_capacitance(vdd: float = opamp.VDD_NOM) -> float:
    """Node capacitance from the explicit load plus the next inverter's gate."""
    gate_area_m2 = (W_INV_N + W_INV_P) * L_INV * 1e-12  # um^2 -> m^2
    return CLOAD + C_OX * gate_area_m2


def hand_frequency(i_starve: float, vdd: float = opamp.VDD_NOM) -> float:
    """f = I / (N * C * VDD), the textbook current-starved ring frequency."""
    return i_starve / (N_STAGES * hand_capacitance(vdd) * vdd)


@dataclass
class VcoPoint:
    vctl: float
    freq_hz: float
    starve_current_a: float
    hand_freq_hz: float


def _period_from_zero_crossings(t: np.ndarray, v: np.ndarray, vdd: float) -> float:
    """Average period from rising crossings of vdd/2, skipping the start-up cycles."""
    rising = np.where((v[:-1] < vdd / 2) & (v[1:] >= vdd / 2))[0]
    t_cross = t[rising]
    # Skip the start-up transient: keep only crossings after the first 30% of the record.
    t_cross = t_cross[t_cross > 0.3 * t[-1]]
    if t_cross.size < 3:
        raise ValueError("ring did not oscillate long enough to measure a period")
    return float(np.mean(np.diff(t_cross)))


def characterize(vctl: float, corner: str = "tt", temp: float = 27.0,
                 vdd: float = opamp.VDD_NOM) -> VcoPoint:
    osc = simulate(bench(vctl, corner, temp, vdd), tables=("osc.txt",))
    table = osc.tables["osc.txt"]  # columns: time, v(n1)
    t, v = table[:, 0], table[:, 1]
    freq = 1.0 / _period_from_zero_crossings(t, v, vdd)
    i_starve = simulate(starve_current_bench(vctl, corner, temp, vdd))["idn"]
    return VcoPoint(vctl=vctl, freq_hz=freq, starve_current_a=i_starve,
                    hand_freq_hz=hand_frequency(i_starve, vdd))
