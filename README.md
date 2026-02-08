# Sweep

A modern, modular disk cleaning application for Linux.

Sweep finds and removes cached files, temporary data, old logs, and other
reclaimable space across your system. It ships with 40 built-in plugins
covering browsers, package managers, development tools, and more.

## Features

- **40 built-in cleaning plugins** -- caches, logs, trash, thumbnails, old kernels, dev tools, etc.
- **GTK4 / libadwaita GUI** -- modern desktop interface with scan previews and selective cleaning
- **CLI** -- scriptable command-line interface
- **Safe by design** -- preview everything before deleting, risk levels per plugin
- **Parallel scanning** -- multi-threaded engine for fast scans
- **Smart root handling** -- batches privileged operations into a single password prompt
- **Extensible** -- drop-in plugin system with discovery from multiple locations

## Installation

Requires **Python 3.10+** and [uv](https://docs.astral.sh/uv/).

```bash
# Clone and install
git clone https://github.com/BlueManCZ/sweep.git
cd sweep
uv sync
```

For the GTK interface, you also need **GTK4**, **libadwaita**, and **PyGObject**
installed as system packages.

## Usage

### GUI

```bash
uv run sweep-gtk
```

### CLI

```bash
# List available plugins
uv run sweep list

# Preview reclaimable space
uv run sweep scan

# Scan specific plugins
uv run sweep scan --plugins trash,browser_cache

# Clean (with confirmation)
uv run sweep clean
```

## Project Structure

```
src/
  sweep/           # Backend
    core/          # Engine, plugin loader, registry
    plugins/       # 40 built-in cleaning plugins
    models/        # Data models
    cli.py         # CLI entry point
  sweep_gtk/       # Frontend (GTK4 / libadwaita)
    views/         # Dashboard, modules list, scan results
    widgets/       # Reusable UI components
```

## License

[GPL-3.0](LICENSE)
