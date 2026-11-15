"""Clocked StrongARM latch comparator in Sky130 transistors.

When clk is low, the outputs and the internal nodes are precharged to VDD.
When clk goes high, the tail current starts the differential pair. The
cross-coupled latch then regenerates the small input difference to a full
logic level. The output is high on outp when inp is above inn.

The test bench drives both inputs around the common-mode level with a
differential step, and times how long the latch takes to reach a full
decision after clk rises.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import opamp, pdk
from .spice import simulate

VCM = 0.9
CLK_PERIOD = 2e-9
CLOAD = 5e-15

_LATCH_SUBCKT = f"""
.subckt strongarm inp inn outp outn clk vdd vss
XMTAIL tail clk vss vss {pdk.NFET} W=4 L=0.15 nf=1 m=1
XM1 x1 inp tail vss {pdk.NFET} W=4 L=0.15 nf=1 m=1
XM2 x2 inn tail vss {pdk.NFET} W=4 L=0.15 nf=1 m=1
XM3 outn outp x1 vss {pdk.NFET} W=2 L=0.15 nf=1 m=1
XM4 outp outn x2 vss {pdk.NFET} W=2 L=0.15 nf=1 m=1
XM5 outn outp vdd vdd {pdk.PFET} W=4 L=0.15 nf=1 m=1
XM6 outp outn vdd vdd {pdk.PFET} W=4 L=0.15 nf=1 m=1
XM7 outp clk vdd vdd {pdk.PFET} W=2 L=0.15 nf=1 m=1
XM8 outn clk vdd vdd {pdk.PFET} W=2 L=0.15 nf=1 m=1
XM9 x1 clk vdd vdd {pdk.PFET} W=2 L=0.15 nf=1 m=1
XM10 x2 clk vdd vdd {pdk.PFET} W=2 L=0.15 nf=1 m=1
.ends strongarm
"""


def bench(vid: float, corner: str = "tt", temp: float = 27.0, vdd: float = opamp.VDD_NOM) -> str:
    """One decision: differential input ``vid`` (V), clock period 2 ns."""
    return (
        "* StrongARM comparator decision test\n"
        ".option scale=1e-6\n"
        f".temp {temp}\n"
        + pdk.library_text(corner)
        + _LATCH_SUBCKT
        + f"""
VDD vdd 0 {vdd}
Vclk clk 0 PULSE(0 {vdd} 0.5n 20p 20p 0.9n {CLK_PERIOD})
Vinp inp 0 DC {VCM + vid / 2}
Vinn inn 0 DC {VCM - vid / 2}
X1 inp inn outp outn clk vdd 0 strongarm
CLP outp 0 {CLOAD}
CLN outn 0 {CLOAD}
.control
tran 5p 4n
wrdata cmp.txt v(outp) v(outn) v(clk)
.endc
.end
"""
    )


@dataclass
class Decision:
    vid: float
    decided_high: bool
    delay_s: float


def decide(vid: float, corner: str = "tt", temp: float = 27.0, vdd: float = opamp.VDD_NOM) -> Decision:
    """Simulate one decision and return its polarity and clock-to-decision delay."""
    res = simulate(bench(vid, corner, temp, vdd), tables=("cmp.txt",))
    table = res.tables["cmp.txt"]  # columns: t, outp, t, outn, t, clk
    t, outp, outn, clk = table[:, 0], table[:, 1], table[:, 3], table[:, 5]
    diff = outp - outn
    rising = np.where((clk[:-1] < vdd / 2) & (clk[1:] >= vdd / 2))[0]
    t_clk = t[rising[0]]
    # Sample the decision just before clk falls (the evaluation phase is 0.9 ns long).
    final = diff[np.argmin(np.abs(t - (t_clk + 0.85e-9)))]
    settled = np.where((t > t_clk) & (np.abs(diff) >= 0.9 * vdd))[0]
    delay = float(t[settled[0]] - t_clk) if settled.size else float("nan")
    return Decision(vid=vid, decided_high=bool(final > 0), delay_s=delay)
