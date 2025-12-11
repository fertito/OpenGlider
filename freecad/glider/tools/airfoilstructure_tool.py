"""
Airfoil Structure Tool for OpenGlider FreeCAD workbench.

This tool allows configuration of structural elements on rib profiles:
- Rod sleeves (fourreaux de joncs) for extrados and intrados
- Attachment reinforcements with half-moon load distribution rods (suspended ribs only)
"""

from .tools import BaseTool, Line_old
import FreeCADGui as Gui
from PySide import QtCore, QtGui
from openglider.glider.rib import RodSleeve, AttachmentReinforcement
import numpy as np
from pivy import coin
import os


class AirfoilStructureTool(BaseTool):
    widget_name = "Airfoil Structure"

    def __init__(self, obj):
        super(AirfoilStructureTool, self).__init__(obj)

        # Profile type selector
        self.ribTypeComboBox = QtGui.QComboBox(self.base_widget)
        
        # === Extrados Sleeve Group ===
        self.extradosGroupBox = QtGui.QGroupBox("Extrados Rod Sleeve", self.base_widget)
        self.extradosLayout = QtGui.QFormLayout(self.extradosGroupBox)
        
        self.extradosEnabledCheckBox = QtGui.QCheckBox("Enable", self.extradosGroupBox)
        self.extradosWidthSpinBox = QtGui.QDoubleSpinBox(self.extradosGroupBox)
        self.extradosOffsetSpinBox = QtGui.QDoubleSpinBox(self.extradosGroupBox)
        self.extradosStartSpinBox = QtGui.QDoubleSpinBox(self.extradosGroupBox)
        self.extradosEndSpinBox = QtGui.QDoubleSpinBox(self.extradosGroupBox)
        # Leading edge termination
        self.extradosLeAngleSpinBox = QtGui.QDoubleSpinBox(self.extradosGroupBox)
        self.extradosLeLengthSpinBox = QtGui.QDoubleSpinBox(self.extradosGroupBox)
        # Trailing edge termination
        self.extradosTeAngleSpinBox = QtGui.QDoubleSpinBox(self.extradosGroupBox)
        self.extradosTeLengthSpinBox = QtGui.QDoubleSpinBox(self.extradosGroupBox)
        
        # === Intrados Sleeve Group ===
        self.intradosGroupBox = QtGui.QGroupBox("Intrados Rod Sleeve", self.base_widget)
        self.intradosLayout = QtGui.QFormLayout(self.intradosGroupBox)
        
        self.intradosEnabledCheckBox = QtGui.QCheckBox("Enable", self.intradosGroupBox)
        self.intradosWidthSpinBox = QtGui.QDoubleSpinBox(self.intradosGroupBox)
        self.intradosOffsetSpinBox = QtGui.QDoubleSpinBox(self.intradosGroupBox)
        self.intradosStartSpinBox = QtGui.QDoubleSpinBox(self.intradosGroupBox)
        self.intradosEndSpinBox = QtGui.QDoubleSpinBox(self.intradosGroupBox)
        # Leading edge termination
        self.intradosLeAngleSpinBox = QtGui.QDoubleSpinBox(self.intradosGroupBox)
        self.intradosLeLengthSpinBox = QtGui.QDoubleSpinBox(self.intradosGroupBox)
        # Trailing edge termination
        self.intradosTeAngleSpinBox = QtGui.QDoubleSpinBox(self.intradosGroupBox)
        self.intradosTeLengthSpinBox = QtGui.QDoubleSpinBox(self.intradosGroupBox)
        
        
        # === Attachment Reinforcement Group (only for suspended) ===
        self.reinforcementGroupBox = QtGui.QGroupBox("Attachment Reinforcements", self.base_widget)
        self.reinforcementLayout = QtGui.QFormLayout(self.reinforcementGroupBox)
        
        self.reinforcementEnabledCheckBox = QtGui.QCheckBox("Enable Reinforcements", self.reinforcementGroupBox)
        self.reinforcementEnabledCheckBox.setChecked(True)  # Enabled by default
        self.reinforcementApplyAllCheckBox = QtGui.QCheckBox("Apply same parameters to all", self.reinforcementGroupBox)
        self.reinforcementApplyAllCheckBox.setChecked(False)  # Individual config by default
        
        self.reinforcementStack = QtGui.QStackedWidget(self.reinforcementGroupBox)
        
        # Master Config
        self.masterConfig = ReinforcementConfigWidget(self.reinforcementGroupBox)
        self.reinforcementStack.addWidget(self.masterConfig)
        
        # Tabbed Config
        self.reinforcementTabs = QtGui.QTabWidget(self.reinforcementGroupBox)
        self.reinforcementStack.addWidget(self.reinforcementTabs)
        self.reinforcement_widgets = []

        self.applyButton = QtGui.QPushButton("Apply", self.base_widget)

        self.preview_root = coin.SoSeparator()
        self.setup_widget()
        self.setup_pivy()

    def setup_widget(self):
        self.ribTypeComboBox.addItems(["Non-Suspended", "Suspended"])
        self.layout.addRow("Profile Type", self.ribTypeComboBox)
        
        # --- Configure Extrados Sleeve ---
        self.extradosLayout.addRow(self.extradosEnabledCheckBox)
        
        self.extradosWidthSpinBox.setSingleStep(1.0)
        self.extradosWidthSpinBox.setDecimals(1)
        self.extradosWidthSpinBox.setSuffix(" mm")
        self.extradosWidthSpinBox.setRange(1.0, 50.0)
        self.extradosWidthSpinBox.setValue(15.0)
        self.extradosLayout.addRow("Width", self.extradosWidthSpinBox)
        
        self.extradosOffsetSpinBox.setSingleStep(0.5)
        self.extradosOffsetSpinBox.setDecimals(1)
        self.extradosOffsetSpinBox.setSuffix(" mm")
        self.extradosOffsetSpinBox.setRange(0.0, 20.0)
        self.extradosOffsetSpinBox.setValue(5.0)
        self.extradosLayout.addRow("Offset", self.extradosOffsetSpinBox)
        
        self.extradosStartSpinBox.setSingleStep(1.0)
        self.extradosStartSpinBox.setDecimals(1)
        self.extradosStartSpinBox.setSuffix(" %")
        self.extradosStartSpinBox.setRange(0.0, 100.0)
        self.extradosStartSpinBox.setValue(0.0)
        self.extradosLayout.addRow("Start (% chord)", self.extradosStartSpinBox)
        
        self.extradosEndSpinBox.setSingleStep(1.0)
        self.extradosEndSpinBox.setDecimals(1)
        self.extradosEndSpinBox.setSuffix(" %")
        self.extradosEndSpinBox.setRange(0.0, 100.0)
        self.extradosEndSpinBox.setValue(71.0)
        self.extradosLayout.addRow("End (% chord)", self.extradosEndSpinBox)
        
        # Leading edge termination
        self.extradosLayout.addRow(QtGui.QLabel("<b>Leading Edge</b>"))
        self.extradosLeAngleSpinBox.setSingleStep(5.0)
        self.extradosLeAngleSpinBox.setDecimals(0)
        self.extradosLeAngleSpinBox.setSuffix(" °")
        self.extradosLeAngleSpinBox.setRange(0.0, 360.0)
        self.extradosLeAngleSpinBox.setValue(350.0)  # Default: 350 deg
        self.extradosLayout.addRow("LE Angle", self.extradosLeAngleSpinBox)
        
        self.extradosLeLengthSpinBox.setSingleStep(5.0)
        self.extradosLeLengthSpinBox.setDecimals(0)
        self.extradosLeLengthSpinBox.setSuffix(" mm")
        self.extradosLeLengthSpinBox.setRange(10.0, 200.0)
        self.extradosLeLengthSpinBox.setValue(125.0)
        self.extradosLayout.addRow("LE Length", self.extradosLeLengthSpinBox)
        
        # Trailing edge termination
        self.extradosLayout.addRow(QtGui.QLabel("<b>Trailing Edge</b>"))
        self.extradosTeAngleSpinBox.setSingleStep(5.0)
        self.extradosTeAngleSpinBox.setDecimals(0)
        self.extradosTeAngleSpinBox.setSuffix(" °")
        self.extradosTeAngleSpinBox.setRange(0.0, 360.0)
        self.extradosTeAngleSpinBox.setValue(325.0)  # Default: 325 deg
        self.extradosLayout.addRow("TE Angle", self.extradosTeAngleSpinBox)
        
        self.extradosTeLengthSpinBox.setSingleStep(5.0)
        self.extradosTeLengthSpinBox.setDecimals(0)
        self.extradosTeLengthSpinBox.setSuffix(" mm")
        self.extradosTeLengthSpinBox.setRange(10.0, 200.0)
        self.extradosTeLengthSpinBox.setValue(75.0)
        self.extradosLayout.addRow("TE Length", self.extradosTeLengthSpinBox)

        
        self.layout.addRow(self.extradosGroupBox)
        
        # --- Configure Intrados Sleeve ---
        self.intradosLayout.addRow(self.intradosEnabledCheckBox)
        
        self.intradosWidthSpinBox.setSingleStep(1.0)
        self.intradosWidthSpinBox.setDecimals(1)
        self.intradosWidthSpinBox.setSuffix(" mm")
        self.intradosWidthSpinBox.setRange(1.0, 50.0)
        self.intradosWidthSpinBox.setValue(15.0)
        self.intradosLayout.addRow("Width", self.intradosWidthSpinBox)
        
        self.intradosOffsetSpinBox.setSingleStep(0.5)
        self.intradosOffsetSpinBox.setDecimals(1)
        self.intradosOffsetSpinBox.setSuffix(" mm")
        self.intradosOffsetSpinBox.setRange(0.0, 20.0)
        self.intradosOffsetSpinBox.setValue(5.0)
        self.intradosLayout.addRow("Offset", self.intradosOffsetSpinBox)
        
        self.intradosStartSpinBox.setSingleStep(1.0)
        self.intradosStartSpinBox.setDecimals(1)
        self.intradosStartSpinBox.setSuffix(" %")
        self.intradosStartSpinBox.setRange(0.0, 100.0)
        self.intradosStartSpinBox.setValue(6.0)  # Start 6%
        self.intradosLayout.addRow("Start (% chord)", self.intradosStartSpinBox)
        
        self.intradosEndSpinBox.setSingleStep(1.0)
        self.intradosEndSpinBox.setDecimals(1)
        self.intradosEndSpinBox.setSuffix(" %")
        self.intradosEndSpinBox.setRange(0.0, 100.0)
        self.intradosEndSpinBox.setValue(50.0) # End 50%
        self.intradosLayout.addRow("End (% chord)", self.intradosEndSpinBox)
        
        # Leading edge termination
        self.intradosLayout.addRow(QtGui.QLabel("<b>Leading Edge</b>"))
        self.intradosLeAngleSpinBox.setSingleStep(5.0)
        self.intradosLeAngleSpinBox.setDecimals(0)
        self.intradosLeAngleSpinBox.setSuffix(" °")
        self.intradosLeAngleSpinBox.setRange(0.0, 360.0)
        self.intradosLeAngleSpinBox.setValue(100.0)  # Default: 100 deg
        self.intradosLayout.addRow("LE Angle", self.intradosLeAngleSpinBox)
        
        self.intradosLeLengthSpinBox.setSingleStep(5.0)
        self.intradosLeLengthSpinBox.setDecimals(0)
        self.intradosLeLengthSpinBox.setSuffix(" mm")
        self.intradosLeLengthSpinBox.setRange(10.0, 200.0)
        self.intradosLeLengthSpinBox.setValue(100.0)
        self.intradosLayout.addRow("LE Length", self.intradosLeLengthSpinBox)
        
        # Trailing edge termination
        self.intradosLayout.addRow(QtGui.QLabel("<b>Trailing Edge</b>"))
        self.intradosTeAngleSpinBox.setSingleStep(5.0)
        self.intradosTeAngleSpinBox.setDecimals(0)
        self.intradosTeAngleSpinBox.setSuffix(" °")
        self.intradosTeAngleSpinBox.setRange(0.0, 360.0)
        self.intradosTeAngleSpinBox.setValue(20.0)  # Default: 20 deg
        self.intradosLayout.addRow("TE Angle", self.intradosTeAngleSpinBox)
        
        self.intradosTeLengthSpinBox.setSingleStep(5.0)
        self.intradosTeLengthSpinBox.setDecimals(0)
        self.intradosTeLengthSpinBox.setSuffix(" mm")
        self.intradosTeLengthSpinBox.setRange(10.0, 200.0)
        self.intradosTeLengthSpinBox.setValue(90.0)
        self.intradosLayout.addRow("TE Length", self.intradosTeLengthSpinBox)
        
        self.layout.addRow(self.intradosGroupBox)
        
        # --- Configure Attachment Reinforcements ---
        self.reinforcementLayout.addRow(self.reinforcementEnabledCheckBox)
        

        self.reinforcementLayout.addRow(self.reinforcementApplyAllCheckBox)
        self.reinforcementLayout.addRow(self.reinforcementStack)
        
        self.layout.addRow(self.reinforcementGroupBox)
        
        # Apply button
        button_layout = QtGui.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.applyButton)
        self.layout.addRow(button_layout)

        # Load initial values
        self.update_form_from_glider_data()

        # Connections - Extrados
        self.extradosEnabledCheckBox.stateChanged.connect(self.update_preview)
        self.extradosWidthSpinBox.valueChanged.connect(self.update_preview)
        self.extradosOffsetSpinBox.valueChanged.connect(self.update_preview)
        self.extradosStartSpinBox.valueChanged.connect(self.update_preview)
        self.extradosEndSpinBox.valueChanged.connect(self.update_preview)
        self.extradosLeAngleSpinBox.valueChanged.connect(self.update_preview)
        self.extradosLeLengthSpinBox.valueChanged.connect(self.update_preview)
        self.extradosTeAngleSpinBox.valueChanged.connect(self.update_preview)
        self.extradosTeLengthSpinBox.valueChanged.connect(self.update_preview)
        
        # Connections - Intrados
        self.intradosEnabledCheckBox.stateChanged.connect(self.update_preview)
        self.intradosWidthSpinBox.valueChanged.connect(self.update_preview)
        self.intradosOffsetSpinBox.valueChanged.connect(self.update_preview)
        self.intradosStartSpinBox.valueChanged.connect(self.update_preview)
        self.intradosEndSpinBox.valueChanged.connect(self.update_preview)
        self.intradosLeAngleSpinBox.valueChanged.connect(self.update_preview)
        self.intradosLeLengthSpinBox.valueChanged.connect(self.update_preview)
        self.intradosTeAngleSpinBox.valueChanged.connect(self.update_preview)
        self.intradosTeLengthSpinBox.valueChanged.connect(self.update_preview)
        
        # Connections - Reinforcements
        self.reinforcementEnabledCheckBox.stateChanged.connect(self.update_preview)
        self.reinforcementApplyAllCheckBox.stateChanged.connect(self.on_reinforcement_mode_change)
        self.reinforcementApplyAllCheckBox.stateChanged.connect(self.update_preview)
        # Master config signals are connected in ReinforcementConfigWidget
        self.masterConfig.changed.connect(self.update_preview)
        
        self.ribTypeComboBox.currentIndexChanged.connect(self.on_rib_type_change)
        self.applyButton.clicked.connect(self.accept)

        # Set initial visibility of reinforcement group (only for suspended)
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        self.reinforcementGroupBox.setVisible(is_suspended)

    def setup_pivy(self):
        self.task_separator.addChild(self.preview_root)
        self.update_preview()
        Gui.SendMsgToActiveView("ViewFit")

    def get_representative_rib(self, suspended=False):
        glider_instance = self.obj.Proxy.getGliderInstance()
        suspended_ribs = {att.rib for att in glider_instance.attachment_points if hasattr(att, 'rib')}
        for rib in glider_instance.ribs:
            if suspended == (rib in suspended_ribs):
                return rib
        return None
    
    def get_valid_attachment_points(self, rib):
        """Get attachment points < 90% chord."""
        glider_instance = self.obj.Proxy.getGliderInstance()
        all_aps = glider_instance.get_rib_attachment_points(rib)
        # Filter points by position (assuming rib_pos is normalized chord position 0-1)
        valid_aps = [ap for ap in all_aps if ap.rib_pos <= 0.90]
        # Sort by position just in case
        valid_aps.sort(key=lambda x: x.rib_pos)
        return valid_aps

    def on_rib_type_change(self, new_index):
        previous_index = 1 - new_index
        # Save data for previous state
        self.update_glider_data(is_suspended=previous_index == 1)
        
        is_suspended = new_index == 1
        self.reinforcementGroupBox.setVisible(is_suspended)
        
        # Reload data for new state
        self.update_form_from_glider_data()
        self.update_preview(force=True)

    def on_reinforcement_mode_change(self, state):
        """Switch between Master and Tabbed view."""
        if self.reinforcementApplyAllCheckBox.isChecked():
            self.reinforcementStack.setCurrentWidget(self.masterConfig)
        else:
            self.reinforcementStack.setCurrentWidget(self.reinforcementTabs)

    def update_reinforcement_tabs(self, valid_aps):
        """Rebuild tabs based on current valid attachment points."""
        # Clear existing tabs (except we might want to preserve values if reloading same rib?)
        # For now, simplistic approach: rebuild.
        # Ideally we load values from parametric_glider after rebuilding.
        
        self.reinforcementTabs.clear()
        self.reinforcement_widgets = []
        
        for i, ap in enumerate(valid_aps):
            label = "AP {} ({:.1f}%)".format(i + 1, ap.rib_pos * 100)
            widget = ReinforcementConfigWidget()
            widget.changed.connect(self.update_preview)
            self.reinforcementTabs.addTab(widget, label)
            self.reinforcement_widgets.append(widget)

    def update_preview(self, *args, **kwargs):
        self.preview_root.removeAllChildren()

        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        rib = self.get_representative_rib(suspended=is_suspended)
        if not rib:
            return

        # Draw profile outline - scaled by chord
        profile_points = [p * rib.chord for p in rib.profile_2d.data]
        profile_3d = [[p[0], p[1], 0] for p in profile_points]
        self.preview_root.addChild(Line_old(profile_3d + [profile_3d[0]], width=2).object)
        
        # Visualizing attachment points (red dots) if suspended
        valid_aps = []
        if is_suspended:
            valid_aps = self.get_valid_attachment_points(rib)
            for ap in valid_aps:
                self._draw_attachment_point_marker(rib, ap.rib_pos)

        # Draw extrados sleeve if enabled
        if self.extradosEnabledCheckBox.isChecked():
            sleeve = self._create_extrados_sleeve()
            self._draw_sleeve(sleeve, rib, color='blue')

        # Draw intrados sleeve if enabled
        if self.intradosEnabledCheckBox.isChecked():
            sleeve = self._create_intrados_sleeve()
            self._draw_sleeve(sleeve, rib, color='green')

        # Draw attachment reinforcements if enabled and suspended
        if is_suspended and self.reinforcementEnabledCheckBox.isChecked():
            apply_all = self.reinforcementApplyAllCheckBox.isChecked()
            
            for i, ap in enumerate(valid_aps):
                # Get config
                if apply_all:
                    config = self.masterConfig.get_values()
                else:
                    # Individual config
                    if i < len(self.reinforcement_widgets):
                        config = self.reinforcement_widgets[i].get_values()
                    else:
                        continue # Should not happen if tabs aligned with valid_aps
                
                if config['enabled']:
                    reinforcement = self._create_reinforcement(ap.rib_pos, config)
                    self._draw_reinforcement(reinforcement, rib)

    def _create_extrados_sleeve(self):
        """Create a RodSleeve from current extrados UI values."""
        return RodSleeve(
            surface='extrados',
            width=self.extradosWidthSpinBox.value() / 1000.0,
            offset=self.extradosOffsetSpinBox.value() / 1000.0,
            start_chord=self.extradosStartSpinBox.value() / 100.0,
            end_chord=self.extradosEndSpinBox.value() / 100.0,
            le_angle=self.extradosLeAngleSpinBox.value(),
            te_angle=self.extradosTeAngleSpinBox.value(),
            le_length=self.extradosLeLengthSpinBox.value() / 1000.0,
            te_length=self.extradosTeLengthSpinBox.value() / 1000.0,
        )

    def _create_intrados_sleeve(self):
        """Create a RodSleeve from current intrados UI values."""
        return RodSleeve(
            surface='intrados',
            width=self.intradosWidthSpinBox.value() / 1000.0,
            offset=self.intradosOffsetSpinBox.value() / 1000.0,
            start_chord=self.intradosStartSpinBox.value() / 100.0,
            end_chord=self.intradosEndSpinBox.value() / 100.0,
            le_angle=self.intradosLeAngleSpinBox.value(),
            te_angle=self.intradosTeAngleSpinBox.value(),
            le_length=self.intradosLeLengthSpinBox.value() / 1000.0,
            te_length=self.intradosTeLengthSpinBox.value() / 1000.0,
        )

    def _create_reinforcement(self, position, config, name=""):
        """Create an AttachmentReinforcement from config values."""
        return AttachmentReinforcement(
            position=position,
            surface_offset=config.get('surface_offset', 0.003),
            halfmoon_radius=config['halfmoon_radius'],
            rod_enabled=config.get('rod_enabled', True),
            rod_offset=config['rod_offset'],
            rod_width=config['rod_width'],
            rod_end_offset=config.get('rod_end_offset', 10.0),
            name=name,
        )


    def _draw_sleeve(self, sleeve, rib, color='blue'):
        """Draw a rod sleeve preview (main sleeve only, no terminations for now)."""
        try:
            # Just draw the main sleeve without the problematic terminations
            inner_points, outer_points = sleeve.get_sleeve_points(rib)
            
            if inner_points and outer_points:
                inner_3d = [[p[0], p[1], 0] for p in inner_points]
                self.preview_root.addChild(Line_old(inner_3d, color=color, width=2).object)
                
                outer_3d = [[p[0], p[1], 0] for p in outer_points]
                self.preview_root.addChild(Line_old(outer_3d, color=color, width=2).object)
                
                # Draw end caps
                if len(inner_points) > 0 and len(outer_points) > 0:
                    start_cap = [[inner_points[0][0], inner_points[0][1], 0],
                                 [outer_points[0][0], outer_points[0][1], 0]]
                    self.preview_root.addChild(Line_old(start_cap, color=color, width=1).object)
                    
                    end_cap = [[inner_points[-1][0], inner_points[-1][1], 0],
                               [outer_points[-1][0], outer_points[-1][1], 0]]
                    self.preview_root.addChild(Line_old(end_cap, color=color, width=1).object)
        except Exception as e:
            print(f"Error drawing sleeve: {e}")

    def _draw_attachment_point_marker(self, rib, position):
        """Draw a red marker at the attachment point position."""
        profile = rib.profile_2d
        # Get point from profile coordinate system
        idx = profile(position)
        center_point = profile[idx] * rib.chord
        
        # Create a small diamond marker
        size = 0.005  # 5mm visual size
        center_3d = np.array([center_point[0], center_point[1], 0])
        
        marker_points = [
            center_3d + np.array([size, 0, 0]),
            center_3d + np.array([0, size, 0]),
            center_3d + np.array([-size, 0, 0]),
            center_3d + np.array([0, -size, 0]),
            center_3d + np.array([size, 0, 0])
        ]
        
        self.preview_root.addChild(Line_old(marker_points, color='red', width=3).object)

    def _draw_reinforcement(self, reinforcement, rib):
        """Draw an attachment reinforcement preview."""
        try:
            flat = reinforcement.get_flattened(rib)
            
            # Draw half-moon fabric reinforcement in yellow
            halfmoon_points = [[p[0], p[1], 0] for p in flat['halfmoon'].data]
            if halfmoon_points:
                self.preview_root.addChild(Line_old(halfmoon_points, color='yellow', width=2).object)
            
            # Draw rod sleeve in red
            rod_points = [[p[0], p[1], 0] for p in flat['rod_sleeve'].data]
            if rod_points:
                self.preview_root.addChild(Line_old(rod_points, color='red', width=2).object)
        except Exception as e:
            print(f"Error drawing reinforcement: {e}")

    def update_form_from_glider_data(self):
        """Load values from parametric glider into UI."""
        pg = self.parametric_glider
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        suffix = "_s" if is_suspended else "_ns"

        widgets = [
            self.extradosEnabledCheckBox, self.extradosWidthSpinBox, self.extradosOffsetSpinBox,
            self.extradosStartSpinBox, self.extradosEndSpinBox,
            self.extradosLeAngleSpinBox, self.extradosLeLengthSpinBox,
            self.extradosTeAngleSpinBox, self.extradosTeLengthSpinBox,
            self.intradosEnabledCheckBox, self.intradosWidthSpinBox, self.intradosOffsetSpinBox,
            self.intradosStartSpinBox, self.intradosEndSpinBox,
            self.intradosLeAngleSpinBox, self.intradosLeLengthSpinBox,
            self.intradosTeAngleSpinBox, self.intradosTeLengthSpinBox,
        ]

        for w in widgets:
            w.blockSignals(True)

        # Load extrados sleeve values
        self.extradosEnabledCheckBox.setChecked(getattr(pg, f'extrados_sleeve_enabled{suffix}', True))
        self.extradosWidthSpinBox.setValue(getattr(pg, f'extrados_sleeve_width{suffix}', 0.015) * 1000.0)
        self.extradosOffsetSpinBox.setValue(getattr(pg, f'extrados_sleeve_offset{suffix}', 0.005) * 1000.0)
        self.extradosStartSpinBox.setValue(getattr(pg, f'extrados_sleeve_start{suffix}', 0.0) * 100.0)
        self.extradosEndSpinBox.setValue(getattr(pg, f'extrados_sleeve_end{suffix}', 0.71) * 100.0)
        self.extradosLeAngleSpinBox.setValue(getattr(pg, f'extrados_sleeve_le_angle{suffix}', 350.0))
        self.extradosLeLengthSpinBox.setValue(getattr(pg, f'extrados_sleeve_le_length{suffix}', 0.125) * 1000.0)
        self.extradosTeAngleSpinBox.setValue(getattr(pg, f'extrados_sleeve_te_angle{suffix}', 325.0))
        self.extradosTeLengthSpinBox.setValue(getattr(pg, f'extrados_sleeve_te_length{suffix}', 0.075) * 1000.0)

        # Load intrados sleeve values
        self.intradosEnabledCheckBox.setChecked(getattr(pg, f'intrados_sleeve_enabled{suffix}', True))
        self.intradosWidthSpinBox.setValue(getattr(pg, f'intrados_sleeve_width{suffix}', 0.015) * 1000.0)
        self.intradosOffsetSpinBox.setValue(getattr(pg, f'intrados_sleeve_offset{suffix}', 0.005) * 1000.0)
        self.intradosStartSpinBox.setValue(getattr(pg, f'intrados_sleeve_start{suffix}', 0.06) * 100.0)
        self.intradosEndSpinBox.setValue(getattr(pg, f'intrados_sleeve_end{suffix}', 0.50) * 100.0)
        self.intradosLeAngleSpinBox.setValue(getattr(pg, f'intrados_sleeve_le_angle{suffix}', 100.0))
        self.intradosLeLengthSpinBox.setValue(getattr(pg, f'intrados_sleeve_le_length{suffix}', 0.100) * 1000.0)
        self.intradosTeAngleSpinBox.setValue(getattr(pg, f'intrados_sleeve_te_angle{suffix}', 20.0))
        self.intradosTeLengthSpinBox.setValue(getattr(pg, f'intrados_sleeve_te_length{suffix}', 0.090) * 1000.0)

        for w in widgets:
            w.blockSignals(False)

        # Load reinforcement values (only for suspended)
        if is_suspended:
            # Rebuild tabs first
            rib = self.get_representative_rib(suspended=True)
            if rib:
                valid_aps = self.get_valid_attachment_points(rib)
                self.update_reinforcement_tabs(valid_aps)
            
            # Global Enable/ApplyAll
            self.reinforcementEnabledCheckBox.setChecked(getattr(pg, 'reinforcement_enabled_s', True))
            apply_all = getattr(pg, 'reinforcement_apply_all_s', True)
            self.reinforcementApplyAllCheckBox.setChecked(apply_all)
            self.on_reinforcement_mode_change(None) # Update stack

            # Load Master Config
            master_config = getattr(pg, 'reinforcement_master_s', {})
            self.masterConfig.set_values(master_config)
            
            # Load Individual Configs
            configs = getattr(pg, 'reinforcement_configs_s', [])
            for i, widget in enumerate(self.reinforcement_widgets):
                if i < len(configs):
                    widget.set_values(configs[i])
                else:
                    pass

    def update_glider_data(self, is_suspended):
        """Save UI values to parametric glider."""
        pg = self.parametric_glider
        suffix = "_s" if is_suspended else "_ns"

        # Save extrados sleeve values
        setattr(pg, f'extrados_sleeve_enabled{suffix}', self.extradosEnabledCheckBox.isChecked())
        setattr(pg, f'extrados_sleeve_width{suffix}', self.extradosWidthSpinBox.value() / 1000.0)
        setattr(pg, f'extrados_sleeve_offset{suffix}', self.extradosOffsetSpinBox.value() / 1000.0)
        setattr(pg, f'extrados_sleeve_start{suffix}', self.extradosStartSpinBox.value() / 100.0)
        setattr(pg, f'extrados_sleeve_end{suffix}', self.extradosEndSpinBox.value() / 100.0)
        setattr(pg, f'extrados_sleeve_le_angle{suffix}', self.extradosLeAngleSpinBox.value())
        setattr(pg, f'extrados_sleeve_le_length{suffix}', self.extradosLeLengthSpinBox.value() / 1000.0)
        setattr(pg, f'extrados_sleeve_te_angle{suffix}', self.extradosTeAngleSpinBox.value())
        setattr(pg, f'extrados_sleeve_te_length{suffix}', self.extradosTeLengthSpinBox.value() / 1000.0)

        # Save intrados sleeve values
        setattr(pg, f'intrados_sleeve_enabled{suffix}', self.intradosEnabledCheckBox.isChecked())
        setattr(pg, f'intrados_sleeve_width{suffix}', self.intradosWidthSpinBox.value() / 1000.0)
        setattr(pg, f'intrados_sleeve_offset{suffix}', self.intradosOffsetSpinBox.value() / 1000.0)
        setattr(pg, f'intrados_sleeve_start{suffix}', self.intradosStartSpinBox.value() / 100.0)
        setattr(pg, f'intrados_sleeve_end{suffix}', self.intradosEndSpinBox.value() / 100.0)
        setattr(pg, f'intrados_sleeve_le_angle{suffix}', self.intradosLeAngleSpinBox.value())
        setattr(pg, f'intrados_sleeve_le_length{suffix}', self.intradosLeLengthSpinBox.value() / 1000.0)
        setattr(pg, f'intrados_sleeve_te_angle{suffix}', self.intradosTeAngleSpinBox.value())
        setattr(pg, f'intrados_sleeve_te_length{suffix}', self.intradosTeLengthSpinBox.value() / 1000.0)

        # Save reinforcement values (only for suspended)
        if is_suspended:
            setattr(pg, 'reinforcement_enabled_s', self.reinforcementEnabledCheckBox.isChecked())
            setattr(pg, 'reinforcement_apply_all_s', self.reinforcementApplyAllCheckBox.isChecked())
            setattr(pg, 'reinforcement_master_s', self.masterConfig.get_values())
            
            # Save list of configs
            configs = [w.get_values() for w in self.reinforcement_widgets]
            setattr(pg, 'reinforcement_configs_s', configs)

    def apply_reinforcements_to_ribs(self):
        """Apply reinforcement configurations to the actual rib objects for 2D export."""
        pg = self.parametric_glider
        glider_instance = self.obj.Proxy.getGliderInstance()
        
        # Only apply if reinforcements are enabled for suspended ribs
        if not getattr(pg, 'reinforcement_enabled_s', False):
            # Clear reinforcements from all ribs
            for rib in glider_instance.ribs:
                rib.reinforcements = []
            return
        
        apply_all = getattr(pg, 'reinforcement_apply_all_s', True)
        master_config = getattr(pg, 'reinforcement_master_s', {})
        configs = getattr(pg, 'reinforcement_configs_s', [])
        
        # Identify suspended ribs and build rib index map
        suspended_ribs = {att.rib for att in glider_instance.attachment_points if hasattr(att, 'rib')}
        
        for rib_idx, rib in enumerate(glider_instance.ribs):
            if rib in suspended_ribs:
                # Get valid attachment points for this rib
                valid_aps = self.get_valid_attachment_points(rib)
                
                reinforcements = []
                for i, ap in enumerate(valid_aps):
                    # Get config
                    if apply_all:
                        config = master_config
                    else:
                        config = configs[i] if i < len(configs) else master_config
                    
                    if config.get('enabled', True):
                        # Generate name: rib index + attachment point name (contains line letter)
                        # ap.name typically contains the line letter (A, B, C, D, etc.)
                        name = f"{rib_idx + 1}{ap.name}" if ap.name else f"{rib_idx + 1}_{i + 1}"
                        
                        reinforcement = self._create_reinforcement(ap.rib_pos, config, name)
                        reinforcements.append(reinforcement)
                
                rib.reinforcements = reinforcements
            else:
                # Non-suspended ribs don't get reinforcements
                rib.reinforcements = []

    def accept(self):
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        self.update_glider_data(is_suspended)
        # Apply reinforcements to ribs for 2D export
        self.apply_reinforcements_to_ribs()
        self.update_view_glider()
        super(AirfoilStructureTool, self).accept()


