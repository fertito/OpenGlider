from .tools import BaseTool, Line_old
import FreeCADGui as Gui
from PySide import QtCore, QtGui
from openglider.glider.rib import RibHole
import numpy as np
from pivy import coin
import os
import FreeCAD

class HoleDesignTool(BaseTool):
    widget_name = "Hole Design"

    def __init__(self, obj):
        FreeCAD.Console.PrintMessage("--- HoleDesignTool: __init__ started ---\\n")
        super(HoleDesignTool, self).__init__(obj)
        FreeCAD.Console.PrintMessage(f"BaseTool init complete. self.base_widget: {self.base_widget}, self.layout: {self.layout}\\n")
        FreeCAD.Console.PrintMessage(f"Initial self.form from BaseTool: {self.form}\\n")

        # UI Elements with parent widget specified
        self.ribTypeComboBox = QtGui.QComboBox(self.base_widget)
        self.numHolesSpinBox = QtGui.QSpinBox(self.base_widget)
        self.holeWidthSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.holeHeightSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.verticalShiftSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.rotationSpinBox = QtGui.QDoubleSpinBox(self.base_widget)
        self.applyButton = QtGui.QPushButton("Apply", self.base_widget)
        FreeCAD.Console.PrintMessage("UI widgets created.\\n")

        self.preview_root = coin.SoSeparator()
        self.setup_widget()
        FreeCAD.Console.PrintMessage("setup_widget complete.\\n")
        self.setup_pivy()
        FreeCAD.Console.PrintMessage("setup_pivy complete.\\n")
        FreeCAD.Console.PrintMessage(f"Final self.form before exiting __init__: {self.form}\\n")
        FreeCAD.Console.PrintMessage("--- HoleDesignTool: __init__ finished ---\\n")


    def setup_widget(self):
        FreeCAD.Console.PrintMessage("--- setup_widget started ---\\n")
        # Add items to combo box
        self.ribTypeComboBox.addItems(["Non-Suspended", "Suspended"])

        # Add widgets to the QFormLayout provided by BaseTool
        self.layout.addRow("Rib Type", self.ribTypeComboBox)
        self.layout.addRow("Number of Holes", self.numHolesSpinBox)
        self.layout.addRow("Hole Width (%)", self.holeWidthSpinBox)
        self.layout.addRow("Hole Height (%)", self.holeHeightSpinBox)
        self.layout.addRow("Vertical Shift (%)", self.verticalShiftSpinBox)
        self.layout.addRow("Rotation (deg)", self.rotationSpinBox)

        # Right-align the apply button
        button_layout = QtGui.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.applyButton)
        self.layout.addRow(button_layout)
        FreeCAD.Console.PrintMessage("Widgets added to layout.\\n")

        # Configure spinboxes
        for spinbox in [self.holeWidthSpinBox, self.holeHeightSpinBox, self.verticalShiftSpinBox]:
            spinbox.setSingleStep(0.01)
            spinbox.setDecimals(3)
            spinbox.setMinimum(0.0)
            spinbox.setMaximum(1.0) # Relative to chord
        self.rotationSpinBox.setSingleStep(1.0)
        self.rotationSpinBox.setMinimum(-180)
        self.rotationSpinBox.setMaximum(180)

        # Load initial values
        self.update_form_from_glider_data()

        # Connections
        self.ribTypeComboBox.currentIndexChanged.connect(self.on_rib_type_change)
        self.numHolesSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.holeWidthSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.holeHeightSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.verticalShiftSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.rotationSpinBox.valueChanged.connect(self.update_glider_data_and_preview)
        self.applyButton.clicked.connect(self.accept)
        FreeCAD.Console.PrintMessage(f"self.form in setup_widget: {self.form}\\n")
        FreeCAD.Console.PrintMessage("--- setup_widget finished ---\\n")

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
        # Then, load the values for the newly selected rib type
        self.update_form_from_glider_data()
        self.update_preview()

    def update_preview(self, *args):
        self.preview_root.removeAllChildren()

        is_suspended = self.ribTypeComboBox.currentIndex() == 1
        rib = self.get_representative_rib(suspended=is_suspended)
        if not rib: return

        profile_points = list(rib.profile_2d.data)
        # Manually close the polygon by appending the start point
        self.preview_root.addChild(Line_old(profile_points + [profile_points[0]], width=2).object)

        # Draw attachment points
        glider_instance = self.obj.Proxy.getGliderInstance()
        attachment_points = glider_instance.get_rib_attachment_points(rib)
        for ap in attachment_points:
            # Align on the bottom surface (intrados)
            point_2d = rib.profile_2d.align([ap.rib_pos, -1.0])

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

        # Get current parameters from the UI
        num_holes = self.numHolesSpinBox.value()
        hole_width = self.holeWidthSpinBox.value() * rib.chord
        hole_height = self.holeHeightSpinBox.value() * rib.chord
        vertical_shift = self.verticalShiftSpinBox.value() * rib.chord
        rotation = self.rotationSpinBox.value()

        for i in range(num_holes):
            pos_x = (i + 1.0) / (num_holes + 1.0)
            camber_point = rib.profile_2d.profilepoint(pos_x, 0.0)
            hole_center = np.array([camber_point[0], camber_point[1] + vertical_shift])

            ellipse_points = []
            for angle in np.linspace(0, 2 * np.pi, 50):
                x = hole_width/2 * np.cos(angle)
                y = hole_height/2 * np.sin(angle)
                ellipse_points.append([x, y])

            ellipse_poly = np.array(ellipse_points)
            rot_matrix = np.array([[np.cos(np.deg2rad(rotation)), -np.sin(np.deg2rad(rotation))],
                                   [np.sin(np.deg2rad(rotation)), np.cos(np.deg2rad(rotation))]])
            ellipse_poly = ellipse_poly.dot(rot_matrix)
            ellipse_poly += hole_center

            ellipse_points_closed = list(ellipse_poly)
            self.preview_root.addChild(Line_old(ellipse_points_closed + [ellipse_points_closed[0]], color='blue').object)

        self.view.draw()

    def update_form_from_glider_data(self):
        pg = self.parametric_glider
        is_suspended = self.ribTypeComboBox.currentIndex() == 1

        suffix = "_s" if is_suspended else "_ns"

        # Block signals to prevent feedback loops
        for widget in [self.numHolesSpinBox, self.holeWidthSpinBox, self.holeHeightSpinBox, self.verticalShiftSpinBox, self.rotationSpinBox]:
            widget.blockSignals(True)

        self.numHolesSpinBox.setValue(getattr(pg, f'num_holes{suffix}', 3 if not is_suspended else 1))
        self.holeWidthSpinBox.setValue(getattr(pg, f'hole_width{suffix}', 0.1))
        self.holeHeightSpinBox.setValue(getattr(pg, f'hole_height{suffix}', 0.05))
        self.verticalShiftSpinBox.setValue(getattr(pg, f'vertical_shift{suffix}', 0.0))
        self.rotationSpinBox.setValue(getattr(pg, f'rotation{suffix}', 0.0))

        # Unblock signals
        for widget in [self.numHolesSpinBox, self.holeWidthSpinBox, self.holeHeightSpinBox, self.verticalShiftSpinBox, self.rotationSpinBox]:
            widget.blockSignals(False)

    def update_glider_data_and_preview(self, *args, switch=False):
        pg = self.parametric_glider

        # When switching tabs, we need to know which set of data to save.
        # The index gives the *new* tab, so we save to the *opposite* of the current one if switching.
        current_idx = self.ribTypeComboBox.currentIndex()
        is_suspended = (current_idx == 1 and not switch) or \
                       (current_idx == 0 and switch)

        suffix = "_s" if is_suspended else "_ns"

        setattr(pg, f'num_holes{suffix}', self.numHolesSpinBox.value())
        setattr(pg, f'hole_width{suffix}', self.holeWidthSpinBox.value())
        setattr(pg, f'hole_height{suffix}', self.holeHeightSpinBox.value())
        setattr(pg, f'vertical_shift{suffix}', self.verticalShiftSpinBox.value())
        setattr(pg, f'rotation{suffix}', self.rotationSpinBox.value())

        self.update_preview()

    def accept(self):
        self.update_glider_data_and_preview()
        super(HoleDesignTool, self).accept()
