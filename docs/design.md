# Design notes

This file holds the technical detail that the README leaves out: the PDK
setup, how each netlist is built, what was checked against which hand
calculation, and what went wrong on the way.

## Layout

| path | what it does |
|---|---|
| `analog_blocks/pdk.py` | finds the Sky130 model files, inlines the PDK includes, reads the mismatch coefficient |
| `analog_blocks/spice.py` | runs ngspice in batch mode in a temporary folder and parses `print` lines and `wrdata` tables |
| `analog_blocks/opamp.py` | two-stage Miller op-amp: netlist, AC, noise and offset benches |
| `analog_blocks/bandgap.py` | PNP bandgap reference, with the op-amp as its error amplifier |
| `analog_blocks/comparator.py` | StrongARM latch comparator with a transient decision test |
| `analog_blocks/vco.py` | current-starved five-stage ring oscillator, transient frequency and starve-current probe |
| `analog_blocks/handcalc.py` | closed-form formulas: gain, GBW, phase margin, Pelgrom offset, thermal noise, bandgap, ring frequency |
| `analog_blocks/checks.py` | the pass/fail list used by both the summary and the tests |
| `analog_blocks/suite.py` | nominal run, PVT grid and Monte Carlo |
| `analog_blocks/plots.py`, `cli.py` | PNG plots, `summary.md`, `summary.json`, command line |
| `tests/` | hand-calculation tests (no simulator) and simulator tests (`-m sim`) |
| `scripts/fetch_pdk.sh` | downloads only the device folders used, pinned to one commit |

## PDK setup

The models come from `google/skywater-pdk-libs-sky130_fd_pr` at commit
`f62031a1be9aefe902d6d54cddd6f59b57627436`. The script clones the repository
without file contents, then checks out `models/` and the three device
folders the project uses (`nfet_01v8`, `pfet_01v8`, `pnp_05v5`). The whole
PDK is several gigabytes. This subset is about 40 MB.

ngspice resolves `.include` paths against the working directory, but the PDK
includes its binned model files by a path relative to the including file. So
`pdk.py` inlines the includes itself before writing the netlist. The corner
files also need `models/parameters/invariant.spice`, `lod.spice` and
`models/corners/<corner>/nonfet.spice`. Without those, ngspice reports
undefined parameters such as `wlod_diff` and `dkbfpp5x`.

Process corners are `tt`, `ff`, `ss`, `sf` and `fs`. Each one selects that
corner's `.corner.spice` file for the NMOS and PMOS, and the matching
`nonfet.spice` for the PNP.

## Op-amp

NMOS input pair, PMOS mirror load, PMOS common-source second stage, NMOS
current-source load. Miller capacitor 1 pF across the second stage, load
1 pF. Tail and load currents are mirrored from a 20 uA reference.

Open-loop bench: an inductor (1 MH) from the output to the inverting input
and a capacitor (1 MF) from that input to ground. At DC the inductor is a
short, so unity-gain feedback sets the bias. At AC and noise frequencies it
is open, so the loop is broken for measurement. The AC gain at 1 Hz is the
DC gain. The UGF and phase margin are interpolated from the `wrdata` table.

Hand checks, with the small-signal values from the simulated operating point:

- DC gain: `A = gm2/(gds2+gds4) * gm6/(gds6+gds7)`. The simulation and hand
  value agree to 0.03 dB.
- Unity-gain frequency: `GBW = gm2/(2 pi Cc)`. The simulation is 5% below.
- Phase margin: `90 - atan(GBW/p2) - atan(GBW/z)`, with `p2 = gm6/CL` and
  `z = gm6/Cc`. The hand value is 4 degrees above the simulation. The third
  pole at the mirror node is left out of the hand formula.

Offset: each of M1 to M4 gets an ideal voltage source in series with its
gate. The source value is a random Vth error drawn with
`sigma = A_VT / sqrt(W*L)`. `A_VT` is read from the PDK file, where it is
`vth0_slope1 = 7.356 mV*um`. The PDK's own Monte Carlo switch is a single
global parameter, so it gives the same draw for every transistor. Injecting
the errors per device gives independent mismatch. The hand sigma combines the
input pair with the load mirror, referred to the input by `gm3/gm2`.

