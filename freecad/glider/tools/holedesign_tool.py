from .tools import BaseTool, Line_old
import FreeCADGui as Gui
from PySide import QtCore, QtGui
from openglider.glider.rib import RibHole
from openglider.utils.geometry import is_inside_triangle
import numpy as np
from pivy import coin
import os

class HoleDesignTool(BaseTool):
    widget_name = "Hole Design"

    def __init__(self, obj):
        super(HoleDesignTool, self).__init__(obj)

        # UI Elements with parent widget specified
        self.ribTypeComboBox = QtGui.QComboBox(self.base_widget)
        self.holeShapeComboBox = QtGui.QComboBox(self.base_widget)
        self.numHolesSpinBox = QtGui.QSpinBox(self.base_widget)
        self.holeWidthSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.holeHeightSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.holeHeightSpinBox.hide()  # Not in layout, hide to prevent floating widget

        self.holeMarginSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.verticalShiftSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.minPosSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.maxPosSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.holeCornerRadiusSpinBox = QtGui.QDoubleSpinBox(self.base_widget)

        # Controls for no-hole zones on suspended ribs
        self.noHoleZoneLabel = QtGui.QLabel("<b>No-Hole Zone Geometry</b>", self.base_widget)
        self.noHoleArcAngleSpinBox = QtGui.QDoubleSpinBox(self.base_widget)  # Arc span angle
        self.noHoleAngleSpinBox = QtGui.QDoubleSpinBox(self.base_widget)  # Direction to extrados

        # Preview rib selector - ComboBox to show only relevant ribs with real names
        self.previewRibComboBox = QtGui.QComboBox(self.base_widget)
        self._rib_indices = []  # Mapping from combo index to actual rib index

        self.applyButton = QtGui.QPushButton("Apply", self.base_widget)

        self.preview_root = coin.SoSeparator()
        self.setup_widget()
        self.setup_pivy()

    def setup_widget(self):
        # Add items to combo box
        self.ribTypeComboBox.addItems(["Non-Suspended", "Suspended"])
        self.holeShapeComboBox.addItems(["Ellipse", "Rounded Rectangle"])


        # Add widgets to the QFormLayout provided by BaseTool
        self.layout.addRow("Rib Type", self.ribTypeComboBox)
        self.layout.addRow("Hole Shape", self.holeShapeComboBox)
        self.layout.addRow("Number of Holes", self.numHolesSpinBox)
        self.layout.addRow("Hole Width (%)", self.holeWidthSpinBox)
        self.layout.addRow("Height Margin (mm)", self.holeMarginSpinBox)
        self.layout.addRow("Vertical Shift (%)", self.verticalShiftSpinBox)
        self.layout.addRow("Min Position (%)", self.minPosSpinBox)
        self.layout.addRow("Max Position (%)", self.maxPosSpinBox)
        self.layout.addRow("Corner Radius (mm)", self.holeCornerRadiusSpinBox)

        self.layout.addRow(self.noHoleZoneLabel)
        self.layout.addRow("Arc Span (deg)", self.noHoleArcAngleSpinBox)
        self.layout.addRow("Exclusion Angle (deg)", self.noHoleAngleSpinBox)
        self.layout.addRow("Preview Rib", self.previewRibComboBox)

        # Right-align the apply button
        button_layout = QtGui.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.applyButton)
        self.layout.addRow(button_layout)

        # Configure spinboxes
        for spinbox in [self.holeWidthSpinBox, self.holeHeightSpinBox, self.verticalShiftSpinBox]:
            spinbox.setSingleStep(0.01)
            spinbox.setDecimals(3)
            spinbox.setMinimum(0.0)
            spinbox.setMaximum(1.0) # Relative to chord

        # Margin spinbox (in mm)
        self.holeMarginSpinBox.setSingleStep(1.0) # 1mm steps
        self.holeMarginSpinBox.setDecimals(1)
        self.holeMarginSpinBox.setSuffix(" mm")
        self.holeMarginSpinBox.setRange(0.0, 1000.0) # Reasonable max margin

        # Corner radius spinbox (as percentage 0-50%)
        self.holeCornerRadiusSpinBox.setSingleStep(1.0) # 1% steps
        self.holeCornerRadiusSpinBox.setDecimals(0)
        self.holeCornerRadiusSpinBox.setSuffix(" %")
        self.holeCornerRadiusSpinBox.setRange(0.0, 50.0) # Max 50% = half the smallest dimension

        for spinbox in [self.minPosSpinBox, self.maxPosSpinBox]:
            spinbox.setSingleStep(0.01)
            spinbox.setDecimals(3)
            spinbox.setMinimum(0.0)
            spinbox.setMaximum(1.0) # Relative to chord

        self.noHoleArcAngleSpinBox.setSingleStep(5.0)
        self.noHoleArcAngleSpinBox.setMinimum(0)
        self.noHoleArcAngleSpinBox.setMaximum(180)
        self.noHoleArcAngleSpinBox.setValue(120)  # Default: 120° arc span
        
        self.noHoleAngleSpinBox.setSingleStep(1.0)
        self.noHoleAngleSpinBox.setMinimum(0)
        self.noHoleAngleSpinBox.setMaximum(90)

        # Load initial values
        self.update_form_from_glider_data()

        # Connections
        self.ribTypeComboBox.currentIndexChanged.connect(self.on_rib_type_change)
        self.holeShapeComboBox.currentIndexChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.numHolesSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.holeWidthSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))

        self.holeHeightSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.holeMarginSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.verticalShiftSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.minPosSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.maxPosSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.holeCornerRadiusSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.noHoleArcAngleSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.noHoleAngleSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.previewRibComboBox.currentIndexChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.applyButton.clicked.connect(self.accept)

        # Set initial visibility of no-hole zone controls
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        self.noHoleZoneLabel.setVisible(is_suspended)
        self.noHoleArcAngleSpinBox.setVisible(is_suspended)
        self.layout.labelForField(self.noHoleArcAngleSpinBox).setVisible(is_suspended)
        self.noHoleAngleSpinBox.setVisible(is_suspended)
        self.layout.labelForField(self.noHoleAngleSpinBox).setVisible(is_suspended)

    def setup_pivy(self):
        self.task_separator.addChild(self.preview_root)
        # Set spinbox max to actual rib count
        glider_instance = self.obj.Proxy.getGliderInstance()
        num_ribs = len(glider_instance.ribs) if glider_instance.ribs else 1
        self._populate_rib_combo()  # Populate with filtered ribs based on type
        self.update_preview()
        Gui.SendMsgToActiveView("ViewFit")

    def _is_truly_suspended(self, rib, glider_instance):
        """Check if rib has true suspension attachments (not just brake tabs)."""
        # Filter attachment points - exclude brake tabs (>90% chord)
        attachment_points = glider_instance.get_rib_attachment_points(rib)
        true_suspension_aps = [ap for ap in attachment_points if hasattr(ap, 'rib_pos') and ap.rib_pos <= 0.9]
        return len(true_suspension_aps) > 0
    
    def _populate_rib_combo(self):
        """Populate rib combo box with filtered ribs based on suspended/non-suspended type."""
        glider_instance = self.obj.Proxy.getGliderInstance()
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        
        # Block signals while updating
        self.previewRibComboBox.blockSignals(True)
        
        # Remember current selection if possible
        old_rib_idx = None
        if self._rib_indices and self.previewRibComboBox.currentIndex() >= 0:
            old_combo_idx = self.previewRibComboBox.currentIndex()
            if old_combo_idx < len(self._rib_indices):
                old_rib_idx = self._rib_indices[old_combo_idx]
        
        self.previewRibComboBox.clear()
        self._rib_indices = []
        
        for i, rib in enumerate(glider_instance.ribs):
            truly_suspended = self._is_truly_suspended(rib, glider_instance)
            
            # Check thickness to exclude flat ribs (like wingtips)
            try:
                # Check thickness at 30% chord (typical max thickness location)
                p_up = rib.profile_2d.profilepoint(-0.3)
                p_down = rib.profile_2d.profilepoint(0.3)
                thickness = p_up[1] - p_down[1]
                if thickness < 1e-3: # Less than 0.1% thickness -> Flat/Line
                    continue
            except:
                pass # If calculation fails, include it (safer)

            # Filter based on type
            if is_suspended and truly_suspended:
                self._rib_indices.append(i)
                self.previewRibComboBox.addItem(f"{i}: {rib.name}")
            elif not is_suspended and not truly_suspended:
                self._rib_indices.append(i)
                self.previewRibComboBox.addItem(f"{i}: {rib.name}")
        
        # Restore selection if possible
        if old_rib_idx is not None and old_rib_idx in self._rib_indices:
            new_combo_idx = self._rib_indices.index(old_rib_idx)
            self.previewRibComboBox.setCurrentIndex(new_combo_idx)
        elif self._rib_indices:
            self.previewRibComboBox.setCurrentIndex(0)
        
        self.previewRibComboBox.blockSignals(False)
    
    def get_representative_rib(self, suspended=False):
        """Get a representative rib for preview.
        
        Get rib for preview based on spinner selection (like airfoil structure).
        """
        glider_instance = self.obj.Proxy.getGliderInstance()
        combo_idx = self.previewRibComboBox.currentIndex()
        rib_idx = self._rib_indices[combo_idx] if 0 <= combo_idx < len(self._rib_indices) else 0
        
        if rib_idx < len(glider_instance.ribs):
            return glider_instance.ribs[rib_idx]
        return glider_instance.ribs[0] if glider_instance.ribs else None

    def on_height_mode_change(self, index):
        # Simplified - always use margin mode
        self.update_glider_data_and_preview(switch=False)

    def on_rib_type_change(self, new_index):
        # Save the data of the previous tab before switching
        previous_index = 1 - new_index
        self.update_glider_data(is_suspended=previous_index == 1)

        is_suspended = new_index == 1

        # Show/hide no-hole zone controls
        self.noHoleZoneLabel.setVisible(is_suspended)
        self.noHoleArcAngleSpinBox.setVisible(is_suspended)
        self.layout.labelForField(self.noHoleArcAngleSpinBox).setVisible(is_suspended)
        self.noHoleAngleSpinBox.setVisible(is_suspended)
        # Also hide the labels associated with the spinboxes
        self.layout.labelForField(self.noHoleAngleSpinBox).setVisible(is_suspended)
        

        # Then, load the values for the newly selected rib type
        self.update_form_from_glider_data()
        # Repopulate rib combo with filtered ribs for the new type
        self._populate_rib_combo()
        self.update_preview()

    def update_preview(self, *args):
        self.preview_root.removeAllChildren()

        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        rib = self.get_representative_rib(suspended=is_suspended)
        if not rib: return

        # Toujours récupérer glider_instance pour pouvoir appeler get_hull sur SingleSkinRib
        glider_instance = self.obj.Proxy.getGliderInstance()

        # Pour SingleSkinRib, utiliser get_hull() qui retourne le vrai profil avec les bows
        from openglider.glider.rib.rib import SingleSkinRib
        if isinstance(rib, SingleSkinRib):
            try:
                hull_profile = rib.get_hull(glider_instance)
            except Exception:
                hull_profile = rib.profile_2d
        else:
            hull_profile = rib.profile_2d

        # Draw profile outline - scaled by chord (like airfoil structure)
        scale = rib.chord  # All preview elements should be scaled by this
        profile_points = [p * scale for p in hull_profile.data]
        profile_3d = [[p[0], p[1], 0] for p in profile_points]
        self.preview_root.addChild(Line_old(profile_3d + [profile_3d[0]], width=2).object)

        no_hole_zones = []
        halfmoon_circles = []  # List of (center, radius) for each halfmoon - used for exclusion
        if is_suspended:
            all_attachment_points = glider_instance.get_rib_attachment_points(rib)
            # Filter to exclude brake tabs (>90% chord) - only true suspension attachments
            attachment_points = [ap for ap in all_attachment_points if hasattr(ap, 'rib_pos') and ap.rib_pos <= 0.9]
            for ap in attachment_points:
                # Visualize attachment point - scale by chord
                ap_pos_norm = rib.profile_2d.align([ap.rib_pos, -1.0])
                ap_pos_scaled = ap_pos_norm * scale
                marker = coin.SoSeparator()
                trans = coin.SoTranslation()
                trans.translation.setValue(ap_pos_scaled[0], ap_pos_scaled[1], 0)
                mat = coin.SoMaterial()
                mat.diffuseColor.setValue(1, 0, 0) # Red
                sphere = coin.SoSphere()
                sphere.radius = 0.005 * scale  # Scale marker size too
                marker.addChild(trans)
                marker.addChild(mat)
                marker.addChild(sphere)
                self.preview_root.addChild(marker)

                # Define and draw no-hole zones
                angle = self.noHoleAngleSpinBox.value()
                # Keep v1 normalized for geometric calculations (extrados_poly uses normalized coords)
                v1 = ap_pos_norm  # Apex on intrados (normalized)
                v1_scaled = ap_pos_scaled  # For drawing only
                
                angle_rad = np.deg2rad(angle)

                # Get the actual pilot point from the lineset
                # This is the main/pilot point where all lines converge
                pilot_point_3d = None
                if hasattr(glider_instance, 'lineset') and glider_instance.lineset:
                    try:
                        # Use the lineset's method to get the main attachment point
                        main_ap = glider_instance.lineset.get_main_attachment_point()
                        if main_ap is not None and hasattr(main_ap, 'vec') and main_ap.vec is not None:
                            pilot_point_3d = np.array(main_ap.vec)
                    except Exception:
                        pass  # Will fall back to vertical
                
                # Calculate line direction in 2D profile coordinates
                if pilot_point_3d is not None:
                    # Get attachment point 3D position
                    ap_pos_3d = np.array(ap.get_position())
                    
                    # Use actual LE and TE 3D positions to establish coordinate frame
                    # This is the correct way to project onto the rib's plane
                    
                    # Leading edge 3D position (nose of profile)
                    le_3d = np.array(rib.profile_3d.data[rib.profile_2d.noseindex])
                    
                    # Trailing edge 3D position (average of first and last points)
                    te_3d = (np.array(rib.profile_3d.data[0]) + np.array(rib.profile_3d.data[-1])) / 2
                    
                    # DEBUG: Print all 3D coordinates
                    print(f"[DEBUG] Pilot 3D: ({pilot_point_3d[0]:.3f}, {pilot_point_3d[1]:.3f}, {pilot_point_3d[2]:.3f})")
                    print(f"[DEBUG] LE 3D: ({le_3d[0]:.3f}, {le_3d[1]:.3f}, {le_3d[2]:.3f})")
                    print(f"[DEBUG] TE 3D: ({te_3d[0]:.3f}, {te_3d[1]:.3f}, {te_3d[2]:.3f})")
                    print(f"[DEBUG] AP 3D: ({ap_pos_3d[0]:.3f}, {ap_pos_3d[1]:.3f}, {ap_pos_3d[2]:.3f})")
                    
                    # Chord vector: from TE to LE (so that LE is at x=0 in 2D, TE at x~=1)
                    chord_3d = le_3d - te_3d
                    chord_length = np.linalg.norm(chord_3d)
                    chord_dir = chord_3d / chord_length if chord_length > 0 else np.array([0, 1, 0])
                    
                    print(f"[DEBUG] Chord length: {chord_length:.3f}")
                    print(f"[DEBUG] Chord dir: ({chord_dir[0]:.3f}, {chord_dir[1]:.3f}, {chord_dir[2]:.3f})")
                    
                    # Span direction (perpendicular to chord, in the rib plane)
                    # Use a point on the upper surface to define the plane
                    upper_idx = len(rib.profile_3d.data) // 4  # A point on upper surface
                    upper_3d = np.array(rib.profile_3d.data[upper_idx])
                    
                    # Normal to rib plane
                    v1_3d = upper_3d - te_3d
                    normal = np.cross(chord_3d, v1_3d)
                    normal = normal / np.linalg.norm(normal) if np.linalg.norm(normal) > 0 else np.array([1, 0, 0])
                    
                    # Up direction (perpendicular to chord, in rib plane)
                    up_dir = np.cross(normal, chord_dir)
                    up_dir = up_dir / np.linalg.norm(up_dir) if np.linalg.norm(up_dir) > 0 else np.array([0, 0, 1])
                    
                    print(f"[DEBUG] Up dir: ({up_dir[0]:.3f}, {up_dir[1]:.3f}, {up_dir[2]:.3f})")
                    
                    # Project pilot point onto rib's coordinate frame
                    # Reference is TE (so LE is at positive x)
                    pilot_rel_3d = pilot_point_3d - te_3d
                    pilot_chord_pos = np.dot(pilot_rel_3d, chord_dir) / chord_length  # 0=TE, 1=LE
                    pilot_up_pos = np.dot(pilot_rel_3d, up_dir) / chord_length  # Positive = above chord
                    
                    print(f"[DEBUG] Pilot chord pos: {pilot_chord_pos:.3f} (0=TE, 1=LE)")
                    print(f"[DEBUG] Pilot up pos: {pilot_up_pos:.3f}")
                    
                    # In profile_2d: LE (nose) is at x=0, TE is at x ≈ -0.5 (profile_2d.data[0] and [-1])
                    # Get actual TE position in profile_2d coordinates
                    te_2d_x = (rib.profile_2d.data[0][0] + rib.profile_2d.data[-1][0]) / 2  # Average of start/end
                    le_2d_x = rib.profile_2d.data[rib.profile_2d.noseindex][0]  # LE is at noseindex
                    
                    # Interpolate: pilot_chord_pos 0=TE, 1=LE
                    pilot_2d_x = te_2d_x + pilot_chord_pos * (le_2d_x - te_2d_x)
                    pilot_2d_y = pilot_up_pos  # Y is already in chord-normalized units
                    pilot_2d_norm = np.array([pilot_2d_x, pilot_2d_y])
                    pilot_2d = pilot_2d_norm * scale  # Scale to real coordinates
                    
                    print(f"[DEBUG] TE 2D x: {te_2d_x:.3f}, LE 2D x: {le_2d_x:.3f}")
                    print(f"[DEBUG] Pilot 2D (norm): ({pilot_2d_x:.3f}, {pilot_2d_y:.3f})")
                    print(f"[DEBUG] Pilot 2D (scaled): ({pilot_2d[0]:.3f}, {pilot_2d[1]:.3f})")
                    
                    # VISUALIZATION: Draw the pilot point for verification (only once)
                    # The nose is at profile_2d noseindex, which is typically x=0 in normalized coords
                    nose_pos = rib.profile_2d.data[rib.profile_2d.noseindex]
                    pilot_rel_to_nose = pilot_2d_norm - nose_pos
                    print(f"[HoleDesign] Pilot point 2D coords: ({pilot_2d[0]:.3f}, {pilot_2d[1]:.3f})")
                    print(f"[HoleDesign] Pilot relative to nose (LE): ({pilot_rel_to_nose[0]:.3f}, {pilot_rel_to_nose[1]:.3f})")
                    
                    # Draw pilot point marker (large blue sphere + cross)
                    pilot_marker = coin.SoSeparator()
                    pilot_trans = coin.SoTransform()
                    pilot_trans.translation.setValue(pilot_2d[0], pilot_2d[1], 0)
                    pilot_mat = coin.SoMaterial()
                    pilot_mat.diffuseColor.setValue(0, 0, 1)  # Blue
                    pilot_sphere = coin.SoSphere()
                    pilot_sphere.radius = 0.05 * scale  # Scale marker size
                    pilot_marker.addChild(pilot_trans)
                    pilot_marker.addChild(pilot_mat)
                    pilot_marker.addChild(pilot_sphere)
                    self.preview_root.addChild(pilot_marker)
                    
                    # Draw cross lines at pilot point for visibility
                    cross_size = 0.1 * scale
                    cross_h = [np.array([pilot_2d[0] - cross_size, pilot_2d[1]]), 
                               np.array([pilot_2d[0] + cross_size, pilot_2d[1]])]
                    cross_v = [np.array([pilot_2d[0], pilot_2d[1] - cross_size]), 
                               np.array([pilot_2d[0], pilot_2d[1] + cross_size])]
                    self.preview_root.addChild(Line_old(cross_h, color='green', width=3).object)
                    self.preview_root.addChild(Line_old(cross_v, color='green', width=3).object)
                    
                    # Draw line from pilot to this attachment point (both scaled)
                    self.preview_root.addChild(Line_old([pilot_2d, v1_scaled], color='green', width=1).object)
                    
                    # Direction from pilot 2D position to attachment point (use NORMALIZED coords for angle calculation)
                    line_direction = v1 - pilot_2d_norm
                    
                    if np.linalg.norm(line_direction) > 1e-9:
                        line_direction = line_direction / np.linalg.norm(line_direction)
                    else:
                        line_direction = np.array([0, 1])
                else:
                    # Fallback to vertical if no lineset data
                    line_direction = np.array([0, 1])
                
                # The angle_offset is now based on the suspension line direction
                # This makes the exclusion angle centered on the line axis
                angle_offset = np.arctan2(line_direction[1], line_direction[0])
                
                # Draw the suspension line axis for visualization (scaled)
                axis_end_scaled = v1_scaled + line_direction * 0.1 * scale
                self.preview_root.addChild(Line_old([v1_scaled, axis_end_scaled], color='yellow', width=2).object)

                dir2 = np.array([np.cos(angle_offset - angle_rad), np.sin(angle_offset - angle_rad)])
                dir3 = np.array([np.cos(angle_offset + angle_rad), np.sin(angle_offset + angle_rad)])

                extrados_poly = rib.profile_2d.get_extrados_poly()

                # Use a very large number to ensure the line cuts through the extrados
                far_factor = rib.chord * 100

                v2 = extrados_poly.line_intersection(v1, v1 + dir2 * far_factor)
                v3 = extrados_poly.line_intersection(v1, v1 + dir3 * far_factor)

                if v2 is not None and v3 is not None:
                    # Get reinforcement config for this attachment point
                    pg = self.parametric_glider
                    halfmoon_radius_norm = 0.0
                    
                    if getattr(pg, 'reinforcement_enabled_s', False):
                        apply_all = getattr(pg, 'reinforcement_apply_all_s', False)
                        master_config = getattr(pg, 'reinforcement_master_s', {})
                        configs = getattr(pg, 'reinforcement_configs_s', [])
                        
                        # Find this AP's index among valid attachment points
                        all_aps = glider_instance.get_rib_attachment_points(rib)
                        valid_aps = [a for a in all_aps if a.rib_pos <= 0.90]
                        valid_aps.sort(key=lambda x: x.rib_pos)
                        
                        try:
                            ap_index = valid_aps.index(ap)
                            if apply_all:
                                config = master_config
                            else:
                                config = configs[ap_index] if ap_index < len(configs) else master_config
                            
                            if config.get('enabled', True):
                                halfmoon_radius = config.get('halfmoon_radius', 0.03)  # in meters
                                halfmoon_radius_norm = halfmoon_radius / rib.chord
                                # Store center (v1) and radius for hole exclusion check
                                halfmoon_circles.append((v1, halfmoon_radius_norm))
                        except (ValueError, IndexError):
                            pass
                    
                    if halfmoon_radius_norm > 1e-6:
                        # TWO-ANGLE SYSTEM:
                        # 1. Arc Span angle defines where on the halfmoon the exclusion sides START
                        # 2. Exclusion Angle defines the direction of sides going to extrados
                        # BOTH are now centered on the suspension line axis (angle_offset)
                        
                        arc_span_deg = self.noHoleArcAngleSpinBox.value()  # e.g., 120 degrees
                        arc_span_rad = np.deg2rad(arc_span_deg)
                        half_arc = arc_span_rad / 2.0
                        
                        # Arc start points at ±(arc_span/2) from the SUSPENSION LINE AXIS
                        # angle_offset = direction toward pilot point
                        arc_angle_left = angle_offset + half_arc   # Left side of arc
                        arc_angle_right = angle_offset - half_arc  # Right side of arc
                        
                        # Calculate arc start points (relative to v1 as center)
                        v1_left = v1 + halfmoon_radius_norm * np.array([np.cos(arc_angle_left), np.sin(arc_angle_left)])
                        v1_right = v1 + halfmoon_radius_norm * np.array([np.cos(arc_angle_right), np.sin(arc_angle_right)])
                        
                        # Now trace lines from arc points at the Side Angle to extrados
                        v2_new = extrados_poly.line_intersection(v1_left, v1_left + dir3 * far_factor)
                        v3_new = extrados_poly.line_intersection(v1_right, v1_right + dir2 * far_factor)
                        
                        if v2_new is not None and v3_new is not None:
                            # Generate the FULL HALFMOON arc (from 0° to 180°)
                            # This ensures holes are excluded from the entire reinforcement area
                            full_halfmoon = []
                            num_arc_pts = 20
                            for i in range(num_arc_pts + 1):
                                t = i / num_arc_pts
                                arc_ang = np.pi + t * (-np.pi)  # 180° to 0° (left to right through top)
                                arc_pt = v1 + halfmoon_radius_norm * np.array([np.cos(arc_ang), np.sin(arc_ang)])
                                full_halfmoon.append(arc_pt)
                            
                            # Generate the upper arc portion (from arc_angle_left to arc_angle_right)
                            upper_arc = []
                            for i in range(num_arc_pts + 1):
                                t = i / num_arc_pts
                                arc_ang = arc_angle_left - t * (arc_angle_left - arc_angle_right)
                                arc_pt = v1 + halfmoon_radius_norm * np.array([np.cos(arc_ang), np.sin(arc_ang)])
                                upper_arc.append(arc_pt)
                            
                            # Trace the EXTRADOS curve between v2_new and v3_new
                            # This makes the top of the exclusion zone follow the airfoil shape
                            extrados_curve = []
                            # Find the positions on extrados
                            v2_x, v3_x = v2_new[0], v3_new[0]
                            x_min, x_max = min(v2_x, v3_x), max(v2_x, v3_x)
                            num_ext_pts = 15
                            for i in range(num_ext_pts + 1):
                                t = i / num_ext_pts
                                x = v2_x + t * (v3_x - v2_x)
                                # Find corresponding y on extrados at this x
                                # Use profile_2d to get extrados point
                                ext_pts = [p for p in rib.profile_2d.data if p[1] > 0]  # extrados points
                                closest = min(ext_pts, key=lambda p: abs(p[0] - x), default=None)
                                if closest is not None:
                                    extrados_curve.append(np.array(closest))
                                else:
                                    # Fallback: interpolate
                                    y = v2_new[1] + t * (v3_new[1] - v2_new[1])
                                    extrados_curve.append(np.array([x, y]))
                            
                            # Exclusion zone: full halfmoon + extrados area
                            # The zone polygon goes: full_halfmoon + sides to extrados + extrados curve back
                            exclusion_polygon = full_halfmoon + [v3_new] + list(reversed(extrados_curve)) + [v2_new, full_halfmoon[0]]
                            no_hole_zones.append(tuple(exclusion_polygon))
                            
                            # For visual, draw: upper arc -> right side -> extrados curve -> left side -> close
                            zone_points = upper_arc + [v3_new] + list(reversed(extrados_curve)) + [v2_new, upper_arc[0]]
                            # Scale for drawing
                            zone_points_scaled = [p * scale for p in zone_points]
                            self.preview_root.addChild(Line_old(zone_points_scaled, color='red', width=1).object)
                        else:
                            # Fallback to original triangle
                            no_hole_zones.append((v1, v2, v3))
                            zone_points = [v1, v2, v3, v1]
                            zone_points_scaled = [p * scale for p in zone_points]
                            self.preview_root.addChild(Line_old(zone_points_scaled, color='red', width=1).object)
                    else:
                        # No reinforcement - use simple triangle
                        no_hole_zones.append((v1, v2, v3))
                        zone_points = [v1, v2, v3, v1]
                        zone_points_scaled = [p * scale for p in zone_points]
                        self.preview_root.addChild(Line_old(zone_points_scaled, color='red', width=1).object)
                    
                    

        # Get current parameters from the UI
        num_holes = self.numHolesSpinBox.value()
        hole_width_perc = self.holeWidthSpinBox.value()
        hole_height_perc = self.holeHeightSpinBox.value()
        hole_height_mode = 0  # Default: margin mode
        hole_margin_m = self.holeMarginSpinBox.value() / 1000.0 # Convert mm to m for usage
        vertical_shift_perc = self.verticalShiftSpinBox.value()
        hole_shape_index = self.holeShapeComboBox.currentIndex()
        min_pos = self.minPosSpinBox.value()
        max_pos = self.maxPosSpinBox.value()

        if num_holes == 0:
            return

        allowed_ranges = [(min_pos, max_pos)]

        # Visualize Airfoil Structure elements (rod sleeves and reinforcements)
        pg = self.parametric_glider
        glider_instance = self.obj.Proxy.getGliderInstance()
        rib_idx = glider_instance.ribs.index(rib) if rib in glider_instance.ribs else 0
        
        # Draw rod sleeves from configuration
        from openglider.glider.rib.elements import RodSleeve
        suffix = '_s' if is_suspended else '_ns'
        
        # Draw extrados sleeves
        extrados_enabled = getattr(pg, f'extrados_sleeves_enabled{suffix}', True)
        extrados_configs = getattr(pg, f'extrados_sleeves{suffix}', [])
        print(f"DEBUG: extrados_enabled={extrados_enabled}, configs={len(extrados_configs)}, suffix={suffix}")
        if extrados_enabled and extrados_configs:
            for config in extrados_configs:
                excluded_ribs = config.get('excluded_ribs', [])
                if rib_idx not in excluded_ribs:
                    try:
                        sleeve = RodSleeve(
                            surface='extrados',
                            width=config.get('width', 0.015),
                            offset=config.get('offset', 0.005),
                            start_chord=config.get('start_chord', 0.0),
                            end_chord=config.get('end_chord', 0.7),
                        )
                        inner_pts, outer_pts = sleeve.get_sleeve_points(rib)
                        if inner_pts and outer_pts:
                            # Draw at full scale (already scaled by rib.chord in get_sleeve_points)
                            sleeve_poly = list(inner_pts) + list(reversed(outer_pts)) + [inner_pts[0]]
                            self.preview_root.addChild(Line_old(sleeve_poly, color='green', width=2).object)
                    except Exception as e:
                        import traceback
                        print(f"Error drawing extrados sleeve: {e}")
                        traceback.print_exc()
        
        # Draw intrados sleeves
        intrados_enabled = getattr(pg, f'intrados_sleeves_enabled{suffix}', True)
        intrados_configs = getattr(pg, f'intrados_sleeves{suffix}', [])
        print(f"DEBUG: intrados_enabled={intrados_enabled}, configs={len(intrados_configs)}, suffix={suffix}")
        if intrados_enabled and intrados_configs:
            for config in intrados_configs:
                excluded_ribs = config.get('excluded_ribs', [])
                if rib_idx not in excluded_ribs:
                    try:
                        sleeve = RodSleeve(
                            surface='intrados',
                            width=config.get('width', 0.015),
                            offset=config.get('offset', 0.005),
                            start_chord=config.get('start_chord', 0.06),
                            end_chord=config.get('end_chord', 0.5),
                        )
                        inner_pts, outer_pts = sleeve.get_sleeve_points(rib)
                        if inner_pts and outer_pts:
                            # Draw at full scale (already scaled by rib.chord in get_sleeve_points)
                            sleeve_poly = list(inner_pts) + list(reversed(outer_pts)) + [inner_pts[0]]
                            self.preview_root.addChild(Line_old(sleeve_poly, color='white', width=2).object)
                    except Exception as e:
                        import traceback
                        print(f"Error drawing intrados sleeve: {e}")
                        traceback.print_exc()
        
        # Draw reinforcements if they exist for this rib (suspended only)
        if is_suspended and hasattr(rib, 'reinforcements') and rib.reinforcements:
            for reinf in rib.reinforcements:
                try:
                    halfmoon_pts = reinf.get_halfmoon_points(rib)
                    if halfmoon_pts:
                        # Draw at full scale (already scaled in get_halfmoon_points)
                        self.preview_root.addChild(Line_old(list(halfmoon_pts), color='yellow', width=2).object)
                except Exception as e:
                    print(f"Error drawing reinforcement: {e}")

        # Distribute holes across the allowed ranges
        total_allowable_length = sum(end - start for start, end in allowed_ranges)
        if total_allowable_length <= 1e-6:
            return

        # A more robust way to distribute N holes across M ranges
        holes_to_distribute = num_holes
        for i, (start, end) in enumerate(allowed_ranges):
            range_length = end - start
            if range_length <= 0: continue

            is_last_range = (i == len(allowed_ranges) - 1)
            if is_last_range:
                num_holes_in_range = holes_to_distribute
            else:
                num_holes_in_range = int(round(num_holes * (range_length / total_allowable_length)))

            if num_holes_in_range <= 0:
                continue

            holes_to_distribute -= num_holes_in_range

            if num_holes_in_range == 1:
                potential_positions = [start + range_length / 2] # Center the single hole
            else:
                potential_positions = np.linspace(start, end, num_holes_in_range)

            for pos_x in potential_positions:
                upper_point = hull_profile.profilepoint(-pos_x)
                lower_point = hull_profile.profilepoint(pos_x)
                local_thickness = upper_point[1] - lower_point[1]
                if local_thickness < 1e-6:
                    continue

                new_lower_bound = lower_point
                if is_suspended:
                    hole_center_x = (upper_point[0] + lower_point[0]) / 2.0
                    min_y_ceiling = upper_point[1]
                    
                    # Check if this position is inside any halfmoon circle
                    inside_halfmoon = False
                    for hm_center, hm_radius in halfmoon_circles:
                        dist = np.sqrt((hole_center_x - hm_center[0])**2 + (lower_point[1] - hm_center[1])**2)
                        if dist < hm_radius:
                            inside_halfmoon = True
                            break
                    
                    if inside_halfmoon:
                        continue  # Skip hole positions inside halfmoon

                    for zone in no_hole_zones:
                        # Get all x values from zone vertices
                        zone_x = [v[0] for v in zone]
                        if min(zone_x) <= hole_center_x <= max(zone_x):
                            # Iterate over edges of the polygon
                            n = len(zone)
                            for i in range(n):
                                p1 = zone[i]
                                p2 = zone[(i + 1) % n]
                                if p1[0] != p2[0] and ((p1[0] <= hole_center_x <= p2[0]) or (p2[0] <= hole_center_x <= p1[0])):
                                    y_intersect = p1[1] + (p2[1] - p1[1]) * (hole_center_x - p1[0]) / (p2[0] - p1[0])
                                    if y_intersect < min_y_ceiling:
                                        min_y_ceiling = min(min_y_ceiling, y_intersect)

                    available_height = min_y_ceiling - lower_point[1]
                    hole_center = np.array([hole_center_x, lower_point[1] + available_height / 2])
                    
                    # Apply vertical shift within available height
                    hole_center[1] += available_height / 2 * vertical_shift_perc
                    
                else:
                    available_height = upper_point[1] - lower_point[1]
                    hole_center = lower_point + (upper_point - lower_point) / 2 * (1 + vertical_shift_perc)

                if available_height < 1e-4:
                    continue
                
                # Always use margin mode for hole height
                hole_height = available_height - 2 * hole_margin_m
                
                hole_width = hole_width_perc * rib.chord

                if hole_height <= 0 or hole_width <= 0:
                    continue

                if hole_shape_index == 0: # Ellipse
                    shape_points = []
                    for angle in np.linspace(0, 2 * np.pi, 50):
                        x = hole_width / 2 * np.cos(angle)
                        y = hole_height / 2 * np.sin(angle)
                        shape_points.append([x, y])
                else: # Rounded Rectangle
                    corner_radius_ratio = self.holeCornerRadiusSpinBox.value() / 100.0 # Convert % to ratio
                    shape_points = self.create_rounded_rectangle(hole_width, hole_height, corner_radius_ratio)

                shape_poly = np.array(shape_points)
                shape_poly += hole_center

                shape_points_closed = list(shape_poly)
                # Scale for drawing (points are in normalized coords)
                shape_points_scaled = [p * scale for p in shape_points_closed]
                self.preview_root.addChild(Line_old(shape_points_scaled + [shape_points_scaled[0]], color='blue').object)

    def create_rounded_rectangle(self, width, height, corner_radius_ratio=0.25):
        # corner_radius_ratio is a ratio of min(width, height)
        radius = min(width, height) * corner_radius_ratio
        if radius > width / 2.0: radius = width / 2.0
        if radius > height / 2.0: radius = height / 2.0
        
        w = width / 2 - radius
        h = height / 2 - radius

        points = []
        # Top right corner
        for angle in np.linspace(0, np.pi/2, 10):
            points.append((w + radius * np.cos(angle), h + radius * np.sin(angle)))
        # Top left corner
        for angle in np.linspace(np.pi/2, np.pi, 10):
            points.append((-w + radius * np.cos(angle), h + radius * np.sin(angle)))
        # Bottom left corner
        for angle in np.linspace(np.pi, 3*np.pi/2, 10):
            points.append((-w + radius * np.cos(angle), -h + radius * np.sin(angle)))
        # Bottom right corner
        for angle in np.linspace(3*np.pi/2, 2*np.pi, 10):
            points.append((w + radius * np.cos(angle), -h + radius * np.sin(angle)))
            
        points.append(points[0]) # Close the loop

        return points

    def update_form_from_glider_data(self):
        pg = self.parametric_glider
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        print(f"DEBUG: update_form - Current Tab: {'Suspended' if is_suspended else 'Non-Suspended'}")
        
        suffix = '_s' if is_suspended else '_ns'

        widgets_to_block = [self.holeShapeComboBox, self.numHolesSpinBox, self.holeWidthSpinBox,
                            self.holeHeightSpinBox, self.verticalShiftSpinBox,
                            self.minPosSpinBox, self.maxPosSpinBox,
                            self.holeMarginSpinBox, self.holeCornerRadiusSpinBox]
        if is_suspended:
            widgets_to_block.extend([self.noHoleAngleSpinBox])

        # Block signals to prevent feedback loops
        for widget in widgets_to_block:
            widget.blockSignals(True)

        self.holeShapeComboBox.setCurrentIndex(getattr(pg, f'hole_shape{suffix}', 0))
        self.numHolesSpinBox.setValue(getattr(pg, f'num_holes{suffix}', 30))
        self.holeWidthSpinBox.setValue(getattr(pg, f'hole_width{suffix}', 0.003))
        self.holeHeightSpinBox.setValue(getattr(pg, f'hole_height{suffix}', 0.8))
        self.verticalShiftSpinBox.setValue(getattr(pg, f'vertical_shift{suffix}', 0.0))
        self.minPosSpinBox.setValue(getattr(pg, f'min_hole_pos{suffix}', 0.2))
        self.maxPosSpinBox.setValue(getattr(pg, f'max_hole_pos{suffix}', 0.8))

        self.holeMarginSpinBox.setValue(getattr(pg, f'hole_margin{suffix}', 0.02) * 1000.0) # Convert m to mm for UI
        self.holeCornerRadiusSpinBox.setValue(getattr(pg, f'hole_corner_radius{suffix}', 0.25) * 100.0) # Convert ratio to % for UI

        if is_suspended:
            val = getattr(pg, 'susp_hole_radius_top_s', 'MISSING')
            print(f"DEBUG: update_form - Reading susp_hole_radius_top_s: {val} (Type: {type(val)})")
            
            self.noHoleAngleSpinBox.setValue(getattr(pg, 'hole_free_angle_s', 30.0))

        # Initial visibility update
        self.on_height_mode_change(0)  # Default mode

        # Unblock signals
        for widget in widgets_to_block:
            widget.blockSignals(False)

    def update_glider_data(self, is_suspended):
        pg = self.parametric_glider
        if is_suspended:
            pg.hole_shape_s = self.holeShapeComboBox.currentIndex()
            pg.num_holes_s = self.numHolesSpinBox.value()
            pg.hole_width_s = self.holeWidthSpinBox.value()
            pg.hole_height_s = self.holeHeightSpinBox.value()
            pg.vertical_shift_s = self.verticalShiftSpinBox.value()
            pg.min_hole_pos_s = self.minPosSpinBox.value()
            pg.max_hole_pos_s = self.maxPosSpinBox.value()
            pg.hole_free_angle_s = self.noHoleAngleSpinBox.value()
            pg.hole_height_mode_s = 1  # Margin mode (fixed mm margin instead of percent)
            pg.hole_margin_s = self.holeMarginSpinBox.value() / 1000.0 # Convert mm to m for storage
            pg.hole_corner_radius_s = self.holeCornerRadiusSpinBox.value() / 100.0 # Convert % to ratio
        else:
            pg.hole_shape_ns = self.holeShapeComboBox.currentIndex()
            pg.num_holes_ns = self.numHolesSpinBox.value()
            pg.hole_width_ns = self.holeWidthSpinBox.value()
            pg.hole_height_ns = self.holeHeightSpinBox.value()
            pg.vertical_shift_ns = self.verticalShiftSpinBox.value()
            pg.min_hole_pos_ns = self.minPosSpinBox.value()
            pg.max_hole_pos_ns = self.maxPosSpinBox.value()
            pg.hole_height_mode_ns = 1  # Margin mode (fixed mm margin instead of percent)
            pg.hole_margin_ns = self.holeMarginSpinBox.value() / 1000.0 # Convert mm to m for storage
            pg.hole_corner_radius_ns = self.holeCornerRadiusSpinBox.value() / 100.0 # Convert % to ratio

    def update_glider_data_and_preview(self, *args, switch=False):
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        self.update_glider_data(is_suspended)
        self.update_preview()

    def accept(self):
        # When accepting, save the data from the currently visible tab.
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        self.update_glider_data(is_suspended)
        self.update_view_glider()
        super(HoleDesignTool, self).accept()
