# sky130-analog-blocks

I built a set of small analog chip circuits and a script that tests them in a computer simulation, because I wanted to check my hand calculations against real transistor models instead of the ideal parts in textbook formulas. The circuits are a voltage reference, an op-amp, a comparator and a ring oscillator. The transistor models come from SkyWater's free Sky130 chip process, and the simulator is ngspice, a free program that does the same job as the paid simulators big chip companies use.

Running one command simulates all four circuits at many temperatures, supply voltages and process corners, runs a random mismatch test, saves plots, and checks every result against a hand calculation. Each check prints PASS or FAIL.

## What the circuits do

- **Bandgap reference**: makes a voltage of about 1.21 V that barely changes with temperature. Chips use it as a stable reference for other circuits.
- **Two-stage op-amp**: an amplifier with about 69 dB of gain (roughly 3,000 times). It is the building block that the other circuits rely on. The bandgap uses it inside its feedback loop.
- **Comparator**: looks at two voltages and says which one is higher, on each clock tick. It is the core of an analog-to-digital converter.
- **Ring oscillator**: five inverters in a loop that make a square wave. A control voltage sets how fast it runs. It is the simplest kind of voltage-controlled oscillator (VCO).

## How it works

A Python script writes a text netlist for each circuit. A netlist is a list of transistors, resistors and wires, in the format a circuit simulator reads. The script runs ngspice on that netlist, reads back the voltages and currents it prints, and compares them with the answer from a formula I worked out by hand.

The transistor models are the Sky130 device files from the open PDK. The script includes the process corners (typical, fast, slow and the two mixed corners), so each result can be checked across chip variation as well as temperature and supply voltage.

## Results

From one full run (`python -m analog_blocks run`), all 14 checks pass. The numbers below are from the typical corner at 27 C and 1.8 V unless noted.

| block | simulated | hand value | what it shows |
|---|---|---|---|
| op-amp DC gain | 68.7 dB | 68.7 dB | matches the hand formula |
| op-amp unity-gain frequency | 27.9 MHz | 29.3 MHz | within 5% |
| op-amp phase margin | 65.6 deg | 69.6 deg | within 4 deg, the hand formula leaves out one pole |
| bandgap voltage | 1.210 V | 1.195 V | within 15 mV, see the notes below |
| bandgap drift, -40 to 125 C | 21 ppm per C | 99 ppm per C | well under the 100 ppm per C spec |
| op-amp offset, 100 random mismatch samples | 5.45 mV | 5.57 mV | the spread of the random transistor mismatch matches the formula |
| comparator delay at 10 mV input | 290 ps | n/a | decides correctly for both polarities |
| ring oscillator at 1.2 V control | 284 MHz | 1362 MHz | the simple formula is about 5 times too high, see the notes below |

Over all 45 combinations of process corner, supply (plus or minus 10%) and temperature (-40, 27 and 125 C):

- the bandgap stays between 1.197 V and 1.216 V,
- the op-amp phase margin stays above 62 deg,
- the comparator decides correctly every time,
- the ring oscillator runs from 70 MHz to 592 MHz.

The plots are in [`results/`](results/): the op-amp frequency response, the noise spectrum, the bandgap against temperature, the oscillator tuning curve and the mismatch histogram. The full table is in [`results/summary.md`](results/summary.md).

## Notes on the hand-calculation gaps

- **Bandgap**: the hand formula, using the simulated transistor voltage, is 15 mV low at room temperature. The reason is that the two current mirror legs sit at different voltages, so their currents are not exactly equal. The formula assumes they are.
- **Ring oscillator**: the textbook formula assumes the current-limiting transistors stay saturated while each stage switches. In the simulation they leave saturation, so the real frequency is about one fifth of the formula. I kept the simple formula as the check and set the test to accept a ratio between 0.1 and 0.5.
- **Noise**: the simulated noise is above the thermal floor at low frequency because of flicker noise (1/f noise), which the device model includes. The thermal floor from the formula is 14 nV per root hertz, and the simulation gives 35 nV at 1 MHz.

## How to run it

You need Python 3.10 or newer, and ngspice.

```bash
brew install ngspice                   # macOS; on Ubuntu: sudo apt-get install ngspice
scripts/fetch_pdk.sh                   # downloads only the Sky130 device files used here (about 40 MB)
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
python -m analog_blocks run            # full run, about 10 minutes; writes results/
python -m analog_blocks run --quick    # nominal and 20 mismatch samples, about 30 seconds
pytest -m "not sim"                    # hand-calculation tests, no simulator needed
pytest -m sim                          # simulator tests, need ngspice and the PDK
```

The PDK location can be changed with the `SKY130_PDK_ROOT` environment variable. The default is `~/.cache/sky130-analog-blocks/pdk-src`.

## Tests and CI

The unit tests check the formulas on their own. The simulator tests run ngspice on each circuit and check the results against the hand values. GitHub Actions runs both on every push, installs ngspice and the PDK, and uploads the regenerated `results/` folder as an artifact.

## Limits

- This is schematic-level work. There is no layout, so wiring parasitics are not included, and nothing here has been taped out.
- The resistors are ideal, so the bandgap's remaining drift comes from the transistors only.
- Only one op-amp size and one bias current are tried. It is a test bench for the flow, not an optimised design.

More detail on the netlists, the PDK setup and the mismatch method is in [`docs/design.md`](docs/design.md).
