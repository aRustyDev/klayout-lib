# Design notes — microresistor test-structure mask

Reference design for `macros/resistors.lym`. All dimensions are **drawn**
dimensions in micrometres; the database grid is 1 nm (`DBU = 0.001`).

**Assumption throughout: every device is patterned from the same film**, so the
resistivity ρ and the thickness t are common to all of them and the sheet
resistance

    R_s = ρ / t          [ohm per square]

is a single constant for the whole mask. Nothing here needs to know its value.
Every device is therefore designed to be read as a multiple of `R_s`, which is
what makes the sweep a measurement of the film rather than of any one resistor.

## How length and width set the resistance

For a uniform bar of length `L`, width `W` and thickness `t`:

    R = ρ·L / (W·t)  =  (ρ/t)·(L/W)  =  R_s · N,      N = L / W

`N` is the **number of squares**: the count of `W × W` tiles laid end to end
along the current path. It is dimensionless, and it is the only geometric
quantity that survives.

- **Length is directly proportional.** Double `L` and you double `R` — twice as
  much material in series.
- **Width is inversely proportional.** Double `W` and you halve `R` — two
  identical paths in parallel.
- **Only the ratio matters.** `L = 100, W = 10` and `L = 20, W = 2` both give
  `N = 10` and therefore the same resistance, despite the second occupying 25×
  less area. Absolute size cancels.

That last point is the one worth testing rather than trusting, because it is
only true of an ideal sheet. Two effects break it in practice, and the sweep is
built to separate them:

- **Contact resistance** adds a constant, not a proportional, term:
  `R_measured = R_s·N + 2·R_c`. It dominates when `N` is small.
- **Linewidth bias.** Lithography and lift-off make the finished line differ
  from the drawn one by some `ΔW`, so the effective count is `L / (W − ΔW)`.
  A fixed `ΔW` is a rounding error at `W = 50` and a large fraction at
  `W = 2`, which is why narrow lines are in the sweep at all.

## The devices

`N` is the drawn square count; `R = N · R_s` before contact resistance.
Footprint is the drawn cell including its pads.

### Straight bars — `W` fixed, `L` swept

| device | L (µm) | W (µm) | N | footprint (µm) |
|---|---|---|---|---|
| `BAR_L10_W10` | 10 | 10 | 1.00 | 150 × 40 |
| `BAR_L20_W10` | 20 | 10 | 2.00 | 160 × 40 |
| `BAR_L50_W10` | 50 | 10 | 5.00 | 190 × 40 |
| `BAR_L100_W10` | 100 | 10 | 10.00 | 130 × 40 |
| `BAR_L200_W10` | 200 | 10 | 20.00 | 230 × 40 |

A 20× span in `N` at constant width. Plotting `R` against `L` should give a
straight line: **the slope is `R_s / W`, and the intercept at `L = 0` is
`2·R_c`.** That is the cleanest way to get contact resistance out of the way —
it is the one term that does not scale with length, so extrapolating to zero
length isolates it.

`BAR_L10_W10` is deliberately a single square. On its own it is a poor
resistor, because at `N = 1` the contact term is comparable to the body; that
is exactly why it anchors the low end of the fit.

### Straight bars — `L` fixed, `W` swept

| device | L (µm) | W (µm) | N | footprint (µm) |
|---|---|---|---|---|
| `BAR_L100_W5` | 100 | 5 | 20.00 | 135 × 40 |
| `BAR_L100_W10` | 100 | 10 | 10.00 | 130 × 40 |
| `BAR_L100_W20` | 100 | 20 | 5.00 | 120 × 40 |
| `BAR_L100_W50` | 100 | 50 | 2.00 | 115 × 50 |

A 10× span in width at constant length, giving the `1/W` half of the relation.
Plotting `R` against `1/W` should also be linear with slope `R_s·L`. Any
systematic curvature — narrow lines reading high — is linewidth bias, and
fitting `R = R_s·L/(W − ΔW)` extracts `ΔW`.

### Aspect-ratio control

| device | L (µm) | W (µm) | N | area (µm²) |
|---|---|---|---|---|
| `BAR_L100_W10` | 100 | 10 | 10.00 | 1000 |
| `BAR_L20_W2` | 20 | 2 | 10.00 | 40 |

Same square count, **25× less area**. Ideal-sheet theory says these two must
measure the same. If they do not, the difference is edge bias or film
non-uniformity, and the narrow one will be the one that is wrong — a `ΔW` of
0.2 µm is 2 % at `W = 10` and 10 % at `W = 2`.

> Note: the original macro commented this pair as "1/100 the area". That is
> wrong — each linear dimension is 1/5, so the area ratio is 1/25. Corrected in
> the macro.

### Dogbone — separating body from contact

| device | neck L (µm) | neck W (µm) | head (µm) | N | footprint (µm) |
|---|---|---|---|---|---|
| `DOG_L50_W4_H20` | 50 | 4 | 20 × 20 | 12.50 | 110 × 40 |
| `DOG_L50_W4_H20_RN3` | 50 | 4 | 20 × 20 | 12.50 | 110 × 40 |

A narrow neck between wide heads. `N` counts the **neck only**: current
spreading inside the head is a two-dimensional problem with no closed form. The
point of the geometry is that the spreading happens where the sheet is wide, so
that end term is both small and repeatable — which is what a bar with contacts
its own width cannot promise.

`head_um` must exceed `width_um`, or it is simply a bar; the constructor
enforces it. The `_RN3` variant fillets the four concave neck-to-head corners
with a 3 µm radius. Same `N`, same drawn `L` and `W` — the only difference is
whether current turns a sharp corner entering the neck.

