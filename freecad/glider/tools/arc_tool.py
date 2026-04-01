import FreeCADGui as Gui
from pivy import coin

from openglider.vector.polygon import CirclePart
from PySide import QtGui, QtCore

from pivy.graphics import InteractionSeparator, Line, Point, Marker

from .tools import (
    BaseTool,
    input_field,
    spline_select,
    text_field,
    vector3D,
    vector2D,
    ControlPointContainer,
)


class ArcTool(BaseTool):
    hide = False
    widget_name = "ArcTool"

    def __init__(self, obj):
        """adds a symmetric spline to the scene"""
        super(ArcTool, self).__init__(obj)
        sbrot1 = coin.SbRotation()
        sbrot1.setValue(coin.SbVec3f(1, 0, 0), coin.SbVec3f(0, 1, 0))
        sbrot2 = coin.SbRotation()
        sbrot2.setValue(coin.SbVec3f(0, 0, 1), coin.SbVec3f(0, 1, 0))
        self.obj.ViewObject.Proxy.rotate(sbrot1 * sbrot2)

        controlpoints = list(
            map(vector3D, self.parametric_glider.arc.curve.controlpoints)
        )
        self.arc_cpc = ControlPointContainer(self.rm, controlpoints)
        self.Qnum_arc = QtGui.QSpinBox(self.base_widget)
        self.spline_select = spline_select(
            [self.parametric_glider.arc.curve],
            self.update_spline_type,
            self.base_widget,
        )
        self.shape = coin.SoSeparator()
        self.circle = coin.SoSeparator()
        self.task_separator += self.arc_cpc, self.shape, self.circle

        # Arc properties widgets (read-only info)
        self.Qarc_length = QtGui.QDoubleSpinBox(self.base_widget)
        self.Qprojected_span = QtGui.QDoubleSpinBox(self.base_widget)
        self.Qarc_height = QtGui.QDoubleSpinBox(self.base_widget)
        self.Qflattening = QtGui.QDoubleSpinBox(self.base_widget)

        # Control points table (normalized)
        self.Qpoints_table = QtGui.QTableWidget(self.base_widget)
        self.Qapply_points = QtGui.QPushButton("Apply Points", self.base_widget)

        self.setup_widget()
        self.setup_pivy()

    def setup_widget(self):
        self.Qnum_arc.setMaximum(9)
        self.Qnum_arc.setMinimum(2)
        self.Qnum_arc.setValue(len(self.parametric_glider.arc.curve.controlpoints))
        self.parametric_glider.arc.curve.numpoints = self.Qnum_arc.value()

        # Basic controls
        self.layout.setWidget(0, text_field, QtGui.QLabel("arc num_points"))
        self.layout.setWidget(0, input_field, self.Qnum_arc)
        self.layout.setWidget(1, text_field, QtGui.QLabel("bspline type"))
        self.layout.setWidget(1, input_field, self.spline_select)

        # Separator - Arc Properties
        separator1 = QtGui.QFrame()
        separator1.setFrameShape(QtGui.QFrame.HLine)
        separator1.setFrameShadow(QtGui.QFrame.Sunken)
        self.layout.setWidget(2, text_field, separator1)
        self.layout.setWidget(2, input_field, QtGui.QLabel("Arc Properties"))

        # Arc properties (read-only)
        self._setup_readonly_spinbox(self.Qarc_length, " m", 3)
        self._setup_readonly_spinbox(self.Qprojected_span, " m", 3)
        self._setup_readonly_spinbox(self.Qarc_height, " m", 3)
        self._setup_readonly_spinbox(self.Qflattening, " %", 1)
        self.Qflattening.setMaximum(100.0)

        # Légende lecture seule
        legend = QtGui.QLabel("ℹ️  Valeurs calculées (lecture seule)")
        legend.setStyleSheet("color: #7ab3e0; font-style: italic; font-size: 10px;")
        self.layout.setWidget(3, text_field, legend)

        self.layout.setWidget(4, text_field, QtGui.QLabel("Arc length"))
        self.layout.setWidget(4, input_field, self.Qarc_length)
        self.layout.setWidget(5, text_field, QtGui.QLabel("Projected span"))
        self.layout.setWidget(5, input_field, self.Qprojected_span)
        self.layout.setWidget(6, text_field, QtGui.QLabel("Arc height"))
        self.layout.setWidget(6, input_field, self.Qarc_height)
        self.layout.setWidget(7, text_field, QtGui.QLabel("Flattening"))
        self.layout.setWidget(7, input_field, self.Qflattening)

        # Separator - Control Points
        separator2 = QtGui.QFrame()
        separator2.setFrameShape(QtGui.QFrame.HLine)
        separator2.setFrameShadow(QtGui.QFrame.Sunken)
        self.layout.setWidget(8, text_field, separator2)
        self.layout.setWidget(8, input_field, QtGui.QLabel("Control Points (%)"))

        # Control points table (normalized)
        self.Qpoints_table.setColumnCount(3)
        self.Qpoints_table.setHorizontalHeaderLabels(["#", "Y (%)", "Z (%)"])
        self.Qpoints_table.horizontalHeader().setStretchLastSection(True)
        self.Qpoints_table.setColumnWidth(0, 30)
        self.Qpoints_table.setMaximumHeight(180)
        self.Qpoints_table.setEditTriggers(QtGui.QAbstractItemView.DoubleClicked)

        self.layout.setWidget(9, text_field, self.Qpoints_table)
        self.layout.setWidget(10, input_field, self.Qapply_points)

        # Connections
        self.Qnum_arc.valueChanged.connect(self.update_num)
        self.Qapply_points.clicked.connect(self.apply_control_points)

    def _setup_readonly_spinbox(self, spinbox, suffix, decimals):
        """Configure a spinbox for read-only display"""
        spinbox.setReadOnly(True)
        spinbox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        spinbox.setSuffix(suffix)
        spinbox.setDecimals(decimals)
        spinbox.setMaximum(9999.0)
        spinbox.setMinimum(-9999.0)
        spinbox.setStyleSheet("QDoubleSpinBox { background-color: #1a3a5c; color: #ffffff; border: 1px solid #2a5a8c; }")

    def setup_pivy(self):
        self.arc_cpc.on_drag.append(self.update_spline)
        self.arc_cpc.on_drag_release.append(self.update_real_arc)
        self.arc_cpc.on_drag_release.append(self.update_arc_properties)

        self.update_spline()
        self.update_real_arc()
        self.update_num()
        self.update_arc_properties()

    def update_spline(self):
        self.shape.removeAllChildren()
        self.parametric_glider.arc.curve.controlpoints = [
            vector2D(i) for i in self.arc_cpc.control_pos
        ]
        l = Line(vector3D(self.parametric_glider.arc.curve.get_sequence(num=30)))
        l.drawstyle.lineWidth = 2
        self.shape += l
        self.draw_circle()

    def draw_circle(self):
        self.circle.removeAllChildren()
        p1, p2, p3 = self.parametric_glider.arc.curve.get_sequence(num=30)[[0, 15, -1]]
        circle = CirclePart(p1, p2, p3)
        self.circle += Line(vector3D(circle.get_sequence()))
        self.circle += Point(vector3D([circle.center]))
        self.circle += Line(vector3D([p2, circle.center, p3]))

    def update_spline_type(self):
        self.arc_cpc.control_pos = self.parametric_glider.arc.curve.controlpoints
        self.update_spline()

    def get_arc_positions(self):
        return self.parametric_glider.arc.get_arc_positions(
            self.parametric_glider.shape.rib_x_values
        )

    def update_real_arc(self):
        l = Line(vector3D(self.get_arc_positions()))
        l.drawstyle.lineWidth = 2
        l.set_color("red")
        self.shape += l

    def update_num(self, *arg):
        self.parametric_glider.arc.curve.numpoints = self.Qnum_arc.value()
        self.arc_cpc.control_pos = self.parametric_glider.arc.curve.controlpoints
        self.update_spline()
        self.update_arc_properties()

    def _get_half_span(self):
        """Get half span from the last control point's Y coordinate"""
        controlpoints = self.parametric_glider.arc.curve.controlpoints
        if len(controlpoints) > 0:
            return abs(controlpoints[-1][0])
        return 1.0  # fallback

    def update_arc_properties(self):
        """Update the read-only arc properties display"""
        x_values = self.parametric_glider.shape.rib_x_values
        arc = self.parametric_glider.arc

        # Block signals
        self.Qarc_length.blockSignals(True)
        self.Qprojected_span.blockSignals(True)
        self.Qarc_height.blockSignals(True)
        self.Qflattening.blockSignals(True)

        # Update values (multiply by 2 for full span)
        self.Qarc_length.setValue(arc.get_arc_length(x_values) * 2)
        self.Qprojected_span.setValue(arc.get_projected_span(x_values) * 2)
        self.Qarc_height.setValue(arc.get_height(x_values))
        self.Qflattening.setValue(arc.get_flattening(x_values) * 100)

        self.Qarc_length.blockSignals(False)
        self.Qprojected_span.blockSignals(False)
        self.Qarc_height.blockSignals(False)
        self.Qflattening.blockSignals(False)

        # Update control points table
        self.update_points_table()

    def update_points_table(self):
        """Update the control points table with normalized values (%)"""
        controlpoints = self.parametric_glider.arc.curve.controlpoints
        half_span = self._get_half_span()

        self.Qpoints_table.blockSignals(True)
        self.Qpoints_table.setRowCount(len(controlpoints))

        for i, pt in enumerate(controlpoints):
            # Point number (read-only)
            num_item = QtGui.QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~QtCore.Qt.ItemIsEditable)
            num_item.setTextAlignment(QtCore.Qt.AlignCenter)
            num_item.setBackground(QtGui.QColor(26, 58, 92))  # bleu read-only
            num_item.setForeground(QtGui.QColor(255, 255, 255))
            self.Qpoints_table.setItem(i, 0, num_item)

            # Y % (normalized)
            y_pct = (pt[0] / half_span) * 100 if half_span != 0 else 0
            y_item = QtGui.QTableWidgetItem(f"{y_pct:.2f}")
            # First point Y is fixed at 0%, last point Y is fixed at 100%
            if i == 0 or i == len(controlpoints) - 1:
                y_item.setFlags(y_item.flags() & ~QtCore.Qt.ItemIsEditable)
                y_item.setBackground(QtGui.QColor(26, 58, 92))  # bleu read-only
                y_item.setForeground(QtGui.QColor(255, 255, 255))
            self.Qpoints_table.setItem(i, 1, y_item)

            # Z % (normalized - negative values are below)
            z_pct = (pt[1] / half_span) * 100 if half_span != 0 else 0
            z_item = QtGui.QTableWidgetItem(f"{z_pct:.2f}")
            self.Qpoints_table.setItem(i, 2, z_item)

        self.Qpoints_table.blockSignals(False)

    def apply_control_points(self):
        """Apply edited control points from the table"""
        import numpy as np

        half_span = self._get_half_span()
        new_controlpoints = []

        for i in range(self.Qpoints_table.rowCount()):
            y_item = self.Qpoints_table.item(i, 1)
            z_item = self.Qpoints_table.item(i, 2)

            if y_item and z_item:
                try:
                    y_pct = float(y_item.text())
                    z_pct = float(z_item.text())

                    # Denormalize: convert % back to absolute values
                    y_abs = (y_pct / 100) * half_span
                    z_abs = (z_pct / 100) * half_span

                    new_controlpoints.append(np.array([y_abs, z_abs]))
                except ValueError:
                    # Keep original point if parsing fails
                    original = self.parametric_glider.arc.curve.controlpoints[i]
                    new_controlpoints.append(np.array(original))

        # Update the curve
        self.parametric_glider.arc.curve.controlpoints = new_controlpoints

        # Update visual controls
        self.arc_cpc.control_pos = self.parametric_glider.arc.curve.controlpoints

        # Refresh display
        self.update_spline()
        self.update_real_arc()
        self.update_arc_properties()

    def accept(self):
        self.arc_cpc.remove_callbacks()
        super(ArcTool, self).accept()
        self.obj.ViewObject.Proxy.rotate()
        self.update_view_glider()
        Gui.activeDocument().activeView().viewFront()

    def reject(self):
        self.arc_cpc.remove_callbacks()
        self.obj.ViewObject.Proxy.rotate()
        Gui.activeDocument().activeView().viewFront()
        super(ArcTool, self).reject()
