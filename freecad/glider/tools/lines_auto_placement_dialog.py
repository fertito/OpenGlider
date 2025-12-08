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
    
    configChanged = QtCore.Signal()
    
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
        self.enable_checkbox.toggled.connect(lambda: self.configChanged.emit())
        self.position_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        self.interval_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        self.start_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        
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
    
    # Predefined architecture patterns
    ARCHITECTURE_PATTERNS = [
        ("Direct (1:1)", [1]),
        ("2:1", [2]),
        ("3:1", [3]),
        ("2:2:1", [2, 2]),
        ("3:2:1", [3, 2]),
        ("4:2:1", [4, 2]),
        ("2:2:2:1", [2, 2, 2]),
    ]
    
    def __init__(self, parametric_glider, parent=None):
        super(LinesAutoPlacementDialog, self).__init__(parent)
        self.parametric_glider = parametric_glider
        self.half_cell_num = parametric_glider.shape.half_cell_num
        
        self.setWindowTitle("Auto-placement des suspentes")
        self.setMinimumWidth(550)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QtGui.QVBoxLayout(self)
        
        # === General Section ===
        general_group = QtGui.QGroupBox("Général")
        general_layout = QtGui.QFormLayout(general_group)
        
        # Info about cells
        info_label = QtGui.QLabel(f"Demi-voile: {self.half_cell_num} cellules")
        info_label.setStyleSheet("color: gray;")
        general_layout.addRow("", info_label)
        
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
            row.configChanged.connect(self._update_info)
            
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
        
        # === Stabilo Section ===
        stabilo_group = QtGui.QGroupBox("Stabilo (bout d'aile)")
        stabilo_layout = QtGui.QFormLayout(stabilo_group)
        
        self.stabilo_checkbox = QtGui.QCheckBox("Inclure stabilo")
        self.stabilo_checkbox.setChecked(True)
        stabilo_layout.addRow("", self.stabilo_checkbox)
        
        self.stabilo_position = QtGui.QDoubleSpinBox()
        self.stabilo_position.setRange(0, 100)
        self.stabilo_position.setValue(50)
        self.stabilo_position.setSuffix(" %")
        stabilo_layout.addRow("Position sur corde:", self.stabilo_position)
        
        main_layout.addWidget(stabilo_group)
        
        # === Architecture Section ===
        arch_group = QtGui.QGroupBox("Architecture des suspentes")
        arch_layout = QtGui.QFormLayout(arch_group)
        
        # Predefined architecture patterns
        self.arch_pattern_combo = QtGui.QComboBox()
        for name, _ in self.ARCHITECTURE_PATTERNS:
            self.arch_pattern_combo.addItem(name)
        self.arch_pattern_combo.setCurrentIndex(3)  # Default: 2:2:1
        arch_layout.addRow("Pattern:", self.arch_pattern_combo)
        
        # Custom pattern input
        self.custom_pattern_edit = QtGui.QLineEdit()
        self.custom_pattern_edit.setPlaceholderText("ex: 2,2,1 ou 3,2")
        self.custom_pattern_edit.setEnabled(False)
        arch_layout.addRow("Pattern custom:", self.custom_pattern_edit)
        
        # Use custom checkbox
        self.use_custom_checkbox = QtGui.QCheckBox("Utiliser pattern custom")
        self.use_custom_checkbox.toggled.connect(self._toggle_custom_pattern)
        arch_layout.addRow("", self.use_custom_checkbox)
        
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
    
    def _toggle_custom_pattern(self, enabled):
        self.custom_pattern_edit.setEnabled(enabled)
        self.arch_pattern_combo.setEnabled(not enabled)
        
    def _update_info(self):
        """Update the info label with current configuration summary."""
        if not hasattr(self, 'info_label'):
            return
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
        # Add stabilo if enabled (check if attribute exists first)
        if hasattr(self, 'stabilo_checkbox') and self.stabilo_checkbox.isChecked():
            count += 1
        return count
    
    def _get_architecture_pattern(self):
        """Get the architecture pattern as a list of merge factors."""
        if self.use_custom_checkbox.isChecked():
            try:
                pattern_str = self.custom_pattern_edit.text().strip()
                pattern = [int(x.strip()) for x in pattern_str.split(",") if x.strip()]
                return pattern if pattern else [1]
            except ValueError:
                return [1]
        else:
            idx = self.arch_pattern_combo.currentIndex()
            return self.ARCHITECTURE_PATTERNS[idx][1]
    
    def preview(self):
        """Show preview of the configuration."""
        count = self._count_attachment_points()
        pattern = self._get_architecture_pattern()
        pattern_str = ":".join(str(p) for p in pattern) + ":1"
        
        QtGui.QMessageBox.information(
            self,
            "Aperçu",
            f"Cette configuration générera:\n"
            f"- {count} points d'attache supérieurs\n"
            f"- 1 point d'attache inférieur\n"
            f"- Architecture: {pattern_str}\n"
            f"- Stabilo: {'Oui' if self.stabilo_checkbox.isChecked() else 'Non'}"
        )
    
    def get_configuration(self):
        """Return the complete configuration as a dictionary."""
        return {
            "lower_position": [
                self.lower_x.value(),
                self.lower_y.value(),
                self.lower_z.value(),
            ],
            "line_types": {
                lt: row.get_config() 
                for lt, row in self.line_type_rows.items()
            },
            "architecture_pattern": self._get_architecture_pattern(),
            "line_type_name": self.line_type_combo.currentText(),
            "include_stabilo": self.stabilo_checkbox.isChecked(),
            "stabilo_position": self.stabilo_position.value() / 100.0,
        }
    
    def generate_lineset(self):
        """Generate LineSet2D based on the current configuration."""
        config = self.get_configuration()
        
        lines = []
        all_upper_nodes = {}  # {line_type: [nodes]}
        
        # Generate upper nodes for each enabled line type
        for line_type in ["A", "B", "C", "D", "F"]:  # Ordered
            lt_config = config["line_types"].get(line_type)
            if lt_config and lt_config["enabled"]:
                nodes = self._generate_upper_nodes(line_type, lt_config)
                if nodes:
                    all_upper_nodes[line_type] = nodes
        
        # Generate stabilo node if enabled
        stabilo_node = None
        if config["include_stabilo"]:
            stabilo_node = self._generate_stabilo_node(config["stabilo_position"])
        
        # Generate lower node(s) - one per line type group
        lower_nodes = {}
        for line_type in all_upper_nodes.keys():
            lower_nodes[line_type] = self._generate_lower_node(
                config["lower_position"], 
                line_type
            )
        
        # Also add a lower node for stabilo
        if stabilo_node:
            lower_nodes["S"] = self._generate_lower_node(
                config["lower_position"],
                "S"
            )
        
        # Generate line architecture for each line type group
        for line_type, upper_nodes in all_upper_nodes.items():
            if upper_nodes:
                lower_node = lower_nodes[line_type]
                type_lines = self._generate_architecture(
                    upper_nodes,
                    lower_node,
                    config["architecture_pattern"],
                    config["line_type_name"],
                    line_type,
                )
                lines.extend(type_lines)
        
        # Generate stabilo lines (direct connection)
        if stabilo_node:
            lower_node = lower_nodes["S"]
            stabilo_line = Line2D(
                lower_node=lower_node,
                upper_node=stabilo_node,
                target_length=1.0,  # Default length, will be recalculated
                line_type=config["line_type_name"],
                layer="S",
                name="S1",
            )
            lines.append(stabilo_line)
        
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
    
    def _generate_stabilo_node(self, rib_pos):
        """Generate UpperNode2D for stabilo (wing tip)."""
        # Stabilo is on the last rib (half_cell_num - 1 with cell_pos=1, 
        # or equivalently the tip rib)
        cell_no = self.half_cell_num - 1
        
        node = UpperNode2D(
            cell_no=cell_no,
            rib_pos=rib_pos,
            cell_pos=1,  # On the outer rib of the last cell (tip)
            force=1.0,
            name="S1",
            layer="S",
        )
        return node
    
    def _generate_lower_node(self, position, line_type):
        """Generate LowerNode2D for harness attachment."""
        # Offset the 2D position based on line type for visual separation
        type_offsets = {"A": -2, "B": -1, "C": 0, "D": 1, "F": 2, "S": 3}
        offset = type_offsets.get(line_type, 0) * 0.5
        
        node = LowerNode2D(
            pos_2D=[position[0] + offset, position[2]],  # x, z for 2D view
            pos_3D=[position[0] + offset, position[1], position[2]],
            name=f"lower_{line_type}",
            layer=line_type,
        )
        return node
    
    def _generate_architecture(self, upper_nodes, lower_node, pattern, 
                               line_type_name, layer):
        """
        Generate line architecture connecting upper nodes to lower node.
        
        pattern: list of merge factors, e.g., [2, 2] for 2:2:1
        """
        lines = []
        
        if not upper_nodes:
            return lines
        
        # If pattern is [1] or we have 1 node, direct connection
        if pattern == [1] or len(upper_nodes) <= 1:
            for node in upper_nodes:
                line = Line2D(
                    lower_node=lower_node,
                    upper_node=node,
                    target_length=1.0,  # Default length
                    line_type=line_type_name,
                    layer=layer,
                    name=node.name,
                )
                lines.append(line)
            return lines
        
        # Multi-level architecture with pattern-based merging
        current_level_nodes = list(upper_nodes)
        
        for level, merge_factor in enumerate(pattern):
            if len(current_level_nodes) <= 1:
                break
                
            next_level_nodes = []
            
            # Group nodes by merge_factor
            for i in range(0, len(current_level_nodes), merge_factor):
                group = current_level_nodes[i:i + merge_factor]
                
                if len(group) == 1:
                    # Single node left over, pass through
                    next_level_nodes.append(group[0])
                else:
                    # Create intermediate batch node
                    pos_2d = self._calculate_batch_position(group, level)
                    
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
                            target_length=1.0,  # Default length
                            line_type=line_type_name,
                            layer=layer,
                            name=f"{layer}_l{level}_{i + j}",
                        )
                        lines.append(line)
                    
                    next_level_nodes.append(batch_node)
            
            current_level_nodes = next_level_nodes
        
        # Connect final level nodes to lower node
        for i, node in enumerate(current_level_nodes):
            line = Line2D(
                lower_node=lower_node,
                upper_node=node,
                target_length=1.0,  # Default length
                line_type=line_type_name,
                layer=layer,
                name=f"{layer}_main_{i}",
            )
            lines.append(line)
        
        return lines
    
    def _calculate_batch_position(self, group, level):
        """Calculate the 2D position for a batch node."""
        # Check what kind of nodes we have
        pos_2d_list = []
        
        for n in group:
            if isinstance(n, UpperNode2D):
                # Get 2D position from shape
                try:
                    cell_int = int(round(n.cell_no + n.cell_pos))
                    cell_int = max(0, min(cell_int, self.half_cell_num - 1))
                    pos = list(self.parametric_glider.shape[cell_int, n.rib_pos])
                    pos_2d_list.append(pos)
                except Exception:
                    pos_2d_list.append([n.cell_no * 0.5, n.rib_pos * 2.0])
            elif hasattr(n, 'pos_2D'):
                # BatchNode2D has pos_2D
                pos_2d_list.append(list(n.pos_2D))
            else:
                # Fallback
                pos_2d_list.append([0, 0])
        
        # Average the positions
        if pos_2d_list:
            pos_2d = [
                sum(p[0] for p in pos_2d_list) / len(pos_2d_list),
                sum(p[1] for p in pos_2d_list) / len(pos_2d_list),
            ]
        else:
            pos_2d = [0, 0]
        
        # Move down for each level
        pos_2d[1] = pos_2d[1] - (level + 1) * 1.5
        
        return pos_2d

