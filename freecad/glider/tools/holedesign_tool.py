from .tools import BaseTool, Line_old
import FreeCADGui as Gui
from PySide import QtCore, QtGui
from openglider.glider.rib import RibHole
import numpy as np
from pivy import coin
import os

from .tools import BaseTool, Line_old, text_field, input_field

class HoleDesignTool(BaseTool):
    widget_name = "Hole Design"

    def __init__(self, obj):
        super(HoleDesignTool, self).__init__(obj)

        # UI Elements
        self.tabWidget = QtGui.QTabWidget()
        self.tab_ns = QtGui.QWidget()
        self.tab_s = QtGui.QWidget()

        self.numHolesSpinBox_ns = QtGui.QSpinBox()
        self.holeWidthSpinBox_ns = QtGui.QDoubleSpinBox()
        self.holeHeightSpinBox_ns = QtGui.QDoubleSpinBox()
        self.verticalShiftSpinBox_ns = QtGui.QDoubleSpinBox()
        self.rotationSpinBox_ns = QtGui.QDoubleSpinBox()

        self.numHolesSpinBox_s = QtGui.QSpinBox()
        self.holeWidthSpinBox_s = QtGui.QDoubleSpinBox()
        self.holeHeightSpinBox_s = QtGui.QDoubleSpinBox()
        self.verticalShiftSpinBox_s = QtGui.QDoubleSpinBox()
        self.rotationSpinBox_s = QtGui.QDoubleSpinBox()

        self.applyButton = QtGui.QPushButton("Apply")

        self.preview_root = coin.SoSeparator()
        self.setup_widget()
        self.setup_pivy()

    def setup_widget(self):

        # Non-Suspended Tab Layout
        layout_ns = QtGui.QGridLayout(self.tab_ns)
        layout_ns.addWidget(QtGui.QLabel("Number of Holes"), 0, 0)
        layout_ns.addWidget(self.numHolesSpinBox_ns, 0, 1)
        layout_ns.addWidget(QtGui.QLabel("Hole Width"), 1, 0)
        layout_ns.addWidget(self.holeWidthSpinBox_ns, 1, 1)
        layout_ns.addWidget(QtGui.QLabel("Hole Height"), 2, 0)
        layout_ns.addWidget(self.holeHeightSpinBox_ns, 2, 1)
        layout_ns.addWidget(QtGui.QLabel("Vertical Shift"), 3, 0)
        layout_ns.addWidget(self.verticalShiftSpinBox_ns, 3, 1)
        layout_ns.addWidget(QtGui.QLabel("Rotation"), 4, 0)
        layout_ns.addWidget(self.rotationSpinBox_ns, 4, 1)

        # Suspended Tab Layout
        layout_s = QtGui.QGridLayout(self.tab_s)
        layout_s.addWidget(QtGui.QLabel("Number of Holes"), 0, 0)
        layout_s.addWidget(self.numHolesSpinBox_s, 0, 1)
        layout_s.addWidget(QtGui.QLabel("Hole Width"), 1, 0)
        layout_s.addWidget(self.holeWidthSpinBox_s, 1, 1)
        layout_s.addWidget(QtGui.QLabel("Hole Height"), 2, 0)
        layout_s.addWidget(self.holeHeightSpinBox_s, 2, 1)
        layout_s.addWidget(QtGui.QLabel("Vertical Shift"), 3, 0)
        layout_s.addWidget(self.verticalShiftSpinBox_s, 3, 1)
        layout_s.addWidget(QtGui.QLabel("Rotation"), 4, 0)
        layout_s.addWidget(self.rotationSpinBox_s, 4, 1)

        self.tabWidget.addTab(self.tab_ns, "Non-Suspended")
        self.tabWidget.addTab(self.tab_s, "Suspended")

        self.layout.addWidget(self.tabWidget, 0, 0, 1, 2)
        self.layout.addWidget(self.applyButton, 1, 1)

        for spinbox in [self.holeWidthSpinBox_ns, self.holeHeightSpinBox_ns, self.verticalShiftSpinBox_ns, self.rotationSpinBox_ns,
                        self.holeWidthSpinBox_s, self.holeHeightSpinBox_s, self.verticalShiftSpinBox_s, self.rotationSpinBox_s]:
            spinbox.setSingleStep(0.01)
            spinbox.setDecimals(3)
            spinbox.setMinimum(-10.0)
            spinbox.setMaximum(10.0)

        self.update_form_values()

        # Connections
        self.tabWidget.currentChanged.connect(self.update_preview)
        self.numHolesSpinBox_ns.valueChanged.connect(self.update_data_and_preview)
        self.holeWidthSpinBox_ns.valueChanged.connect(self.update_data_and_preview)
        self.holeHeightSpinBox_ns.valueChanged.connect(self.update_data_and_preview)
        self.verticalShiftSpinBox_ns.valueChanged.connect(self.update_data_and_preview)
        self.rotationSpinBox_ns.valueChanged.connect(self.update_data_and_preview)

        self.numHolesSpinBox_s.valueChanged.connect(self.update_data_and_preview)
        self.holeWidthSpinBox_s.valueChanged.connect(self.update_data_and_preview)
        self.holeHeightSpinBox_s.valueChanged.connect(self.update_data_and_preview)
        self.verticalShiftSpinBox_s.valueChanged.connect(self.update_data_and_preview)
        self.rotationSpinBox_s.valueChanged.connect(self.update_data_and_preview)

        self.applyButton.clicked.connect(self.accept)

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

    def update_preview(self, *args):
        self.preview_root.removeAllChildren()

        is_suspended = self.tabWidget.currentIndex() == 1
        rib = self.get_representative_rib(suspended=is_suspended)
        if not rib: return

        profile_points = list(rib.profile_2d.data)
        # Manually close the polygon by appending the start point
        self.preview_root.addChild(Line_old(profile_points + [profile_points[0]], width=2).object)

        # Draw attachment points
        glider_instance = self.obj.Proxy.getGliderInstance()
        attachment_points = glider_instance.get_rib_attachment_points(rib)
        for ap in attachment_points:
            point_2d = rib.profile_2d.profilepoint(ap.rib_pos, 0.0) # Get point on the camber line

            # Create a small circle marker
            marker_sep = coin.SoSeparator()
            translation = coin.SoTranslation()
            translation.translation.setValue(point_2d[0], point_2d[1], 0)
            color = coin.SoMaterial()
            color.diffuseColor.setValue(1, 0, 0) # Red
            sphere = coin.SoSphere()
            sphere.radius = 0.005 # Small radius for the marker

            marker_sep.addChild(translation)
            marker_sep.addChild(color)
            marker_sep.addChild(sphere)
            self.preview_root.addChild(marker_sep)

        params = self.get_params_from_tab(is_suspended)

        for i in range(params['num_holes']):
            pos_x = (i + 1.0) / (params['num_holes'] + 1.0)
            camber_point = rib.profile_2d.profilepoint(pos_x, 0.0)
            hole_center = np.array([camber_point[0], camber_point[1] + params['vertical_shift']])

            ellipse_points = []
            for angle in np.linspace(0, 2 * np.pi, 50):
                x = params['hole_width']/2 * np.cos(angle)
                y = params['hole_height']/2 * np.sin(angle)
                ellipse_points.append([x, y])

            ellipse_poly = np.array(ellipse_points)
            rot_matrix = np.array([[np.cos(np.deg2rad(params['rotation'])), -np.sin(np.deg2rad(params['rotation']))],
                                   [np.sin(np.deg2rad(params['rotation'])), np.cos(np.deg2rad(params['rotation']))]])
            ellipse_poly = ellipse_poly.dot(rot_matrix)
            ellipse_poly += hole_center

            ellipse_points_closed = list(ellipse_poly)
            self.preview_root.addChild(Line_old(ellipse_points_closed + [ellipse_points_closed[0]], color='blue').object)

        self.view.draw()

    def get_params_from_tab(self, is_suspended):
        if is_suspended:
            return {
                "num_holes": self.numHolesSpinBox_s.value(),
                "hole_width": self.holeWidthSpinBox_s.value(),
                "hole_height": self.holeHeightSpinBox_s.value(),
                "vertical_shift": self.verticalShiftSpinBox_s.value(),
                "rotation": self.rotationSpinBox_s.value(),
            }
        else:
            return {
                "num_holes": self.numHolesSpinBox_ns.value(),
                "hole_width": self.holeWidthSpinBox_ns.value(),
                "hole_height": self.holeHeightSpinBox_ns.value(),
                "vertical_shift": self.verticalShiftSpinBox_ns.value(),
                "rotation": self.rotationSpinBox_ns.value(),
            }

    def update_form_values(self):
        pg = self.parametric_glider
        self.numHolesSpinBox_ns.setValue(getattr(pg, 'num_holes_ns', 3))
        self.holeWidthSpinBox_ns.setValue(getattr(pg, 'hole_width_ns', 0.3))
        self.holeHeightSpinBox_ns.setValue(getattr(pg, 'hole_height_ns', 0.7))
        self.verticalShiftSpinBox_ns.setValue(getattr(pg, 'vertical_shift_ns', 0.0))
        self.rotationSpinBox_ns.setValue(getattr(pg, 'rotation_ns', 0.0))

        self.numHolesSpinBox_s.setValue(getattr(pg, 'num_holes_s', 1))
        self.holeWidthSpinBox_s.setValue(getattr(pg, 'hole_width_s', 0.2))
        self.holeHeightSpinBox_s.setValue(getattr(pg, 'hole_height_s', 0.5))
        self.verticalShiftSpinBox_s.setValue(getattr(pg, 'vertical_shift_s', 0.0))
        self.rotationSpinBox_s.setValue(getattr(pg, 'rotation_s', 0.0))

    def update_data_and_preview(self, *args):
        pg = self.parametric_glider
        pg.num_holes_ns = self.numHolesSpinBox_ns.value()
        pg.hole_width_ns = self.holeWidthSpinBox_ns.value()
        pg.hole_height_ns = self.holeHeightSpinBox_ns.value()
        pg.vertical_shift_ns = self.verticalShiftSpinBox_ns.value()
        pg.rotation_ns = self.rotationSpinBox_ns.value()

        pg.num_holes_s = self.numHolesSpinBox_s.value()
        pg.hole_width_s = self.holeWidthSpinBox_s.value()
        pg.hole_height_s = self.holeHeightSpinBox_s.value()
        pg.vertical_shift_s = self.verticalShiftSpinBox_s.value()
        pg.rotation_s = self.rotationSpinBox_s.value()

        self.update_preview()

    def accept(self):
        self.update_data_and_preview()
        super(HoleDesignTool, self).accept()
