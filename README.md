# SV Studio

SV Studio is a small, local desktop IDE for SystemVerilog and UVM. The visible
workflow is intentionally limited to five things:

- Project files
- SystemVerilog editor
- Run
- Console
- Waveform

There is no simulator selector, UVM path selector, verbosity selector, seed
form, or custom command form. SV Studio detects whether the project is plain
SystemVerilog or UVM and runs the best free local flow automatically.

## What Run does

For a plain SystemVerilog project, Run:

1. checks the SystemVerilog sources;
2. builds and runs the simulation;
3. opens `.svstudio/waves.vcd` in the Waveform tab.

For a UVM project, the same Run button automatically adds the project-local
CHIPS Alliance UVM library, chooses the configured test class, creates a random
seed, runs the test, and opens the waveform.

The Console hides WSL commands, generated C++ build commands, UVM library
boilerplate, and encoding noise. It keeps project diagnostics, UVM test output,
scoreboard summaries, errors, fatals, and the final result.

## Free local engine

The default engine is fully open source and needs no commercial license:

- [Verilator](https://github.com/verilator/verilator)
- [CHIPS Alliance UVM for Verilator](https://github.com/chipsalliance/uvm-verilator)
- Z3 constrained-random solver
- WSL Ubuntu on Windows

If the engine or project-local UVM library is missing, the first Run offers the
one-time free setup. There are no toolchain settings to manage afterward.

## Start

Use the portable Windows package, or run from source:

```powershell
.\run.ps1
```

No browser is used and project files stay on the local machine.

## Minimal project file

SV Studio maintains a small `.svstudio.json` file internally:

```json
{
  "name": "My Project",
  "top": "tb_top",
  "test": "my_test",
  "sources": ["rtl/**/*.sv", "tb/tb_top.sv"],
  "include_dirs": ["tb"],
  "waveform": ".svstudio/waves.vcd"
}
```

Ordinary SystemVerilog projects may leave `test` empty. UVM projects normally
use one top-level testbench that includes the class files in compilation order.

## Shortcuts

| Shortcut | Action |
| --- | --- |
| `F5` | Run SystemVerilog or UVM automatically |
| `Shift+F5` | Stop |
| `Ctrl+S` | Save |
| `Ctrl+Alt+S` | Save all |
| `Ctrl+F` | Find |

## Build the Windows package

```powershell
.\tools\build_windows.ps1 -Version "0.3.0"
```

The portable archive is written to
`dist/SVStudio-Windows-x64-v0.3.0.zip`. GitHub Actions runs the tests and builds
the package on every push; version tags publish the archive as a GitHub Release.
