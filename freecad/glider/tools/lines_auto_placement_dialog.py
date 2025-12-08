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


class LineTypeConfigRow(QtGui.QWidget):
    """Widget for configuring a single line type (A, B, C, D, F)."""
    
    configChanged = QtCore.Signal()
    
    # Predefined patterns
    PATTERNS = [
        ("1:1", [1]),
        ("2:1", [2]),
        ("3:1", [3]),
        ("2:2:1", [2, 2]),
        ("3:2:1", [3, 2]),
        ("4:2:1", [4, 2]),
    ]
    
    def __init__(self, line_type_name, default_position, default_pattern_idx=1, parent=None):
        super(LineTypeConfigRow, self).__init__(parent)
        self.line_type_name = line_type_name
        
        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        # Enable checkbox with line type name
        self.enable_checkbox = QtGui.QCheckBox(line_type_name)
        self.enable_checkbox.setChecked(True)
        self.enable_checkbox.setFixedWidth(40)
        layout.addWidget(self.enable_checkbox)
        
        # Position (%)
        self.position_spinbox = QtGui.QDoubleSpinBox()
        self.position_spinbox.setRange(0, 100)
        self.position_spinbox.setValue(default_position)
        self.position_spinbox.setDecimals(1)
        self.position_spinbox.setSuffix(" %")
        self.position_spinbox.setFixedWidth(70)
        layout.addWidget(self.position_spinbox)
        
        # Interval (every X cells)
        self.interval_spinbox = QtGui.QSpinBox()
        self.interval_spinbox.setRange(1, 10)
        self.interval_spinbox.setValue(1)
        self.interval_spinbox.setPrefix("/ ")
        self.interval_spinbox.setSuffix(" cell")
        self.interval_spinbox.setFixedWidth(70)
        layout.addWidget(self.interval_spinbox)
        
        # Start cell
        self.start_spinbox = QtGui.QSpinBox()
        self.start_spinbox.setRange(0, 50)
        self.start_spinbox.setValue(0)
        self.start_spinbox.setPrefix("@ ")
        self.start_spinbox.setFixedWidth(55)
        layout.addWidget(self.start_spinbox)
        
        # Pattern selector
        self.pattern_combo = QtGui.QComboBox()
        for name, _ in self.PATTERNS:
            self.pattern_combo.addItem(name)
        self.pattern_combo.setCurrentIndex(default_pattern_idx)
        self.pattern_combo.setFixedWidth(70)
        layout.addWidget(self.pattern_combo)
        
        # Connect signals
        self.enable_checkbox.toggled.connect(self._update_enabled_state)
        self.enable_checkbox.toggled.connect(lambda: self.configChanged.emit())
        self.position_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        self.interval_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        self.start_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        self.pattern_combo.currentIndexChanged.connect(lambda: self.configChanged.emit())
        
    def _update_enabled_state(self, enabled):
        self.position_spinbox.setEnabled(enabled)
        self.interval_spinbox.setEnabled(enabled)
        self.start_spinbox.setEnabled(enabled)
        self.pattern_combo.setEnabled(enabled)
    
    def is_enabled(self):
        return self.enable_checkbox.isChecked()
    
    def get_pattern(self):
        idx = self.pattern_combo.currentIndex()
        return self.PATTERNS[idx][1]
    
    def get_config(self):
        return {
            "enabled": self.is_enabled(),
            "position": self.position_spinbox.value() / 100.0,
            "interval": self.interval_spinbox.value(),
            "start_cell": self.start_spinbox.value(),
            "pattern": self.get_pattern(),
        }


