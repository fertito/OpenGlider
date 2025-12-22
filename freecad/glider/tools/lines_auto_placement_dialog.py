"""
Lines Auto-Placement Dialog for OpenGlider

This dialog allows users to automatically generate suspension line attachment points
and line architecture based on configurable parameters.

Architecture concept:
- Lines are organized by TYPE (A, B, C, D, F) along the chord
- Within each type, lines are organized by GROUPS along the span
- Each GROUP corresponds to ONE "basse" (lower line connecting to riser)
- Each group can have its own pattern (3:1, 2:2:1, etc.)

Example for A lines with 6 attachment points:
- Group 1 (A1): pattern 3:1 → 3 hautes connect to basse A1
- Group 2 (A2): pattern 2:2:1 → 2+2 hautes connect via inters to basse A2
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


class GroupPatternWidget(QtGui.QWidget):
    """Widget for defining pattern per group."""
    
    PATTERNS = ["1:1", "2:1", "3:1", "2:2:1", "3:2:1", "4:2:1"]
    
    def __init__(self, parent=None):
        super(GroupPatternWidget, self).__init__(parent)
        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Pattern input as text
        self.pattern_edit = QtGui.QLineEdit()
        self.pattern_edit.setPlaceholderText("ex: 3:1, 2:2:1, 2:1, 2:1")
        self.pattern_edit.setText("2:1")
        layout.addWidget(self.pattern_edit)
        
        # Help label
        help_label = QtGui.QLabel("Format: pattern1, pattern2, ... (répété si besoin)")
        help_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(help_label)
    
    def get_patterns(self):
        """Parse pattern string and return list of patterns."""
        text = self.pattern_edit.text().strip()
        if not text:
            return [[2]]  # Default 2:1
        
        patterns = []
        for part in text.split(","):
            part = part.strip()
            if ":" in part:
                try:
                    pattern = [int(x) for x in part.split(":") if x.strip() and x.strip() != "1"]
                    if not pattern:
                        pattern = [1]
                    patterns.append(pattern)
                except ValueError:
                    patterns.append([2])  # Default
            else:
                try:
                    patterns.append([int(part)])
                except ValueError:
                    patterns.append([2])
        
        return patterns if patterns else [[2]]


class LineTypeConfigRow(QtGui.QWidget):
    """Widget for configuring a single line type (A, B, C, D, F)."""
    
    configChanged = QtCore.Signal()
    
    def __init__(self, line_type_name, default_position, default_pattern="2:1", parent=None):
        super(LineTypeConfigRow, self).__init__(parent)
        self.line_type_name = line_type_name
        
        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        # Enable checkbox
        self.enable_checkbox = QtGui.QCheckBox(line_type_name)
        self.enable_checkbox.setChecked(True)
        self.enable_checkbox.setFixedWidth(40)
        layout.addWidget(self.enable_checkbox)
        
        # Position (%)
        self.position_spinbox = QtGui.QDoubleSpinBox()
        self.position_spinbox.setRange(0, 100)
        self.position_spinbox.setValue(default_position)
        self.position_spinbox.setDecimals(1)
        self.position_spinbox.setSuffix("%")
        self.position_spinbox.setFixedWidth(65)
        layout.addWidget(self.position_spinbox)
        
        # Interval
        self.interval_spinbox = QtGui.QSpinBox()
        self.interval_spinbox.setRange(1, 10)
        self.interval_spinbox.setValue(1)
        self.interval_spinbox.setPrefix("/")
        self.interval_spinbox.setFixedWidth(45)
        layout.addWidget(self.interval_spinbox)
        
        # Start cell
        self.start_spinbox = QtGui.QSpinBox()
        self.start_spinbox.setRange(0, 50)
        self.start_spinbox.setValue(0)
        self.start_spinbox.setPrefix("@")
        self.start_spinbox.setFixedWidth(45)
        layout.addWidget(self.start_spinbox)
        
        # Group patterns (text input)
        self.patterns_edit = QtGui.QLineEdit()
        self.patterns_edit.setPlaceholderText("2:1, 3:1, ...")
        self.patterns_edit.setText(default_pattern)
        self.patterns_edit.setFixedWidth(120)
        layout.addWidget(self.patterns_edit)
        
        # Connect signals
        self.enable_checkbox.toggled.connect(self._update_enabled_state)
        self.enable_checkbox.toggled.connect(lambda: self.configChanged.emit())
        self.position_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        self.interval_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        self.start_spinbox.valueChanged.connect(lambda: self.configChanged.emit())
        self.patterns_edit.textChanged.connect(lambda: self.configChanged.emit())
        
    def _update_enabled_state(self, enabled):
        self.position_spinbox.setEnabled(enabled)
        self.interval_spinbox.setEnabled(enabled)
        self.start_spinbox.setEnabled(enabled)
        self.patterns_edit.setEnabled(enabled)
    
    def is_enabled(self):
        return self.enable_checkbox.isChecked()
    
    def get_group_patterns(self):
        """Parse group patterns from text input."""
        text = self.patterns_edit.text().strip()
        if not text:
            return [[2]]  # Default 2:1
        
        patterns = []
        for part in text.split(","):
            part = part.strip()
            if ":" in part:
                try:
                    # Parse "2:2:1" -> [2, 2] (remove final :1)
                    nums = [int(x) for x in part.split(":") if x.strip()]
                    # Remove trailing 1s (they're implicit)
                    while len(nums) > 1 and nums[-1] == 1:
                        nums.pop()
                    patterns.append(nums if nums else [1])
                except ValueError:
                    patterns.append([2])
            else:
                try:
                    patterns.append([int(part)])
                except ValueError:
                    patterns.append([2])
        
        return patterns if patterns else [[2]]
    
    def get_config(self):
        return {
            "enabled": self.is_enabled(),
            "position": self.position_spinbox.value() / 100.0,
            "interval": self.interval_spinbox.value(),
            "start_cell": self.start_spinbox.value(),
            "group_patterns": self.get_group_patterns(),
        }


class LinesAutoPlacementDialog(QtGui.QDialog):
    """Dialog for automatic placement of suspension lines."""
    
    # Default configurations
    LINE_DEFAULTS = {
        "A": {"position": 8.5, "interval": 1, "pattern": "3:1, 2:2:1"},
        "B": {"position": 27.5, "interval": 2, "pattern": "2:2:1, 2:1"},
        "C": {"position": 53.0, "interval": 2, "pattern": "2:1"},
        "D": {"position": 77.0, "interval": 3, "pattern": "2:1"},
        "F": {"position": 100.0, "interval": 1, "pattern": "1:1"},
    }
    
    def __init__(self, parametric_glider, parent=None):
        super(LinesAutoPlacementDialog, self).__init__(parent)
        self.parametric_glider = parametric_glider
        self.half_cell_num = parametric_glider.shape.half_cell_num
        self.half_rib_num = parametric_glider.shape.half_rib_num
        
        # Calculate span - shape.span gives half-span (from center to tip)
        try:
            self.half_span = self.parametric_glider.shape.span
        except:
            self.half_span = 6.0
        
        self.setWindowTitle("Auto-placement des suspentes")
        self.setMinimumWidth(520)
        
        self.setup_ui()
        self.load_from_glider()  # Load saved configuration
        
    def setup_ui(self):
        main_layout = QtGui.QVBoxLayout(self)
        
        # === Point Pilote ===
        lower_group = QtGui.QGroupBox("Point Pilote (X=envergure, Y=corde, Z=hauteur)")
        lower_layout = QtGui.QFormLayout(lower_group)
        
        # Demi-écartement (X - span direction)
        self.demi_ecartement = QtGui.QDoubleSpinBox()
        self.demi_ecartement.setRange(0, 2.0)
        self.demi_ecartement.setValue(0.2)
        self.demi_ecartement.setSingleStep(0.05)
        self.demi_ecartement.setSuffix(" m")
        lower_layout.addRow("Demi-écartement:", self.demi_ecartement)
        
        # Profondeur (Y - chord direction, from leading edge)
        self.profondeur = QtGui.QDoubleSpinBox()
        self.profondeur.setRange(-5, 5)
        self.profondeur.setValue(0.5)
        self.profondeur.setSingleStep(0.1)
        self.profondeur.setSuffix(" m")
        lower_layout.addRow("Profondeur:", self.profondeur)
        
        # Hauteur cône (Z - height below wing)
        hauteur_widget = QtGui.QWidget()
        hauteur_layout = QtGui.QHBoxLayout(hauteur_widget)
        hauteur_layout.setContentsMargins(0, 0, 0, 0)
        
        self.hauteur_cone = QtGui.QDoubleSpinBox()
        self.hauteur_cone.setRange(1, 15)
        # Auto value: ~75% of full wingspan (typical ratio for paragliders)
        auto_hauteur = round(self.half_span * 2 * 0.75, 1)
        self.hauteur_cone.setValue(auto_hauteur)
        self.hauteur_cone.setSingleStep(0.5)
        self.hauteur_cone.setSuffix(" m")
        self.hauteur_cone.setEnabled(False)
        hauteur_layout.addWidget(self.hauteur_cone)
        
        self.hauteur_auto = QtGui.QCheckBox("Auto (75% envergure)")
        self.hauteur_auto.setChecked(True)
        self.hauteur_auto.toggled.connect(self._update_hauteur_auto)
        hauteur_layout.addWidget(self.hauteur_auto)
        
        lower_layout.addRow("Hauteur cône:", hauteur_widget)
        
        main_layout.addWidget(lower_group)
        
        # === Point Freins (offset from pilote) ===
        brake_group = QtGui.QGroupBox("Point Freins (décalage par rapport au point pilote)")
        brake_layout = QtGui.QFormLayout(brake_group)
        
        # Enable separate brake point
        self.brake_separate = QtGui.QCheckBox("Point séparé pour les freins")
        self.brake_separate.setChecked(True)
        self.brake_separate.toggled.connect(self._update_brake_enabled)
        brake_layout.addRow("", self.brake_separate)
        
        # Offset hauteur (Z - higher than pilote, positive = higher)
        self.brake_offset_z = QtGui.QDoubleSpinBox()
        self.brake_offset_z.setRange(-1.0, 2.0)
        self.brake_offset_z.setValue(0.40)  # 40cm higher
        self.brake_offset_z.setSingleStep(0.05)
        self.brake_offset_z.setSuffix(" m")
        brake_layout.addRow("Décalage hauteur:", self.brake_offset_z)
        
        # Offset écartement (Y - more outward, positive = more spread)
        self.brake_offset_y = QtGui.QDoubleSpinBox()
        self.brake_offset_y.setRange(-0.5, 1.0)
        self.brake_offset_y.setValue(0.15)  # 15cm more outward
        self.brake_offset_y.setSingleStep(0.05)
        self.brake_offset_y.setSuffix(" m")
        brake_layout.addRow("Décalage écartement:", self.brake_offset_y)
        
        # Offset profondeur (X - chord direction, positive = more backward)
        self.brake_offset_x = QtGui.QDoubleSpinBox()
        self.brake_offset_x.setRange(-1.0, 1.0)
        self.brake_offset_x.setValue(0.0)  # 0cm by default
        self.brake_offset_x.setSingleStep(0.05)
        self.brake_offset_x.setSuffix(" m")
        brake_layout.addRow("Décalage profondeur:", self.brake_offset_x)
        
        main_layout.addWidget(brake_group)

        
        # === Lengths ===
        lengths_group = QtGui.QGroupBox("Longueurs")
        lengths_layout = QtGui.QFormLayout(lengths_group)
        
        self.riser_length = QtGui.QDoubleSpinBox()
        self.riser_length.setRange(0.1, 2.0)
        self.riser_length.setValue(0.47)
        self.riser_length.setSingleStep(0.01)
        self.riser_length.setSuffix(" m")
        lengths_layout.addRow("Élévateurs:", self.riser_length)
        
        # Basses (longest)
        basses_widget = QtGui.QWidget()
        basses_layout = QtGui.QHBoxLayout(basses_widget)
        basses_layout.setContentsMargins(0, 0, 0, 0)
        self.basses_length = QtGui.QDoubleSpinBox()
        self.basses_length.setRange(0.5, 10.0)
        self.basses_length.setValue(round(self.hauteur_cone.value() * 0.45, 2))
        self.basses_length.setSuffix(" m")
        self.basses_length.setEnabled(False)
        basses_layout.addWidget(self.basses_length)
        self.basses_auto = QtGui.QCheckBox("Auto")
        self.basses_auto.setChecked(True)
        self.basses_auto.toggled.connect(lambda c: self.basses_length.setEnabled(not c))
        basses_layout.addWidget(self.basses_auto)
        lengths_layout.addRow("Basses:", basses_widget)
        
        # Inter (medium)
        inter_widget = QtGui.QWidget()
        inter_layout = QtGui.QHBoxLayout(inter_widget)
        inter_layout.setContentsMargins(0, 0, 0, 0)
        self.inter_length = QtGui.QDoubleSpinBox()
        self.inter_length.setRange(0.3, 8.0)
        self.inter_length.setValue(round(self.hauteur_cone.value() * 0.30, 2))
        self.inter_length.setSuffix(" m")
        self.inter_length.setEnabled(False)
        inter_layout.addWidget(self.inter_length)
        self.inter_auto = QtGui.QCheckBox("Auto")
        self.inter_auto.setChecked(True)
        self.inter_auto.toggled.connect(lambda c: self.inter_length.setEnabled(not c))
        inter_layout.addWidget(self.inter_auto)
        lengths_layout.addRow("Inter:", inter_widget)
        
        # Hautes (shortest)
        hautes_widget = QtGui.QWidget()
        hautes_layout = QtGui.QHBoxLayout(hautes_widget)
        hautes_layout.setContentsMargins(0, 0, 0, 0)
        self.hautes_length = QtGui.QDoubleSpinBox()
        self.hautes_length.setRange(0.2, 5.0)
        self.hautes_length.setValue(round(self.hauteur_cone.value() * 0.20, 2))
        self.hautes_length.setSuffix(" m")
        self.hautes_length.setEnabled(False)
        hautes_layout.addWidget(self.hautes_length)
        self.hautes_auto = QtGui.QCheckBox("Auto")
        self.hautes_auto.setChecked(True)
        self.hautes_auto.toggled.connect(lambda c: self.hautes_length.setEnabled(not c))
        hautes_layout.addWidget(self.hautes_auto)
        lengths_layout.addRow("Hautes:", hautes_widget)
        
        # Help text for auto calculation
        lengths_help = QtGui.QLabel("Auto: Basses=45%, Inter=30%, Hautes=20% du cône")
        lengths_help.setStyleSheet("color: gray; font-size: 10px;")
        lengths_layout.addRow("", lengths_help)
        
        main_layout.addWidget(lengths_group)
        
        # === Line Types ===
        lines_group = QtGui.QGroupBox("Lignes (Type | Pos | /Cell | @Start | Patterns)")
        lines_layout = QtGui.QVBoxLayout(lines_group)
        
        self.line_type_rows = {}
        for lt in ["A", "B", "C", "D", "F"]:
            defaults = self.LINE_DEFAULTS[lt]
            row = LineTypeConfigRow(lt, defaults["position"], defaults["pattern"])
            row.interval_spinbox.setValue(defaults["interval"])
            self.line_type_rows[lt] = row
            lines_layout.addWidget(row)
            row.configChanged.connect(self._update_info)
        
        # Help text
        help_text = QtGui.QLabel("Patterns: 2:1 = 2 hautes→1 basse | 2:2:1 = 2+2 hautes→2 inter→1 basse")
        help_text.setStyleSheet("color: gray; font-size: 10px;")
        lines_layout.addWidget(help_text)
        
        main_layout.addWidget(lines_group)
        
        # === Stabilo ===
        stabilo_group = QtGui.QGroupBox("Stabilo")
        stabilo_layout = QtGui.QFormLayout(stabilo_group)
        
        self.stabilo_checkbox = QtGui.QCheckBox("Inclure")
        self.stabilo_checkbox.setChecked(True)
        self.stabilo_checkbox.toggled.connect(self._update_stabilo_enabled)
        stabilo_layout.addRow("", self.stabilo_checkbox)
        
        # Number of stabilo attachment points
        self.stabilo_count = QtGui.QSpinBox()
        self.stabilo_count.setRange(1, 5)
        self.stabilo_count.setValue(2)
        stabilo_layout.addRow("Nb points:", self.stabilo_count)
        
        self.stabilo_position = QtGui.QDoubleSpinBox()
        self.stabilo_position.setRange(0, 100)
        self.stabilo_position.setValue(50)
        self.stabilo_position.setSuffix(" %")
        stabilo_layout.addRow("Position:", self.stabilo_position)
        
        # Which riser to connect stabilo to
        self.stabilo_riser = QtGui.QComboBox()
        self.stabilo_riser.addItems(["A", "B", "C", "D", "F"])
        self.stabilo_riser.setCurrentText("A")  # Default to A riser
        stabilo_layout.addRow("Connecter à:", self.stabilo_riser)
        
        main_layout.addWidget(stabilo_group)
        
        # === Material ===
        material_group = QtGui.QGroupBox("Matériau")
        material_layout = QtGui.QFormLayout(material_group)
        
        self.line_type_combo = QtGui.QComboBox()
        for lt in sorted(LineType.types.keys()):
            self.line_type_combo.addItem(lt)
        idx = self.line_type_combo.findText("default")
        if idx >= 0:
            self.line_type_combo.setCurrentIndex(idx)
        material_layout.addRow("Type:", self.line_type_combo)
        
        main_layout.addWidget(material_group)
        
        # === Buttons ===
        button_layout = QtGui.QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QtGui.QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QtGui.QPushButton("Appliquer")
        apply_btn.clicked.connect(self.accept)
        apply_btn.setDefault(True)
        button_layout.addWidget(apply_btn)
        
        main_layout.addLayout(button_layout)
        
        # Info
        self.info_label = QtGui.QLabel("")
        self.info_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.info_label)
        
        self._update_info()
    
    def _update_info(self):
        if not hasattr(self, 'info_label'):
            return
        count = 0
        groups = 0
        for lt, row in self.line_type_rows.items():
            if row.is_enabled():
                cfg = row.get_config()
                n = len(list(range(cfg["start_cell"], self.half_cell_num, cfg["interval"])))
                count += n
                groups += 1
        if hasattr(self, 'stabilo_checkbox') and self.stabilo_checkbox.isChecked():
            count += self.stabilo_count.value() if hasattr(self, 'stabilo_count') else 1
        self.info_label.setText(f"Points: {count} | Élévateurs: {groups}")
    
    def _update_stabilo_enabled(self, enabled):
        """Update stabilo controls enabled state."""
        self.stabilo_count.setEnabled(enabled)
        self.stabilo_position.setEnabled(enabled)
        self.stabilo_riser.setEnabled(enabled)
    
    def _update_brake_enabled(self, enabled):
        """Update brake offset controls enabled state."""
        self.brake_offset_z.setEnabled(enabled)
        self.brake_offset_y.setEnabled(enabled)
        self.brake_offset_x.setEnabled(enabled)
    
    def _update_hauteur_auto(self, auto):
        """Update hauteur cone when auto is toggled."""
        self.hauteur_cone.setEnabled(not auto)
        if auto:
            # Recalculate from full span (75% of wingspan)
            self.hauteur_cone.setValue(round(self.half_span * 2 * 0.75, 1))
    
    def load_from_glider(self):
        """Load configuration from ParametricGlider if available."""
        config = getattr(self.parametric_glider, 'lines_placement_config', None)
        if not config:
            return
        
        # Point Pilote
        if 'demi_ecartement' in config:
            self.demi_ecartement.setValue(config['demi_ecartement'])
        if 'profondeur' in config:
            self.profondeur.setValue(config['profondeur'])
        if 'hauteur_auto' in config:
            self.hauteur_auto.setChecked(config['hauteur_auto'])
        if 'hauteur_cone' in config:
            self.hauteur_cone.setValue(config['hauteur_cone'])
        
        # Point Freins
        if 'brake_separate' in config:
            self.brake_separate.setChecked(config['brake_separate'])
        if 'brake_offset_z' in config:
            self.brake_offset_z.setValue(config['brake_offset_z'])
        if 'brake_offset_y' in config:
            self.brake_offset_y.setValue(config['brake_offset_y'])
        if 'brake_offset_x' in config:
            self.brake_offset_x.setValue(config['brake_offset_x'])
        
        # Lengths
        if 'riser_length' in config:
            self.riser_length.setValue(config['riser_length'])
        if 'basses_auto' in config:
            self.basses_auto.setChecked(config['basses_auto'])
        if 'basses_length' in config:
            self.basses_length.setValue(config['basses_length'])
        if 'inter_auto' in config:
            self.inter_auto.setChecked(config['inter_auto'])
        if 'inter_length' in config:
            self.inter_length.setValue(config['inter_length'])
        if 'hautes_auto' in config:
            self.hautes_auto.setChecked(config['hautes_auto'])
        if 'hautes_length' in config:
            self.hautes_length.setValue(config['hautes_length'])
        
        # Line types
        if 'line_types' in config:
            for lt, lt_config in config['line_types'].items():
                if lt in self.line_type_rows:
                    row = self.line_type_rows[lt]
                    if 'enabled' in lt_config:
                        row.enable_checkbox.setChecked(lt_config['enabled'])
                    if 'position' in lt_config:
                        row.position_spinbox.setValue(lt_config['position'])
                    if 'interval' in lt_config:
                        row.interval_spinbox.setValue(lt_config['interval'])
                    if 'start_cell' in lt_config:
                        row.start_spinbox.setValue(lt_config['start_cell'])
                    if 'patterns' in lt_config:
                        row.patterns_edit.setText(lt_config['patterns'])
        
        # Stabilo
        if 'include_stabilo' in config:
            self.stabilo_checkbox.setChecked(config['include_stabilo'])
        if 'stabilo_count' in config:
            self.stabilo_count.setValue(config['stabilo_count'])
        if 'stabilo_position' in config:
            self.stabilo_position.setValue(config['stabilo_position'])
        if 'stabilo_riser' in config:
            idx = self.stabilo_riser.findText(config['stabilo_riser'])
            if idx >= 0:
                self.stabilo_riser.setCurrentIndex(idx)
        
        # Material
        if 'line_type_name' in config:
            idx = self.line_type_combo.findText(config['line_type_name'])
            if idx >= 0:
                self.line_type_combo.setCurrentIndex(idx)
        
        self._update_info()
    
    def save_to_glider(self):
        """Save configuration to ParametricGlider for persistence."""
        config = {
            "demi_ecartement": self.demi_ecartement.value(),
            "profondeur": self.profondeur.value(),
            "hauteur_auto": self.hauteur_auto.isChecked(),
            "hauteur_cone": self.hauteur_cone.value(),
            "brake_separate": self.brake_separate.isChecked(),
            "brake_offset_z": self.brake_offset_z.value(),
            "brake_offset_y": self.brake_offset_y.value(),
            "brake_offset_x": self.brake_offset_x.value(),
            "riser_length": self.riser_length.value(),
            "basses_auto": self.basses_auto.isChecked(),
            "basses_length": self.basses_length.value(),
            "inter_auto": self.inter_auto.isChecked(),
            "inter_length": self.inter_length.value(),
            "hautes_auto": self.hautes_auto.isChecked(),
            "hautes_length": self.hautes_length.value(),
            "include_stabilo": self.stabilo_checkbox.isChecked(),
            "stabilo_count": self.stabilo_count.value(),
            "stabilo_position": self.stabilo_position.value(),
            "stabilo_riser": self.stabilo_riser.currentText(),
            "line_type_name": self.line_type_combo.currentText(),
            "line_types": {}
        }
        
        for lt, row in self.line_type_rows.items():
            config["line_types"][lt] = {
                "enabled": row.enable_checkbox.isChecked(),
                "position": row.position_spinbox.value(),
                "interval": row.interval_spinbox.value(),
                "start_cell": row.start_spinbox.value(),
                "patterns": row.patterns_edit.text(),
            }
        
        self.parametric_glider.lines_placement_config = config
    
    def get_configuration(self):
        # Calculate cone height - auto uses full span (envergure totale)
        if self.hauteur_auto.isChecked():
            # ~75% of full wingspan (2 * half_span)
            hauteur = round(self.half_span * 2 * 0.75, 2)
        else:
            hauteur = self.hauteur_cone.value()
        
        # Calculate lengths based on cone height with proper hierarchy
        # Basses (longest): 45% of cone height
        basses = self.basses_length.value()
        if self.basses_auto.isChecked():
            basses = round(hauteur * 0.45, 2)
        
        # Inter (medium): 30% of cone height
        inter = self.inter_length.value()
        if self.inter_auto.isChecked():
            inter = round(hauteur * 0.30, 2)
        
        # Hautes (shortest): 20% of cone height  
        hautes = self.hautes_length.value()
        if self.hautes_auto.isChecked():
            hautes = round(hauteur * 0.20, 2)
        
        return {
            "demi_ecartement": self.demi_ecartement.value(),  # X - span
            "profondeur": self.profondeur.value(),            # Y - chord
            "hauteur_cone": hauteur,                          # Z - height
            "brake_separate": self.brake_separate.isChecked(),
            "brake_offset_z": self.brake_offset_z.value(),    # Higher than pilote
            "brake_offset_y": self.brake_offset_y.value(),    # More outward than pilote
            "brake_offset_x": self.brake_offset_x.value(),    # Depth offset from pilote
            "riser_length": self.riser_length.value(),
            "basses_length": basses,
            "inter_length": inter,
            "hautes_length": hautes,
            "line_types": {lt: row.get_config() for lt, row in self.line_type_rows.items()},
            "line_type_name": self.line_type_combo.currentText(),
            "include_stabilo": self.stabilo_checkbox.isChecked(),
            "stabilo_count": self.stabilo_count.value(),
            "stabilo_position": self.stabilo_position.value() / 100.0,
            "stabilo_riser": self.stabilo_riser.currentText(),
        }
    
    def generate_lineset(self):
        """Generate LineSet2D."""
        self.save_to_glider()  # Persist configuration for next time
        config = self.get_configuration()
        lines = []
        
        # Point Pilote coordinates (raw values from user)
        # X = profondeur (chord direction)
        # Y = demi-écartement (span direction)  
        # Z = -hauteur_cone (below wing)
        lower_x = config["profondeur"]
        lower_y = config["demi_ecartement"]
        lower_z = -config["hauteur_cone"]
        
        # Single main lower node (point pilote)
        main_lower = LowerNode2D(
            pos_2D=[lower_x, lower_z],
            pos_3D=[lower_x, lower_y, lower_z],
            name="pilote",
            layer="",
        )
        
        # Brake lower node (point freins) - separate if enabled
        brake_lower = main_lower  # Default: same as main
        if config["brake_separate"]:
            brake_z = lower_z + config["brake_offset_z"]  # Higher (less negative)
            brake_y = lower_y + config["brake_offset_y"]  # More outward
            brake_x = lower_x + config["brake_offset_x"]  # Depth offset
            brake_lower = LowerNode2D(
                pos_2D=[brake_x, brake_z],
                pos_3D=[brake_x, brake_y, brake_z],
                name="freins",
                layer="F",
            )
        
        # Get enabled types
        enabled = [lt for lt in ["A", "B", "C", "D", "F"] 
                  if config["line_types"][lt]["enabled"]]
        
        # Calculate layout parameters for clean 2D view
        # Spread risers horizontally based on their chord position
        # This creates a clear visual separation between line types
        riser_nodes = {}
        
        # Get the shape extent for scaling
        try:
            shape = self.parametric_glider.shape.get_half_shape()
            x_extent = abs(shape.front[-1][0] - shape.front[0][0])  # Span
        except:
            x_extent = 6.0
        
        # Base height for risers (just above lower attachment points)
        riser_base_z = lower_z + config["riser_length"]
        
        for i, lt in enumerate(enabled):
            # Position risers based on chord position of the line type
            # This spreads them out naturally along the chord
            lt_position = config["line_types"][lt]["position"] / 100.0
            riser_x = lt_position * 1.5  # Scale for visual clarity
            
            # Use brake_lower for F lines, main_lower for others
            lower_node_for_riser = brake_lower if lt == "F" else main_lower
            actual_lower_z = lower_node_for_riser.pos_3D[2] if hasattr(lower_node_for_riser, 'pos_3D') else lower_z
            
            riser = BatchNode2D(
                pos_2D=[riser_x, actual_lower_z + config["riser_length"]],
                name=f"riser_{lt}",
                layer=lt,
            )
            riser_nodes[lt] = riser
            lines.append(Line2D(
                lower_node=lower_node_for_riser,
                upper_node=riser,
                target_length=config["riser_length"],
                line_type=config["line_type_name"],
                layer=lt,
                name=f"riser_{lt}",
            ))
        
        # Generate lines for each type
        for lt in enabled:
            lt_config = config["line_types"][lt]
            upper_nodes = self._generate_upper_nodes(lt, lt_config)
            
            if upper_nodes:
                lt_lines = self._generate_grouped_architecture(
                    upper_nodes=upper_nodes,
                    riser_node=riser_nodes[lt],
                    group_patterns=lt_config["group_patterns"],
                    basses_length=config["basses_length"],
                    inter_length=config["inter_length"],
                    hautes_length=config["hautes_length"],
                    line_type_name=config["line_type_name"],
                    layer=lt,
                )
                lines.extend(lt_lines)
        
        # Stabilo - connects to an existing riser, not to pilot point directly
        if config["include_stabilo"]:
            stabilo_riser_name = config["stabilo_riser"]
            stabilo_count = config["stabilo_count"]
            
            # Find the riser to connect to
            if stabilo_riser_name in riser_nodes:
                stabilo_riser = riser_nodes[stabilo_riser_name]
            else:
                # Fallback: use first available riser or create one
                stabilo_riser = list(riser_nodes.values())[0] if riser_nodes else None
            
            if stabilo_riser:
                # Generate stabilo attachment points on the last cells
                stabilo_nodes = []
                for i in range(stabilo_count):
                    # Distribute points on the outermost cells
                    cell_no = self.half_cell_num - 1 - i
                    if cell_no < 0:
                        cell_no = 0
                    
                    stabilo = UpperNode2D(
                        cell_no=cell_no,
                        rib_pos=config["stabilo_position"],
                        cell_pos=0,
                        force=1.0,
                        name=f"S{i + 1}",
                        layer="S",
                    )
                    stabilo_nodes.append(stabilo)
                
                # Calculate basse position (average of all stabilo points)
                stab_avg_pos = self._calc_batch_position(stabilo_nodes, 0)
                riser_pos = stabilo_riser.pos_2D if hasattr(stabilo_riser, 'pos_2D') else [0, 0]
                
                # Basse node between riser and all stabilo points
                # Position it proportionally based on basses vs hautes lengths
                total_stab_height = config["basses_length"] + config["hautes_length"]
                basse_ratio = config["basses_length"] / total_stab_height if total_stab_height > 0 else 0.6
                basse_y = riser_pos[1] + (stab_avg_pos[1] - riser_pos[1]) * basse_ratio
                
                stab_basse = BatchNode2D(
                    pos_2D=[stab_avg_pos[0], basse_y],
                    name="S_basse",
                    layer="S",
                )
                
                # Connect basse to riser
                lines.append(Line2D(
                    lower_node=stabilo_riser,
                    upper_node=stab_basse,
                    target_length=config["basses_length"],
                    line_type=config["line_type_name"],
                    layer="S",
                    name="S_basse",
                ))
                
                # Connect each stabilo point (hautes) to the single basse
                for i, stabilo in enumerate(stabilo_nodes):
                    lines.append(Line2D(
                        lower_node=stab_basse,
                        upper_node=stabilo,
                        target_length=config["hautes_length"],
                        line_type=config["line_type_name"],
                        layer="S",
                        name=f"S{i + 1}",
                    ))
        
        return LineSet2D(lines)
    
    def _generate_upper_nodes(self, line_type, config):
        """Generate upper attachment points."""
        nodes = []
        start = config["start_cell"]
        interval = config["interval"]
        position = config["position"]
        
        idx = 1
        for cell_no in range(start, self.half_cell_num, interval):
            # Ensure cell_no is valid
            if cell_no >= self.half_cell_num:
                break
            node = UpperNode2D(
                cell_no=cell_no,
                rib_pos=position,
                cell_pos=0,
                force=1.0,
                name=f"{line_type}{idx}",
                layer=line_type,
            )
            nodes.append(node)
            idx += 1
        
        return nodes
    
    def _generate_grouped_architecture(self, upper_nodes, riser_node, group_patterns,
                                       basses_length, inter_length, hautes_length, line_type_name, layer):
        """
        Generate architecture with groups.
        Each group = 1 basse connected to riser.
        Pattern defines how hautes connect to basse (via inter if needed).
        """
        lines = []
        
        if not upper_nodes:
            return lines
        
        # Get riser position for reference
        riser_pos = riser_node.pos_2D if hasattr(riser_node, 'pos_2D') else [0, 0]
        
        # Total number of groups for spacing calculation
        total_groups = 0
        temp_idx = 0
        for g in range(len(upper_nodes)):
            pattern = group_patterns[total_groups % len(group_patterns)]
            nodes_per = self._calc_nodes_for_pattern(pattern)
            if temp_idx >= len(upper_nodes):
                break
            temp_idx += nodes_per
            total_groups += 1
        
        node_idx = 0
        group_idx = 0
        
        while node_idx < len(upper_nodes):
            # Get pattern for this group (cycle through patterns)
            pattern = group_patterns[group_idx % len(group_patterns)]
            
            # Calculate how many nodes this pattern consumes
            nodes_per_group = self._calc_nodes_for_pattern(pattern)
            
            # Get nodes for this group
            group_nodes = upper_nodes[node_idx:node_idx + nodes_per_group]
            
            if not group_nodes:
                break
            
            # Calculate basse position:
            # X: average of upper nodes X positions  
            # Y: positioned between riser and upper nodes, proportional to basses_length
            upper_avg_pos = self._calc_batch_position(group_nodes, 0)
            
            # Interpolate X position: spread from riser X toward upper nodes X
            # This creates a nice fan-out effect
            if total_groups > 1:
                group_spread = (group_idx / (total_groups - 1)) - 0.5  # -0.5 to 0.5
            else:
                group_spread = 0
            
            basse_x = upper_avg_pos[0]  # Use upper nodes X position
            
            # Y position: between riser and upper nodes, scaled by basses_length ratio
            # Total line length = basses + inter + hautes
            total_line_height = basses_length + inter_length + hautes_length
            basse_y_ratio = basses_length / total_line_height if total_line_height > 0 else 0.33
            basse_y = riser_pos[1] + (upper_avg_pos[1] - riser_pos[1]) * basse_y_ratio
            
            basse_node = BatchNode2D(
                pos_2D=[basse_x, basse_y],
                name=f"{layer}{group_idx + 1}_basse",
                layer=layer,
            )
            
            # Connect basse to riser
            lines.append(Line2D(
                lower_node=riser_node,
                upper_node=basse_node,
                target_length=basses_length,
                line_type=line_type_name,
                layer=layer,
                name=f"{layer}{group_idx + 1}",
            ))
            
            # Generate architecture within group (hautes connect via inter to basse)
            group_lines = self._generate_group_architecture(
                group_nodes, basse_node, pattern, inter_length, hautes_length, line_type_name, layer, group_idx
            )
            lines.extend(group_lines)
            
            node_idx += len(group_nodes)
            group_idx += 1
        
        return lines
    
    def _calc_nodes_for_pattern(self, pattern):
        """Calculate how many upper nodes a pattern consumes."""
        if pattern == [1]:
            return 1
        
        # Pattern [2] = 2 nodes
        # Pattern [2, 2] = 2*2 = 4 nodes
        # Pattern [3] = 3 nodes
        # Pattern [3, 2] = 3*2 = 6 nodes
        result = 1
        for p in pattern:
            result *= p
        return result
    
    def _generate_group_architecture(self, nodes, basse_node, pattern, 
                                    inter_length, hautes_length, line_type_name, layer, group_idx):
        """
        Generate lines within a group.
        - hautes_length: length of lines connecting to wing (uppermost)
        - inter_length: length of intermediate lines
        """
        lines = []
        
        # Get basse position for reference
        basse_pos = basse_node.pos_2D if hasattr(basse_node, 'pos_2D') else [0, 0]
        
        if pattern == [1] or len(nodes) == 1:
            # Direct connection: use hautes_length (direct basse to wing)
            for i, node in enumerate(nodes):
                lines.append(Line2D(
                    lower_node=basse_node,
                    upper_node=node,
                    target_length=hautes_length,  # Direct to wing = hautes
                    line_type=line_type_name,
                    layer=layer,
                    name=node.name,
                ))
            return lines
        
        if len(pattern) == 1:
            # Simple pattern like 2:1 or 3:1: hautes go directly from basse to wing
            merge = pattern[0]
            for i, node in enumerate(nodes):
                lines.append(Line2D(
                    lower_node=basse_node,
                    upper_node=node,
                    target_length=hautes_length,  # Direct to wing = hautes
                    line_type=line_type_name,
                    layer=layer,
                    name=node.name,
                ))
            return lines
        
        # Multi-level pattern like 2:2:1
        # First level connects to upper nodes (hautes), subsequent levels use inter
        current_nodes = list(nodes)
        total_levels = len(pattern) - 1
        
        for level, merge in enumerate(pattern[:-1]):  # All but last (which connects to basse)
            next_nodes = []
            
            for i in range(0, len(current_nodes), merge):
                group = current_nodes[i:i + merge]
                if len(group) == 1:
                    next_nodes.append(group[0])
                    continue
                
                # Calculate inter position between basse and upper nodes
                upper_avg_pos = self._calc_batch_position(group, level)
                
                # Position inter node proportionally between basse and upper
                # Earlier levels are closer to upper nodes
                level_ratio = (level + 1) / (total_levels + 1)  # 0.33, 0.5, 0.66...
                inter_x = upper_avg_pos[0]  # Keep same X as upper nodes
                inter_y = basse_pos[1] + (upper_avg_pos[1] - basse_pos[1]) * (1 - level_ratio * 0.5)
                
                inter_node = BatchNode2D(
                    pos_2D=[inter_x, inter_y],
                    name=f"{layer}{group_idx + 1}_i{level}_{i // merge}",
                    layer=layer,
                )
                
                # First level (level 0) connects to wing = hautes_length
                # Other levels use inter_length
                line_length = hautes_length if level == 0 else inter_length
                
                for node in group:
                    lines.append(Line2D(
                        lower_node=inter_node,
                        upper_node=node,
                        target_length=line_length,
                        line_type=line_type_name,
                        layer=layer,
                        name=f"{node.name}_h",
                    ))
                
                next_nodes.append(inter_node)
            
            current_nodes = next_nodes
        
        # Connect remaining inter nodes to basse with inter_length
        for node in current_nodes:
            lines.append(Line2D(
                lower_node=basse_node,
                upper_node=node,
                target_length=inter_length,
                line_type=line_type_name,
                layer=layer,
                name=f"{layer}{group_idx + 1}_to_basse",
            ))
        
        return lines
    
    def _calc_batch_position(self, nodes, level):
        """Calculate average 2D position for batch node."""
        positions = []
        
        for n in nodes:
            if isinstance(n, UpperNode2D):
                try:
                    cell = min(n.cell_no, self.half_cell_num - 1)
                    pos = list(self.parametric_glider.shape[cell, n.rib_pos])
                    positions.append(pos)
                except:
                    positions.append([n.cell_no * 0.5, 0])
            elif hasattr(n, 'pos_2D'):
                positions.append(list(n.pos_2D))
        
        if positions:
            return [
                sum(p[0] for p in positions) / len(positions),
                sum(p[1] for p in positions) / len(positions),
            ]
        return [0, 0]
