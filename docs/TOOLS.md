# OpenGlider Tools Documentation

This document describes the various tools and features available in the OpenGlider workbench for FreeCAD.

## Glider Tools

These tools are the core functionality for designing and modifying the paraglider.

*   **Create Glider**: Creates a new default glider instance in the document.
*   **Import Glider**: Imports a glider configuration from `.json` or `.ods` formats.
*   **Shape**: Modifies the planform shape of the glider (Projected shape, Aspect Ratio, etc.).
*   **Arc**: Modifies the arc of the glider (Anhedral/Dihedral).
*   **Angle of Attack (AoA)**: Modifies the Angle of Attack distribution along the span.
*   **Z-Rotation (Twist)**: Modifies the rib Z-rotation (Washout/Twist) distribution.
*   **Airfoils**: (Deprecated) Create/modify airfoils. Use the Airfoil workbench or *Airfoil Distribution* instead.
*   **Airfoil Distribution**: Distributes different airfoils along the span of the glider.
*   **Ballooning**: Creates or modifies ballooning distributions (3D shaping/bulging between ribs).
*   **Ballooning Distribution**: Distributes ballooning settings along the span.
*   **Lines**: Create and modify the suspension line geometry.
*   **Line Observe**: Check and observe line forces and lengths.
*   **Cells**: Edit cell properties such as count and distribution.
*   **Mini Ribs**: Create or modify mini ribs (reinforcements at the trailing edge).
*   **Airfoil Structure**: Configure internal structure like rod sleeves and attachment reinforcements.
*   **Hole Design**: Graphically design holes in the ribs for weight reduction/airflow.
*   **Cut (Design)**: Cut cells for specific coloring schemes or openings.
*   **Colors**: Modify the colors of the glider panels.
*   **Export 2D**: Export the glider to OpenOffice or JSON formats.

## Production

Tools related to manufacturing and analysis.

*   **Unwrap Glider (Patterns)**: Flattens the 3D glider into 2D patterns for cutting.
*   **Panel Method**: Computes aerodynamic properties using a potential-flow panel method.
*   **Polars**: Calculate and view polar curves for performance analysis.
*   **Import DXF**: fast DXF import helper.

## Features

Advanced modifiers that add specific geometric features to the glider.

*   **Rib Feature**: Explicitly apply airfoils to ribs.
*   **Ballooning Feature**: Explicitly apply ballooning to ribs.
*   **Sharknose Feature**: Creates a "shark nose" profile at the air intake for better stability.
*   **Single Skin Rib Feature**: Creates single-skin ribs (bows between attachment points), useful for single-skin gliders.
*   **Flap Feature**: Modifies or shortens the trailing edge (for flaps or brakes).
*   **Scale Feature**: Scales the entire glider by a 1D factor.
*   **Ballooning Multiplier**: Multiplies ballooning values by a scaling factor.

## View

*   **View Command**: Sets the camera to a specific perspective for viewing the glider.
