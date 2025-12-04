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
        self.rotationSpinBox = QtGui.QDoubleSpinBox(self.base_widget)

        # Controls for no-hole zones on suspended ribs
        self.noHoleZoneLabel = QtGui.QLabel("<b>No-Hole Zone Geometry</b>", self.base_widget)
        self.noHoleBaseWidthSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
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
        self.layout.addRow("Rotation (deg)", self.rotationSpinBox)

        # Add separator and controls for no-hole zones
        self.layout.addRow(self.noHoleZoneLabel)
        self.layout.addRow("Base Width (%)", self.noHoleBaseWidthSpinBox)
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
        self.rotationSpinBox.setSingleStep(1.0)
        self.rotationSpinBox.setMinimum(-180)
        self.rotationSpinBox.setMaximum(180)

        self.noHoleBaseWidthSpinBox.setSingleStep(0.01)
        self.noHoleBaseWidthSpinBox.setDecimals(3)
        self.noHoleBaseWidthSpinBox.setMinimum(0.0)
        self.noHoleBaseWidthSpinBox.setMaximum(1.0)
        self.noHoleAngleSpinBox.setSingleStep(1.0)
        self.noHoleAngleSpinBox.setMinimum(0)
        self.noHoleAngleSpinBox.setMaximum(90)

        # Load initial values
        self.update_form_from_glider_data()

        # Connections
        self.ribTypeComboBox.currentIndexChanged.connect(self.on_rib_type_change)
        self.holeShapeComboBox.currentIndexChanged.connect(self.update_glider_data_and_preview)
        self.numHolesSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.holeWidthSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.holeHeightSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.verticalShiftSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.rotationSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.noHoleBaseWidthSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.noHoleAngleSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.applyButton.clicked.connect(self.accept)

        # Set initial visibility of no-hole zone controls
        self.on_rib_type_change()

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

    def on_rib_type_change(self):
        # First, save the current UI values to the correct glider attributes
        self.update_glider_data_and_preview(switch=True)

        is_suspended = self.ribTypeComboBox.currentIndex() == 1

        # Show/hide no-hole zone controls
        self.noHoleZoneLabel.setVisible(is_suspended)
        self.noHoleBaseWidthSpinBox.setVisible(is_suspended)
        self.noHoleAngleSpinBox.setVisible(is_suspended)
        # Also hide the labels associated with the spinboxes
        self.layout.labelForField(self.noHoleBaseWidthSpinBox).setVisible(is_suspended)
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
                base_width = self.noHoleBaseWidthSpinBox.value() * rib.chord
                angle = self.noHoleAngleSpinBox.value()

                v1 = ap_pos_on_surface

                base_half_width = base_width / 2.0
                triangle_height = base_half_width / np.tan(np.deg2rad(angle)) if angle > 0 else 0

                upper_point = rib.profile_2d.align([ap.rib_pos, 1.0])
                direction_vec = upper_point - v1
                norm_direction_vec = np.linalg.norm(direction_vec)
                if norm_direction_vec > 1e-9:
                    direction_vec /= norm_direction_vec
                else:
                    direction_vec = np.array([0, 1])

                apex = v1 + direction_vec * triangle_height

                perp_vec = np.array([-direction_vec[1], direction_vec[0]])
                v2 = apex + perp_vec * base_half_width
                v3 = apex - perp_vec * base_half_width

                no_hole_zones.append((v1, v2, v3))

                zone_points = [v1, v2, v3, v1] # Closed loop for visualization
                self.preview_root.addChild(Line_old(zone_points, color='red', width=1, style='dashed').object)

        # Get current parameters from the UI
        num_holes = self.numHolesSpinBox.value()
        hole_width_perc = self.holeWidthSpinBox.value()
        hole_height_perc = self.holeHeightSpinBox.value()
        vertical_shift_perc = self.verticalShiftSpinBox.value()
        rotation = self.rotationSpinBox.value()
        hole_shape_index = self.holeShapeComboBox.currentIndex()

        for i in range(num_holes):
            pos_x = (i + 1.0) / (num_holes + 1.0)

            upper_point = rib.profile_2d.profilepoint(-pos_x)
            lower_point = rib.profile_2d.profilepoint(pos_x)
            local_thickness = upper_point[1] - lower_point[1]

            if local_thickness < 1e-6: continue

            hole_center = lower_point + (upper_point - lower_point) / 2 * (1 + vertical_shift_perc)

            if is_suspended and any(is_inside_triangle(hole_center, *zone) for zone in no_hole_zones):
                continue

            hole_width = hole_width_perc * rib.chord
            hole_height = hole_height_perc * local_thickness

            if hole_shape_index == 0: # Ellipse
                shape_points = []
                for angle in np.linspace(0, 2 * np.pi, 50):
                    x = hole_width / 2 * np.cos(angle)
                    y = hole_height / 2 * np.sin(angle)
                    shape_points.append([x, y])
            else: # Rounded Rectangle
                shape_points = self.create_rounded_rectangle(hole_width, hole_height)

            shape_poly = np.array(shape_points)
            rot_matrix = np.array([[np.cos(np.deg2rad(rotation)), -np.sin(np.deg2rad(rotation))],
                                   [np.sin(np.deg2rad(rotation)), np.cos(np.deg2rad(rotation))]])
            shape_poly = shape_poly.dot(rot_matrix)
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
                            self.holeHeightSpinBox, self.verticalShiftSpinBox, self.rotationSpinBox]
        if is_suspended:
            widgets_to_block.extend([self.noHoleBaseWidthSpinBox, self.noHoleAngleSpinBox])

        # Block signals to prevent feedback loops
        for widget in widgets_to_block:
            widget.blockSignals(True)

        self.holeShapeComboBox.setCurrentIndex(getattr(pg, f'hole_shape{suffix}', 0))
        self.numHolesSpinBox.setValue(getattr(pg, f'num_holes{suffix}', 30))
        self.holeWidthSpinBox.setValue(getattr(pg, f'hole_width{suffix}', 0.003))
        self.holeHeightSpinBox.setValue(getattr(pg, f'hole_height{suffix}', 0.8))
        self.verticalShiftSpinBox.setValue(getattr(pg, f'vertical_shift{suffix}', 0.0))
        self.rotationSpinBox.setValue(getattr(pg, f'rotation{suffix}', 0.0))
        if is_suspended:
            self.noHoleBaseWidthSpinBox.setValue(getattr(pg, 'hole_free_base_width_s', 0.1))
            self.noHoleAngleSpinBox.setValue(getattr(pg, 'hole_free_angle_s', 30.0))

        # Unblock signals
        for widget in widgets_to_block:
            widget.blockSignals(False)

    def update_glider_data_and_preview(self, *args, switch=False):
        pg = self.parametric_glider

        # When switching tabs, we need to know which set of data to save.
        # The index gives the *new* tab, so we save to the *opposite* of the current one if switching.
        current_idx = self.ribTypeComboBox.currentIndex()
        is_suspended = (current_idx == 1 and not switch) or \
                       (current_idx == 0 and switch)

        suffix = "_s" if is_suspended else "_ns"

        setattr(pg, f'hole_shape{suffix}', self.holeShapeComboBox.currentIndex())
        setattr(pg, f'num_holes{suffix}', self.numHolesSpinBox.value())
        setattr(pg, f'hole_width{suffix}', self.holeWidthSpinBox.value())
        setattr(pg, f'hole_height{suffix}', self.holeHeightSpinBox.value())
        setattr(pg, f'vertical_shift{suffix}', self.verticalShiftSpinBox.value())
        setattr(pg, f'rotation{suffix}', self.rotationSpinBox.value())

        if is_suspended:
            pg.hole_free_base_width_s = self.noHoleBaseWidthSpinBox.value()
            pg.hole_free_angle_s = self.noHoleAngleSpinBox.value()

        self.update_preview()

    def accept(self):
        self.update_glider_data_and_preview()
        super(HoleDesignTool, self).accept()
