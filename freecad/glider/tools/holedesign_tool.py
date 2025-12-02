import os
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from openglider.glider.rib import RibHole
import numpy as np
import Part

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

        self.glider_obj = self.obj.parent
        self.preview_objects = []

        # --- Connections ---
        self.form.applyButton.clicked.connect(self.accept)
        # Non-suspended
        self.form.numHolesSpinBox_ns.valueChanged.connect(self.update_preview)
        self.form.holeWidthSpinBox_ns.valueChanged.connect(self.update_preview)
        self.form.holeHeightSpinBox_ns.valueChanged.connect(self.update_preview)
        self.form.verticalShiftSpinBox_ns.valueChanged.connect(self.update_preview)
        self.form.rotationSpinBox_ns.valueChanged.connect(self.update_preview)
        # Suspended
        self.form.numHolesSpinBox_s.valueChanged.connect(self.update_preview)
        self.form.holeWidthSpinBox_s.valueChanged.connect(self.update_preview)
        self.form.holeHeightSpinBox_s.valueChanged.connect(self.update_preview)
        self.form.verticalShiftSpinBox_s.valueChanged.connect(self.update_preview)
        self.form.rotationSpinBox_s.valueChanged.connect(self.update_preview)

        self.form.tabWidget.currentChanged.connect(self.update_preview)

        self.glider_obj.ViewObject.hide()
        self.update_form()
        self.update_preview()

    def get_representative_rib(self, suspended=False):
        try:
            glider_instance = self.glider_obj.Proxy.getGliderInstance()
            suspended_ribs = {att.rib for att in glider_instance.lineset.attachment_points if hasattr(att, 'rib')}

            for rib in glider_instance.ribs:
                is_suspended = rib in suspended_ribs
                if suspended and is_suspended:
                    return rib
                if not suspended and not is_suspended:
                    return rib
        except Exception as e:
            App.Console.PrintError(f"Error getting representative rib: {e}\\n")
        return None

    def update_preview(self):
        for obj in self.preview_objects:
            try: App.ActiveDocument.removeObject(obj.Name)
            except: pass
        self.preview_objects = []

        is_suspended_tab = self.form.tabWidget.currentIndex() == 1
        rib = self.get_representative_rib(suspended=is_suspended_tab)

        if not rib:
            # Maybe show a text message in the 3D view
            return

        # Draw profile
        profile_points = [App.Vector(p[0], p[1], 0) for p in rib.profile_2d.data]
        profile_obj = App.ActiveDocument.addObject("Part::Feature", "ProfilePreview")
        profile_obj.Shape = Part.makePolygon(profile_points + [profile_points[0]])
        self.preview_objects.append(profile_obj)

        if is_suspended_tab:
            num_holes, hole_width, hole_height, vertical_shift, rotation = (
                self.form.numHolesSpinBox_s.value(),
                self.form.holeWidthSpinBox_s.value(),
                self.form.holeHeightSpinBox_s.value(),
                self.form.verticalShiftSpinBox_s.value(),
                self.form.rotationSpinBox_s.value(),
            )
        else:
            num_holes, hole_width, hole_height, vertical_shift, rotation = (
                self.form.numHolesSpinBox_ns.value(),
                self.form.holeWidthSpinBox_ns.value(),
                self.form.holeHeightSpinBox_ns.value(),
                self.form.verticalShiftSpinBox_ns.value(),
                self.form.rotationSpinBox_ns.value(),
            )

        for i in range(num_holes):
            pos_x = (i + 1.0) / (num_holes + 1.0)
            camber_point = rib.profile_2d.profilepoint(pos_x, 0.0)
            hole_center = App.Vector(camber_point[0], camber_point[1] + vertical_shift, 0)

            # Correct way to create an ellipse
            ellipse_geom = Part.Ellipse(hole_center, hole_width / 2, hole_height / 2)
            ellipse = ellipse_geom.toShape()

            ellipse.rotate(hole_center, App.Vector(0, 0, 1), rotation)
            hole_obj = App.ActiveDocument.addObject("Part::Feature", f"HolePreview_{i}")
            hole_obj.Shape = ellipse
            self.preview_objects.append(hole_obj)

        App.ActiveDocument.recompute()
        Gui.SendMsgToActiveView("ViewFit")

    def update_form(self):
        self.form.numHolesSpinBox_ns.setValue(self.obj.num_holes_ns)
        self.form.holeWidthSpinBox_ns.setValue(self.obj.hole_width_ns)
        self.form.holeHeightSpinBox_ns.setValue(self.obj.hole_height_ns)
        self.form.verticalShiftSpinBox_ns.setValue(self.obj.vertical_shift_ns)
        self.form.rotationSpinBox_ns.setValue(self.obj.rotation_ns)

        self.form.numHolesSpinBox_s.setValue(self.obj.num_holes_s)
        self.form.holeWidthSpinBox_s.setValue(self.obj.hole_width_s)
        self.form.holeHeightSpinBox_s.setValue(self.obj.hole_height_s)
        self.form.verticalShiftSpinBox_s.setValue(self.obj.vertical_shift_s)
        self.form.rotationSpinBox_s.setValue(self.obj.rotation_s)

    def apply_changes(self):
        self.obj.holes = True
        self.obj.num_holes_ns = self.form.numHolesSpinBox_ns.value()
        self.obj.hole_width_ns = self.form.holeWidthSpinBox_ns.value()
        self.obj.hole_height_ns = self.form.holeHeightSpinBox_ns.value()
        self.obj.vertical_shift_ns = self.form.verticalShiftSpinBox_ns.value()
        self.obj.rotation_ns = self.form.rotationSpinBox_ns.value()

        self.obj.num_holes_s = self.form.numHolesSpinBox_s.value()
        self.obj.hole_width_s = self.form.holeWidthSpinBox_s.value()
        self.obj.hole_height_s = self.form.holeHeightSpinBox_s.value()
        self.obj.vertical_shift_s = self.form.verticalShiftSpinBox_s.value()
        self.obj.rotation_s = self.form.rotationSpinBox_s.value()

        App.Console.PrintMessage("Hole properties updated.\\n")

    def cleanup(self):
        for obj in self.preview_objects:
            try: App.ActiveDocument.removeObject(obj.Name)
            except: pass
        self.glider_obj.ViewObject.show()
        App.ActiveDocument.recompute()

    def accept(self):
        self.apply_changes()
        self.cleanup()
        Gui.Control.closeDialog(self)
        return True

    def reject(self):
        self.cleanup()
        Gui.Control.closeDialog(self)
        return True