class ReinforcementConfigWidget(QtGui.QWidget):
    """Widget for configuring a single reinforcement's parameters."""
    changed = QtCore.Signal()
    
    def __init__(self, parent=None):
        super(ReinforcementConfigWidget, self).__init__(parent)
        self.layout = QtGui.QFormLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 5)
        
        self.enableCheckBox = QtGui.QCheckBox("Enable")
        self.enableCheckBox.setChecked(True)
        self.layout.addRow(self.enableCheckBox)
        
        self.surfaceOffsetSpinBox = QtGui.QDoubleSpinBox()
        self.surfaceOffsetSpinBox.setSingleStep(0.5)
        self.surfaceOffsetSpinBox.setDecimals(1)
        self.surfaceOffsetSpinBox.setSuffix(" mm")
        self.surfaceOffsetSpinBox.setRange(0.0, 1000.0)
        self.surfaceOffsetSpinBox.setValue(0.5)  # 0.5mm default
        self.layout.addRow("Surface offset", self.surfaceOffsetSpinBox)
        
        self.halfmoonRadiusSpinBox = QtGui.QDoubleSpinBox()
        self.halfmoonRadiusSpinBox.setSingleStep(1.0)
        self.halfmoonRadiusSpinBox.setDecimals(1)
        self.halfmoonRadiusSpinBox.setSuffix(" mm")
        self.halfmoonRadiusSpinBox.setRange(0.0, 1000.0)
        self.halfmoonRadiusSpinBox.setValue(100.0)  # 100mm default
        self.layout.addRow("Half-moon radius", self.halfmoonRadiusSpinBox)
        
        self.rodEnabledCheckBox = QtGui.QCheckBox("Enable Rod Sleeve")
        self.rodEnabledCheckBox.setChecked(True)
        self.layout.addRow(self.rodEnabledCheckBox)
        
        self.rodOffsetSpinBox = QtGui.QDoubleSpinBox()
        self.rodOffsetSpinBox.setSingleStep(1.0)
        self.rodOffsetSpinBox.setDecimals(1)
        self.rodOffsetSpinBox.setSuffix(" mm")
        self.rodOffsetSpinBox.setRange(0.0, 1000.0)
        self.rodOffsetSpinBox.setValue(8.0)  # 8mm default
        self.layout.addRow("Rod offset", self.rodOffsetSpinBox)
        
        self.rodWidthSpinBox = QtGui.QDoubleSpinBox()
        self.rodWidthSpinBox.setSingleStep(0.5)
        self.rodWidthSpinBox.setDecimals(1)
        self.rodWidthSpinBox.setSuffix(" mm")
        self.rodWidthSpinBox.setRange(0.0, 1000.0)
        self.rodWidthSpinBox.setValue(9.0)  # 9mm default
        self.layout.addRow("Rod width", self.rodWidthSpinBox)
        
        self.rodEndOffsetSpinBox = QtGui.QDoubleSpinBox()
        self.rodEndOffsetSpinBox.setSingleStep(1.0)
        self.rodEndOffsetSpinBox.setDecimals(1)
        self.rodEndOffsetSpinBox.setSuffix(" °")
        self.rodEndOffsetSpinBox.setRange(0.0, 90.0)
        self.rodEndOffsetSpinBox.setValue(1.0)  # 1° default
        self.layout.addRow("Rod end offset", self.rodEndOffsetSpinBox)
        
        self.enableCheckBox.stateChanged.connect(self.emit_changed)
        self.surfaceOffsetSpinBox.valueChanged.connect(self.emit_changed)
        self.halfmoonRadiusSpinBox.valueChanged.connect(self.emit_changed)
        self.rodEnabledCheckBox.stateChanged.connect(self.emit_changed)
        self.rodOffsetSpinBox.valueChanged.connect(self.emit_changed)
        self.rodWidthSpinBox.valueChanged.connect(self.emit_changed)
        self.rodEndOffsetSpinBox.valueChanged.connect(self.emit_changed)
        
    def emit_changed(self):
        self.changed.emit()
        
    def get_values(self):
        return {
            'enabled': self.enableCheckBox.isChecked(),
            'surface_offset': self.surfaceOffsetSpinBox.value() / 1000.0,
            'halfmoon_radius': self.halfmoonRadiusSpinBox.value() / 1000.0,
            'rod_enabled': self.rodEnabledCheckBox.isChecked(),
            'rod_offset': self.rodOffsetSpinBox.value() / 1000.0,
            'rod_width': self.rodWidthSpinBox.value() / 1000.0,
            'rod_end_offset': self.rodEndOffsetSpinBox.value(),
        }
        
    def set_values(self, config):
        if not config:
            return
        self.enableCheckBox.setChecked(config.get('enabled', True))
        self.surfaceOffsetSpinBox.setValue(config.get('surface_offset', 0.003) * 1000.0)
        self.halfmoonRadiusSpinBox.setValue(config.get('halfmoon_radius', 0.03) * 1000.0)
        self.rodEnabledCheckBox.setChecked(config.get('rod_enabled', True))
        self.rodOffsetSpinBox.setValue(config.get('rod_offset', 0.005) * 1000.0)
        self.rodWidthSpinBox.setValue(config.get('rod_width', 0.005) * 1000.0)
        self.rodEndOffsetSpinBox.setValue(config.get('rod_end_offset', 10.0))

