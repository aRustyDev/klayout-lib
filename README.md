# klayout-lib

Parametric device generators for [KLayout](https://www.klayout.de/).

Currently ships one package, `microresistor`: patternable resistor test
structures (straight bars, dogbones, serpentines, van der Pauw crosses) plus the
process/extraction arithmetic that a GDS file cannot carry.

## Install

No PyPI publish — install straight from git:

```sh
pip3 install --user git+ssh://git@github.com/aRustyDev/klayout-lib.git
```

**Use the same interpreter KLayout embeds**, so the package lands on a path
KLayout searches. On macOS with KLayout 0.30.x that is CommandLineTools Python
3.9, and `--user` puts it in `~/Library/Python/3.9/lib/python/site-packages`,
which is already on KLayout's `sys.path`:

```sh
/Library/Developer/CommandLineTools/usr/bin/python3 -m pip install --user \
    git+ssh://git@github.com/aRustyDev/klayout-lib.git
```

Confirm KLayout can see it:

```sh
klayout -b -r /dev/stdin <<<'import microresistor; print(microresistor.__file__)'
```

To pick up new commits, add `--force-reinstall`; to pin a revision, append
`@<tag-or-sha>` to the URL.

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

## Layout

| Module | Contents | Needs |
|---|---|---|
| `units` | `DBU`, `um()`, `tag()` | — |
| `process` | `Material`, `Process` | — |
| `extraction` | `sheet_resistance_vdp()` | — |
| `report` | `report_lines()` | — |
| `base` | `Resistor` ABC, `merged()` | pya |
| `devices` | `StraightBar`, `Dogbone`, `Serpentine`, `GreekCross` | pya |
| `labels` | `text_cell()` | pya + GUI `Basic` PCell library |
| `placement` | `stack()` | pya |

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
- **The pure layer imports without `pya`.** `units`, `process`, `extraction` and
  `report` are resolved eagerly; the geometry names are resolved lazily via PEP
  562, so `from microresistor.process import Process` works under a bare CPython.

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
