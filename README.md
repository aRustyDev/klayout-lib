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
