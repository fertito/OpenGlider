from .tools import BaseTool, input_field
from .table import base_table_widget
from .glider import draw_glider
from PySide import QtGui
from openglider.glider.rib import MiniRib


class MiniRibsTool(BaseTool):
    hide = True
    turn = False
    widget_name = "Mini Ribs"

    def __init__(self, obj):
        super(MiniRibsTool, self).__init__(obj)
        self.miniribs_table = miniribs_table()
        self.miniribs_table.get_from_ParametricGlider(self.parametric_glider)
        
        # If no miniribs in elements, populate with defaults
        if not self.parametric_glider.elements.get("miniribs"):
            self.set_defaults()
            # Apply defaults immediately so they exist in backend
            self.apply_elements()

        self.miniribs_button = QtGui.QPushButton("edit miniribs")
        self.miniribs_button.clicked.connect(self.miniribs_table.show)
        self.layout.setWidget(0, input_field, self.miniribs_button)

        self.draw_glider()

    def set_defaults(self):
        # Default values requested by user
        # Intrados: 80% - 99%
        # Extrados: 75% - 99%
        # Centered: y=0.5
        # All cells
        
        try:
            glider_inst = self.obj.Proxy.getGliderInstance()
            num_cells = len(glider_inst.cells)
            all_cells = list(range(num_cells))
        except Exception:
            all_cells = [0] 

        default_row = {
            "yvalue": 0.5,
            "intrados_start": 0.8,
            "extrados_start": 0.75,
            "end_distance_cm": 2.0,  # 2cm from TE
            "transition_length": 0.05,  # 5% chord progressive transition
            "cells": all_cells
        }
        
        self.miniribs_table.table.setRowCount(1)
        self.miniribs_table.set_row(0, default_row)

    def draw_glider(self):
        self.task_separator.removeAllChildren()
        draw_glider(
            self.parametric_glider.get_glider_3d(),
            self.task_separator,
            ribs=True,
            fill_ribs=False,
        )

    def apply_elements(self):
        self.miniribs_table.apply_to_glider(self.parametric_glider)
        self.draw_glider()

    def accept(self):
        self.apply_elements()
        self.update_view_glider()
        self.miniribs_table.hide()
        del self.miniribs_table
        self.task_separator.removeAllChildren()  # Clean up visualization
        super(MiniRibsTool, self).accept()

    def reject(self):
        self.miniribs_table.hide()
        del self.miniribs_table
        self.task_separator.removeAllChildren()  # Clean up visualization
        super(MiniRibsTool, self).reject()


class miniribs_table(base_table_widget):
    name = "miniribs"
    keyword = "miniribs"

    def __init__(self):
        super(miniribs_table, self).__init__(name="miniribs")
        self.table.setRowCount(200)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "y_value",
                "int_start",
                "ext_start",
                "end_cm",      # Fixed distance from TE in cm
                "trans_len",   # Transition length (chord %)
                "cells",
            ]
        )

    def get_from_ParametricGlider(self, ParametricGlider):
        if "miniribs" in ParametricGlider.elements:
            miniribs = ParametricGlider.elements["miniribs"]
            for row, element in enumerate(miniribs):
                # end_distance is stored in meters, display in cm
                end_dist_cm = (element.get("end_distance") or 0.02) * 100
                entries = [
                    element.get("yvalue", 0.5),
                    element.get("intrados_start", 0.8),
                    element.get("extrados_start", 0.75),
                    end_dist_cm,
                    element.get("transition_length", 0.05),
                ]
                entries.append(element.get("cells", [0]))
                self.table.setRow(row, entries)

    def set_row(self, row_idx, data):
        entries = [
            data["yvalue"],
            data["intrados_start"],
            data["extrados_start"],
            data.get("end_distance_cm", 2.0),  # in cm
            data.get("transition_length", 0.05),
            data["cells"]
        ]
        self.table.setRow(row_idx, entries)

    def apply_to_glider(self, ParametricGlider):
        num_rows = self.table.rowCount()
        ParametricGlider.elements[self.keyword] = []
        for n_row in range(num_rows):
            row = self.get_row(n_row)
            if row:
                minirib = {}
                minirib["yvalue"] = row[0]
                minirib["intrados_start"] = row[1]
                minirib["extrados_start"] = row[2]
                # Convert cm to meters for storage
                end_cm = row[3]
                minirib["end_distance"] = end_cm / 100 if end_cm > 0 else 0.02
                minirib["transition_length"] = row[4]
                minirib["cells"] = row[-1]
                minirib["name"] = "minirib" 
                ParametricGlider.elements["miniribs"].append(minirib)

    def get_row(self, n_row):
        str_row = [
            self.table.item(n_row, i).text()
            for i in range(6)
            if self.table.item(n_row, i)
        ]
        str_row = [item for item in str_row if item != ""]
        if len(str_row) != 6:
            return None
        try:
            # Replace comma with dot for French locale decimal separator
            float_values = [float(s.replace(',', '.')) for s in str_row[:-1]]
            cell_values = list(map(int, str_row[-1].replace(' ', '').split(",")))
            return float_values + [cell_values]
        except (TypeError, ValueError) as e:
            print(e)
            print("something wrong with row " + str(n_row))
            return None

