# Simulation summary

PDK: SkyWater Sky130, pinned to f62031a1be9a. Simulator: ngspice.
All numbers are from ngspice runs. Hand values use the simulated bias point.

## Checks against hand calculations

| check | simulated | hand / target | rule | result |
|---|---|---|---|---|
| op-amp DC gain (dB) | 68.7 | 68.73 | within +/-1 dB | PASS |
| op-amp unity-gain freq (MHz) | 27.89 | 29.35 | within +/-15% | PASS |
| op-amp phase margin (deg) | 65.55 | 69.58 | within +/-8 deg | PASS |
| bandgap Vref at 27 C (V) | 1.21 | 1.195 | within +/-0.03 V | PASS |
| bandgap drift, -40 to 125 C (ppm/C) | 20.52 | 100 | spec: <= 100 ppm/C (hand estimate is in summary.md) | PASS |
| op-amp offset sigma, Monte Carlo (mV) | 5.453 | 5.573 | within +/-35% | PASS |
| op-amp noise 1 MHz above thermal floor (nV/rtHz) | 35.52 | 14.1 | simulated >= hand floor (flicker adds) | PASS |
| comparator decides +10 mV high and -10 mV low | 1 | 1 | both polarities correct | PASS |
| comparator delay (ps) | 290 | 0 | < 1000 ps | PASS |
| VCO sim/hand frequency ratio | 0.2087 | 1 | 0.1-0.5 (hand is optimistic, see design.md) | PASS |
| PVT points simulated without error | 45 | 45 | all corners, supplies and temperatures | PASS |
| comparator correct at every PVT point | 45 | 45 | all points | PASS |
| bandgap Vref min across PVT (V) | 1.197 | 1.15 | between 1.15 and 1.27 V | PASS |
| op-amp phase margin min across PVT (deg) | 62.96 | 45 | >= 45 deg | PASS |

14 of 14 checks pass.

Bandgap drift: the hand formula with the simulated Vbe gives 99 ppm/C; the simulation gives 21 ppm/C. The gap comes from the output mirror leg sitting at a different drain voltage, which the hand formula ignores.

## Monte Carlo offset

n = 100 samples, sigma = 5.45 mV, mean = -2.07 mV.

## Ring oscillator tuning

| Vctl (V) | simulated (MHz) | hand (MHz) | starve current (uA) |
|---|---|---|---|
| 1.10 | 132.5 | 979 | 209 |
| 1.20 | 284.3 | 1362 | 291 |
| 1.30 | 451.4 | 1783 | 381 |
| 1.40 | 581.8 | 2235 | 478 |

## PVT sweep

