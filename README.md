# klayout-lib

Parametric device generators for [KLayout](https://www.klayout.de/).

Currently ships one package, `microresistor`: patternable resistor test
structures (straight bars, dogbones, serpentines, van der Pauw crosses) plus the
process/extraction arithmetic that a GDS file cannot carry.

## Install

No PyPI publish — install straight from git with
[uv](https://docs.astral.sh/uv/):

```sh
uv pip install \
    --python /Library/Developer/CommandLineTools/usr/bin/python3 \
    --target ~/.klayout/python \
    git+ssh://git@github.com/aRustyDev/klayout-lib.git
```

Both flags carry weight:

- **`--target ~/.klayout/python`** — KLayout puts this directory on `sys.path`
  at startup, so anything installed there is importable from a macro. It is
  KLayout-scoped and wipeable, unlike a shared user site-packages.
- **`--python <CommandLineTools python3>`** — resolve against the interpreter
  KLayout actually embeds (CPython 3.9.6 for KLayout 0.30.x on macOS), so
  `requires-python` and environment markers are evaluated for the right version.

`uv pip install --user` is refused outright — *"pip's `--user` is unsupported
(use a virtual environment instead)"* — and a virtual environment is no help
here, because KLayout never activates one. `--target` is the mechanism that fits.

Confirm KLayout can see it. Note that `klayout` is **not** on `$PATH` by default
on macOS, and that KLayout cannot read a script from a shell heredoc
(`-r /dev/stdin` fails with `Unable to open file`), so use a real file:

```sh
printf 'import microresistor\nprint(microresistor.__file__)\n' > /tmp/mr_check.py
/Applications/klayout.app/Contents/MacOS/klayout -b -r /tmp/mr_check.py
# -> /Users/you/.klayout/python/microresistor/__init__.py
```

### Upgrading, pinning, removing

```sh
# pick up new commits
uv pip install --python /Library/Developer/CommandLineTools/usr/bin/python3 \
    --target ~/.klayout/python --reinstall \
    git+ssh://git@github.com/aRustyDev/klayout-lib.git

# pin a tag, branch or sha by appending @<ref> to the URL
#   git+ssh://git@github.com/aRustyDev/klayout-lib.git@v0.1.0

# remove
uv pip uninstall --python /Library/Developer/CommandLineTools/usr/bin/python3 \
    --target ~/.klayout/python klayout-lib
```

### Why `klayout` is not a dependency

Inside KLayout, `pya` is built in. The standalone `klayout` wheel is only needed
to run the geometry tests *outside* the GUI, and it has **no prebuilt cp39 arm64
wheel** — declaring it as a runtime dependency would make a plain `pip install`
compile KLayout from C++ source. It lives in the `test` extra instead.

## Use

```python
from microresistor import Process, StraightBar, Serpentine, stack, report_lines

bar = StraightBar(length_um=100, width_um=10)
bar.n_squares()            # 10.0
Process(sheet_resistance=50).predict(bar.n_squares())   # 500.0 ohm
```

See [`macros/resistors.lym`](macros/resistors.lym) for a complete mask script —
copy it into `~/.klayout/pymacros/` and run it with F5. Set `MICRORESISTOR_OUT`
to choose where the GDS is written.

### Pads

A pad is a different film from the resistor — usually thick Au over something
thin and resistive — so it goes on its own mask layer. `build_cell` refuses to
draw one without being told which:

```python
from microresistor import Corner, CornerSpec, Pad

pad = Pad(size_um=40, corner=CornerSpec(Corner.TAPERED, chamfer_um=6))
cell = bar.build_cell(layout, metal_layer, pad=pad, pad_layer=pad_layer)
```

A Greek cross gets four pads and a bar two. The cell name picks up a pad suffix
(`BAR_L100_W10_PAD40TP6`), so one device can be built with several pad styles
without colliding.

**A pad contacts the trace one of two ways, and the `lead` chooses which.**

Without a lead — the default — the pad is centred on the terminal and simply
**overlaps the trace**. That is the right answer whenever the device is longer
than the pad is wide.

```python
Pad(size_um=40)                              # overlaps the trace
Pad(size_um=40, lead=Lead(length_um=30))     # sits outside, strapped back
```

With a lead, the pad is pushed clear of the device by `length_um` and joined
back by a strap `width_um` wide (defaulting to the terminal's own width, so it
adds no constriction of its own). That is how a real test structure gets a big
probe pad onto a small resistor: two overlapping 40 µm pads on a 10 µm bar meet
in the middle and short it out, and `build_cell` refuses to draw them.

| bar | terminals apart | overlapping 40 µm pad | 40 µm pad on a lead |
|---|---|---|---|
| `L10_W10` | 7.5 µm | shorts | fine |
| `L50_W10` | 40.0 µm | shorts — exact tie | fine |
| `L100_W10` | 90 µm | fine | fine |

The offset lives inside `Lead` rather than beside it on `Pad`, which makes the
one invalid combination — a pad pushed away from the device with nothing
joining it back — impossible to express. A `Lead(length_um=0)` is likewise
refused, and says to drop the lead instead.

### Mixing pad styles across one sweep

Most masks want both: an overlap wherever the device is long enough to take
one, a lead where it is not. A `PadPlan` holds the two styles and `build_cells`
applies them, so you name a pad only where you care:

```python
OVERLAP = Pad(size_um=40)
LEADED  = Pad(size_um=40, lead=Lead(length_um=30))
PADS    = PadPlan(overlap=OVERLAP, leaded=LEADED)

DEVICES = [
    StraightBar(10, 10),                        # AUTO -> leaded, too short
    StraightBar(200, 10),                       # AUTO -> overlap, it fits
    (GreekCross(...), LEADED),                  # explicit
    (Dogbone(50, 4, 20), None),                 # explicitly bare
]

asm = build_cells(layout, metal, DEVICES, plan=PADS, pad_layer=pads)
grid(layout, top, asm.cells, cols=3)
report_lines(asm.devices, PROCESS, pads=asm.pads)
```

A bare device takes `AUTO`; a `(device, pad)` pair overrides it. `AUTO` prefers
the overlapping pad — it adds no lead resistance and no extra constriction —
and falls back to the lead only when the overlap would bridge the terminals.
`None` is a decision ("draw this one bare"), which is not the same as `AUTO`.

`Assembly` keeps `cells`, `devices` and `pads` aligned by index, so the report
can name the style each device actually got:

```
BAR_L50_W10    squares=  5.00  R_s not measured yet    PAD40TP6L30
BAR_L100_W10   squares= 10.00  R_s not measured yet    PAD40TP6
```

`asm.bare` lists anything that ended up with no pad, and `plan.describe(device)`
explains any single choice.

**Watch for confounding.** If you are comparing two devices that differ only in
geometry, pin their pads explicitly rather than leaving both on `AUTO` — the
policy keys off device length, so a geometry change can silently change the pad
style too and the comparison stops being like for like. The macro's two Greek
crosses are both pinned to `LEADED` for exactly this reason.

`pads_bridge(pad)` answers the question directly, and
`report_lines(devices, process, pad=pad)` flags any device it would skip, so a
missing pad is announced rather than silently dropped.

### Alignment marks, the die outline, and the substrate

Two patterned layers cannot be registered to each other without marks, and this
library has had two since pads moved off the resistor layer:

```python
marks = alignment_marks(layout, resistor_layer, pad_layer, size_um=100)
```

That gives a coarse cross on the primary layer for the aligner to acquire, plus
a box-in-box straddling both layers — a frame on one and a smaller filled box
on the other — whose gap is even on all four sides only when the two masks are
registered. `cross()`, `frame()`, `filled_box()`, `box_in_box()` and
`build_mark_cell()` are exposed if you want to compose your own.

```python
box = die_outline(layout, top, die_layer, width_um, height_um)
fits_in_die(top.bbox(), box)     # did everything actually land inside?
```

**The silicon substrate is deliberately not drawn.** A GDS describes *masks* —
patterned layers — and the substrate is unpatterned starting material, so there
is no mask for it; a filled "substrate" rectangle would say nothing to a fab.
Its electrical properties belong in `Process` for the same reason resistivity
does: *a GDS file cannot hold those things*. What is worth recording is where
the **die** ends, which is what the boundary layer above is for — conventionally
a non-printing layer used for dicing and floorplanning.

### Floorplanning

`stack()` puts everything in one column, which turns a sweep into a ribbon.
`grid()` lays cells out in rows and columns instead. Measured on this library's
own 17-device sweep:

| cols | footprint | aspect |
|---|---|---|
| 1 (`stack`) | 340 × 3010 µm | 8.85 |
| **3** | **1080 × 1230 µm** | **1.14** |
| 6 | 2160 × 720 µm | 3.00 |

More columns is not better: total area grows with `cols`, because each column
is as wide as its widest member. And `grid()` does **not** help
unconditionally — a row of devices that are themselves wide and flat just
becomes a wider, flatter block. It pays off on a mixed sweep at a tuned column
count, and both behaviours are pinned by tests.

### Corner styles

Three treatments, available on pads and on device corners:

| Style | Parameter | Shape |
|---|---|---|
| `Corner.SQUARE` | — | 90 degrees, the default |
| `Corner.ROUNDED` | `radius_um` | circular arc |
| `Corner.TAPERED` | `chamfer_um` | single 45-degree cut |

Which corners get treated depends on the device, because it depends on their
sign. A serpentine's bends are **convex**, so `TAPERED` cuts the outside of the
turn and leaves the crowded inside sharp — a standard miter. A dogbone's
neck-to-head junction and a Greek cross's reentrant corners are **concave**, so
the treatment fills them in instead.

**The square count follows the shape.** This is the point, not a detail: a
rounded bend genuinely carries a different resistance from a sharp one, so
`n_squares()` changes with the corner style rather than reporting a constant
that only ever applied to 90 degrees.

```python
spec = CornerSpec(Corner.ROUNDED, radius_um=12)
s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5,
               pitch_um=30, corner=spec)
s.n_squares()      # 47.44, against 48.48 for the same trace with sharp bends
```

`ROUNDED` uses the analytic 90-degree annular-bend result,
`(pi/2) / ln(r_outer / r_inner)`, and needs no fitted constant. `SQUARE` and
`TAPERED` use literature defaults (0.56 and 0.50) that texts disagree about;
override either with `CornerSpec(..., squares_override=...)` once you have
measured your own.

### Serpentines as waves

A meander is often easier to sweep in wave terms than in legs and pitches:

```python
s = Serpentine.from_wave(trace_thickness_um=10, amplitude_um=40,
                         length_um=120, wavelength_um=60)
s.n_legs, s.pitch_um, s.leg_length_um      # 5, 30.0, 80.0
```

One period is a down-and-up, so `pitch = wavelength / 2`. Amplitude is
zero-to-peak in the usual wave sense, so the leg spans twice it. Pass
`frequency_per_um` instead of `wavelength_um` if you prefer (`f = 1 / lambda`);
exactly one of the two is required.

`length_um` is a **request**: the span is quantised to whole legs, so read
`s.length_um` back rather than assuming you got what you asked for. The
`wavelength_um`, `frequency_per_um` and `amplitude_um` properties likewise
report what was actually built.

Note the parameter is `trace_thickness_um`, never plain `thickness`:
`Process.thickness_nm` already means the deposited **film** thickness, the z
dimension that derives sheet resistance, and the two must not be confusable.

## Layout

| Module | Contents | Needs |
|---|---|---|
| `units` | `DBU`, `um()`, `tag()` | — |
| `process` | `Material`, `Process` | — |
| `extraction` | `sheet_resistance_vdp()` | — |
| `corners` | `Corner`, `CornerSpec` — shapes *and* their square counts | — |
| `report` | `report_lines()` | — |
| `base` | `Resistor` ABC, `merged()`, `apply_corners()` | pya |
| `devices` | `StraightBar`, `Dogbone`, `Serpentine`, `GreekCross` | pya |
| `pads` | `Pad`, `Lead` | pya |
| `assembly` | `PadPlan`, `AUTO`, `build_cells()` — mixing pad styles | — |
| `marks` | alignment marks, `die_outline()`, `fits_in_die()` | pya |
| `labels` | `text_cell()` | pya + the `Basic` PCell library |
| `placement` | `stack()`, `grid()` | pya |

Design rules, which the module docstrings expand on:

- **Geometry classes carry only geometry.** No resistivity, thickness or
  resistance — a GDS cannot hold those, so they live in `process`, and turning
  measurements back into process parameters lives in `extraction`.
- **`Resistor` is an interface** (`shapes` / `terminals` / `n_squares`), not a
  data container. That is what lets a 4-terminal Greek cross and a 2-terminal bar
  coexist without either lying about its shape; `GreekCross.n_squares()` returns
  `None` rather than a fiction.
- **Each device is built in its own local frame.** `stack()` normalises with
  `cell.bbox()`, so no device has to agree with any other about its origin.
- **Pads are not part of the resistor.** Different film, different layer,
  contact resistance rather than sheet squares — so `build_cell` refuses to draw
  a pad without a `pad_layer`, and the resistor layer is bit-identical with and
  without pads.
- **The pure layer imports without `pya`.** `units`, `process`, `extraction`,
  `corners` and `report` are resolved eagerly; the geometry names are resolved
  lazily via PEP 562, so `from microresistor.process import Process` works under
  a bare CPython. `corners` is in that layer deliberately: the square-count
  model is the part most able to be silently wrong, so it stays testable without
  KLayout.

Targets **Python 3.9** — the interpreter KLayout 0.30.x embeds. No `X | Y`
unions, no 3.10+ syntax.

## Develop

Tests run against `src/` with no install step:

```sh
uv run --with klayout --with pytest pytest      # full suite
uv run --python 3.9 --with pytest pytest        # pure layer on KLayout's 3.9
```

The second command deliberately omits the `klayout` wheel: the geometry modules
skip via `importorskip`, and what remains proves the pure layer really is
importable without `pya` on the version KLayout runs. Do **not** combine
`--python 3.9` with `--with klayout` — that triggers the source build described
above.

Reinstall when you want KLayout itself to see your changes.