class LinesAutoPlacementDialog(QtGui.QDialog):
    """Dialog for automatic placement of suspension lines."""
    
    # Default positions and patterns for each line type
    LINE_DEFAULTS = {
        "A": {"position": 8.5, "interval": 1, "pattern_idx": 2},   # 3:1
        "B": {"position": 27.5, "interval": 2, "pattern_idx": 3},  # 2:2:1
        "C": {"position": 53.0, "interval": 2, "pattern_idx": 1},  # 2:1
        "D": {"position": 77.0, "interval": 3, "pattern_idx": 1},  # 2:1
        "F": {"position": 100.0, "interval": 1, "pattern_idx": 0}, # 1:1
    }
    
    def __init__(self, parametric_glider, parent=None):
        super(LinesAutoPlacementDialog, self).__init__(parent)
        self.parametric_glider = parametric_glider
        self.half_cell_num = parametric_glider.shape.half_cell_num
        
        # Calculate default span for basses length
        try:
            shape = parametric_glider.shape.get_half_shape()
            self.span = abs(shape.front[-1][0] - shape.front[0][0])
        except:
            self.span = 6.0  # Default fallback
        
        self.setWindowTitle("Auto-placement des suspentes")
        self.setMinimumWidth(500)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QtGui.QVBoxLayout(self)
        
        # === Lower Attachment Point ===
        lower_group = QtGui.QGroupBox("Point d'attache (élévateur)")
        lower_layout = QtGui.QFormLayout(lower_group)
        
        # Position 3D
        pos_widget = QtGui.QWidget()
        pos_layout = QtGui.QHBoxLayout(pos_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lower_x = QtGui.QDoubleSpinBox()
        self.lower_x.setRange(-50, 50)
        self.lower_x.setValue(0)
        self.lower_x.setSuffix(" m")
        pos_layout.addWidget(QtGui.QLabel("X:"))
        pos_layout.addWidget(self.lower_x)
        
        self.lower_y = QtGui.QDoubleSpinBox()
        self.lower_y.setRange(-50, 50)
        self.lower_y.setValue(0)
        self.lower_y.setSuffix(" m")
        pos_layout.addWidget(QtGui.QLabel("Y:"))
        pos_layout.addWidget(self.lower_y)
        
        self.lower_z = QtGui.QDoubleSpinBox()
        self.lower_z.setRange(-50, 50)
        self.lower_z.setValue(-7)
        self.lower_z.setSuffix(" m")
        pos_layout.addWidget(QtGui.QLabel("Z:"))
        pos_layout.addWidget(self.lower_z)
        
        lower_layout.addRow("Position:", pos_widget)
        main_layout.addWidget(lower_group)
        
        # === Lengths ===
        lengths_group = QtGui.QGroupBox("Longueurs")
        lengths_layout = QtGui.QFormLayout(lengths_group)
        
        # Riser length
        self.riser_length = QtGui.QDoubleSpinBox()
        self.riser_length.setRange(0.1, 2.0)
        self.riser_length.setValue(0.47)
        self.riser_length.setSingleStep(0.01)
        self.riser_length.setSuffix(" m")
        lengths_layout.addRow("Élévateurs:", self.riser_length)
        
        # Basses length
        basses_widget = QtGui.QWidget()
        basses_layout = QtGui.QHBoxLayout(basses_widget)
        basses_layout.setContentsMargins(0, 0, 0, 0)
        
        self.basses_length = QtGui.QDoubleSpinBox()
        self.basses_length.setRange(0.5, 10.0)
        self.basses_length.setValue(round(self.span / 3, 2))
        self.basses_length.setSingleStep(0.1)
        self.basses_length.setSuffix(" m")
        basses_layout.addWidget(self.basses_length)
        
        self.basses_auto = QtGui.QCheckBox("Auto (1/3 span)")
        self.basses_auto.setChecked(True)
        self.basses_auto.toggled.connect(self._update_basses_auto)
        basses_layout.addWidget(self.basses_auto)
        
        lengths_layout.addRow("Basses:", basses_widget)
        
        # Inter length
        inter_widget = QtGui.QWidget()
        inter_layout = QtGui.QHBoxLayout(inter_widget)
        inter_layout.setContentsMargins(0, 0, 0, 0)
        
        self.inter_length = QtGui.QDoubleSpinBox()
        self.inter_length.setRange(0.5, 10.0)
        self.inter_length.setValue(round(self.span / 3 - 1, 2))
        self.inter_length.setSingleStep(0.1)
        self.inter_length.setSuffix(" m")
        inter_layout.addWidget(self.inter_length)
        
        self.inter_auto = QtGui.QCheckBox("Auto (basses - 1m)")
        self.inter_auto.setChecked(True)
        self.inter_auto.toggled.connect(self._update_inter_auto)
        inter_layout.addWidget(self.inter_auto)
        
        lengths_layout.addRow("Intermédiaires:", inter_widget)
        
        # Hautes info
        self.hautes_label = QtGui.QLabel("(calculées automatiquement)")
        self.hautes_label.setStyleSheet("color: gray; font-style: italic;")
        lengths_layout.addRow("Hautes:", self.hautes_label)
        
        main_layout.addWidget(lengths_group)
        
        # === Line Types Configuration ===
        lines_group = QtGui.QGroupBox("Configuration par type de ligne")
        lines_layout = QtGui.QVBoxLayout(lines_group)
        
        # Header
        header_widget = QtGui.QWidget()
        header_layout = QtGui.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(QtGui.QLabel("Type"))
        header_layout.addWidget(QtGui.QLabel("Position"))
        header_layout.addWidget(QtGui.QLabel("Intervalle"))
        header_layout.addWidget(QtGui.QLabel("Départ"))
        header_layout.addWidget(QtGui.QLabel("Pattern"))
        lines_layout.addWidget(header_widget)
        
        # Line type rows
        self.line_type_rows = {}
        for line_type in ["A", "B", "C", "D", "F"]:
            defaults = self.LINE_DEFAULTS[line_type]
            row = LineTypeConfigRow(
                line_type, 
                defaults["position"],
                defaults["pattern_idx"]
            )
            row.interval_spinbox.setValue(defaults["interval"])
            self.line_type_rows[line_type] = row
            lines_layout.addWidget(row)
            row.configChanged.connect(self._update_info)
        
        main_layout.addWidget(lines_group)
        
        # === Stabilo Section ===
        stabilo_group = QtGui.QGroupBox("Stabilo")
        stabilo_layout = QtGui.QFormLayout(stabilo_group)
        
        self.stabilo_checkbox = QtGui.QCheckBox("Inclure stabilo")
        self.stabilo_checkbox.setChecked(True)
        stabilo_layout.addRow("", self.stabilo_checkbox)
        
        self.stabilo_position = QtGui.QDoubleSpinBox()
        self.stabilo_position.setRange(0, 100)
        self.stabilo_position.setValue(50)
        self.stabilo_position.setSuffix(" %")
        stabilo_layout.addRow("Position:", self.stabilo_position)
        
        main_layout.addWidget(stabilo_group)
        
        # === Line Material Type ===
        material_group = QtGui.QGroupBox("Matériau")
        material_layout = QtGui.QFormLayout(material_group)
        
        self.line_type_combo = QtGui.QComboBox()
        for lt in sorted(LineType.types.keys()):
            self.line_type_combo.addItem(lt)
        default_idx = self.line_type_combo.findText("default")
        if default_idx >= 0:
            self.line_type_combo.setCurrentIndex(default_idx)
        material_layout.addRow("Type de ligne:", self.line_type_combo)
        
        main_layout.addWidget(material_group)
        
        # === Buttons ===
        button_layout = QtGui.QHBoxLayout()
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
        self.info_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.info_label)
        
        self._update_info()
    
    def _update_basses_auto(self, checked):
        self.basses_length.setEnabled(not checked)
        if checked:
            self.basses_length.setValue(round(self.span / 3, 2))
    
    def _update_inter_auto(self, checked):
        self.inter_length.setEnabled(not checked)
        if checked:
            basses = self.basses_length.value()
            self.inter_length.setValue(max(0.5, basses - 1.0))
    
    def _update_info(self):
        if not hasattr(self, 'info_label'):
            return
        count = self._count_attachment_points()
        enabled = [lt for lt, row in self.line_type_rows.items() if row.is_enabled()]
        self.info_label.setText(f"Points: {count} | Élévateurs: {len(enabled)} ({', '.join(enabled)})")
    
    def _count_attachment_points(self):
        count = 0
        for lt, row in self.line_type_rows.items():
            if row.is_enabled():
                config = row.get_config()
                for _ in range(config["start_cell"], self.half_cell_num, config["interval"]):
                    count += 1
        if hasattr(self, 'stabilo_checkbox') and self.stabilo_checkbox.isChecked():
            count += 1
        return count
    
    def get_configuration(self):
        return {
            "lower_position": [
                self.lower_x.value(),
                self.lower_y.value(),
                self.lower_z.value(),
            ],
            "riser_length": self.riser_length.value(),
            "basses_length": self.basses_length.value(),
            "inter_length": self.inter_length.value(),
            "line_types": {
                lt: row.get_config() 
                for lt, row in self.line_type_rows.items()
            },
            "line_type_name": self.line_type_combo.currentText(),
            "include_stabilo": self.stabilo_checkbox.isChecked(),
            "stabilo_position": self.stabilo_position.value() / 100.0,
        }
    
    def generate_lineset(self):
        """Generate LineSet2D based on the current configuration."""
        config = self.get_configuration()
        lines = []
        
        # Create SINGLE lower attachment point
        lower_pos = config["lower_position"]
        main_lower_node = LowerNode2D(
            pos_2D=[lower_pos[0], lower_pos[2]],
            pos_3D=lower_pos,
            name="main",
            layer="",
        )
        
        # Get enabled line types
        enabled_types = [lt for lt in ["A", "B", "C", "D", "F"] 
                        if config["line_types"][lt]["enabled"]]
        
        # Create riser nodes (one per enabled line type)
        riser_nodes = {}
        riser_spacing = 0.3  # Spacing between risers in 2D view
        for i, lt in enumerate(enabled_types):
            offset = (i - len(enabled_types) / 2) * riser_spacing
            riser_node = BatchNode2D(
                pos_2D=[lower_pos[0] + offset, lower_pos[2] + config["riser_length"]],
                name=f"riser_{lt}",
                layer=lt,
            )
            riser_nodes[lt] = riser_node
            
            # Connect riser to main lower node
            riser_line = Line2D(
                lower_node=main_lower_node,
                upper_node=riser_node,
                target_length=config["riser_length"],
                line_type=config["line_type_name"],
                layer=lt,
                name=f"riser_{lt}",
            )
            lines.append(riser_line)
        
        # Generate upper attachment points and architecture for each line type
        for lt in enabled_types:
            lt_config = config["line_types"][lt]
            upper_nodes = self._generate_upper_nodes(lt, lt_config)
            
            if upper_nodes:
                lt_lines = self._generate_line_architecture(
                    upper_nodes=upper_nodes,
                    riser_node=riser_nodes[lt],
                    pattern=lt_config["pattern"],
                    basses_length=config["basses_length"],
                    inter_length=config["inter_length"],
                    line_type_name=config["line_type_name"],
                    layer=lt,
                )
                lines.extend(lt_lines)
        
        # Generate stabilo if enabled
        if config["include_stabilo"]:
            stabilo_node = UpperNode2D(
                cell_no=self.half_cell_num - 1,
                rib_pos=config["stabilo_position"],
                cell_pos=1,
                force=1.0,
                name="S1",
                layer="S",
            )
            # Create stabilo riser
            stabilo_riser = BatchNode2D(
                pos_2D=[lower_pos[0] + len(enabled_types) * riser_spacing / 2 + 0.3, 
                       lower_pos[2] + config["riser_length"]],
                name="riser_S",
                layer="S",
            )
            # Riser to main
            lines.append(Line2D(
                lower_node=main_lower_node,
                upper_node=stabilo_riser,
                target_length=config["riser_length"],
                line_type=config["line_type_name"],
                layer="S",
                name="riser_S",
            ))
            # Stabilo to riser
            lines.append(Line2D(
                lower_node=stabilo_riser,
                upper_node=stabilo_node,
                target_length=config["basses_length"],
                line_type=config["line_type_name"],
                layer="S",
                name="S1",
            ))
        
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
                cell_pos=0,
                force=1.0,
                name=f"{line_type}{index}",
                layer=line_type,
            )
            nodes.append(node)
            index += 1
        
        return nodes
    
    def _generate_line_architecture(self, upper_nodes, riser_node, pattern,
                                    basses_length, inter_length, line_type_name, layer):
        """
        Generate line architecture from upper nodes down to riser.
        
        Pattern interpretation:
        - [1] = direct connection (hautes only)
        - [2] = 2:1 (2 hautes -> 1 basse)
        - [2, 2] = 2:2:1 (2 hautes -> 1 inter, 2 inters -> 1 basse)
        """
        lines = []
        
        if not upper_nodes:
            return lines
        
        # Direct connection (pattern [1])
        if pattern == [1]:
            for node in upper_nodes:
                line = Line2D(
                    lower_node=riser_node,
                    upper_node=node,
                    target_length=basses_length,
                    line_type=line_type_name,
                    layer=layer,
                    name=node.name,
                )
                lines.append(line)
            return lines
        
        # Multi-level architecture
        current_nodes = list(upper_nodes)
        level_lengths = self._calculate_level_lengths(pattern, basses_length, inter_length)
        
        for level_idx, merge_factor in enumerate(pattern):
            next_nodes = []
            is_last_level = (level_idx == len(pattern) - 1)
            current_length = level_lengths[level_idx]
            
            # Group nodes
            for group_idx in range(0, len(current_nodes), merge_factor):
                group = current_nodes[group_idx:group_idx + merge_factor]
                
                if is_last_level:
                    # Connect to riser
                    for node in group:
                        line = Line2D(
                            lower_node=riser_node,
                            upper_node=node,
                            target_length=current_length,
                            line_type=line_type_name,
                            layer=layer,
                            name=f"{layer}_basse_{group_idx}",
                        )
                        lines.append(line)
                else:
                    # Create intermediate node
                    batch_pos = self._calculate_batch_position(group, level_idx)
                    batch_node = BatchNode2D(
                        pos_2D=batch_pos,
                        name=f"{layer}_inter_{level_idx}_{group_idx // merge_factor}",
                        layer=layer,
                    )
                    
                    # Connect group to batch
                    for i, node in enumerate(group):
                        line = Line2D(
                            lower_node=batch_node,
                            upper_node=node,
                            target_length=current_length,
                            line_type=line_type_name,
                            layer=layer,
                            name=f"{layer}_l{level_idx}_{group_idx + i}",
                        )
                        lines.append(line)
                    
                    next_nodes.append(batch_node)
            
            current_nodes = next_nodes if next_nodes else current_nodes
        
        # Connect remaining nodes to riser
        if current_nodes and current_nodes[0] != riser_node:
            for i, node in enumerate(current_nodes):
                line = Line2D(
                    lower_node=riser_node,
                    upper_node=node,
                    target_length=basses_length,
                    line_type=line_type_name,
                    layer=layer,
                    name=f"{layer}_basse_{i}",
                )
                lines.append(line)
        
        return lines
    
    def _calculate_level_lengths(self, pattern, basses_length, inter_length):
        """Calculate lengths for each level."""
        num_levels = len(pattern)
        if num_levels == 1:
            return [basses_length]
        
        # Last level is basses, previous are inter, first is hautes (calculated)
        lengths = []
        for i in range(num_levels):
            if i == num_levels - 1:
                lengths.append(basses_length)
            else:
                lengths.append(inter_length)
        return lengths
    
    def _calculate_batch_position(self, group, level):
        """Calculate 2D position for intermediate batch node."""
        pos_list = []
        
        for n in group:
            if isinstance(n, UpperNode2D):
                try:
                    cell_int = int(round(n.cell_no + n.cell_pos))
                    cell_int = max(0, min(cell_int, self.half_cell_num - 1))
                    pos = list(self.parametric_glider.shape[cell_int, n.rib_pos])
                    pos_list.append(pos)
                except Exception:
                    pos_list.append([n.cell_no * 0.5, n.rib_pos * 2.0])
            elif hasattr(n, 'pos_2D'):
                pos_list.append(list(n.pos_2D))
        
        if pos_list:
            avg_pos = [
                sum(p[0] for p in pos_list) / len(pos_list),
                sum(p[1] for p in pos_list) / len(pos_list),
            ]
        else:
            avg_pos = [0, 0]
        
        # Move down based on level
        avg_pos[1] -= (level + 1) * 1.5
        
        return avg_pos