| corner | VDD (V) | T (C) | op-amp gain (dB) | UGF (MHz) | PM (deg) | Vref (V) | comparator | delay (ps) | VCO (MHz) |
|---|---|---|---|---|---|---|---|---|---|
| tt | 1.62 | -40 | 63.7 | 31.3 | 66.2 | 1.2129 | ok | 345 | 117 |
| tt | 1.62 | 27 | 64.9 | 27.5 | 65.8 | 1.2095 | ok | 310 | 275 |
| tt | 1.62 | 125 | 65.0 | 22.8 | 66.7 | 1.2040 | ok | 290 | 434 |
| tt | 1.8 | -40 | 69.0 | 31.9 | 65.9 | 1.2114 | ok | 320 | 122 |
| tt | 1.8 | 27 | 68.7 | 27.9 | 65.6 | 1.2103 | ok | 290 | 284 |
| tt | 1.8 | 125 | 67.8 | 23.0 | 66.6 | 1.2073 | ok | 285 | 465 |
| tt | 1.98 | -40 | 70.8 | 32.1 | 65.8 | 1.2113 | ok | 315 | 124 |
| tt | 1.98 | 27 | 70.3 | 28.0 | 65.5 | 1.2109 | ok | 295 | 287 |
| tt | 1.98 | 125 | 69.2 | 23.1 | 66.6 | 1.2090 | ok | 290 | 476 |
| ff | 1.62 | -40 | 64.0 | 32.3 | 65.9 | 1.2087 | ok | 215 | 187 |
| ff | 1.62 | 27 | 64.8 | 28.4 | 65.6 | 1.2044 | ok | 210 | 381 |
| ff | 1.62 | 125 | 64.6 | 23.4 | 66.5 | 1.1971 | ok | 215 | 550 |
| ff | 1.8 | -40 | 68.5 | 32.8 | 65.7 | 1.2078 | ok | 200 | 190 |
| ff | 1.8 | 27 | 68.1 | 28.7 | 65.4 | 1.2054 | ok | 200 | 388 |
| ff | 1.8 | 125 | 67.1 | 23.6 | 66.4 | 1.2005 | ok | 210 | 583 |
| ff | 1.98 | -40 | 70.1 | 32.9 | 65.6 | 1.2079 | ok | 195 | 186 |
| ff | 1.98 | 27 | 69.6 | 28.8 | 65.3 | 1.2061 | ok | 200 | 383 |
| ff | 1.98 | 125 | 68.5 | 23.7 | 66.4 | 1.2022 | ok | 215 | 592 |
| ss | 1.62 | -40 | 63.0 | 30.3 | 66.5 | 1.2162 | ok | 575 | 70 |
| ss | 1.62 | 27 | 64.6 | 26.7 | 66.1 | 1.2141 | ok | 480 | 196 |
| ss | 1.62 | 125 | 65.0 | 22.1 | 66.9 | 1.2109 | ok | 415 | 334 |
| ss | 1.8 | -40 | 69.3 | 30.9 | 66.1 | 1.2141 | ok | 550 | 73 |
| ss | 1.8 | 27 | 69.1 | 27.0 | 65.8 | 1.2146 | ok | 455 | 203 |
| ss | 1.8 | 125 | 68.1 | 22.3 | 66.8 | 1.2142 | ok | 405 | 361 |
| ss | 1.98 | -40 | 71.4 | 31.1 | 66.0 | 1.2138 | ok | 555 | 76 |
| ss | 1.98 | 27 | 70.9 | 27.2 | 65.8 | 1.2151 | ok | 460 | 207 |
| ss | 1.98 | 125 | 69.7 | 22.4 | 66.8 | 1.2158 | ok | 420 | 373 |
| sf | 1.62 | -40 | 57.9 | 31.4 | 64.4 | 1.2149 | ok | 280 | 79 |
| sf | 1.62 | 27 | 61.7 | 28.1 | 63.6 | 1.2091 | ok | 260 | 226 |
| sf | 1.62 | 125 | 63.3 | 23.4 | 64.8 | 1.2010 | ok | 250 | 402 |
| sf | 1.8 | -40 | 68.1 | 32.8 | 63.3 | 1.2112 | ok | 235 | 85 |
| sf | 1.8 | 27 | 67.9 | 28.7 | 63.0 | 1.2094 | ok | 225 | 235 |
| sf | 1.8 | 125 | 67.2 | 23.7 | 64.5 | 1.2042 | ok | 230 | 426 |
| sf | 1.98 | -40 | 70.5 | 33.1 | 63.2 | 1.2109 | ok | 215 | 88 |
| sf | 1.98 | 27 | 70.0 | 28.9 | 63.0 | 1.2099 | ok | 215 | 239 |
| sf | 1.98 | 125 | 69.0 | 23.8 | 64.5 | 1.2058 | ok | 225 | 433 |
| fs | 1.62 | -40 | 66.2 | 30.5 | 68.3 | 1.2123 | ok | 585 | 158 |
| fs | 1.62 | 27 | 66.6 | 26.7 | 67.9 | 1.2104 | ok | 460 | 320 |
| fs | 1.62 | 125 | 66.2 | 22.1 | 68.6 | 1.2075 | ok | 405 | 441 |
| fs | 1.8 | -40 | 69.6 | 30.8 | 68.1 | 1.2117 | ok | 590 | 162 |
| fs | 1.8 | 27 | 69.3 | 27.0 | 67.8 | 1.2115 | ok | 470 | 330 |
| fs | 1.8 | 125 | 68.3 | 22.2 | 68.6 | 1.2109 | ok | 415 | 484 |
| fs | 1.98 | -40 | 71.1 | 30.9 | 68.1 | 1.2118 | ok | 605 | 160 |
| fs | 1.98 | 27 | 70.6 | 27.0 | 67.8 | 1.2122 | ok | 485 | 331 |
| fs | 1.98 | 125 | 69.5 | 22.3 | 68.6 | 1.2126 | ok | 430 | 505 |

