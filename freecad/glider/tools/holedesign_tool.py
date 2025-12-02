import os
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore

# This class will be instantiated by a command in __init__.py
class HoleDesignTool(object):
    def __init__(self, obj):
        self.obj = obj
        self.form = Gui.PySideUic.loadUi(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..",
                "ui",
                "holedesign.ui",
            )
        )
        self.form.applyButton.clicked.connect(self.apply_changes)

        # Populate the form with current values from the selected feature
        self.update_form()

    def update_form(self):
        selection = Gui.Selection.getSelection()
        if not selection or not hasattr(selection[0], "Proxy") or not hasattr(selection[0].Proxy, "obj"):
            return

        feature_obj = selection[0]
        if "hole_width" in feature_obj.PropertiesList:
            self.form.holeWidthSpinBox.setValue(feature_obj.hole_width)
            self.form.holeHeightSpinBox.setValue(feature_obj.hole_height)
            self.form.verticalShiftSpinBox.setValue(feature_obj.vertical_shift)
            self.form.rotationSpinBox.setValue(feature_obj.rotation)

    def apply_changes(self):
        selection = Gui.Selection.getSelection()
        if not selection:
            App.Console.PrintWarning("Please select a HoleFeature object to apply changes.\\n")
            return

        feature_obj = selection[0]

        # Check if it's a hole feature
        if not "hole_width" in feature_obj.PropertiesList:
            App.Console.PrintWarning("Selected object is not a valid HoleFeature.\\n")
            return

        feature_obj.holes = True
        feature_obj.hole_width = self.form.holeWidthSpinBox.value()
        feature_obj.hole_height = self.form.holeHeightSpinBox.value()
        feature_obj.vertical_shift = self.form.verticalShiftSpinBox.value()
        feature_obj.rotation = self.form.rotationSpinBox.value()

        App.ActiveDocument.recompute()
        App.Console.PrintMessage("Hole properties updated.\\n")

    def accept(self):
        self.apply_changes()
        Gui.Control.closeDialog(self)
        return True

    def reject(self):
        Gui.Control.closeDialog(self)
        return True

    def get_form(self):
        return self.form
