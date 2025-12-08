"""
Lines Auto-Placement Dialog for OpenGlider

This dialog allows users to automatically generate suspension line attachment points
and line architecture based on configurable parameters.
"""

from __future__ import division

import numpy as np
from PySide import QtCore, QtGui

from openglider.glider.parametric.lines import (
    BatchNode2D,
    Line2D,
    LineSet2D,
    LowerNode2D,
    UpperNode2D,
)
from openglider.lines.line_types import LineType


class LineTypeRow(QtGui.QWidget):
    """Widget for configuring a single line type (A, B, C, D, F)."""
    
    def __init__(self, line_type_name, default_position, parent=None):
        super(LineTypeRow, self).__init__(parent)
        self.line_type_name = line_type_name
        
        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Enable checkbox
        self.enable_checkbox = QtGui.QCheckBox(line_type_name)
        self.enable_checkbox.setChecked(True)
        self.enable_checkbox.setFixedWidth(50)
        layout.addWidget(self.enable_checkbox)
        
        # Position (%)
        layout.addWidget(QtGui.QLabel("Pos %:"))
        self.position_spinbox = QtGui.QDoubleSpinBox()
        self.position_spinbox.setRange(0, 100)
        self.position_spinbox.setValue(default_position)
        self.position_spinbox.setDecimals(1)
        self.position_spinbox.setSingleStep(0.5)
        self.position_spinbox.setFixedWidth(70)
        layout.addWidget(self.position_spinbox)
        
        # Every X cells
        layout.addWidget(QtGui.QLabel("Every:"))
        self.interval_spinbox = QtGui.QSpinBox()
        self.interval_spinbox.setRange(1, 10)
        self.interval_spinbox.setValue(1)
        self.interval_spinbox.setFixedWidth(50)
        layout.addWidget(self.interval_spinbox)
        
        # Start cell
        layout.addWidget(QtGui.QLabel("Start:"))
        self.start_spinbox = QtGui.QSpinBox()
        self.start_spinbox.setRange(0, 50)
        self.start_spinbox.setValue(0)
        self.start_spinbox.setFixedWidth(50)
        layout.addWidget(self.start_spinbox)
        
        # Connect enable checkbox to enable/disable other controls
        self.enable_checkbox.toggled.connect(self._update_enabled_state)
        
    def _update_enabled_state(self, enabled):
        self.position_spinbox.setEnabled(enabled)
        self.interval_spinbox.setEnabled(enabled)
        self.start_spinbox.setEnabled(enabled)
    
    def is_enabled(self):
        return self.enable_checkbox.isChecked()
    
    def get_config(self):
        return {
            "enabled": self.is_enabled(),
            "position": self.position_spinbox.value() / 100.0,  # Convert to 0-1
            "interval": self.interval_spinbox.value(),
            "start_cell": self.start_spinbox.value(),
        }


