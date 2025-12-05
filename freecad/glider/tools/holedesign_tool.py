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
        self.verticalShiftSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.minPosSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.maxPosSpinBox = QtGui.QDoubleSpinBox(self.base_widget)

        # Controls for no-hole zones on suspended ribs
        self.noHoleZoneLabel = QtGui.QLabel("<b>No-Hole Zone Geometry</b>", self.base_widget)
        self.noHoleAngleSpinBox = QtGui.QDoubleSpinBox(self.base_widget)

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
        self.layout.addRow("Hole Height (%)", self.holeHeightSpinBox)
        self.layout.addRow("Vertical Shift (%)", self.verticalShiftSpinBox)
        self.layout.addRow("Min Position (%)", self.minPosSpinBox)
        self.layout.addRow("Max Position (%)", self.maxPosSpinBox)

        # Add separator and controls for no-hole zones
        self.layout.addRow(self.noHoleZoneLabel)
        self.layout.addRow("Angle (deg)", self.noHoleAngleSpinBox)

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

        for spinbox in [self.minPosSpinBox, self.maxPosSpinBox]:
            spinbox.setSingleStep(0.01)
            spinbox.setDecimals(3)
            spinbox.setMinimum(0.0)
            spinbox.setMaximum(1.0)

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
        self.verticalShiftSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.minPosSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.maxPosSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.noHoleAngleSpinBox.valueChanged.connect(lambda: self.update_glider_data_and_preview(switch=False))
        self.applyButton.clicked.connect(self.accept)

        # Set initial visibility of no-hole zone controls
        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        self.noHoleZoneLabel.setVisible(is_suspended)
        self.noHoleAngleSpinBox.setVisible(is_suspended)
        self.layout.labelForField(self.noHoleAngleSpinBox).setVisible(is_suspended)

    def setup_pivy(self):
        self.task_separator.addChild(self.preview_root)
        self.update_preview()
        Gui.SendMsgToActiveView("ViewFit")

    def get_representative_rib(self, suspended=False):
        glider_instance = self.obj.Proxy.getGliderInstance()
        suspended_ribs = {att.rib for att in glider_instance.lineset.attachment_points if hasattr(att, 'rib')}
        for rib in glider_instance.ribs:
            if suspended == (rib in suspended_ribs):
                return rib
        return None

    def on_rib_type_change(self, new_index):
        # Save the data of the previous tab before switching
        previous_index = 1 - new_index
        self.update_glider_data(is_suspended=previous_index == 1)

        is_suspended = new_index == 1

        # Show/hide no-hole zone controls
        self.noHoleZoneLabel.setVisible(is_suspended)
        self.noHoleAngleSpinBox.setVisible(is_suspended)
        # Also hide the labels associated with the spinboxes
        self.layout.labelForField(self.noHoleAngleSpinBox).setVisible(is_suspended)

        # Then, load the values for the newly selected rib type
        self.update_form_from_glider_data()
        self.update_preview()

    def update_preview(self, *args):
        self.preview_root.removeAllChildren()

        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        rib = self.get_representative_rib(suspended=is_suspended)
        if not rib: return

        profile_points = list(rib.profile_2d.data)
        self.preview_root.addChild(Line_old(profile_points + [profile_points[0]], width=2).object)

        no_hole_zones = []
        if is_suspended:
            glider_instance = self.obj.Proxy.getGliderInstance()
            attachment_points = glider_instance.get_rib_attachment_points(rib)
            for ap in attachment_points:
                # Visualize attachment point
                ap_pos_on_surface = rib.profile_2d.align([ap.rib_pos, -1.0])
                marker = coin.SoSeparator()
                trans = coin.SoTranslation()
                trans.translation.setValue(ap_pos_on_surface[0], ap_pos_on_surface[1], 0)
                mat = coin.SoMaterial()
                mat.diffuseColor.setValue(1, 0, 0) # Red
                sphere = coin.SoSphere()
                sphere.radius = 0.005
                marker.addChild(trans)
                marker.addChild(mat)
                marker.addChild(sphere)
                self.preview_root.addChild(marker)

                # Define and draw no-hole zones
                angle = self.noHoleAngleSpinBox.value()
                v1 = ap_pos_on_surface # Apex on intrados

                angle_rad = np.deg2rad(angle)

                upper_point = rib.profile_2d.align([ap.rib_pos, 1.0])
                local_vertical = upper_point - v1
                if np.linalg.norm(local_vertical) < 1e-9: continue
                local_vertical /= np.linalg.norm(local_vertical)

                angle_offset = np.arctan2(local_vertical[1], local_vertical[0])

                dir2 = np.array([np.cos(angle_offset - angle_rad), np.sin(angle_offset - angle_rad)])
                dir3 = np.array([np.cos(angle_offset + angle_rad), np.sin(angle_offset + angle_rad)])

                extrados_poly = rib.profile_2d.get_extrados_poly()

                # Use a very large number to ensure the line cuts through the extrados
                far_factor = rib.chord * 100

                v2 = extrados_poly.line_intersection(v1, v1 + dir2 * far_factor)
                v3 = extrados_poly.line_intersection(v1, v1 + dir3 * far_factor)

                if v2 is not None and v3 is not None:
                    no_hole_zones.append((v1, v2, v3))
                    zone_points = [v1, v2, v3, v1] # Closed loop for visualization
                    self.preview_root.addChild(Line_old(zone_points, color='red', width=1).object)

        # Get current parameters from the UI
        num_holes = self.numHolesSpinBox.value()
        hole_width_perc = self.holeWidthSpinBox.value()
        hole_height_perc = self.holeHeightSpinBox.value()
        vertical_shift_perc = self.verticalShiftSpinBox.value()
        hole_shape_index = self.holeShapeComboBox.currentIndex()
        min_pos = self.minPosSpinBox.value()
        max_pos = self.maxPosSpinBox.value()

        if num_holes == 0:
            return

        allowed_ranges = [(min_pos, max_pos)]

        if is_suspended and no_hole_zones:
            zone_x_ranges = []
            # we need to project the triangle x-range onto the chord-percentage axis
            nose_x = rib.profile_2d.data[rib.profile_2d.noseindex][0]

            for v1, v2, v3 in no_hole_zones:
                min_x_abs = min(v1[0], v2[0], v3[0])
                max_x_abs = max(v1[0], v2[0], v3[0])

                # convert absolute x coordinates to percentage of chord
                min_x_perc = (min_x_abs - nose_x) / rib.chord
                max_x_perc = (max_x_abs - nose_x) / rib.chord
                zone_x_ranges.append((min_x_perc, max_x_perc))

            zone_x_ranges.sort()

            # Subtract the no-hole zones from the allowed range
            new_allowed_ranges = []
            current_pos = allowed_ranges[0][0]
            for zone_start, zone_end in zone_x_ranges:
                if current_pos < zone_start:
                    new_allowed_ranges.append((current_pos, zone_start))
                current_pos = max(current_pos, zone_end)
            if current_pos < allowed_ranges[0][1]:
                new_allowed_ranges.append((current_pos, allowed_ranges[0][1]))
            allowed_ranges = new_allowed_ranges

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
                upper_point = rib.profile_2d.profilepoint(-pos_x)
                lower_point = rib.profile_2d.profilepoint(pos_x)
                local_thickness = upper_point[1] - lower_point[1]
                if local_thickness < 1e-6:
                    continue

                new_lower_bound = lower_point
                if is_suspended:
                    hole_center_x = (upper_point[0] + lower_point[0]) / 2.0
                    max_y_no_hole = -float('inf')

                    for v1, v2, v3 in no_hole_zones:
                        if min(v1[0], v2[0], v3[0]) <= hole_center_x <= max(v1[0], v2[0], v3[0]):
                            for p1, p2 in [(v1, v2), (v2, v3), (v3, v1)]:
                                if p1[0] != p2[0] and ((p1[0] <= hole_center_x <= p2[0]) or (p2[0] <= hole_center_x <= p1[0])):
                                    y_intersect = p1[1] + (p2[1] - p1[1]) * (hole_center_x - p1[0]) / (p2[0] - p1[0])
                                    if y_intersect > lower_point[1]:
                                        max_y_no_hole = max(max_y_no_hole, y_intersect)

                    if max_y_no_hole > -float('inf'):
                        new_lower_bound = np.array([hole_center_x, max_y_no_hole])

                available_height = upper_point[1] - new_lower_bound[1]
                if available_height < 1e-4:
                    continue

                hole_center = new_lower_bound + (upper_point - new_lower_bound) / 2 * (1 + vertical_shift_perc)
                hole_height = hole_height_perc * available_height
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
                    shape_points = self.create_rounded_rectangle(hole_width, hole_height)

                shape_poly = np.array(shape_points)
                shape_poly += hole_center

                shape_points_closed = list(shape_poly)
                self.preview_root.addChild(Line_old(shape_points_closed + [shape_points_closed[0]], color='blue').object)

    def create_rounded_rectangle(self, width, height, radius_ratio=0.25):
        radius = min(width, height) * radius_ratio
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

        return points

    def update_form_from_glider_data(self):
        pg = self.parametric_glider
        is_suspended = self.ribTypeComboBox.currentIndex() == 1

        suffix = "_s" if is_suspended else "_ns"

        widgets_to_block = [self.holeShapeComboBox, self.numHolesSpinBox, self.holeWidthSpinBox,
                            self.holeHeightSpinBox, self.verticalShiftSpinBox,
                            self.minPosSpinBox, self.maxPosSpinBox]
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
        self.minPosSpinBox.setValue(getattr(pg, 'min_hole_pos', 0.2))
        self.maxPosSpinBox.setValue(getattr(pg, 'max_hole_pos', 0.8))
        if is_suspended:
            self.noHoleAngleSpinBox.setValue(getattr(pg, 'hole_free_angle_s', 30.0))

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
            pg.hole_free_angle_s = self.noHoleAngleSpinBox.value()
        else:
            pg.hole_shape_ns = self.holeShapeComboBox.currentIndex()
            pg.num_holes_ns = self.numHolesSpinBox.value()
            pg.hole_width_ns = self.holeWidthSpinBox.value()
            pg.hole_height_ns = self.holeHeightSpinBox.value()
            pg.vertical_shift_ns = self.verticalShiftSpinBox.value()

        pg.min_hole_pos = self.minPosSpinBox.value()
        pg.max_hole_pos = self.maxPosSpinBox.value()

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