Noise: the simulated input-referred density is 79 nV/rtHz at 100 kHz and
36 nV/rtHz at 1 MHz. The thermal-only hand floor is 14 nV/rtHz. The gap
comes from flicker noise, which the PDK's device model includes. The
simulation is therefore reported as above the floor, not matched to it.

## Bandgap

Q1 is one PNP. Q2 has area 8 (`M=8`). The op-amp forces the Q1 and Q2
branch voltages equal, which sets `I = VT ln 8 / R1`. A PMOS copy of `I` runs
through R2 into Q3, so `Vref = Vbe + (R2/R1) VT ln 8`. R1 = 5 kOhm and
R2 = 42 kOhm. The resistors are ideal, so the temperature drift that remains
comes from the transistors.

The hand check uses the simulated `Vbe` in the formula. It is 15 mV below
the simulated `Vref` at 27 C. The reason is that the output mirror leg sits
at a different drain voltage from the reference leg, so channel-length
modulation makes its current a little higher. The formula assumes the two
currents are equal.

The same effect changes the drift. The hand formula with the simulated `Vbe`
gives about 99 ppm/C. The simulation gives about 21 ppm/C. The spec in the
checks is therefore a limit of 100 ppm/C, and the hand estimate is printed
next to it in `summary.md`.

## Comparator

Latched StrongARM: a clocked tail, an NMOS input pair, cross-coupled NMOS and
PMOS latches, and precharge PMOS on the outputs and internal nodes. The test
drives +/-10 mV around 0.9 V and samples the decision just before clk falls.
Both polarities are correct at every PVT point. The clock-to-decision delay
is about 290 ps at 10 mV.

## Ring oscillator

Five inverters. Each has a PMOS starve device above and an NMOS starve device
below. The NMOS starve gate is `Vctl` and the PMOS starve gate is `VDD - Vctl`.
Each node has a 20 fF explicit load.

The first version used equal starve widths and a control range of 0.7 to
1.4 V. Oscillation was far too slow. The PMOS threshold is about 0.85 V, so
at `Vctl = 0.9 V` the PMOS starve device carries under 1 uA. The PMOS starve
is now 3x wider (12 um against 4 um), and `Vctl` runs from 1.1 V to 1.4 V.
Below about 1.1 V the PMOS device does not turn on hard enough to oscillate
in the simulated window.

Hand estimate: `f = I / (N C VDD)`, with `I` the saturation current of the
NMOS starve device from a DC sweep, and `C` the load plus the next gate
capacitance. The simulation is about 5x slower than this estimate. A scaling
test shows why: doubling the explicit load halves the frequency, so the load
dominates, but the effective current during each transition is about one
fifth of the saturation current. The starve device leaves saturation as the
node moves. So the textbook formula is an upper bound here, and the tests
check that the ratio stays between 0.1 and 0.5.

## PVT and Monte Carlo

PVT is the full grid: 5 corners by 3 supplies (0.9, 1.0 and 1.1 times 1.8 V)
by 3 temperatures (-40, 27 and 125 C). Each point runs the op-amp AC bench,
the bandgap DC point, two comparator decisions and one ring transient.

Monte Carlo draws 100 offset samples (seed 2026). The sample sigma is
compared with the hand sigma. A 100-sample estimate has about 7% statistical
error, so the test tolerance is 35%.

## Known limits

- Resistors are ideal, so the bandgap's drift comes from the transistors
  only.
- The VCO's starve current is measured from a DC sweep. A transient
  measurement would give a better current estimate, but it is harder to
  automate.
- Noise above about 10 MHz is affected by the op-amp's gain roll-off, so the
  input-referred figure there is not a clean device number.
- Only one op-amp size and one bias current are explored. This is a test
  bench for the flow, not an optimised design.
- Layout parasitics are not included. Results are schematic-level only, and
  there is no tapeout claim.