class LinesAutoPlacementDialog(QtGui.QDialog):
    """Dialog for automatic placement of suspension lines."""
    
    # Default positions for each line type (in %)
    DEFAULT_POSITIONS = {
        "A": 8.5,
        "B": 27.5,
        "C": 53.0,
        "D": 77.0,
        "F": 100.0,
    }
    
    def __init__(self, parametric_glider, parent=None):
        super(LinesAutoPlacementDialog, self).__init__(parent)
        self.parametric_glider = parametric_glider
        self.half_cell_num = parametric_glider.shape.half_cell_num
        
        self.setWindowTitle("Auto-placement des suspentes")
        self.setMinimumWidth(500)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QtGui.QVBoxLayout(self)
        
        # === General Section ===
        general_group = QtGui.QGroupBox("Général")
        general_layout = QtGui.QFormLayout(general_group)
        
        # Number of line rows
        self.num_rows_combo = QtGui.QComboBox()
        self.num_rows_combo.addItems(["2 lignes", "3 lignes", "4 lignes"])
        self.num_rows_combo.setCurrentIndex(1)  # Default: 3 lines
        general_layout.addRow("Nombre de rangées:", self.num_rows_combo)
        
        main_layout.addWidget(general_group)
        
        # === Lower Attachment Point ===
        lower_group = QtGui.QGroupBox("Point d'attache inférieur (élévateur)")
        lower_layout = QtGui.QFormLayout(lower_group)
        
        # Position X, Y, Z
        pos_widget = QtGui.QWidget()
        pos_layout = QtGui.QHBoxLayout(pos_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lower_x = QtGui.QDoubleSpinBox()
        self.lower_x.setRange(-50, 50)
        self.lower_x.setValue(0)
        self.lower_x.setDecimals(2)
        pos_layout.addWidget(QtGui.QLabel("X:"))
        pos_layout.addWidget(self.lower_x)
        
        self.lower_y = QtGui.QDoubleSpinBox()
        self.lower_y.setRange(-50, 50)
        self.lower_y.setValue(0)
        self.lower_y.setDecimals(2)
        pos_layout.addWidget(QtGui.QLabel("Y:"))
        pos_layout.addWidget(self.lower_y)
        
        self.lower_z = QtGui.QDoubleSpinBox()
        self.lower_z.setRange(-50, 50)
        self.lower_z.setValue(-8)  # Default: 8m below
        self.lower_z.setDecimals(2)
        pos_layout.addWidget(QtGui.QLabel("Z:"))
        pos_layout.addWidget(self.lower_z)
        
        lower_layout.addRow("Position 3D:", pos_widget)
        
        main_layout.addWidget(lower_group)
        
        # === Line Types Configuration ===
        lines_group = QtGui.QGroupBox("Configuration des suspentes")
        lines_layout = QtGui.QVBoxLayout(lines_group)
        
        # Header
        header = QtGui.QLabel("Type | Position (%) | Intervalle (cells) | Cellule départ")
        header.setStyleSheet("font-weight: bold; color: gray;")
        lines_layout.addWidget(header)
        
        # Line type rows
        self.line_type_rows = {}
        for line_type, default_pos in self.DEFAULT_POSITIONS.items():
            row = LineTypeRow(line_type, default_pos)
            self.line_type_rows[line_type] = row
            lines_layout.addWidget(row)
            
            # Set default intervals (A every 1, B every 2, etc.)
            if line_type == "A":
                row.interval_spinbox.setValue(1)
            elif line_type in ("B", "C"):
                row.interval_spinbox.setValue(2)
            elif line_type == "D":
                row.interval_spinbox.setValue(3)
            elif line_type == "F":
                row.interval_spinbox.setValue(1)
        
        main_layout.addWidget(lines_group)
        
        # === Architecture Section ===
        arch_group = QtGui.QGroupBox("Architecture des suspentes")
        arch_layout = QtGui.QFormLayout(arch_group)
        
        # Merge pattern
        self.merge_pattern_combo = QtGui.QComboBox()
        self.merge_pattern_combo.addItems([
            "1:1 (pas de fusion)",
            "2:1 (fusion par 2)",
            "3:1 (fusion par 3)",
            "4:1 (fusion par 4)",
        ])
        self.merge_pattern_combo.setCurrentIndex(1)  # Default: 2:1
        arch_layout.addRow("Pattern de fusion:", self.merge_pattern_combo)
        
        # Number of levels
        self.num_levels_spinbox = QtGui.QSpinBox()
        self.num_levels_spinbox.setRange(1, 4)
        self.num_levels_spinbox.setValue(2)
        arch_layout.addRow("Nombre de niveaux:", self.num_levels_spinbox)
        
        main_layout.addWidget(arch_group)
        
        # === Line Type Selection ===
        linetype_group = QtGui.QGroupBox("Type de suspente")
        linetype_layout = QtGui.QFormLayout(linetype_group)
        
        self.line_type_combo = QtGui.QComboBox()
        for line_type in sorted(LineType.types.keys()):
            self.line_type_combo.addItem(line_type)
        # Try to select "default" if available
        default_idx = self.line_type_combo.findText("default")
        if default_idx >= 0:
            self.line_type_combo.setCurrentIndex(default_idx)
        linetype_layout.addRow("Type de ligne:", self.line_type_combo)
        
        main_layout.addWidget(linetype_group)
        
        # === Buttons ===
        button_layout = QtGui.QHBoxLayout()
        
        self.preview_button = QtGui.QPushButton("Aperçu")
        self.preview_button.clicked.connect(self.preview)
        button_layout.addWidget(self.preview_button)
        
        button_layout.addStretch()
        
        self.cancel_button = QtGui.QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.apply_button = QtGui.QPushButton("Appliquer")
        self.apply_button.clicked.connect(self.accept)
        self.apply_button.setDefault(True)
        button_layout.addWidget(self.apply_button)
        
        main_layout.addLayout(button_layout)
        
        # Info label
        self.info_label = QtGui.QLabel("")
        self.info_label.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(self.info_label)
        
        self._update_info()
        
    def _update_info(self):
        """Update the info label with current configuration summary."""
        count = self._count_attachment_points()
        self.info_label.setText(f"Points d'attache estimés: {count}")
        
    def _count_attachment_points(self):
        """Count how many attachment points will be generated."""
        count = 0
        for line_type, row in self.line_type_rows.items():
            if row.is_enabled():
                config = row.get_config()
                start = config["start_cell"]
                interval = config["interval"]
                for cell_no in range(start, self.half_cell_num, interval):
                    count += 1
        return count
    
    def preview(self):
        """Show preview of the configuration."""
        count = self._count_attachment_points()
        QtGui.QMessageBox.information(
            self,
            "Aperçu",
            f"Cette configuration générera:\n"
            f"- {count} points d'attache supérieurs\n"
            f"- 1 point d'attache inférieur\n"
            f"- Architecture: {self.merge_pattern_combo.currentText()}\n"
            f"- Niveaux: {self.num_levels_spinbox.value()}"
        )
    
    def get_configuration(self):
        """Return the complete configuration as a dictionary."""
        return {
            "num_rows": self.num_rows_combo.currentIndex() + 2,  # 2, 3, or 4
            "lower_position": [
                self.lower_x.value(),
                self.lower_y.value(),
                self.lower_z.value(),
            ],
            "line_types": {
                lt: row.get_config() 
                for lt, row in self.line_type_rows.items()
            },
            "merge_pattern": self.merge_pattern_combo.currentIndex(),  # 0=1:1, 1=2:1, etc.
            "num_levels": self.num_levels_spinbox.value(),
            "line_type_name": self.line_type_combo.currentText(),
        }
    
    def generate_lineset(self):
        """Generate LineSet2D based on the current configuration."""
        config = self.get_configuration()
        
        lines = []
        all_upper_nodes = {}  # {line_type: [nodes]}
        
        # Generate upper nodes for each enabled line type
        for line_type, lt_config in config["line_types"].items():
            if lt_config["enabled"]:
                nodes = self._generate_upper_nodes(line_type, lt_config)
                all_upper_nodes[line_type] = nodes
        
        # Generate lower node(s)
        lower_nodes = self._generate_lower_nodes(config["lower_position"])
        
        # Generate line architecture for each line type group
        for line_type, upper_nodes in all_upper_nodes.items():
            if upper_nodes:
                type_lines = self._generate_architecture(
                    upper_nodes,
                    lower_nodes[0],  # Use first lower node
                    config["merge_pattern"],
                    config["num_levels"],
                    config["line_type_name"],
                    line_type,
                )
                lines.extend(type_lines)
        
        return LineSet2D(lines)
    
    def _generate_upper_nodes(self, line_type, config):
        """Generate UpperNode2D attachment points for a line type."""
        nodes = []
        start = config["start_cell"]
        interval = config["interval"]
        position = config["position"]
        
        index = 1
        for cell_no in range(start, self.half_cell_num, interval):
            node = UpperNode2D(
                cell_no=cell_no,
                rib_pos=position,
                cell_pos=0,  # On the rib
                force=1.0,
                name=f"{line_type}{index}",
                layer=line_type,
            )
            nodes.append(node)
            index += 1
        
        return nodes
    
    def _generate_lower_nodes(self, position):
        """Generate LowerNode2D for harness attachment."""
        node = LowerNode2D(
            pos_2D=[position[0], position[2]],  # x, z for 2D view
            pos_3D=position,
            name="main",
            layer="",
        )
        return [node]
    
    def _generate_architecture(self, upper_nodes, lower_node, merge_pattern, 
                               num_levels, line_type_name, layer):
        """
        Generate line architecture connecting upper nodes to lower node.
        
        merge_pattern: 0=1:1, 1=2:1, 2=3:1, 3=4:1
        num_levels: number of intermediate levels
        """
        lines = []
        merge_factor = merge_pattern + 1  # 1, 2, 3, or 4
        
        if merge_factor == 1 or len(upper_nodes) <= 1:
            # Direct connection, no merging
            for node in upper_nodes:
                line = Line2D(
                    lower_node=lower_node,
                    upper_node=node,
                    target_length=None,  # Will be calculated
                    line_type=line_type_name,
                    layer=layer,
                    name=node.name,
                )
                lines.append(line)
            return lines
        
        # Multi-level architecture with merging
        current_level_nodes = list(upper_nodes)
        level = 0
        
        while len(current_level_nodes) > 1 and level < num_levels:
            next_level_nodes = []
            
            # Group nodes by merge_factor
            for i in range(0, len(current_level_nodes), merge_factor):
                group = current_level_nodes[i:i + merge_factor]
                
                if len(group) == 1 or level == num_levels - 1:
                    # Last level or single node: connect to lower
                    for node in group:
                        line = Line2D(
                            lower_node=lower_node,
                            upper_node=node,
                            target_length=None,
                            line_type=line_type_name,
                            layer=layer,
                            name=f"{layer}_l{level}_{i}",
                        )
                        lines.append(line)
                else:
                    # Create intermediate batch node
                    # Position it between the group members
                    if isinstance(group[0], UpperNode2D):
                        avg_cell = sum(n.cell_no for n in group) / len(group)
                        avg_pos = sum(n.rib_pos for n in group) / len(group)
                        # Get 2D position from shape
                        pos_2d = self.parametric_glider.shape[avg_cell, avg_pos]
                    else:
                        # Batch node - average positions
                        pos_2d = [
                            sum(n.pos_2D[0] for n in group) / len(group),
                            sum(n.pos_2D[1] for n in group) / len(group),
                        ]
                    
                    # Move down for each level
                    pos_2d = [pos_2d[0], pos_2d[1] - (level + 1) * 1.5]
                    
                    batch_node = BatchNode2D(
                        pos_2D=list(pos_2d),
                        name=f"{layer}_b{level}_{i // merge_factor}",
                        layer=layer,
                    )
                    
                    # Connect group to batch node
                    for j, node in enumerate(group):
                        line = Line2D(
                            lower_node=batch_node,
                            upper_node=node,
                            target_length=None,
                            line_type=line_type_name,
                            layer=layer,
                            name=f"{layer}_l{level}_{i + j}",
                        )
                        lines.append(line)
                    
                    next_level_nodes.append(batch_node)
            
            current_level_nodes = next_level_nodes
            level += 1
        
        # Connect remaining nodes to lower
        for i, node in enumerate(current_level_nodes):
            line = Line2D(
                lower_node=lower_node,
                upper_node=node,
                target_length=None,
                line_type=line_type_name,
                layer=layer,
                name=f"{layer}_main_{i}",
            )
            lines.append(line)
        
        return lines
