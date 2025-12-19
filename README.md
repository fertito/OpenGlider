# OpenGlider

[![Build Status](https://travis-ci.org/booya-at/OpenGlider.svg?branch=develop)](https://travis-ci.org/booya-at/OpenGlider)
[![Coverage Status](https://img.shields.io/coveralls/hiaselhans/OpenGlider.svg)](https://coveralls.io/r/hiaselhans/OpenGlider)
[![Documentation Status](https://readthedocs.org/projects/openglider/badge/?version=latest)](https://readthedocs.org/projects/openglider/?badge=latest)

OpenGlider is a **FreeCAD Workbench for Paraglider Design**. It provides a comprehensive set of tools to design, analyze, and manufacture paragliders.

## Project Status & Origins

This project is a fork of the original **OpenGlider** project initiated by [booya-at](https://github.com/booya-at/OpenGlider). We gratefully acknowledge their foundational work. This fork is currently maintained here to continue development and support modern FreeCAD versions.

## Installation

The recommended way to install and run OpenGlider is using **Pixi**.

### Prerequisites
*   **Pixi**: Ensure you have [Pixi](https://prefix.dev/) installed.

### Run with Pixi
To launch FreeCAD with the OpenGlider workbench pre-installed and configured:

```bash
pixi run freecad
```

This command will set up the environment and start FreeCAD. OpenGlider will be available in the workbench selector.

### Legacy Installation
For other installation methods (e.g., manual pip install), please refer to previous documentation or the `pixi.toml` file for dependency listings.

## Tools and Features

OpenGlider offers a wide range of tools for every stage of paraglider design:

*   **Design**: Create gliders, modify shapes, define arcs, and adjust twist (washout).
*   **Structure**: Configure internal structures, mini-ribs, and ballooning.
*   **Analysis**: Perform aerodynamic calculations using the built-in Panel Method and view polars.
*   **Production**: Unwrap the 3D model into 2D cutting patterns and export to various formats.

For a detailed list of all available tools and their descriptions, please see the **[Tools Documentation](docs/TOOLS.md)**.

## Screenshots

![glider workbench gui](docs/freecad_gui.png)
*The Glider Workbench GUI in FreeCAD*

![testcell with miniribs](docs/screen.png)
*Detailed view of cells with mini-ribs*

![demokite plots](docs/screen3.png)
*Aerodynamic plots*

## Documentation & Help

*   **[Tools Documentation](docs/TOOLS.md)**: Detailed reference for all workbench tools.
*   **[Base Module](openglider/README.md)**: Developer documentation for the core `openglider` library.
*   **[GUI Tutorial](https://booya-at.github.io/openglider-tutorial)**: Original tutorial (external link).

## Development

To run unittests:

```bash
pixi run test
```

## Roadmap

The project aims to integrate:
*   **Python** scripting.
*   **Panel Method** for aerodynamics (VSAERO/Apame).
*   **OpenFoam** export for CFD.
*   **ParaFEM** for structural analysis (membrane/truss).
