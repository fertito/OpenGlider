# -*- coding: utf-8 -*-
"""
Airfoil Control Tool - Unified airfoil management for OpenGlider

Combines:
- Profile Distribution (span mapping)
- Profile Overrides (rib-specific)
- Shark Nose (procedural deformation with cell selection)
- Thickness Control (span-based scaling)
- Wingtip Profile (end profile blending)
- AoA (Angle of Attack) management
- Z Rotation (incidence) management
"""
from __future__ import division

import numpy as np
from pivy import coin
from PySide import QtGui, QtCore

from pivy import graphics
from openglider.airfoil import Profile2D
from openglider.glider.rib import Rib
from openglider.vector.spline import SymmetricBSpline

from .tools import (
    BaseTool,
    input_field,
    spline_select,
    text_field,
    ControlPointContainer,
    Line_old,
    vector3D,
)


class AirfoilControlTool(BaseTool):
    """Unified Airfoil Control Tool with tabbed interface"""
    widget_name = "Airfoil Control"
    num_on_drag = 80
    num_release = 200
    
    def __init__(self, obj):
        super(AirfoilControlTool, self).__init__(obj)
        
        # Create main tab widget
        self.tab_widget = QtGui.QTabWidget(self.base_widget)
        self.layout.setWidget(0, QtGui.QFormLayout.SpanningRole, self.tab_widget)
        
        # Shape data for grids
        self.ribs = self.parametric_glider.shape.ribs
        self.front = [rib[0] for rib in self.ribs]
        self.back = [rib[1] for rib in self.ribs]
        self.x_grid = [i[0] for i in self.front]
        self.text_scale = self.parametric_glider.shape.span / len(self.front) / 20.0
        
        # Create tabs
        self._create_distribution_tab()
        self._create_overrides_tab()
        self._create_sharknose_tab()
        self._create_thickness_tab()
        self._create_last_airfoil_tab()
        self._create_aoa_tab()
        self._create_zrot_tab()
        
        # 3D preview elements
        self.shape = coin.SoSeparator()
        self.preview_shape = coin.SoSeparator()
        
        # One SoSwitch per spline tab for visibility toggling
        # Distribution
        self.dist_switch = coin.SoSwitch()
        self.dist_switch.whichChild = 0
        self.dist_container = coin.SoSeparator()
        self.dist_switch.addChild(self.dist_container)
        # Thickness
        self.thickness_switch = coin.SoSwitch()
        self.thickness_switch.whichChild = 0
        self.thickness_container = coin.SoSeparator()
        self.thickness_switch.addChild(self.thickness_container)
        # AoA
        self.aoa_switch = coin.SoSwitch()
        self.aoa_switch.whichChild = 0
        self.aoa_container = coin.SoSeparator()
        self.aoa_switch.addChild(self.aoa_container)
        # Zrot
        self.zrot_switch = coin.SoSwitch()
        self.zrot_switch.whichChild = 0
        self.zrot_container = coin.SoSeparator()
        self.zrot_switch.addChild(self.zrot_container)
        
        self.setup_pivy()
        
        # Connect tab change to show/hide 3D elements
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(self.tab_widget.currentIndex())
        
    def _create_distribution_tab(self):
        """Tab 1: Profile Distribution along span"""
        tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(tab)
        
        # Spline point count
        num_layout = QtGui.QHBoxLayout()
        num_layout.addWidget(QtGui.QLabel("Control points:"))
        self.dist_num_points = QtGui.QSpinBox()
        self.dist_num_points.setRange(2, 9)
        self.dist_num_points.setValue(len(self.parametric_glider.profile_merge_curve.controlpoints))
        self.dist_num_points.valueChanged.connect(self._update_distribution_points)
        num_layout.addWidget(self.dist_num_points)
        layout.addLayout(num_layout)
        
        # Info label
        info = QtGui.QLabel(
            "Drag control points in 3D view to define profile distribution.\n"
            "Y-axis = profile index (0, 1, 2...)"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Control points table
        self.dist_points_table = QtGui.QTableWidget()
        self.dist_points_table.setColumnCount(3)
        self.dist_points_table.setHorizontalHeaderLabels(["#", "Span (%)", "Value"])
        self.dist_points_table.horizontalHeader().setStretchLastSection(True)
        self.dist_points_table.setColumnWidth(0, 30)
        self.dist_points_table.setMaximumHeight(180)
        self.dist_points_table.setEditTriggers(QtGui.QAbstractItemView.DoubleClicked)
        layout.addWidget(self.dist_points_table)
        
        self.dist_apply_btn = QtGui.QPushButton("Apply Points")
        self.dist_apply_btn.clicked.connect(self._apply_distribution_points)
        layout.addWidget(self.dist_apply_btn)
        
        # Profile list
        layout.addWidget(QtGui.QLabel("Available profiles:"))
        self.profile_list = QtGui.QListWidget()
        for i, p in enumerate(self.parametric_glider.profiles):
            self.profile_list.addItem("{}. {}".format(i, p.name))
        layout.addWidget(self.profile_list)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Distribution")
        
    def _create_overrides_tab(self):
        """Tab 2: Rib-specific profile overrides"""
        tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(tab)
        
        # Enable checkbox
        self.overrides_enabled = QtGui.QCheckBox("Enable rib-specific overrides")
        self.overrides_enabled.setChecked(
            getattr(self.parametric_glider, 'profile_overrides_enabled', False)
        )
        self.overrides_enabled.stateChanged.connect(self._update_overrides)
        layout.addWidget(self.overrides_enabled)
        
        # Override table
        self.override_table = QtGui.QTableWidget()
        self.override_table.setColumnCount(3)
        self.override_table.setHorizontalHeaderLabels(["Rib", "Default", "Override"])
        self.override_table.horizontalHeader().setStretchLastSection(True)
        
        x_values = self.parametric_glider.shape.rib_x_values
        profile_merge = self.parametric_glider.profile_merge_curve.interpolation(num=50)
        overrides = getattr(self.parametric_glider, 'profile_overrides', {})
        
        self.override_table.setRowCount(len(x_values))
        for i, x in enumerate(x_values):
            # Rib number
            rib_item = QtGui.QTableWidgetItem("R{}".format(i))
            rib_item.setFlags(rib_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.override_table.setItem(i, 0, rib_item)
            
            # Default profile from merge curve
            factor = profile_merge(abs(x))
            default_idx = int(min(factor, len(self.parametric_glider.profiles) - 1))
            default_name = self.parametric_glider.profiles[default_idx].name if self.parametric_glider.profiles else "N/A"
            default_item = QtGui.QTableWidgetItem(default_name)
            default_item.setFlags(default_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.override_table.setItem(i, 1, default_item)
            
            # Override combo
            combo = QtGui.QComboBox()
            combo.addItem("(Use distribution)")
            for j, p in enumerate(self.parametric_glider.profiles):
                combo.addItem("{}. {}".format(j, p.name))
            
            # Set current override if exists
            if str(i) in overrides:
                combo.setCurrentIndex(overrides[str(i)] + 1)
            
            combo.currentIndexChanged.connect(self._update_overrides)
            self.override_table.setCellWidget(i, 2, combo)
            
        layout.addWidget(self.override_table)
        self.tab_widget.addTab(tab, "Overrides")
        
    def _create_sharknose_tab(self):
        """Tab 3: Shark Nose procedural deformation with cell selection"""
        tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(tab)
        
        # Enable checkbox
        self.sharknose_enabled = QtGui.QCheckBox("Enable shark nose")
        self.sharknose_enabled.setChecked(
            getattr(self.parametric_glider, 'sharknose_enabled', False)
        )
        self.sharknose_enabled.stateChanged.connect(self._update_sharknose)
        layout.addWidget(self.sharknose_enabled)
        
        # Parameters in form layout
        form = QtGui.QFormLayout()
        
        self.sharknose_x1 = QtGui.QDoubleSpinBox()
        self.sharknose_x1.setRange(0.0, 0.5)
        self.sharknose_x1.setSingleStep(0.01)
        self.sharknose_x1.setDecimals(3)
        self.sharknose_x1.setValue(getattr(self.parametric_glider, 'sharknose_x1', 0.06))
        self.sharknose_x1.valueChanged.connect(self._update_sharknose)
        form.addRow("Start position (x1):", self.sharknose_x1)
        
        self.sharknose_x2 = QtGui.QDoubleSpinBox()
        self.sharknose_x2.setRange(0.0, 0.5)
        self.sharknose_x2.setSingleStep(0.01)
        self.sharknose_x2.setDecimals(3)
        self.sharknose_x2.setValue(getattr(self.parametric_glider, 'sharknose_x2', 0.09))
        self.sharknose_x2.valueChanged.connect(self._update_sharknose)
        form.addRow("Max shift position (x2):", self.sharknose_x2)
        
        self.sharknose_x3 = QtGui.QDoubleSpinBox()
        self.sharknose_x3.setRange(0.0, 1.0)
        self.sharknose_x3.setSingleStep(0.05)
        self.sharknose_x3.setDecimals(2)
        self.sharknose_x3.setValue(getattr(self.parametric_glider, 'sharknose_x3', 0.90))
        self.sharknose_x3.valueChanged.connect(self._update_sharknose)
        form.addRow("End position (x3):", self.sharknose_x3)
        
        self.sharknose_y_max = QtGui.QDoubleSpinBox()
        self.sharknose_y_max.setRange(0.0, 0.1)
        self.sharknose_y_max.setSingleStep(0.005)
        self.sharknose_y_max.setDecimals(3)
        self.sharknose_y_max.setValue(getattr(self.parametric_glider, 'sharknose_y_max', 0.03))
        self.sharknose_y_max.valueChanged.connect(self._update_sharknose)
        form.addRow("Max shift amount (y_max):", self.sharknose_y_max)
        
        layout.addLayout(form)
        
        # Cell selection
        layout.addWidget(QtGui.QLabel("Apply to cells:"))
        
        # Select All / None buttons
        btn_layout = QtGui.QHBoxLayout()
        select_all_btn = QtGui.QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_sharknose_cells)
        select_none_btn = QtGui.QPushButton("Select None")
        select_none_btn.clicked.connect(self._select_no_sharknose_cells)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(select_none_btn)
        layout.addLayout(btn_layout)
        
        # Cell checkboxes in scroll area
        scroll = QtGui.QScrollArea()
        scroll.setWidgetResizable(True)
        cell_widget = QtGui.QWidget()
        cell_layout = QtGui.QGridLayout(cell_widget)
        
        num_cells = len(self.parametric_glider.shape.rib_x_values) - 1
        sharknose_cells = getattr(self.parametric_glider, 'sharknose_cells', None)
        if sharknose_cells is None:
            sharknose_cells = list(range(num_cells))  # Default to all cells
        
        self.sharknose_cell_checkboxes = []
        cols = 4
        for i in range(num_cells):
            cb = QtGui.QCheckBox("Cell {}".format(i))
            cb.setChecked(i in sharknose_cells)
            cb.stateChanged.connect(self._update_sharknose)
            cell_layout.addWidget(cb, i // cols, i % cols)
            self.sharknose_cell_checkboxes.append(cb)
        
        scroll.setWidget(cell_widget)
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(tab, "Shark Nose")
        
    def _create_thickness_tab(self):
        """Tab 4: Thickness control along span"""
        tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(tab)
        
        # Enable checkbox
        self.thickness_enabled = QtGui.QCheckBox("Enable thickness variation")
        self.thickness_enabled.setChecked(
            getattr(self.parametric_glider, 'thickness_curve_enabled', False)
        )
        self.thickness_enabled.stateChanged.connect(self._update_thickness)
        layout.addWidget(self.thickness_enabled)
        
        # Spline point count
        num_layout = QtGui.QHBoxLayout()
        num_layout.addWidget(QtGui.QLabel("Control points:"))
        self.thickness_num_points = QtGui.QSpinBox()
        self.thickness_num_points.setRange(2, 9)
        
        # Initialize thickness curve if needed
        if not hasattr(self.parametric_glider, 'thickness_curve') or self.parametric_glider.thickness_curve is None:
            span = self.parametric_glider.shape.span
            self.parametric_glider.thickness_curve = SymmetricBSpline([[0, 1.0], [span, 1.0]])
        
        self.thickness_num_points.setValue(len(self.parametric_glider.thickness_curve.controlpoints))
        self.thickness_num_points.valueChanged.connect(self._update_thickness_points)
        num_layout.addWidget(self.thickness_num_points)
        layout.addLayout(num_layout)
        
        # Info
        info = QtGui.QLabel(
            "Adjust thickness scaling along span.\n"
            "Y-axis: 1.0 = original, 0.8 = 80%, 1.2 = 120%\n"
            "Drag control points in 3D view."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Control points table
        self.thickness_points_table = QtGui.QTableWidget()
        self.thickness_points_table.setColumnCount(3)
        self.thickness_points_table.setHorizontalHeaderLabels(["#", "Span (%)", "Scale"])
        self.thickness_points_table.horizontalHeader().setStretchLastSection(True)
        self.thickness_points_table.setColumnWidth(0, 30)
        self.thickness_points_table.setMaximumHeight(180)
        self.thickness_points_table.setEditTriggers(QtGui.QAbstractItemView.DoubleClicked)
        layout.addWidget(self.thickness_points_table)
        
        self.thickness_apply_btn = QtGui.QPushButton("Apply Points")
        self.thickness_apply_btn.clicked.connect(self._apply_thickness_points)
        layout.addWidget(self.thickness_apply_btn)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Thickness")
        
    def _create_last_airfoil_tab(self):
        """Tab 5: Last Airfoil (stabilo profile)"""
        tab = QtGui.QWidget()
        layout = QtGui.QFormLayout(tab)
        
        # Info
        info = QtGui.QLabel(
            "Define the profile for the last rib (stabilo).\n"
            "This is applied only to the very last rib at the wing tip."
        )
        info.setWordWrap(True)
        layout.addRow(info)
        
        # Enable checkbox
        self.last_airfoil_enabled = QtGui.QCheckBox("Enable custom last airfoil")
        self.last_airfoil_enabled.setChecked(
            getattr(self.parametric_glider, 'last_profile_enabled', False)
        )
        self.last_airfoil_enabled.stateChanged.connect(self._update_last_airfoil)
        layout.addRow(self.last_airfoil_enabled)
        
        # Type selection
        self.last_airfoil_type_group = QtGui.QButtonGroup(tab)
        type_widget = QtGui.QWidget()
        type_layout = QtGui.QVBoxLayout(type_widget)
        type_layout.setContentsMargins(0, 0, 0, 0)
        
        self.last_airfoil_line = QtGui.QRadioButton("Line (zero thickness)")
        self.last_airfoil_thin = QtGui.QRadioButton("Thin profile (scaled)")
        self.last_airfoil_custom = QtGui.QRadioButton("Custom profile")
        
        self.last_airfoil_type_group.addButton(self.last_airfoil_line, 0)
        self.last_airfoil_type_group.addButton(self.last_airfoil_thin, 1)
        self.last_airfoil_type_group.addButton(self.last_airfoil_custom, 2)
        
        last_type = getattr(self.parametric_glider, 'last_profile_type', 'line')
        if last_type == 'line':
            self.last_airfoil_line.setChecked(True)
        elif last_type == 'thin':
            self.last_airfoil_thin.setChecked(True)
        else:
            self.last_airfoil_custom.setChecked(True)
        
        type_layout.addWidget(self.last_airfoil_line)
        type_layout.addWidget(self.last_airfoil_thin)
        type_layout.addWidget(self.last_airfoil_custom)
        layout.addRow("Type:", type_widget)
        
        for btn in [self.last_airfoil_line, self.last_airfoil_thin, self.last_airfoil_custom]:
            btn.toggled.connect(self._update_last_airfoil)
        
        # Relative thickness (for thin type)
        self.last_airfoil_thickness = QtGui.QDoubleSpinBox()
        self.last_airfoil_thickness.setRange(0.05, 1.0)
        self.last_airfoil_thickness.setSingleStep(0.05)
        self.last_airfoil_thickness.setDecimals(2)
        self.last_airfoil_thickness.setValue(
            getattr(self.parametric_glider, 'last_profile_thickness', 0.3)
        )
        self.last_airfoil_thickness.valueChanged.connect(self._update_last_airfoil)
        layout.addRow("Relative thickness:", self.last_airfoil_thickness)
        
        # Custom profile selector
        self.last_airfoil_import = QtGui.QPushButton("Import .dat file...")
        self.last_airfoil_import.clicked.connect(self._import_last_profile)
        layout.addRow("Custom profile:", self.last_airfoil_import)
        
        self.tab_widget.addTab(tab, "Last Airfoil")
        
    def _create_aoa_tab(self):
        """Tab 6: Angle of Attack along span"""
        tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(tab)
        
        # Control points
        num_layout = QtGui.QHBoxLayout()
        num_layout.addWidget(QtGui.QLabel("Control points:"))
        self.aoa_num_points = QtGui.QSpinBox()
        self.aoa_num_points.setRange(2, 9)
        self.aoa_num_points.setValue(len(self.parametric_glider.aoa.controlpoints))
        self.aoa_num_points.valueChanged.connect(self._update_aoa_points)
        num_layout.addWidget(self.aoa_num_points)
        layout.addLayout(num_layout)
        
        # Glide number
        glide_layout = QtGui.QHBoxLayout()
        glide_layout.addWidget(QtGui.QLabel("Glide number:"))
        self.aoa_glide = QtGui.QDoubleSpinBox()
        self.aoa_glide.setRange(1.0, 20.0)
        self.aoa_glide.setSingleStep(0.1)
        self.aoa_glide.setDecimals(1)
        self.aoa_glide.setValue(self.parametric_glider.glide)
        self.aoa_glide.valueChanged.connect(self._update_glide)
        glide_layout.addWidget(self.aoa_glide)
        layout.addLayout(glide_layout)
        
        # Info
        info = QtGui.QLabel(
            "Angle of Attack (AoA) along the span.\n\n"
            "The AoA defines the angle between each rib's chord\n"
            "and the airflow. A higher AoA increases lift but\n"
            "also drag. Typically, the center has a higher AoA\n"
            "and the tips have less, to ensure progressive stall\n"
            "behaviour (tips fly while center stalls first).\n\n"
            "Glide number (finesse): the glide ratio of the wing.\n"
            "Example: 8 means 8m forward per 1m descent.\n"
            "This determines the flight path angle, i.e. the\n"
            "direction of the relative wind seen by the wing.\n\n"
            "Because the wing is curved (arc), external ribs are\n"
            "tilted relative to the center. A tilted rib sees the\n"
            "airflow at a different effective angle. The correction\n"
            "depends on both the arc angle and the glide ratio:\n"
            "  correction = arctan(cos(arc_angle) / glide)\n\n"
            "Red curve: AoA you define (relative to each rib).\n"
            "Blue curve: effective AoA after arc correction.\n"
            "The blue curve shows the actual aerodynamic angle\n"
            "each rib will experience in flight.\n\n"
            "Values are in degrees."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Control points table
        self.aoa_points_table = QtGui.QTableWidget()
        self.aoa_points_table.setColumnCount(3)
        self.aoa_points_table.setHorizontalHeaderLabels(["#", "Span (%)", "AoA (°)"])
        self.aoa_points_table.horizontalHeader().setStretchLastSection(True)
        self.aoa_points_table.setColumnWidth(0, 30)
        self.aoa_points_table.setMaximumHeight(180)
        self.aoa_points_table.setEditTriggers(QtGui.QAbstractItemView.DoubleClicked)
        layout.addWidget(self.aoa_points_table)
        
        self.aoa_apply_btn = QtGui.QPushButton("Apply Points")
        self.aoa_apply_btn.clicked.connect(self._apply_aoa_points)
        layout.addWidget(self.aoa_apply_btn)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "AoA")
        
    def _create_zrot_tab(self):
        """Tab 7: Z Rotation (incidence) along span"""
        tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(tab)
        
        # Control points
        num_layout = QtGui.QHBoxLayout()
        num_layout.addWidget(QtGui.QLabel("Control points:"))
        self.zrot_num_points = QtGui.QSpinBox()
        self.zrot_num_points.setRange(2, 9)
        self.zrot_num_points.setValue(len(self.parametric_glider.zrot.controlpoints))
        self.zrot_num_points.valueChanged.connect(self._update_zrot_points)
        num_layout.addWidget(self.zrot_num_points)
        layout.addLayout(num_layout)
        
        # Auto-calculate buttons
        auto_group = QtGui.QGroupBox("Auto-calculate Zrot")
        auto_layout = QtGui.QVBoxLayout(auto_group)
        
        # Geometric estimation button
        self.zrot_auto_btn = QtGui.QPushButton("Estimation géométrique (zrot=1)")
        self.zrot_auto_btn.setToolTip(
            "Set zrot = 1.0 for all points.\n"
            "Uses the simplified formula: arctan(arc_angle) / glide\n"
            "Fast but ignores induced velocities from the wing."
        )
        self.zrot_auto_btn.clicked.connect(self._auto_zrot_airflow)
        auto_layout.addWidget(self.zrot_auto_btn)
        
        # CFD panel method button
        self.zrot_cfd_btn = QtGui.QPushButton("CFD: Panel Method (parabem)")
        self.zrot_cfd_btn.setToolTip(
            "Run a 3D panel method to compute the actual\n"
            "local flow direction at each rib position.\n"
            "More accurate but takes a few seconds."
        )
        self.zrot_cfd_btn.clicked.connect(self._auto_zrot_cfd)
        auto_layout.addWidget(self.zrot_cfd_btn)
        
        # Check parabem availability
        try:
            __import__("parabem")
        except ImportError:
            self.zrot_cfd_btn.setEnabled(False)
            self.zrot_cfd_btn.setToolTip(
                "parabem is not installed.\n"
                "Install it via pixi or pip to enable CFD computation."
            )
        
        layout.addWidget(auto_group)
        
        # Info
        info = QtGui.QLabel(
            "Z Rotation controls rib rotation around the Z-axis\n"
            "to compensate for arc curvature in the airflow.\n\n"
            "• Estimation géométrique: zrot=1 → arctan(arc)/glide\n"
            "• CFD Panel Method: computes actual flow angles\n"
            "  using parabem 3D potential flow solver"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Control points table
        self.zrot_points_table = QtGui.QTableWidget()
        self.zrot_points_table.setColumnCount(3)
        self.zrot_points_table.setHorizontalHeaderLabels(["#", "Span (%)", "Zrot"])
        self.zrot_points_table.horizontalHeader().setStretchLastSection(True)
        self.zrot_points_table.setColumnWidth(0, 30)
        self.zrot_points_table.setMaximumHeight(180)
        self.zrot_points_table.setEditTriggers(QtGui.QAbstractItemView.DoubleClicked)
        layout.addWidget(self.zrot_points_table)
        
        self.zrot_apply_btn = QtGui.QPushButton("Apply Points")
        self.zrot_apply_btn.clicked.connect(self._apply_zrot_points)
        layout.addWidget(self.zrot_apply_btn)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Z Rotation")
        
    def setup_pivy(self):
        """Setup 3D visualization"""
        # Add shape visualization
        self.task_separator.addChild(self.shape)
        self.task_separator.addChild(self.preview_shape)
        self.task_separator.addChild(self.dist_switch)
        self.task_separator.addChild(self.thickness_switch)
        self.task_separator.addChild(self.aoa_switch)
        self.task_separator.addChild(self.zrot_switch)
        
        # Grid/coords sub-separators (children of the containers)
        self.dist_grid = coin.SoSeparator()
        self.dist_coords = coin.SoSeparator()
        self.dist_container.addChild(self.dist_grid)
        self.dist_container.addChild(self.dist_coords)
        
        self.thickness_grid = coin.SoSeparator()
        self.thickness_coords = coin.SoSeparator()
        self.thickness_container.addChild(self.thickness_grid)
        self.thickness_container.addChild(self.thickness_coords)
        
        self.aoa_grid = coin.SoSeparator()
        self.aoa_coords = coin.SoSeparator()
        self.aoa_container.addChild(self.aoa_grid)
        self.aoa_container.addChild(self.aoa_coords)
        
        self.zrot_grid = coin.SoSeparator()
        self.zrot_coords = coin.SoSeparator()
        self.zrot_container.addChild(self.zrot_grid)
        self.zrot_container.addChild(self.zrot_coords)
        
        # Draw glider shape
        self._draw_shape()
        
        # Setup spline controls for distribution tab
        self._setup_distribution_spline()
        
        # Setup spline controls for thickness tab
        self._setup_thickness_spline()
        
        # Setup spline controls for AoA tab
        self._setup_aoa_spline()
        
        # Setup spline controls for Zrot tab
        self._setup_zrot_spline()
        
    def _on_tab_changed(self, index):
        """Show/hide 3D elements based on which tab is active.
        
        Tab indices:
          0 = Distribution
          1 = Overrides (no 3D spline)
          2 = Shark Nose (no 3D spline)
          3 = Thickness
          4 = Last Airfoil (no 3D spline)
          5 = AoA
          6 = Z Rotation
        """
        self.dist_switch.whichChild = 0 if index == 0 else -1
        self.thickness_switch.whichChild = 0 if index == 3 else -1
        self.aoa_switch.whichChild = 0 if index == 5 else -1
        self.zrot_switch.whichChild = 0 if index == 6 else -1
        
    def _setup_distribution_spline(self):
        """Setup spline control points for profile distribution with grid"""
        scale = np.array([1.0, 1.0])
        pts = np.array(self.parametric_glider.profile_merge_curve.controlpoints) * scale
        pts = list(map(vector3D, pts))
        
        self.dist_controlpoints = ControlPointContainer(self.rm, pts)
        self.dist_curve = Line_old([], color="red", width=2)
        
        self.dist_container.addChild(self.dist_controlpoints)
        self.dist_container.addChild(self.dist_curve.object)
        
        # Fix last point (span end)
        self.dist_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        
        self.dist_controlpoints.on_drag.append(self._on_distribution_drag)
        self.dist_controlpoints.drag_release.append(self._on_distribution_release)
        
        self._update_distribution_curve()
        self._update_distribution_grid()
        self._update_distribution_table()
        
    def _setup_thickness_spline(self):
        """Setup spline control points for thickness with grid"""
        # Offset thickness below distribution
        self.thickness_y_offset = -3.0
        
        scale = np.array([1.0, 1.0])
        pts = np.array(self.parametric_glider.thickness_curve.controlpoints) * scale
        # Offset Y for display
        pts_offset = [[p[0], p[1] + self.thickness_y_offset] for p in pts]
        pts_3d = list(map(vector3D, pts_offset))
        
        self.thickness_controlpoints = ControlPointContainer(self.rm, pts_3d)
        self.thickness_curve_line = Line_old([], color="blue", width=2)
        
        self.thickness_container.addChild(self.thickness_controlpoints)
        self.thickness_container.addChild(self.thickness_curve_line.object)
        
        # Fix last point (span end)
        self.thickness_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        
        self.thickness_controlpoints.on_drag.append(self._on_thickness_drag)
        self.thickness_controlpoints.drag_release.append(self._on_thickness_release)
        
        self._update_thickness_curve()
        self._update_thickness_grid()
        self._update_thickness_table()
        
    def _setup_aoa_spline(self):
        """Setup spline control points for AoA with grid"""
        self.aoa_y_offset = -7.0
        self.aoa_scale = np.array([1.0, 10.0])  # Y scaled ×10 for visibility
        self.aoa_value_scale = 180.0 / np.pi  # radians to degrees
        self.aoa_grid_y_diff = 1.0  # 1 degree grid lines
        
        pts = np.array(self.parametric_glider.aoa.controlpoints) * self.aoa_scale
        # Apply Y offset for display
        pts_offset = [[p[0], p[1] + self.aoa_y_offset] for p in pts]
        pts_3d = list(map(vector3D, pts_offset))
        
        self.aoa_controlpoints = ControlPointContainer(self.rm, pts_3d)
        self.aoa_curve = Line_old([], color="red", width=2)
        self.aoa_absolute_curve = Line_old([], color="blue", width=2)
        
        self.aoa_container.addChild(self.aoa_controlpoints)
        self.aoa_container.addChild(self.aoa_curve.object)
        self.aoa_container.addChild(self.aoa_absolute_curve.object)
        
        # Fix last point (span end)
        self.aoa_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        
        self.aoa_controlpoints.on_drag.append(self._on_aoa_drag)
        self.aoa_controlpoints.drag_release.append(self._on_aoa_release)
        
        # Compute initial aoa_diff values
        self._update_aoa_diff()
        self._update_aoa_curve()
        self._update_aoa_grid()
        self._update_aoa_table()
        
    def _setup_zrot_spline(self):
        """Setup spline control points for Z rotation with grid"""
        self.zrot_y_offset = -10.0
        self.zrot_scale = np.array([1.0, 1.0])
        self.zrot_grid_y_diff = 0.2
        
        pts = np.array(self.parametric_glider.zrot.controlpoints) * self.zrot_scale
        # Apply Y offset for display
        pts_offset = [[p[0], p[1] + self.zrot_y_offset] for p in pts]
        pts_3d = list(map(vector3D, pts_offset))
        
        self.zrot_controlpoints = ControlPointContainer(self.rm, pts_3d)
        self.zrot_curve = Line_old([], color="red", width=2)
        
        self.zrot_container.addChild(self.zrot_controlpoints)
        self.zrot_container.addChild(self.zrot_curve.object)
        
        # Fix last point (span end)
        self.zrot_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        
        self.zrot_controlpoints.on_drag.append(self._on_zrot_drag)
        self.zrot_controlpoints.drag_release.append(self._on_zrot_release)
        
        self._update_zrot_curve()
        self._update_zrot_grid()
        self._update_zrot_table()
        
    def _draw_shape(self):
        """Draw glider shape outline"""
        self.shape.removeAllChildren()
        self.shape.addChild(Line_old(self.front, color="grey").object)
        self.shape.addChild(Line_old(self.back, color="grey").object)
        for rib in self.ribs:
            self.shape.addChild(Line_old(rib, color="grey").object)
            
    def _update_distribution_grid(self):
        """Update grid for distribution spline showing profile indices"""
        self.dist_grid.removeAllChildren()
        self.dist_coords.removeAllChildren()
        
        num_profiles = len(self.parametric_glider.profiles)
        max_x = self.parametric_glider.shape.span
        
        # Create Y grid lines for each profile index (0, 1, 2, ...)
        y_grid = list(range(num_profiles + 1))
        
        # Draw horizontal grid lines
        for y in y_grid:
            line = Line_old([[0, y, -0.001], [max_x, y, -0.001]], color="grey")
            self.dist_grid.addChild(line.object)
        
        # Draw vertical grid lines at rib positions
        for x in self.x_grid:
            line = Line_old([[x, 0, -0.001], [x, num_profiles, -0.001]], color="grey")
            self.dist_grid.addChild(line.object)
        
        # Add Y-axis arrow
        self.dist_coords.addChild(graphics.Arrow([[0, 0, 0], [0, num_profiles + 0.5, 0]]))
        self.dist_coords.addChild(graphics.Arrow([[0, 0, 0], [max_x * 1.1, 0, 0]]))
        
        # Add profile index labels on Y axis
        for i, p in enumerate(self.parametric_glider.profiles):
            textsep = coin.SoSeparator()
            color = coin.SoMaterial()
            color.diffuseColor = [0, 0, 0]
            trans = coin.SoTranslation()
            trans.translation = (-0.5, i, 0.001)
            text = coin.SoText2()
            text.string = str(i)
            textsep += [color, trans, text]
            self.dist_coords.addChild(textsep)
        
        # "Distribution" title label (large)
        textsep = coin.SoSeparator()
        color = coin.SoMaterial()
        color.diffuseColor = [0.8, 0, 0]
        font = coin.SoFont()
        font.size.setValue(18)
        trans = coin.SoTranslation()
        trans.translation = (-3.0, num_profiles + 0.5, 0.001)
        text = coin.SoText2()
        text.string = "Distribution"
        textsep += [color, font, trans, text]
        self.dist_coords.addChild(textsep)
            
    def _update_thickness_grid(self):
        """Update grid for thickness spline"""
        self.thickness_grid.removeAllChildren()
        self.thickness_coords.removeAllChildren()
        
        max_x = self.parametric_glider.shape.span
        y_offset = self.thickness_y_offset
        
        # Draw horizontal grid lines for thickness values (0.5, 1.0, 1.5)
        for y_val in [0.5, 1.0, 1.5]:
            y = y_val + y_offset
            line = Line_old([[0, y, -0.001], [max_x, y, -0.001]], color="grey")
            self.thickness_grid.addChild(line.object)
            
            # Label
            textsep = coin.SoSeparator()
            color = coin.SoMaterial()
            color.diffuseColor = [0, 0, 0.5]
            trans = coin.SoTranslation()
            trans.translation = (-0.8, y, 0.001)
            text = coin.SoText2()
            text.string = str(y_val)
            textsep += [color, trans, text]
            self.thickness_coords.addChild(textsep)
        
        # Draw vertical grid lines at rib positions
        for x in self.x_grid:
            line = Line_old([[x, 0.3 + y_offset, -0.001], [x, 1.7 + y_offset, -0.001]], color="grey")
            self.thickness_grid.addChild(line.object)
        
        # "Thickness" title label (large)
        textsep = coin.SoSeparator()
        color = coin.SoMaterial()
        color.diffuseColor = [0, 0, 0.8]
        font = coin.SoFont()
        font.size.setValue(18)
        trans = coin.SoTranslation()
        trans.translation = (-3.0, 1.6 + y_offset, 0.001)
        text = coin.SoText2()
        text.string = "Thickness"
        textsep += [color, font, trans, text]
        self.thickness_coords.addChild(textsep)
        
    def _update_aoa_grid(self):
        """Update grid for AoA spline showing degree values"""
        self.aoa_grid.removeAllChildren()
        self.aoa_coords.removeAllChildren()
        
        max_x = self.parametric_glider.shape.span
        y_offset = self.aoa_y_offset
        
        # Get current AoA range to determine grid extent
        pts = self.parametric_glider.aoa.get_sequence(num=100)
        if len(pts) > 0:
            max_aoa = max(p[1] for p in pts) * self.aoa_scale[1]
            min_aoa = min(p[1] for p in pts) * self.aoa_scale[1]
        else:
            max_aoa, min_aoa = 1.0, -1.0
        
        # Grid lines in scaled AoA units
        grid_y_diff_scaled = self.aoa_grid_y_diff / self.aoa_value_scale * self.aoa_scale[1]
        if grid_y_diff_scaled < 1e-6:
            grid_y_diff_scaled = 0.1
        
        min_grid = (min(min_aoa, 0) // grid_y_diff_scaled) * grid_y_diff_scaled
        max_grid = ((max_aoa // grid_y_diff_scaled) + 1.5) * grid_y_diff_scaled
        
        y_vals = np.arange(min_grid, max_grid, grid_y_diff_scaled)
        
        # Draw horizontal grid lines
        for y_scaled in y_vals:
            y = y_scaled + y_offset
            line = Line_old([[0, y, -0.001], [max_x, y, -0.001]], color="grey")
            self.aoa_grid.addChild(line.object)
            
            # Degree label
            degree_val = y_scaled / self.aoa_scale[1] * self.aoa_value_scale
            textsep = coin.SoSeparator()
            color = coin.SoMaterial()
            color.diffuseColor = [0.5, 0, 0]
            trans = coin.SoTranslation()
            trans.translation = (-0.8, y, 0.001)
            text = coin.SoText2()
            text.string = "{} °".format(round(degree_val, 1))
            textsep += [color, trans, text]
            self.aoa_coords.addChild(textsep)
        
        # Draw vertical grid lines at rib positions
        for x in self.x_grid:
            line = Line_old([[x, min_grid + y_offset, -0.001], [x, max_grid + y_offset, -0.001]], color="grey")
            self.aoa_grid.addChild(line.object)
        
        # Axes
        self.aoa_coords.addChild(graphics.Arrow([[0, min_grid + y_offset, 0], [0, max_grid + y_offset + grid_y_diff_scaled, 0]]))
        self.aoa_coords.addChild(graphics.Arrow([[0, min_grid + y_offset, 0], [max_x * 1.1, min_grid + y_offset, 0]]))
        
        # "AoA" title label (large)
        textsep = coin.SoSeparator()
        color = coin.SoMaterial()
        color.diffuseColor = [0.8, 0, 0]
        font = coin.SoFont()
        font.size.setValue(18)
        trans = coin.SoTranslation()
        trans.translation = (-3.0, max_grid + y_offset + grid_y_diff_scaled * 0.5, 0.001)
        text = coin.SoText2()
        text.string = "AoA"
        textsep += [color, font, trans, text]
        self.aoa_coords.addChild(textsep)
        
        # Show interpolated AoA values at rib positions
        interpolation = self.parametric_glider.aoa.interpolation(num=100)
        for pt in self.back:
            textsep = coin.SoSeparator()
            color = coin.SoMaterial()
            color.diffuseColor = [0, 0, 0]
            scale_node = coin.SoScale()
            scale_node.scaleFactor = (self.text_scale, self.text_scale, self.text_scale)
            text = coin.SoAsciiText()
            trans = coin.SoTranslation()
            rot = coin.SoRotationXYZ()
            rot.axis = coin.SoRotationXYZ.Z
            rot.angle.setValue(np.pi / 2)
            trans.translation = (pt[0], pt[1], 0.001)
            val_deg = interpolation(pt[0]) * self.aoa_value_scale
            text.string = "{} °".format(round(val_deg, 2))
            textsep += [color, trans, scale_node, rot, text]
            self.aoa_grid.addChild(textsep)
    
    def _update_zrot_grid(self):
        """Update grid for Z rotation spline"""
        self.zrot_grid.removeAllChildren()
        self.zrot_coords.removeAllChildren()
        
        max_x = self.parametric_glider.shape.span
        y_offset = self.zrot_y_offset
        
        # Get current zrot range
        pts = self.parametric_glider.zrot.get_sequence(num=100)
        if len(pts) > 0:
            max_val = max(p[1] for p in pts) * self.zrot_scale[1]
            min_val = min(p[1] for p in pts) * self.zrot_scale[1]
        else:
            max_val, min_val = 0.5, -0.5
        
        grid_y_diff = self.zrot_grid_y_diff
        min_grid = (min(min_val, 0) // grid_y_diff) * grid_y_diff
        max_grid = ((max_val // grid_y_diff) + 1.5) * grid_y_diff
        
        y_vals = np.arange(min_grid, max_grid, grid_y_diff)
        
        # Draw horizontal grid lines
        for y_val in y_vals:
            y = y_val + y_offset
            line = Line_old([[0, y, -0.001], [max_x, y, -0.001]], color="grey")
            self.zrot_grid.addChild(line.object)
            
            # Value label
            textsep = coin.SoSeparator()
            color = coin.SoMaterial()
            color.diffuseColor = [0, 0.5, 0]
            trans = coin.SoTranslation()
            trans.translation = (-0.8, y, 0.001)
            text = coin.SoText2()
            text.string = str(round(y_val, 2))
            textsep += [color, trans, text]
            self.zrot_coords.addChild(textsep)
        
        # Draw vertical grid lines at rib positions
        for x in self.x_grid:
            line = Line_old([[x, min_grid + y_offset, -0.001], [x, max_grid + y_offset, -0.001]], color="grey")
            self.zrot_grid.addChild(line.object)
        
        # Axes
        self.zrot_coords.addChild(graphics.Arrow([[0, min_grid + y_offset, 0], [0, max_grid + y_offset + grid_y_diff, 0]]))
        self.zrot_coords.addChild(graphics.Arrow([[0, min_grid + y_offset, 0], [max_x * 1.1, min_grid + y_offset, 0]]))
        
        # "Z Rotation" title label (large)
        textsep = coin.SoSeparator()
        color = coin.SoMaterial()
        color.diffuseColor = [0, 0.6, 0]
        font = coin.SoFont()
        font.size.setValue(18)
        trans = coin.SoTranslation()
        trans.translation = (-3.0, max_grid + y_offset + grid_y_diff * 0.5, 0.001)
        text = coin.SoText2()
        text.string = "Z Rotation"
        textsep += [color, font, trans, text]
        self.zrot_coords.addChild(textsep)
        
        # Show interpolated values at rib positions
        interpolation = self.parametric_glider.zrot.interpolation(num=100)
        for pt in self.back:
            textsep = coin.SoSeparator()
            color = coin.SoMaterial()
            color.diffuseColor = [0, 0, 0]
            scale_node = coin.SoScale()
            scale_node.scaleFactor = (self.text_scale, self.text_scale, self.text_scale)
            text = coin.SoAsciiText()
            trans = coin.SoTranslation()
            rot = coin.SoRotationXYZ()
            rot.axis = coin.SoRotationXYZ.Z
            rot.angle.setValue(np.pi / 2)
            trans.translation = (pt[0], pt[1], 0.001)
            text.string = str(round(interpolation(pt[0]), 3))
            textsep += [color, trans, scale_node, rot, text]
            self.zrot_grid.addChild(textsep)
            
    def _on_distribution_drag(self):
        """Called when distribution control point is dragged"""
        self._update_distribution_curve()
        
    def _on_distribution_release(self):
        """Called when distribution control point is released"""
        self._update_distribution_curve()
        self._update_distribution_table()
        self.update_view_glider()
        
    def _on_thickness_drag(self):
        """Called when thickness control point is dragged"""
        self._update_thickness_curve()
        
    def _on_thickness_release(self):
        """Called when thickness control point is released"""
        self._update_thickness_curve()
        self._update_thickness_table()
        self.update_view_glider()
    
    def _on_aoa_drag(self):
        """Called when AoA control point is dragged"""
        self._update_aoa_curve()
        
    def _on_aoa_release(self):
        """Called when AoA control point is released"""
        self._update_aoa_curve()
        self._update_aoa_grid()
        self._update_aoa_table()
        self.update_view_glider()
        
    def _on_zrot_drag(self):
        """Called when Zrot control point is dragged"""
        self._update_zrot_curve()
        
    def _on_zrot_release(self):
        """Called when Zrot control point is released"""
        self._update_zrot_curve()
        self._update_zrot_grid()
        self._update_zrot_table()
        self.update_view_glider()
        
    def _update_distribution_curve(self):
        """Update distribution spline from control points"""
        self.parametric_glider.profile_merge_curve.controlpoints = [
            list(p[:-1]) for p in self.dist_controlpoints.control_pos
        ]
        pts = self.parametric_glider.profile_merge_curve.get_sequence(num=100)
        self.dist_curve.update(pts)
        
    def _update_thickness_curve(self):
        """Update thickness spline from control points"""
        # Remove Y offset when storing - control_pos is 3D [x, y, z], we want 2D [x, y-offset]
        pts = [[p[0], p[1] - self.thickness_y_offset] for p in self.thickness_controlpoints.control_pos]
        self.parametric_glider.thickness_curve.controlpoints = pts
        
        # Get curve with offset for display
        curve_pts = self.parametric_glider.thickness_curve.get_sequence(num=100)
        curve_pts_offset = [[p[0], p[1] + self.thickness_y_offset] for p in curve_pts]
        self.thickness_curve_line.update(curve_pts_offset)
    
    def _update_aoa_curve(self):
        """Update AoA spline from control points"""
        # Remove Y offset and scale when storing
        pts = [
            [p[0] / self.aoa_scale[0], (p[1] - self.aoa_y_offset) / self.aoa_scale[1]]
            for p in self.aoa_controlpoints.control_pos
        ]
        self.parametric_glider.aoa.controlpoints = pts
        
        # Get AoA values at rib positions for display
        x_values = self.parametric_glider.shape.rib_x_values
        aoa_values = self.parametric_glider.get_aoa(interpolation_num=self.num_on_drag)
        
        # Red curve: AoA
        self.aoa_curve.update([
            [x * self.aoa_scale[0], aoa * self.aoa_scale[1] + self.aoa_y_offset]
            for x, aoa in zip(x_values, aoa_values)
        ])
        
        # Blue curve: absolute AoA (corrected for arc angle)
        if hasattr(self, 'aoa_absolute_curve') and hasattr(self, '_aoa_diff'):
            self.aoa_absolute_curve.update([
                [x * self.aoa_scale[0], (aoa - aoa_diff) * self.aoa_scale[1] + self.aoa_y_offset]
                for x, aoa, aoa_diff in zip(x_values, aoa_values, self._aoa_diff)
            ])
    
    def _update_zrot_curve(self):
        """Update Zrot spline from control points"""
        # Remove Y offset when storing
        pts = [
            [p[0] / self.zrot_scale[0], (p[1] - self.zrot_y_offset) / self.zrot_scale[1]]
            for p in self.zrot_controlpoints.control_pos
        ]
        self.parametric_glider.zrot.controlpoints = pts
        
        # Get curve for display
        curve_pts = self.parametric_glider.zrot.get_sequence(num=100)
        curve_pts_offset = [
            [p[0] * self.zrot_scale[0], p[1] * self.zrot_scale[1] + self.zrot_y_offset]
            for p in curve_pts
        ]
        self.zrot_curve.update(curve_pts_offset)
    
    def _update_aoa_diff(self):
        """Compute the AoA difference due to arc angle for absolute AoA display"""
        arc_angles = self.parametric_glider.get_arc_angles()
        self._aoa_diff = [
            Rib._aoa_diff(arc_angle, self.parametric_glider.glide)
            for arc_angle in arc_angles
        ]
    
    def _update_glide(self, *args):
        """Update glide number and recompute absolute AoA"""
        self.parametric_glider.glide = self.aoa_glide.value()
        self._update_aoa_diff()
        self._update_aoa_curve()
        self._update_aoa_grid()
        self.update_view_glider()
        
    def _update_distribution_points(self, num):
        """Update number of control points for distribution"""
        self.parametric_glider.profile_merge_curve.numpoints = num
        self.dist_controlpoints.control_pos = np.array(
            self.parametric_glider.profile_merge_curve.controlpoints
        )
        self.dist_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        self._update_distribution_curve()
        self._update_distribution_table()
    
    def _update_aoa_points(self, num):
        """Update number of AoA control points"""
        self.parametric_glider.aoa.numpoints = num
        pts = np.array(self.parametric_glider.aoa.controlpoints) * self.aoa_scale
        pts_offset = [[p[0], p[1] + self.aoa_y_offset] for p in pts]
        self.aoa_controlpoints.control_pos = pts_offset
        self.aoa_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        self._update_aoa_curve()
        self._update_aoa_grid()
        self._update_aoa_table()
    
    def _update_zrot_points(self, num):
        """Update number of Zrot control points"""
        self.parametric_glider.zrot.numpoints = num
        pts = np.array(self.parametric_glider.zrot.controlpoints) * self.zrot_scale
        pts_offset = [[p[0], p[1] + self.zrot_y_offset] for p in pts]
        self.zrot_controlpoints.control_pos = pts_offset
        self.zrot_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        self._update_zrot_curve()
        self._update_zrot_grid()
        self._update_zrot_table()
        
    def _auto_zrot_airflow(self):
        """Set zrot = 1.0 for all control points (align profiles with airflow)"""
        controlpoints = self.parametric_glider.zrot.controlpoints
        new_pts = [[pt[0], 1.0] for pt in controlpoints]
        self.parametric_glider.zrot.controlpoints = new_pts
        
        # Update 3D control points
        pts_scaled = np.array(new_pts) * self.zrot_scale
        pts_offset = [[p[0], p[1] + self.zrot_y_offset] for p in pts_scaled]
        self.zrot_controlpoints.control_pos = pts_offset
        self.zrot_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        
        self._update_zrot_curve()
        self._update_zrot_grid()
        self._update_zrot_table()
        self.update_view_glider()
        
    def _auto_zrot_cfd(self):
        """Compute optimal zrot values using parabem CFD panel method.
        
        Runs a 3D potential flow solver around the glider geometry,
        probes local flow velocity upstream of each rib's leading edge,
        and computes the zrot factor that aligns each rib with the
        actual computed airflow direction.
        """
        try:
            import parabem
            import parabem.pan3d as pan3d
        except ImportError:
            QtGui.QMessageBox.warning(
                None, "parabem not available",
                "parabem is not installed.\n"
                "Install it via pixi or pip to use CFD computation."
            )
            return
        
        from openglider.glider.in_out.export_3d import parabem_Panels
        from openglider.glider.rib.rib import rib_rotation
        
        # Show progress
        self.zrot_cfd_btn.setEnabled(False)
        self.zrot_cfd_btn.setText("Computing...")
        QtGui.QApplication.processEvents()
        
        try:
            # Step 1: Build 3D glider and panel mesh
            glider_3d = self.parametric_glider.get_glider_3d()
            glide = self.parametric_glider.glide
            v_inf = self.parametric_glider.v_inf
            speed = self.parametric_glider.speed
            
            # Mesh parameters
            midribs = 0
            profile_numpoints = 20
            num_average = 5
            farfield = 10
            
            vertices, panels, trailing_edges, _ = parabem_Panels(
                glider_3d,
                midribs=midribs,
                profile_numpoints=profile_numpoints,
                num_average=num_average,
                symmetric=True,
            )
            
            # Step 2: Create and run the panel method case
            case = pan3d.DirichletDoublet0Source0Case3(panels, trailing_edges)
            case.v_inf = parabem.Vector(v_inf)
            case.farfield = farfield
            
            mean_chord = self.parametric_glider.shape.area / self.parametric_glider.shape.span
            wake_length = int(100 * mean_chord)
            case.create_wake(max(wake_length, 100), 10)
            case.run()
            
            # Step 3: Get rib data from the 3D glider
            ribs = glider_3d.ribs
            
            # Step 4: For each rib, compute the local flow and optimal zrot
            zrot_values = []
            debug_lines = []
            
            import FreeCAD
            FreeCAD.Console.PrintMessage(
                f"\n{'='*60}\n"
                f"CFD Zrot Computation\n"
                f"{'='*60}\n"
                f"Glide ratio: {glide:.2f}\n"
                f"Speed: {speed:.2f} m/s\n"
                f"v_inf: [{v_inf[0]:.3f}, {v_inf[1]:.3f}, {v_inf[2]:.3f}]\n"
                f"Panels: {len(panels)}, Vertices: {len(vertices)}\n"
                f"Profile points: {profile_numpoints}, Midribs: {midribs}\n"
                f"Farfield: {farfield}\n"
                f"Mean chord: {mean_chord:.3f} m\n"
                f"{'='*60}\n"
            )
            
            for rib in ribs:
                if rib.pos[1] < 0.001:
                    continue
                
                # Probe point: upstream of the leading edge
                # The leading edge is at rib.align([0, 0, 0])
                le_3d = rib.align([0, 0, 0])
                
                # Offset upstream (against v_inf direction) by one chord length
                v_inf_dir = v_inf / np.linalg.norm(v_inf)
                probe_pos = le_3d - v_inf_dir * mean_chord * 1.0
                
                # Create probe point and compute velocity
                probe = parabem.PanelVector3(
                    float(probe_pos[0]),
                    float(probe_pos[1]),
                    float(probe_pos[2])
                )
                case.off_body_velocity(probe)
                
                # Local flow velocity vector (in global frame)
                v_flow = np.array([probe.velocity.x, probe.velocity.y, probe.velocity.z])
                
                # Get the rib's rotation matrix with zrot=0
                # This gives the frame the rib would have without any Z-correction
                rot_no_zrot = rib_rotation(rib.aoa_absolute, rib.arcang, 0, rib.xrot)
                
                # The rib's local axes in global frame (with zrot=0):
                # "forward" = rib's X axis = chord direction
                rib_x = np.array(rot_no_zrot([1, 0, 0]))
                # "spanwise" = rib's Y axis = span direction  
                rib_y = np.array(rot_no_zrot([0, 1, 0]))
                # "normal" = rib's Z axis = the axis we rotate around
                rib_z = np.array(rot_no_zrot([0, 0, 1]))
                
                # Project velocity into rib's XZ plane (chord-normal plane)
                # The zrot rotation is around the Z-axis of the rib,
                # so we need the angle of the flow in the XY plane of the rib
                v_in_x = np.dot(v_flow, rib_x)
                v_in_y = np.dot(v_flow, rib_y)
                v_in_z = np.dot(v_flow, rib_z)
                
                # The zrot axis is rib_z (from rib_rotation: axis = (rot1*rot2)([0,0,1]))
                # Rotation(-zrot, axis) rotates the rib in the XY plane of the rib's frame
                # So the flow angle that zrot should correct is the angle
                # of the velocity projected into the rib's XY plane,
                # specifically the Y-component relative to X
                # (the "sideslip" angle in the rib's frame)
                
                if abs(v_in_x) > 1e-10:
                    # Flow angle in rib's XY plane
                    # Positive angle = flow has +Y component in rib frame
                    flow_angle = np.arctan2(v_in_y, abs(v_in_x))
                    
                    # The geometric formula: zrot_effective = arctan(arcang) / glide * zrot_factor
                    # The rib_rotation applies Rotation(-zrot_effective, axis)
                    # We want the rib to rotate so its X axis aligns with the flow
                    # in the XY plane. The rotation is -zrot_effective,
                    # so to cancel flow_angle we need: -zrot_effective = -flow_angle
                    # => zrot_effective = flow_angle
                    
                    geom_angle = np.arctan(rib.arcang) / glide if glide > 0 else 0
                    
                    if abs(geom_angle) > 1e-10:
                        zrot_factor = flow_angle / geom_angle
                    else:
                        zrot_factor = 0.0
                else:
                    flow_angle = 0.0
                    geom_angle = 0.0
                    zrot_factor = 0.0
                
                x_pos = rib.pos[1]
                zrot_values.append([x_pos, zrot_factor])
                
                # Debug output
                debug_line = (
                    f"  Rib {rib.name:>12s} | "
                    f"y={x_pos:6.3f} | "
                    f"arc={np.degrees(rib.arcang):+6.2f}° | "
                    f"v_flow=[{v_flow[0]:+.3f},{v_flow[1]:+.3f},{v_flow[2]:+.3f}] | "
                    f"v_rib_xy=[{v_in_x:+.3f},{v_in_y:+.3f}] | "
                    f"flow∠={np.degrees(flow_angle):+6.2f}° | "
                    f"geom∠={np.degrees(geom_angle):+6.2f}° | "
                    f"zrot={zrot_factor:+.4f}"
                )
                debug_lines.append(debug_line)
                FreeCAD.Console.PrintMessage(debug_line + "\n")
            
            if not zrot_values:
                raise RuntimeError("No rib positions found for zrot computation")
            
            FreeCAD.Console.PrintMessage(f"{'='*60}\n")
            
            # Step 5: Interpolate CFD values at control point positions
            from scipy.interpolate import interp1d
            
            cfd_x = np.array([v[0] for v in zrot_values])
            cfd_y = np.array([v[1] for v in zrot_values])
            
            sort_idx = np.argsort(cfd_x)
            cfd_x = cfd_x[sort_idx]
            cfd_y = cfd_y[sort_idx]
            
            current_pts = self.parametric_glider.zrot.controlpoints
            interp_func = interp1d(
                cfd_x, cfd_y,
                kind='linear',
                fill_value='extrapolate',
                bounds_error=False
            )
            
            new_pts = []
            for pt in current_pts:
                new_y = float(interp_func(pt[0]))
                new_pts.append([pt[0], new_y])
            
            # Step 6: Apply the computed zrot values
            self.parametric_glider.zrot.controlpoints = new_pts
            
            pts_scaled = np.array(new_pts) * self.zrot_scale
            pts_offset = [[p[0], p[1] + self.zrot_y_offset] for p in pts_scaled]
            self.zrot_controlpoints.control_pos = pts_offset
            self.zrot_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
            
            self._update_zrot_curve()
            self._update_zrot_grid()
            self._update_zrot_table()
            self.update_view_glider()
            
            # Show results dialog
            result_text = (
                f"<b>CFD Zrot Computation Complete</b><br><br>"
                f"<b>Parameters:</b><br>"
                f"• Glide: {glide:.2f}<br>"
                f"• Speed: {speed:.2f} m/s<br>"
                f"• v_inf: [{v_inf[0]:.3f}, {v_inf[1]:.3f}, {v_inf[2]:.3f}]<br>"
                f"• Panels: {len(panels)}<br>"
                f"• Profile points: {profile_numpoints}<br>"
                f"• Farfield: {farfield}<br><br>"
                f"<b>Results:</b><br>"
                f"• Ribs analyzed: {len(zrot_values)}<br>"
                f"• Zrot range: [{min(v[1] for v in zrot_values):.4f}, "
                f"{max(v[1] for v in zrot_values):.4f}]<br><br>"
                f"<i>See FreeCAD console for per-rib details.</i>"
            )
            QtGui.QMessageBox.information(
                None, "CFD Zrot Results", result_text
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtGui.QMessageBox.warning(
                None, "CFD Computation Error",
                f"Panel method computation failed:\n{str(e)}\n\n"
                "Try the geometric estimation instead."
            )
        finally:
            self.zrot_cfd_btn.setEnabled(True)
            self.zrot_cfd_btn.setText("CFD: Panel Method (parabem)")
        
    def _get_half_span(self):
        """Get half span for normalizing X coordinates to %"""
        controlpoints = self.parametric_glider.profile_merge_curve.controlpoints
        if len(controlpoints) > 0:
            return abs(controlpoints[-1][0])
        return 1.0
    
    # ---- Distribution table ----
    def _update_distribution_table(self):
        """Update distribution control points table with normalized values"""
        controlpoints = self.parametric_glider.profile_merge_curve.controlpoints
        half_span = self._get_half_span()
        
        self.dist_points_table.blockSignals(True)
        self.dist_points_table.setRowCount(len(controlpoints))
        
        for i, pt in enumerate(controlpoints):
            num_item = QtGui.QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~QtCore.Qt.ItemIsEditable)
            num_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.dist_points_table.setItem(i, 0, num_item)
            
            x_pct = (pt[0] / half_span) * 100 if half_span != 0 else 0
            x_item = QtGui.QTableWidgetItem(f"{x_pct:.2f}")
            if i == 0 or i == len(controlpoints) - 1:
                x_item.setFlags(x_item.flags() & ~QtCore.Qt.ItemIsEditable)
                x_item.setBackground(QtGui.QColor(240, 240, 240))
            self.dist_points_table.setItem(i, 1, x_item)
            
            y_item = QtGui.QTableWidgetItem(f"{pt[1]:.4f}")
            self.dist_points_table.setItem(i, 2, y_item)
        
        self.dist_points_table.blockSignals(False)
    
    def _apply_distribution_points(self):
        """Apply edited distribution control points from table"""
        half_span = self._get_half_span()
        new_pts = []
        controlpoints = self.parametric_glider.profile_merge_curve.controlpoints
        
        for i in range(self.dist_points_table.rowCount()):
            x_item = self.dist_points_table.item(i, 1)
            y_item = self.dist_points_table.item(i, 2)
            if x_item and y_item:
                try:
                    x_abs = (float(x_item.text()) / 100) * half_span
                    y_val = float(y_item.text())
                    new_pts.append([x_abs, y_val])
                except ValueError:
                    new_pts.append(list(controlpoints[i]))
        
        self.parametric_glider.profile_merge_curve.controlpoints = new_pts
        self.dist_controlpoints.control_pos = np.array(new_pts)
        self.dist_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        self._update_distribution_curve()
        self._update_distribution_grid()
        self._update_distribution_table()
        self.update_view_glider()
    
    # ---- Thickness table ----
    def _update_thickness_table(self):
        """Update thickness control points table with normalized values"""
        controlpoints = self.parametric_glider.thickness_curve.controlpoints
        half_span = self._get_half_span()
        
        self.thickness_points_table.blockSignals(True)
        self.thickness_points_table.setRowCount(len(controlpoints))
        
        for i, pt in enumerate(controlpoints):
            num_item = QtGui.QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~QtCore.Qt.ItemIsEditable)
            num_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.thickness_points_table.setItem(i, 0, num_item)
            
            x_pct = (pt[0] / half_span) * 100 if half_span != 0 else 0
            x_item = QtGui.QTableWidgetItem(f"{x_pct:.2f}")
            if i == 0 or i == len(controlpoints) - 1:
                x_item.setFlags(x_item.flags() & ~QtCore.Qt.ItemIsEditable)
                x_item.setBackground(QtGui.QColor(240, 240, 240))
            self.thickness_points_table.setItem(i, 1, x_item)
            
            y_item = QtGui.QTableWidgetItem(f"{pt[1]:.4f}")
            self.thickness_points_table.setItem(i, 2, y_item)
        
        self.thickness_points_table.blockSignals(False)
    
    def _apply_thickness_points(self):
        """Apply edited thickness control points from table"""
        half_span = self._get_half_span()
        new_pts = []
        controlpoints = self.parametric_glider.thickness_curve.controlpoints
        
        for i in range(self.thickness_points_table.rowCount()):
            x_item = self.thickness_points_table.item(i, 1)
            y_item = self.thickness_points_table.item(i, 2)
            if x_item and y_item:
                try:
                    x_abs = (float(x_item.text()) / 100) * half_span
                    y_val = float(y_item.text())
                    new_pts.append([x_abs, y_val])
                except ValueError:
                    new_pts.append(list(controlpoints[i]))
        
        self.parametric_glider.thickness_curve.controlpoints = new_pts
        pts_offset = [[p[0], p[1] + self.thickness_y_offset] for p in new_pts]
        self.thickness_controlpoints.control_pos = pts_offset
        self.thickness_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        self._update_thickness_curve()
        self._update_thickness_grid()
        self._update_thickness_table()
        self.update_view_glider()
    
    # ---- AoA table ----
    def _update_aoa_table(self):
        """Update AoA control points table with values in degrees"""
        controlpoints = self.parametric_glider.aoa.controlpoints
        half_span = self._get_half_span()
        
        self.aoa_points_table.blockSignals(True)
        self.aoa_points_table.setRowCount(len(controlpoints))
        
        for i, pt in enumerate(controlpoints):
            num_item = QtGui.QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~QtCore.Qt.ItemIsEditable)
            num_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.aoa_points_table.setItem(i, 0, num_item)
            
            x_pct = (pt[0] / half_span) * 100 if half_span != 0 else 0
            x_item = QtGui.QTableWidgetItem(f"{x_pct:.2f}")
            if i == 0 or i == len(controlpoints) - 1:
                x_item.setFlags(x_item.flags() & ~QtCore.Qt.ItemIsEditable)
                x_item.setBackground(QtGui.QColor(240, 240, 240))
            self.aoa_points_table.setItem(i, 1, x_item)
            
            # Y value in degrees (stored in radians internally)
            y_deg = pt[1] * 180.0 / np.pi
            y_item = QtGui.QTableWidgetItem(f"{y_deg:.2f}")
            self.aoa_points_table.setItem(i, 2, y_item)
        
        self.aoa_points_table.blockSignals(False)
    
    def _apply_aoa_points(self):
        """Apply edited AoA control points from table (degrees → radians)"""
        half_span = self._get_half_span()
        new_pts = []
        controlpoints = self.parametric_glider.aoa.controlpoints
        
        for i in range(self.aoa_points_table.rowCount()):
            x_item = self.aoa_points_table.item(i, 1)
            y_item = self.aoa_points_table.item(i, 2)
            if x_item and y_item:
                try:
                    x_abs = (float(x_item.text()) / 100) * half_span
                    y_rad = float(y_item.text()) * np.pi / 180.0
                    new_pts.append([x_abs, y_rad])
                except ValueError:
                    new_pts.append(list(controlpoints[i]))
        
        self.parametric_glider.aoa.controlpoints = new_pts
        pts_scaled = np.array(new_pts) * self.aoa_scale
        pts_offset = [[p[0], p[1] + self.aoa_y_offset] for p in pts_scaled]
        self.aoa_controlpoints.control_pos = pts_offset
        self.aoa_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        self._update_aoa_diff()
        self._update_aoa_curve()
        self._update_aoa_grid()
        self._update_aoa_table()
        self.update_view_glider()
    
    # ---- Zrot table ----
    def _update_zrot_table(self):
        """Update Z rotation control points table"""
        controlpoints = self.parametric_glider.zrot.controlpoints
        half_span = self._get_half_span()
        
        self.zrot_points_table.blockSignals(True)
        self.zrot_points_table.setRowCount(len(controlpoints))
        
        for i, pt in enumerate(controlpoints):
            num_item = QtGui.QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~QtCore.Qt.ItemIsEditable)
            num_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.zrot_points_table.setItem(i, 0, num_item)
            
            x_pct = (pt[0] / half_span) * 100 if half_span != 0 else 0
            x_item = QtGui.QTableWidgetItem(f"{x_pct:.2f}")
            if i == 0 or i == len(controlpoints) - 1:
                x_item.setFlags(x_item.flags() & ~QtCore.Qt.ItemIsEditable)
                x_item.setBackground(QtGui.QColor(240, 240, 240))
            self.zrot_points_table.setItem(i, 1, x_item)
            
            y_item = QtGui.QTableWidgetItem(f"{pt[1]:.4f}")
            self.zrot_points_table.setItem(i, 2, y_item)
        
        self.zrot_points_table.blockSignals(False)
    
    def _apply_zrot_points(self):
        """Apply edited Z rotation control points from table"""
        half_span = self._get_half_span()
        new_pts = []
        controlpoints = self.parametric_glider.zrot.controlpoints
        
        for i in range(self.zrot_points_table.rowCount()):
            x_item = self.zrot_points_table.item(i, 1)
            y_item = self.zrot_points_table.item(i, 2)
            if x_item and y_item:
                try:
                    x_abs = (float(x_item.text()) / 100) * half_span
                    y_val = float(y_item.text())
                    new_pts.append([x_abs, y_val])
                except ValueError:
                    new_pts.append(list(controlpoints[i]))
        
        self.parametric_glider.zrot.controlpoints = new_pts
        pts_scaled = np.array(new_pts) * self.zrot_scale
        pts_offset = [[p[0], p[1] + self.zrot_y_offset] for p in pts_scaled]
        self.zrot_controlpoints.control_pos = pts_offset
        self.zrot_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
        self._update_zrot_curve()
        self._update_zrot_grid()
        self._update_zrot_table()
        self.update_view_glider()
        
    def _update_overrides(self, *args):
        """Update profile overrides from table"""
        self.parametric_glider.profile_overrides_enabled = self.overrides_enabled.isChecked()
        
        overrides = {}
        for i in range(self.override_table.rowCount()):
            combo = self.override_table.cellWidget(i, 2)
            if combo and combo.currentIndex() > 0:
                overrides[str(i)] = combo.currentIndex() - 1
        
        self.parametric_glider.profile_overrides = overrides
        self.update_view_glider()
        
    def _update_sharknose(self, *args):
        """Update shark nose parameters and cell selection"""
        self.parametric_glider.sharknose_enabled = self.sharknose_enabled.isChecked()
        self.parametric_glider.sharknose_x1 = self.sharknose_x1.value()
        self.parametric_glider.sharknose_x2 = self.sharknose_x2.value()
        self.parametric_glider.sharknose_x3 = self.sharknose_x3.value()
        self.parametric_glider.sharknose_y_max = self.sharknose_y_max.value()
        
        # Update cell selection
        selected_cells = []
        for i, cb in enumerate(self.sharknose_cell_checkboxes):
            if cb.isChecked():
                selected_cells.append(i)
        self.parametric_glider.sharknose_cells = selected_cells
        
        self.update_view_glider()
        
    def _select_all_sharknose_cells(self):
        """Select all cells for shark nose"""
        for cb in self.sharknose_cell_checkboxes:
            cb.setChecked(True)
            
    def _select_no_sharknose_cells(self):
        """Deselect all cells for shark nose"""
        for cb in self.sharknose_cell_checkboxes:
            cb.setChecked(False)
        
    def _update_thickness(self, *args):
        """Update thickness curve enabled state"""
        self.parametric_glider.thickness_curve_enabled = self.thickness_enabled.isChecked()
        self.update_view_glider()
        
    def _update_thickness_points(self, num):
        """Update number of thickness control points"""
        if hasattr(self.parametric_glider, 'thickness_curve') and self.parametric_glider.thickness_curve:
            self.parametric_glider.thickness_curve.numpoints = num
            pts = np.array(self.parametric_glider.thickness_curve.controlpoints)
            pts_offset = [[p[0], p[1] + self.thickness_y_offset] for p in pts]
            self.thickness_controlpoints.control_pos = pts_offset
            self.thickness_controlpoints.control_points[-1].constrained = [0.0, 1.0, 0.0]
            self._update_thickness_curve()
            self._update_thickness_table()
            
    def _update_last_airfoil(self, *args):
        """Update last airfoil parameters"""
        # Determine the selected type
        if self.last_airfoil_line.isChecked():
            profile_type = 'line'
        elif self.last_airfoil_thin.isChecked():
            profile_type = 'thin'
        else:
            profile_type = 'custom'
        
        # Auto-enable when user selects thin or custom (not line)
        # If they select line, respect the checkbox state
        is_enabled = self.last_airfoil_enabled.isChecked()
        if profile_type in ('thin', 'custom') and not is_enabled:
            # Auto-enable
            self.last_airfoil_enabled.setChecked(True)
            is_enabled = True
        
        self.parametric_glider.last_profile_enabled = is_enabled
        self.parametric_glider.last_profile_type = profile_type
        self.parametric_glider.last_profile_thickness = self.last_airfoil_thickness.value()
        
        print(f"[DEBUG UI] _update_last_airfoil: enabled={is_enabled}, type={profile_type}, thickness={self.last_airfoil_thickness.value()}")
        
        self.update_view_glider()
        
    def _import_last_profile(self):
        """Import custom last rib profile from .dat file"""
        filename, _ = QtGui.QFileDialog.getOpenFileName(
            self.base_widget,
            "Import Last Airfoil Profile",
            "",
            "DAT files (*.dat);;All files (*.*)"
        )
        if filename:
            try:
                profile = Profile2D.import_from_dat(filename)
                self.parametric_glider.last_profile_custom = profile
                self.last_airfoil_custom.setChecked(True)
                self.update_view_glider()
                QtGui.QMessageBox.information(
                    self.base_widget,
                    "Success",
                    "Imported last airfoil profile: {}".format(profile.name)
                )
            except Exception as e:
                QtGui.QMessageBox.warning(
                    self.base_widget,
                    "Import Error",
                    "Failed to import profile: {}".format(str(e))
                )
                
    def accept(self):
        """Accept changes and close"""
        if hasattr(self, 'dist_controlpoints'):
            self.dist_controlpoints.remove_callbacks()
        if hasattr(self, 'thickness_controlpoints'):
            self.thickness_controlpoints.remove_callbacks()
        if hasattr(self, 'aoa_controlpoints'):
            self.aoa_controlpoints.remove_callbacks()
        if hasattr(self, 'zrot_controlpoints'):
            self.zrot_controlpoints.remove_callbacks()
        super(AirfoilControlTool, self).accept()
        self.update_view_glider()
        
    def reject(self):
        """Cancel changes and close"""
        if hasattr(self, 'dist_controlpoints'):
            self.dist_controlpoints.remove_callbacks()
        if hasattr(self, 'thickness_controlpoints'):
            self.thickness_controlpoints.remove_callbacks()
        if hasattr(self, 'aoa_controlpoints'):
            self.aoa_controlpoints.remove_callbacks()
        if hasattr(self, 'zrot_controlpoints'):
            self.zrot_controlpoints.remove_callbacks()
        super(AirfoilControlTool, self).reject()


# Keep old name for backwards compatibility
ProfileControlTool = AirfoilControlTool
