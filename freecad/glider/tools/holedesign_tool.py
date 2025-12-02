import os
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
from .features import HoleFeature

class HoleDesignTool:
    def __init__(self):
        self.task_panel = None

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..",
                "icons",
                "hole_design_command.svg",
            ),
            "MenuText": "Hole Design Tool",
            "ToolTip": "Create and edit holes in glider profiles",
        }

    def Activated(self):
        self.task_panel = HoleDesignTaskPanel()
        Gui.Control.showDialog(self.task_panel)

    def IsActive(self):
        return self.task_panel is not None and self.task_panel.isVisible()

class HoleDesignTaskPanel:
    def __init__(self):
        self.form = Gui.PySideUic.loadUi(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..",
                "ui",
                "holedesign.ui",
            )
        )
        self.form.applyButton.clicked.connect(self.apply_changes)

    def apply_changes(self):
        selection = Gui.Selection.getSelection()
        if not selection:
            App.Console.PrintWarning("Please select a HoleFeature object.\\n")
            return

        hole_feature = selection[0].Proxy
        if not isinstance(hole_feature, HoleFeature):
            App.Console.PrintWarning("Please select a HoleFeature object.\\n")
            return

        hole_feature.obj.holes = True
        hole_feature.obj.hole_width = self.form.holeWidthSpinBox.value()
        hole_feature.obj.hole_height = self.form.holeHeightSpinBox.value()
        hole_feature.obj.vertical_shift = self.form.verticalShiftSpinBox.value()
        hole_feature.obj.rotation = self.form.rotationSpinBox.value()

        # For simplicity, we'll just recompute the document
        App.ActiveDocument.recompute()

    def accept(self):
        return True

    def reject(self):
        return True

    def get_form(self):
        return self.form

def register():
    Gui.addCommand("HoleDesignTool", HoleDesignTool())
