from __future__ import division

import numpy as np

import FreeCAD as App
from PySide import QtCore, QtGui

from .tools import (
    BaseTool,
    coin,
    hex_to_rgb,
    input_field,
    rgb_to_hex,
    text_field,
    vector3D,
)
from pivy.graphics import InteractionSeparator, Polygon, COLORS


class ColorPolygon(Polygon):
    std_col = [0.5, 0.5, 0.5]

    def set_enabled(self):
        self.color.diffuseColor = self.std_col
        self.enabled = True

    def set_color(self, col=None):
        self.std_col = col or self.std_col
        self.color.diffuseColor = self.std_col

    def unset_mouse_over(self):
        if self.enabled:
            self.color.diffuseColor = self.std_col

    def unselect(self):
        if self.enabled:
            self.color.diffuseColor = self.std_col


def refresh():
    pass


class ColorTool(BaseTool):
    widget_name = "Color Tool"

    def __init__(self, obj):
        super(ColorTool, self).__init__(obj)

        self.panels = self.parametric_glider.get_panels()

        # panel.materialcode
        # panel.cut_back
        # panel.cut_front
        # cut_front['left']

        # setup the GUI
        self.setup_widget()
        self.setup_pivy()

    def setup_widget(self):
        self.Qcolore_select = QtGui.QPushButton("select color")
        self.layout.setWidget(0, input_field, self.Qcolore_select)
        self.color_dialog = QtGui.QColorDialog()
        self.Qcolore_select.clicked.connect(self.color_dialog.open)
        self.color_dialog.accepted.connect(self.set_color)

        self.Qcolore_replace = QtGui.QPushButton("replace color")
        self.layout.setWidget(1, input_field, self.Qcolore_replace)
        self.color_replace_dialog = QtGui.QColorDialog()
        self.Qcolore_replace.clicked.connect(self.color_replace_dialog.open)
        self.color_replace_dialog.accepted.connect(self.replace_color)

    def setup_pivy(self):
        # get 2d shape properties

        self.selector = InteractionSeparator(self.rm)
        self.task_separator += [self.selector]
        x_values = self.parametric_glider.shape.rib_x_values
        if self.parametric_glider.shape.has_center_cell:
            x_values = [-x_values[0]] + x_values
        for i, cell in enumerate(self.panels):
            for j, panel in enumerate(cell):
                # Get panel y_start/y_end for split panels
                y_start = getattr(panel, 'y_start', 0.0)
                y_end = getattr(panel, 'y_end', 1.0)
                
                # Interpolate X positions based on y range
                x_left = x_values[i] + y_start * (x_values[i + 1] - x_values[i])
                x_right = x_values[i] + y_end * (x_values[i + 1] - x_values[i])
                
                # Interpolate cut positions based on y range
                front_left = panel.cut_front["left"] + y_start * (panel.cut_front["right"] - panel.cut_front["left"])
                front_right = panel.cut_front["left"] + y_end * (panel.cut_front["right"] - panel.cut_front["left"])
                back_left = panel.cut_back["left"] + y_start * (panel.cut_back["right"] - panel.cut_back["left"])
                back_right = panel.cut_back["left"] + y_end * (panel.cut_back["right"] - panel.cut_back["left"])
                
                p1 = [x_left, front_left, 0.0]
                p2 = [x_left, back_left, 0.0]
                p3 = [x_right, back_right, 0.0]
                p4 = [x_right, front_right, 0.0]
                vis_panel = ColorPolygon([p1, p2, p3, p4][::-1], True)
                panel.vis_panel = vis_panel
                if panel.material_code:
                    vis_panel.set_color(hex_to_rgb(panel.material_code))
                self.selector += [vis_panel]

        self.selector.register()

    def set_color(self):
        color = self.color_dialog.currentColor().getRgbF()[:-1]
        for panel in self.selector.selected_objects:
            panel.set_color(color)

    def replace_color(self):
        assert len(self.selector.selected_objects) == 1
        old_color = self.selector.selected_objects[0].std_col
        color = self.color_replace_dialog.currentColor().getRgbF()[:-1]
        for panel in self.selector.dynamic_objects:
            if panel.std_col == old_color:
                panel.set_color(color)

    def accept(self):
        self.selector.unregister()
        colors = []
        colors_by_name = {}  # New: store by panel name for split panels
        
        for cell in self.panels:
            cell_colors = []
            for panel in cell:
                # Get the color and save it directly to the panel
                color_code = rgb_to_hex(panel.vis_panel.std_col, "skytex32_")
                panel.material_code = color_code
                cell_colors.append(color_code)
                # Also store by panel name for split panels
                colors_by_name[panel.name] = color_code
            colors.append(cell_colors)

        self.parametric_glider.elements["materials"] = colors
        self.parametric_glider.elements["materials_by_name"] = colors_by_name
        super(ColorTool, self).accept()
        self.update_view_glider()

    def reject(self):
        self.selector.unregister()
        super(ColorTool, self).reject()
