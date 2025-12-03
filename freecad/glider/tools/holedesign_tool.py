from .tools import BaseTool, Line_old
import FreeCADGui as Gui
from PySide import QtCore, QtGui
from openglider.glider.rib import RibHole
import numpy as np
from pivy import coin
import os

class HoleDesignTool(BaseTool):
    widget_name = "Hole Design"

    def __init__(self, obj):
        super(HoleDesignTool, self).__init__(obj)
        ui_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ui", "holedesign.ui")
        self.form = Gui.PySideUic.loadUi(ui_file)
        self.layout.addWidget(self.form)

        self.preview_root = coin.SoSeparator()
        self.setup_pivy()
        self.setup_widget()

    def setup_widget(self):
        self.update_form_values()
        # Connections
        self.form.tabWidget.currentChanged.connect(self.update_preview)
        for tab_name in ["ns", "s"]:
            getattr(self.form, f"numHolesSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)
            getattr(self.form, f"holeWidthSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)
            getattr(self.form, f"holeHeightSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)
            getattr(self.form, f"verticalShiftSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)
            getattr(self.form, f"rotationSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)

        self.form.applyButton.clicked.connect(self.accept)

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

        is_suspended = self.form.tabWidget.currentIndex() == 1
        rib = self.get_representative_rib(suspended=is_suspended)
        if not rib: return

        profile_points = list(rib.profile_2d.data)
        self.preview_root.addChild(Line_old(profile_points + [profile_points[0]], width=2).object)

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
                "num_holes": self.form.numHolesSpinBox_s.value(),
                "hole_width": self.form.holeWidthSpinBox_s.value(),
                "hole_height": self.form.holeHeightSpinBox_s.value(),
                "vertical_shift": self.form.verticalShiftSpinBox_s.value(),
                "rotation": self.form.rotationSpinBox_s.value(),
            }
        else:
            return {
                "num_holes": self.form.numHolesSpinBox_ns.value(),
                "hole_width": self.form.holeWidthSpinBox_ns.value(),
                "hole_height": self.form.holeHeightSpinBox_ns.value(),
                "vertical_shift": self.form.verticalShiftSpinBox_ns.value(),
                "rotation": self.form.rotationSpinBox_ns.value(),
            }

    def update_form_values(self):
        pg = self.parametric_glider
        self.form.numHolesSpinBox_ns.setValue(getattr(pg, 'num_holes_ns', 3))
        self.form.holeWidthSpinBox_ns.setValue(getattr(pg, 'hole_width_ns', 0.3))
        self.form.holeHeightSpinBox_ns.setValue(getattr(pg, 'hole_height_ns', 0.7))
        self.form.verticalShiftSpinBox_ns.setValue(getattr(pg, 'vertical_shift_ns', 0.0))
        self.form.rotationSpinBox_ns.setValue(getattr(pg, 'rotation_ns', 0.0))

        self.form.numHolesSpinBox_s.setValue(getattr(pg, 'num_holes_s', 1))
        self.form.holeWidthSpinBox_s.setValue(getattr(pg, 'hole_width_s', 0.2))
        self.form.holeHeightSpinBox_s.setValue(getattr(pg, 'hole_height_s', 0.5))
        self.form.verticalShiftSpinBox_s.setValue(getattr(pg, 'vertical_shift_s', 0.0))
        self.form.rotationSpinBox_s.setValue(getattr(pg, 'rotation_s', 0.0))

    def update_data_and_preview(self, *args):
        pg = self.parametric_glider
        pg.num_holes_ns = self.form.numHolesSpinBox_ns.value()
        pg.hole_width_ns = self.form.holeWidthSpinBox_ns.value()
        pg.hole_height_ns = self.form.holeHeightSpinBox_ns.value()
        pg.vertical_shift_ns = self.form.verticalShiftSpinBox_ns.value()
        pg.rotation_ns = self.form.rotationSpinBox_ns.value()

        pg.num_holes_s = self.form.numHolesSpinBox_s.value()
        pg.hole_width_s = self.form.holeWidthSpinBox_s.value()
        pg.hole_height_s = self.form.holeHeightSpinBox_s.value()
        pg.vertical_shift_s = self.form.verticalShiftSpinBox_s.value()
        pg.rotation_s = self.form.rotationSpinBox_s.value()

        self.update_preview()

    def accept(self):
        self.update_data_and_preview()
        super(HoleDesignTool, self).accept()