### Greek cross — sheet resistance directly

| device | arm W (µm) | arm L (µm) | span (µm) | N |
|---|---|---|---|---|
| `VDP_W20_A40` | 20 | 40 | 100 | n/a |
| `VDP_W20_A40_RN5` | 20 | 40 | 100 | n/a |

A van der Pauw structure, and the only device here with **no square count at
all** — `n_squares()` returns `None` rather than a number, because a four-
terminal cross is not a series element and any `L/W` quoted for it would be a
fiction. Force current through one opposing arm pair, measure voltage across
the other, and

    R_s = (π / ln 2) · (V / I)  ≈  4.532 · V/I

falls out with contact resistance **cancelled**. This is the mask's independent
measurement of `R_s`: everything else infers it from a fit, and this reads it
directly. If the two disagree, believe the cross and suspect the contacts.

`_RN5` rounds the four reentrant corners, where the current density at the
centre of the cross is highest.

### Serpentines — large `N` in a small footprint

All four share the same trace: **10 µm wide, 520 µm of centreline** (5 legs of
80 µm on a 30 µm pitch), in a 160 × 120 µm footprint.

| device | corner | N | per corner |
|---|---|---|---|
| `SRP_W10_N5_L80` | 90° | 48.48 | 0.56 |
| `SRP_W10_N5_L80_TP4` | 45° miter, 4 µm | 48.00 | 0.50 |
| `SRP_W10_N5_L80_RN12` | rounded, r = 12 µm | 46.96 | 1.77 |
| `SRP_WAVE` | 90° | 48.48 | 0.56 |

A straight bar of `N ≈ 48` at `W = 10` would be 480 µm long. Folding the same
centreline through eight corners fits it into 130 µm of width — under a third
of the span — which is the reason to use a serpentine at all, and the reason
the corners then have to be accounted for.

A naive `centreline / W` gives 52 squares. It over-counts, because current
crowds on the **inside** of a turn and does not use the full corner. The three
variants are drawn with identical centrelines so that the measured differences
between them isolate the bend contribution and nothing else.

The rounded case is worth reading carefully, because the two numbers pull in
opposite directions: each rounded corner carries **more** squares than a sharp
one (1.77 vs 0.56, from the analytic annular-bend result `(π/2)/ln(r_out/r_in)`
with `r_out/r_in = 17/7`), yet the device total is **lower** — because a bend of
radius 12 µm consumes 24 µm of centreline per corner against the sharp corner's
10 µm, and what it removes from the straight runs outweighs what it adds back.

`SRP_WAVE` is the same geometry declared as a wave — amplitude 40 µm
(zero-to-peak, so an 80 µm leg), wavelength 60 µm (one period is a down-and-up,
so a 30 µm pitch), span 120 µm. It exists as a cross-check: it must produce
`N = 48.48`, identical to `SRP_W10_N5_L80`, and it does.

### Matched pad pair — what the contact itself costs

| device | L (µm) | W (µm) | N | pad | footprint (µm) |
|---|---|---|---|---|---|
| `BAR_PAIR_OVERLAP` | 100 | 10 | 10.00 | overlapping | 130 × 40 |
| `BAR_PAIR_LEADED` | 100 | 10 | 10.00 | on a 30 µm lead | 240 × 40 |

Identical resistors, differing only in how they are contacted. The difference
between them is the lead's own series resistance plus the change in contact
area — the one quantity the rest of the sweep has to assume rather than
measure.

## Pad strategy

Pads are on their own mask layer (3/0) because they are a different, thicker
film; the resistor layer is 1/0. A pad contacts the trace either by
**overlapping** it or by sitting clear and connecting through a **lead**.

The choice is made by fit: an overlapping pad adds no lead resistance and is
preferred, but two 40 µm pads cannot overlap a device whose terminals are less
than 40 µm apart — they would merge and short it. Measured on this sweep:

| bar | terminals apart | pad used |
|---|---|---|
| `BAR_L10_W10` | 7.5 µm | leaded |
| `BAR_L20_W10` | 15 µm | leaded |
| `BAR_L50_W10` | 40.0 µm | leaded (exact tie — they abut) |
| `BAR_L100_W10` | 90 µm | overlapping |

Both Greek crosses are pinned to leaded pads explicitly rather than left to the
policy. They differ only in corner treatment, and if the policy gave them
different pad styles that comparison would be confounded by the contacts.

## What to measure

1. **`R_s` from the Greek cross** — direct, contact-free. Use it as the
   reference.
2. **`R` vs `L` at fixed `W`** — slope gives `R_s/W`, intercept gives `2·R_c`.
3. **`R` vs `1/W` at fixed `L`** — slope gives `R_s·L`; curvature gives `ΔW`.
4. **`BAR_L100_W10` vs `BAR_L20_W2`** — should be equal. Any gap is edge bias.
5. **The three serpentines** — differences are the corner contribution.
6. **The pad pair** — difference is the lead and contact-area term.

Steps 1 and 2 should agree on `R_s`. They are measured through entirely
different paths, so agreement is real evidence and disagreement localises the
problem to the contacts.

## Mask summary

- 19 devices, 4 layers: **1/0** resistor, **3/0** pad, **10/0** drawn text,
  **0/0** die boundary (non-printing).
- Content **1200 × 1887 µm** inside a **1500 × 2187 µm** die.
- Two alignment mark sets, diagonally opposite: a coarse cross for acquisition
  plus a box-in-box to read residual registration between 1/0 and 3/0.
- The silicon substrate is **not drawn**. It is unpatterned starting material,
  so there is no mask layer for it; its properties belong in `Process`.
- Every label is drawn geometry, not a GDS text record, so it prints.
