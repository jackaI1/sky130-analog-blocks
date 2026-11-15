"""Bandgap voltage reference from Sky130 PNP transistors and the op-amp.

The classic PTAT + CTAT circuit:

* Q1 is one PNP. Q2 is an identical PNP with 8 times the area (M=8).
* The op-amp forces both branches to the same node voltage, which sets the
  branch current I = VT * ln(8) / R1. VT = kT/q is the thermal voltage.
* A third PMOS copy of that current runs through R2 into a PNP (Q3), so
  Vref = Vbe + (R2/R1) * VT * ln(8).

The first term falls about 2 mV/K with temperature and the second rises,
so the sum stays nearly flat. Resistors are ideal, so the drift that
remains comes from the transistors.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import opamp, pdk
from .spice import simulate

R1 = 5e3
R2 = 42e3
AREA_RATIO = 8
MIRROR_W, MIRROR_L = 10, 1.0
K_OVER_Q = 8.617333e-5  # V/K


def thermal_voltage(temp_c: float) -> float:
    return K_OVER_Q * (temp_c + 273.15)


def bench(corner: str = "tt", temp: float = 27.0, vdd: float = opamp.VDD_NOM) -> str:
    return (
        "* bandgap reference testbench\n"
        ".option scale=1e-6\n"
        f".temp {temp}\n"
        + pdk.library_text(corner)
        + opamp.subckt_text()
        + f"""
VDD vdd 0 {vdd}
* error amplifier: inp = Q2 branch (nB), inn = Q1 branch (nA)
X1 nqb nqa ngate vdd 0 ota2s
* three PMOS mirror copies, all gates on the op-amp output
XMP1 nqa ngate vdd vdd {pdk.PFET} W={MIRROR_W} L={MIRROR_L} nf=1 m=1
XMP2 nqb ngate vdd vdd {pdk.PFET} W={MIRROR_W} L={MIRROR_L} nf=1 m=1
XMP3 nvref ngate vdd vdd {pdk.PFET} W={MIRROR_W} L={MIRROR_L} nf=1 m=1
* Q1 branch, Q2 branch (behind R1), output branch (behind R2)
XQ1 0 0 nqa 0 {pdk.PNP} M=1
XQ2 0 0 nqc 0 {pdk.PNP} M={AREA_RATIO}
R1 nqb nqc {R1}
XQ3 0 0 nqd 0 {pdk.PNP} M=1
R2 nvref nqd {R2}
* start-up: weak pull-down on the gate so the loop does not sit at zero current
Rstart ngate 0 100Meg
.control
op
let vref = v(nvref)
let vbe = v(nqa)
print vref
print vbe
.endc
.end
"""
)


@dataclass
class BandgapPoint:
    corner: str
    vdd: float
    temp: float
    vref: float
    vbe: float


def characterize(corner: str = "tt", vdd: float = opamp.VDD_NOM, temp: float = 27.0) -> BandgapPoint:
    res = simulate(bench(corner, temp, vdd))
    return BandgapPoint(corner=corner, vdd=vdd, temp=temp, vref=res["vref"], vbe=res["vbe"])


def predicted_vref(vbe: float, temp: float) -> float:
    """Hand formula: Vref = Vbe + (R2/R1) * VT * ln(area ratio)."""
    return vbe + (R2 / R1) * thermal_voltage(temp) * math.log(AREA_RATIO)


def sweep_temperature(corner: str = "tt", vdd: float = opamp.VDD_NOM,
                      temps: np.ndarray | None = None) -> list[BandgapPoint]:
    temps = np.arange(-40, 126, 5.0) if temps is None else temps
    return [characterize(corner, vdd, float(t)) for t in temps]


def drift_ppm_per_c(points: list[BandgapPoint]) -> float:
    """Box-method drift: (max - min) / (Tmax - Tmin) / mean, in ppm per degree C."""
    temps = np.array([p.temp for p in points])
    vref = np.array([p.vref for p in points])
    span_t = temps.max() - temps.min()
    return float((vref.max() - vref.min()) / span_t / vref.mean() * 1e6)
