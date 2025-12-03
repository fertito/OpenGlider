from .tools import BaseTool, Line_old
import FreeCADGui as Gui
from PySide import QtCore, QtGui
from openglider.glider.rib import RibHole
import numpy as np
from pivy import coin

class HoleDesignTool(BaseTool):
    widget_name = "Hole Design"
    _ui_file = "holedesign.ui"

    def __init__(self, obj):
        super(HoleDesignTool, self).__init__(obj)
        self.preview_root = coin.SoSeparator()
        self.setup_pivy()

    def setup_widget(self):
        # Find all widgets and store them as class attributes
        self.tabWidget = self.base_widget.findChild(QtCore.QObject, "tabWidget")
        self.applyButton = self.base_widget.findChild(QtCore.QObject, "applyButton")

        for tab_name in ["ns", "s"]:
            setattr(self, f"numHolesSpinBox_{tab_name}", self.base_widget.findChild(QtCore.QObject, f"numHolesSpinBox_{tab_name}"))
            setattr(self, f"holeWidthSpinBox_{tab_name}", self.base_widget.findChild(QtCore.QObject, f"holeWidthSpinBox_{tab_name}"))
            setattr(self, f"holeHeightSpinBox_{tab_name}", self.base_widget.findChild(QtCore.QObject, f"holeHeightSpinBox_{tab_name}"))
            setattr(self, f"verticalShiftSpinBox_{tab_name}", self.base_widget.findChild(QtCore.QObject, f"verticalShiftSpinBox_{tab_name}"))
            setattr(self, f"rotationSpinBox_{tab_name}", self.base_widget.findChild(QtCore.QObject, f"rotationSpinBox_{tab_name}"))

        self.update_form_values()

        # Connections
        self.tabWidget.currentChanged.connect(self.update_preview)
        for tab_name in ["ns", "s"]:
            getattr(self, f"numHolesSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)
            getattr(self, f"holeWidthSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)
            getattr(self, f"holeHeightSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)
            getattr(self, f"verticalShiftSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)
            getattr(self, f"rotationSpinBox_{tab_name}").valueChanged.connect(self.update_data_and_preview)

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

        self.preview_root.addChild(Line_old(rib.profile_2d.data, width=2, closed=True).object)

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

            self.preview_root.addChild(Line_old(ellipse_poly, closed=True, color='blue').object)

        self.view.draw()

    def get_params_from_tab(self, is_suspended):
        if is_suspended:
            return {
                "num_holes": getattr(self, "numHolesSpinBox_s").value(),
                "hole_width": getattr(self, "holeWidthSpinBox_s").value(),
                "hole_height": getattr(self, "holeHeightSpinBox_s").value(),
                "vertical_shift": getattr(self, "verticalShiftSpinBox_s").value(),
                "rotation": getattr(self, "rotationSpinBox_s").value(),
            }
        else:
            return {
                "num_holes": getattr(self, "numHolesSpinBox_ns").value(),
                "hole_width": getattr(self, "holeWidthSpinBox_ns").value(),
                "hole_height": getattr(self, "holeHeightSpinBox_ns").value(),
                "vertical_shift": getattr(self, "verticalShiftSpinBox_ns").value(),
                "rotation": getattr(self, "rotationSpinBox_ns").value(),
            }

    def update_form_values(self):
        pg = self.parametric_glider
        getattr(self, "numHolesSpinBox_ns").setValue(getattr(pg, 'num_holes_ns', 3))
        getattr(self, "holeWidthSpinBox_ns").setValue(getattr(pg, 'hole_width_ns', 0.3))
        getattr(self, "holeHeightSpinBox_ns").setValue(getattr(pg, 'hole_height_ns', 0.7))
        getattr(self, "verticalShiftSpinBox_ns").setValue(getattr(pg, 'vertical_shift_ns', 0.0))
        getattr(self, "rotationSpinBox_ns").setValue(getattr(pg, 'rotation_ns', 0.0))

        getattr(self, "numHolesSpinBox_s").setValue(getattr(pg, 'num_holes_s', 1))
        getattr(self, "holeWidthSpinBox_s").setValue(getattr(pg, 'hole_width_s', 0.2))
        getattr(self, "holeHeightSpinBox_s").setValue(getattr(pg, 'hole_height_s', 0.5))
        getattr(self, "verticalShiftSpinBox_s").setValue(getattr(pg, 'vertical_shift_s', 0.0))
        getattr(self, "rotationSpinBox_s").setValue(getattr(pg, 'rotation_s', 0.0))

    def update_data_and_preview(self, *args):
        pg = self.parametric_glider
        pg.num_holes_ns = getattr(self, "numHolesSpinBox_ns").value()
        pg.hole_width_ns = getattr(self, "holeWidthSpinBox_ns").value()
        pg.hole_height_ns = getattr(self, "holeHeightSpinBox_ns").value()
        pg.vertical_shift_ns = getattr(self, "verticalShiftSpinBox_ns").value()
        pg.rotation_ns = getattr(self, "rotationSpinBox_ns").value()

        pg.num_holes_s = getattr(self, "numHolesSpinBox_s").value()
        pg.hole_width_s = getattr(self, "holeWidthSpinBox_s").value()
        pg.hole_height_s = getattr(self, "holeHeightSpinBox_s").value()
        pg.vertical_shift_s = getattr(self, "verticalShiftSpinBox_s").value()
        pg.rotation_s = getattr(self, "rotationSpinBox_s").value()

        self.update_preview()

    def accept(self):
        self.update_data_and_preview()
        super(HoleDesignTool, self).accept()
