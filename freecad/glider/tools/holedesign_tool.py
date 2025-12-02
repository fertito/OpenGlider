import os
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
from openglider.glider.rib import RibHole
import numpy as np

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

        # --- Graphics View Setup ---
        self.scene = QtGui.QGraphicsScene()
        self.form.profileView.setScene(self.scene)
        self.profile_item = None
        self.attachment_items = []
        self.hole_items = []
        # -------------------------

        # --- Connections ---
        self.form.applyButton.clicked.connect(self.accept)
        self.form.numHolesSpinBox.valueChanged.connect(self.update_preview)
        self.form.holeWidthSpinBox.valueChanged.connect(self.update_preview)
        self.form.holeHeightSpinBox.valueChanged.connect(self.update_preview)
        self.form.verticalShiftSpinBox.valueChanged.connect(self.update_preview)
        self.form.rotationSpinBox.valueChanged.connect(self.update_preview)
        # -------------------

        self.update_form()
        self.draw_profile_and_attachments()
        self.update_preview()

    def get_glider_and_rib(self):
        """Finds the parent glider and a representative rib for visualization."""
        try:
            feature_obj = Gui.Selection.getSelection()[0]
            glider_obj = feature_obj.parent
            if not hasattr(glider_obj, "Proxy") or not hasattr(glider_obj.Proxy, "getGliderInstance"):
                return None, None

            glider_instance = glider_obj.Proxy.getGliderInstance()

            # In auto mode, find the first non-suspended rib to use as a preview
            if feature_obj.auto_holes:
                suspended_ribs = {att.rib for att in glider_instance.lineset.attachment_points if hasattr(att, 'rib')}
                for rib in glider_instance.ribs:
                    if rib not in suspended_ribs:
                        return glider_instance, rib # Return the first non-suspended rib

            # In manual mode, or if auto mode finds nothing, use the first selected rib
            elif feature_obj.ribs:
                rib_index = feature_obj.ribs[0]
                if rib_index < len(glider_instance.ribs):
                    return glider_instance, glider_instance.ribs[rib_index]

        except Exception as e:
            App.Console.PrintError(f"Error getting glider/rib for preview: {e}\\n")

        return None, None # Default if no suitable rib is found

    def draw_profile_and_attachments(self):
        self.scene.clear()
        self.profile_item = None
        self.attachment_items = []

        glider, rib = self.get_glider_and_rib()
        if not rib:
            return

        # Draw profile
        profile_data = rib.profile_2d.data
        path = QtGui.QPainterPath()
        path.moveTo(profile_data[0][0], -profile_data[0][1])
        for point in profile_data[1:]:
            path.lineTo(point[0], -point[1])
        path.closeSubpath()

        self.profile_item = self.scene.addPath(path, QtGui.QPen(QtCore.Qt.black))

        # Draw attachment points
        attachment_points = glider.get_rib_attachment_points(rib)
        for ap in attachment_points:
            pos_on_profile = rib.profile_2d.profilepoint(ap.rib_pos)
            ellipse = self.scene.addEllipse(
                pos_on_profile[0] - 0.01, -pos_on_profile[1] - 0.01, 0.02, 0.02,
                QtGui.QPen(QtCore.Qt.red), QtGui.QBrush(QtCore.Qt.red)
            )
            self.attachment_items.append(ellipse)

        # Fit view
        self.form.profileView.fitInView(self.scene.itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)

    def update_preview(self):
        # Clear only the holes
        for item in self.hole_items:
            self.scene.removeItem(item)
        self.hole_items = []

        glider, rib = self.get_glider_and_rib()
        if not rib:
            return

        num_holes = self.form.numHolesSpinBox.value()
        hole_width = self.form.holeWidthSpinBox.value()
        hole_height = self.form.holeHeightSpinBox.value()
        vertical_shift = self.form.verticalShiftSpinBox.value()
        rotation = self.form.rotationSpinBox.value()

        # Distribute holes evenly for preview
        for i in range(num_holes):
            pos_x = (i + 1) / (num_holes + 1)

            # Find center point on camber line for the hole
            camber_point = rib.profile_2d.profilepoint(pos_x, 0.0) # h=0.0 for camber line

            hole = RibHole(
                pos_x,
                size=np.array([hole_width, hole_height]),
                vertical_shift=vertical_shift,
                rotation=rotation
            )

            # For simplicity, we draw an ellipse. A more accurate representation
            # would require projecting the hole shape onto the 2D profile plane.
            ellipse = QtGui.QGraphicsEllipseItem(
                -hole.size[0]/2, -hole.size[1]/2, hole.size[0], hole.size[1]
            )
            ellipse.setPos(camber_point[0], -camber_point[1] - hole.vertical_shift)
            ellipse.setRotation(-hole.rotation) # Rotation in QGraphicsView is counter-clockwise
            ellipse.setPen(QtGui.QPen(QtCore.Qt.blue))

            self.scene.addItem(ellipse)
            self.hole_items.append(ellipse)


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
            self.form.numHolesSpinBox.setValue(feature_obj.num_holes)


    def apply_changes(self):
        selection = Gui.Selection.getSelection()
        if not selection:
            App.Console.PrintWarning("Please select a HoleFeature object to apply changes.\\n")
            return

        feature_obj = selection[0]
        if not "hole_width" in feature_obj.PropertiesList:
            App.Console.PrintWarning("Selected object is not a valid HoleFeature.\\n")
            return


        feature_obj.holes = True # Enable hole creation
        feature_obj.num_holes = self.form.numHolesSpinBox.value()
        feature_obj.hole_width = self.form.holeWidthSpinBox.value()
        feature_obj.hole_height = self.form.holeHeightSpinBox.value()
        feature_obj.vertical_shift = self.form.verticalShiftSpinBox.value()
        feature_obj.rotation = self.form.rotationSpinBox.value()

        # The original HoleFeature automatically finds attachment points.
        # We just need to trigger a recompute.
        App.ActiveDocument.recompute()
        App.Console.PrintMessage("Hole properties updated. Recomputing glider...\\n")

    def accept(self):
        self.apply_changes()
        Gui.Control.closeDialog(self)
        return True

    def reject(self):
        Gui.Control.closeDialog(self)
        return True

    def get_form(self):
        return self.form
