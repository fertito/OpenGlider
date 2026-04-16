from __future__ import division

import numpy as np

import FreeCAD as App
from openglider.glider.cell.elements import Panel
from PySide import QtCore, QtGui

from .tools import BaseTool, coin, input_field, text_field, vector3D
from pivy.graphics import InteractionSeparator, Line, Marker
from .design_path import DesignPath, BezierPath, LinePath, PolylinePath

# import ptvsd
# print("Waiting for debugger attach")
# # 5678 is the default attach port in the VS Code debug configurations
# ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)
# ptvsd.wait_for_attach()

def refresh():
    pass


# idea: draw lines between ribs and fill the panels with color
# only straight lines, no curves
# later create some helpers to generate parametric cuts

# TODO

# switch upper lower        x
# add new line              x
# add new point             x
# create line of two nodes  x
# save to dict              x
# set cut type              x
# q set position            x
# delete                    x


class DesignTool(BaseTool):
    widget_name = "Design Tool"

    def __init__(self, obj):
        super(DesignTool, self).__init__(obj)
        self.side = "upper"


        # Initialize shape properties (will be set by update_shape_display)
        self.front = None
        self.back = None
        self.ribs = None
        self.x_values = None
        self._shape_lines = []  # Track shape lines for redraw
        
        CutLine.cuts_to_lines(self.parametric_glider, symmetric_only=False)

        self._add_mode = False
        
        # Design paths (Bezier curves for panel design)
        self.design_paths = []  # List of DesignPath objects
        self._selected_path = None  # Currently selected design path
        self._path_counter = 0  # Counter for unique path IDs
        
        # setup the GUI
        self.setup_widget()
        self.setup_pivy()
        
        # Load existing design paths
        self._load_design_paths()

    def setup_widget(self):
        """set up the qt stuff"""
        self.Qtoggle_side = QtGui.QPushButton("show lower side")
        self.layout.setWidget(0, input_field, self.Qtoggle_side)


        self.tool_widget = QtGui.QWidget()
        self.tool_widget.setWindowTitle("object properties")
        self.tool_layout = QtGui.QFormLayout(self.tool_widget)
        self.form.append(self.tool_widget)

        self.Qcut_type = QtGui.QComboBox(self.tool_widget)
        for _, cut_type in Panel.CUT_TYPES():
            self.Qcut_type.addItem(cut_type)
        self.Qcut_type.setEnabled(False)
        self.Qcut_type.currentIndexChanged.connect(self.cut_type_changed)

        self.tool_layout.setWidget(0, text_field, QtGui.QLabel("cut type"))
        self.tool_layout.setWidget(0, input_field, self.Qcut_type)

        self.QPointPos = QtGui.QDoubleSpinBox()
        self.QPointPos.setMinimum(0)
        self.QPointPos.setMaximum(1)
        self.QPointPos.setSingleStep(0.01)
        self.QPointPos.setDecimals(5)
        self.QPointPos.valueChanged.connect(self.point_pos_changed)

        self.tool_layout.setWidget(1, text_field, QtGui.QLabel("point position"))
        self.tool_layout.setWidget(1, input_field, self.QPointPos)

        # event handlers
        self.Qtoggle_side.clicked.connect(self.toggle_side)

        # Design Path section
        self.Qadd_line = QtGui.QPushButton("+ Line")
        self.Qadd_line.setToolTip("Add a straight line path")
        self.Qadd_polyline = QtGui.QPushButton("+ Polyline")
        self.Qadd_polyline.setToolTip("Add a multi-segment straight line path")
        self.Qadd_bezier = QtGui.QPushButton("+ Bezier")
        self.Qadd_bezier.setToolTip("Add a cubic Bezier curve path")
        
        path_buttons = QtGui.QHBoxLayout()
        path_buttons.addWidget(self.Qadd_line)
        path_buttons.addWidget(self.Qadd_polyline)
        path_buttons.addWidget(self.Qadd_bezier)
        path_widget = QtGui.QWidget()
        path_widget.setLayout(path_buttons)
        self.tool_layout.setWidget(2, text_field, QtGui.QLabel("add path"))
        self.tool_layout.setWidget(2, input_field, path_widget)
        self.Qadd_line.clicked.connect(self.add_line_path)
        self.Qadd_polyline.clicked.connect(self.add_polyline_path)
        self.Qadd_bezier.clicked.connect(self.add_bezier_path)
        
        # Add/Remove Point for Polyline
        self.Qadd_point = QtGui.QPushButton("+ Pt")
        self.Qadd_point.setToolTip("Add a point to the end of the selected path (Polyline mode)")
        self.Qremove_point = QtGui.QPushButton("- Pt")
        self.Qremove_point.setToolTip("Remove the last point from the selected path (Polyline mode)")
        point_buttons = QtGui.QHBoxLayout()
        point_buttons.addWidget(self.Qadd_point)
        point_buttons.addWidget(self.Qremove_point)
        point_widget = QtGui.QWidget()
        point_widget.setLayout(point_buttons)
        self.tool_layout.setWidget(3, text_field, QtGui.QLabel("modify path"))
        self.tool_layout.setWidget(3, input_field, point_widget)
        self.Qadd_point.clicked.connect(self.add_point_to_path)
        self.Qremove_point.clicked.connect(self.remove_point_from_path)
        
        self._update_point_buttons_state()

        # Path cut type
        self.Qpath_cut_type = QtGui.QComboBox(self.tool_widget)
        for _, cut_type in Panel.CUT_TYPES():
            self.Qpath_cut_type.addItem(cut_type)
        self.tool_layout.setWidget(4, text_field, QtGui.QLabel("path cut type"))
        self.tool_layout.setWidget(4, input_field, self.Qpath_cut_type)
        self.Qpath_cut_type.currentIndexChanged.connect(self.path_cut_type_changed)

        # Add cuts at percentage - quick tool
        self.Qpercentage = QtGui.QDoubleSpinBox()
        self.Qpercentage.setMinimum(0)
        self.Qpercentage.setMaximum(100)
        self.Qpercentage.setValue(20)
        self.Qpercentage.setSuffix("%")
        self.Qadd_at_percent = QtGui.QPushButton("Add")
        self.Qadd_at_percent.setToolTip("Add cut line at this chord percentage across all ribs")
        percent_layout = QtGui.QHBoxLayout()
        percent_layout.addWidget(self.Qpercentage)
        percent_layout.addWidget(self.Qadd_at_percent)
        percent_widget = QtGui.QWidget()
        percent_widget.setLayout(percent_layout)
        self.tool_layout.setWidget(5, text_field, QtGui.QLabel("add at %"))
        self.tool_layout.setWidget(5, input_field, percent_widget)
        self.Qadd_at_percent.clicked.connect(self.add_cuts_at_percentage)

        # Apply and Delete buttons
        self.Qapply_paths = QtGui.QPushButton("Apply Paths")
        self.Qapply_paths.setToolTip("Project all paths onto panel cuts")
        self.Qdelete_path = QtGui.QPushButton("Delete Path")
        self.Qdelete_path.setToolTip("Delete selected path")
        action_buttons = QtGui.QHBoxLayout()
        action_buttons.addWidget(self.Qapply_paths)
        action_buttons.addWidget(self.Qdelete_path)
        action_widget = QtGui.QWidget()
        action_widget.setLayout(action_buttons)
        self.tool_layout.setWidget(6, text_field, QtGui.QLabel("actions"))
        self.tool_layout.setWidget(6, input_field, action_widget)
        self.Qapply_paths.clicked.connect(self.apply_paths_to_cuts)
        self.Qdelete_path.clicked.connect(self.delete_selected_path)

        # Select Connected and Delete Selected section
        self.Qselect_connected = QtGui.QPushButton("Select Connected")
        self.Qselect_connected.setToolTip("Select all points and lines connected to current selection")
        self.Qdelete_selected = QtGui.QPushButton("Delete Selected")
        self.Qdelete_selected.setToolTip("Delete all selected points and lines")
        selection_buttons = QtGui.QHBoxLayout()
        selection_buttons.addWidget(self.Qselect_connected)
        selection_buttons.addWidget(self.Qdelete_selected)
        selection_widget = QtGui.QWidget()
        selection_widget.setLayout(selection_buttons)
        self.tool_layout.setWidget(7, text_field, QtGui.QLabel("selection"))
        self.tool_layout.setWidget(7, input_field, selection_widget)
        self.Qselect_connected.clicked.connect(self.select_connected)
        self.Qdelete_selected.clicked.connect(self.delete_selected_cuts)

    def setup_pivy(self):
        """set up the scene"""
        self.shape = coin.SoSeparator()
        self.task_separator += [self.shape]
        
        # Separator for design paths (Bezier curves)
        self.path_separator = InteractionSeparator(self.rm)
        self.path_separator.selection_changed = self.path_selection_changed
        self.path_separator.register()  # Register for marker interaction
        self.shape += [self.path_separator]
        
        # Separator for add_neighbour temp markers  
        self.add_separator = InteractionSeparator(self.rm)
        self.shape += [self.add_separator]
        
        self.update_shape_display()  # Initialize shape properties based on mode
        self.draw_shape()
        self.event_separator = InteractionSeparator(self.rm)
        self.event_separator.selection_changed = self.selection_changed
        self.event_separator.register()
        self.toggle_side()
        self.add_cb = self.view.addEventCallbackPivy(
            coin.SoKeyboardEvent.getClassTypeId(), self.add_geo
        )

    def update_shape_display(self):
        """Update shape properties - always uses half shape (symmetric mode)"""
        _shape = self.parametric_glider.shape.get_half_shape()
        has_center = self.parametric_glider.shape.has_center_cell
        
        front_pts = list(_shape.front)
        back_pts = list(_shape.back)
        
        # For odd cell count gliders, add the center rib at x=0
        # The center rib is the first half-shape rib mirrored to x=0
        if has_center:
            # Get center rib by mirroring the first half-shape rib to x=0
            first_front = _shape.front[0]
            first_back = _shape.back[0]
            # Center rib has x=0, same y coordinates as the first rib
            center_front = [0, first_front[1]]
            center_back = [0, first_back[1]]
            # Insert center rib at the beginning
            front_pts = [center_front] + front_pts
            back_pts = [center_back] + back_pts
        
        self.front = vector3D(front_pts, z=-0.01)
        self.back = vector3D(back_pts, z=-0.01)
        self.ribs = list(zip(self.front, self.back))
        
        # Store rib bounds for use in other methods
        # front_pts and back_pts contain (x, y) for each rib, including center if has_center
        self._rib_front_pts = front_pts
        self._rib_back_pts = back_pts
        
        # Extract x_values from front coordinates
        self.x_values = [pt[0] for pt in front_pts]
    
    def _get_rib_bounds(self, list_idx):
        """Get front and back y coordinates for a rib at the given list index.
        
        Args:
            list_idx: Index in self.x_values/self.ribs (0 = center for odd cells)
            
        Returns:
            (front_y, back_y) - y coordinates of front and back of rib
        """
        front_y = self._rib_front_pts[list_idx][1]
        back_y = self._rib_back_pts[list_idx][1]
        return front_y, back_y
    
    def _list_idx_to_shape_idx(self, list_idx):
        """Convert list index (0-based including center) to shape index.
        
        For odd cells: list_idx=0 is center (no shape equivalent), list_idx=1 maps to shape[0], etc.
        For even cells: list_idx=i maps to shape[i]
        
        Returns shape index, or None if this is the center rib.
        """
        has_center = self.parametric_glider.shape.has_center_cell
        if has_center:
            if list_idx == 0:
                return None  # Center rib has no shape index
            return list_idx - 1
        return list_idx

    # ==================== Design Path Management ====================
    
    def _load_design_paths(self):
        """Load design paths from parametric_glider.elements."""
        paths_data = self.parametric_glider.elements.get("design_paths", [])
        for data in paths_data:
            path = DesignPath.from_dict(data)
            # Only show visuals for paths matching current side
            if path.side == self.side:
                path.setup_visuals(self.path_separator)
            self.design_paths.append(path)
            self._path_counter = max(self._path_counter, 
                                     int(data.get("id", "path_0").split("_")[-1]) + 1)
    
    def _save_design_paths(self):
        """Save design paths to parametric_glider.elements."""
        self.parametric_glider.elements["design_paths"] = [
            path.to_dict() for path in self.design_paths
        ]
    
    def add_line_path(self):
        """Add a new straight line path."""
        # Create line across current visible shape
        if self.x_values and len(self.x_values) >= 2:
            x_start = self.x_values[0]
            x_end = self.x_values[-1]
            # Default position at 20% chord
            y_start = self.parametric_glider.shape[0, 0.2][1]
            y_end = self.parametric_glider.shape[-1, 0.2][1]
        else:
            x_start, x_end = 0, 5
            y_start, y_end = 0, 0
        
        path_id = f"path_{self._path_counter}"
        self._path_counter += 1
        
        cut_type = self.Qpath_cut_type.currentText()
        path = LinePath(
            path_id,
            cut_type,
            self.side,
            [[x_start, y_start], [x_end, y_end]]
        )
        path.setup_visuals(self.path_separator)
        self.design_paths.append(path)
        self._select_path(path)
        
    def add_polyline_path(self):
        """Add a new polyline path."""
        # Create polyline across current visible shape
        if self.x_values and len(self.x_values) >= 2:
            x_start = self.x_values[0]
            x_end = self.x_values[-1]
            x_mid = (x_start + x_end) / 2.0
            # Default position at 20% chord
            y_start = self.parametric_glider.shape[0, 0.2][1]
            y_end = self.parametric_glider.shape[-1, 0.2][1]
            y_mid = (y_start + y_end) / 2.0
            
            # Create a 3-point polyline by default
            pts = [[x_start, y_start], [x_mid, y_mid], [x_end, y_end]]
        else:
            pts = [[0, 0], [2.5, 0], [5, 0]]
            
        path_id = f"path_{self._path_counter}"
        self._path_counter += 1
        
        cut_type = self.Qpath_cut_type.currentText()
        path = PolylinePath(
            path_id,
            cut_type,
            self.side,
            pts
        )
        path.setup_visuals(self.path_separator)
        self.design_paths.append(path)
        self._select_path(path)
    
    def add_point_to_path(self):
        """Add a point to the end of the selected path."""
        if not self._selected_path or len(self._selected_path.control_points) == 0:
            return
            
        pts = self._selected_path.control_points
        if len(pts) >= 2:
            # Extrapolate from last two points
            p1 = pts[-2]
            p2 = pts[-1]
            new_pt = [p2[0] + (p2[0] - p1[0]) * 0.5, p2[1] + (p2[1] - p1[1]) * 0.5]
        else:
            # Just copy the last point with an offset
            p1 = pts[-1]
            new_pt = [p1[0] + 0.5, p1[1]]
            
        self._selected_path.control_points.append(new_pt)
        # Re-create visuals
        self._refresh_path_visuals()
        self._selected_path.select()
        self._update_point_buttons_state()
        
    def remove_point_from_path(self):
        """Remove the last point from the selected path."""
        if not self._selected_path:
            return
            
        # For Polyline, keep at least 2 points
        min_pts = 2
        # For Bezier, it's more complex, requiring specific amount of points, but we'll allow it generally,
        # but really this is meant for Polyline which is why we enforce 2 point minimum
        if isinstance(self._selected_path, BezierPath):
            min_pts = 4 # Keep at least 4 for Bezier
            
        if len(self._selected_path.control_points) > min_pts:
            self._selected_path.control_points.pop()
            # Re-create visuals
            self._refresh_path_visuals()
            self._selected_path.select()
            self._update_point_buttons_state()
            
    def _update_point_buttons_state(self):
        """Update enabled state of add/remove point buttons."""
        has_path = self._selected_path is not None
        can_remove = False
        
        if has_path:
            pts_count = len(self._selected_path.control_points)
            if isinstance(self._selected_path, PolylinePath):
                can_remove = pts_count > 2
            elif isinstance(self._selected_path, BezierPath):
                can_remove = pts_count > 4
                
        self.Qadd_point.setEnabled(has_path)
        self.Qremove_point.setEnabled(can_remove)
    
    def add_bezier_path(self):
        """Add a new cubic Bezier path."""
        # Create Bezier across current visible shape
        if self.x_values and len(self.x_values) >= 2:
            x_start = self.x_values[0]
            x_end = self.x_values[-1]
            x_mid = (x_start + x_end) / 2
            # Default position at 20% chord
            y_start = self.parametric_glider.shape[0, 0.2][1]
            y_end = self.parametric_glider.shape[-1, 0.2][1]
            y_mid = (y_start + y_end) / 2
        else:
            x_start, x_end, x_mid = 0, 5, 2.5
            y_start, y_end, y_mid = 0, 0, 0
        
        path_id = f"path_{self._path_counter}"
        self._path_counter += 1
        
        cut_type = self.Qpath_cut_type.currentText()
        # Create cubic Bezier with 4 control points
        path = BezierPath(
            path_id,
            cut_type,
            self.side,
            [
                [x_start, y_start],  # P0 - start
                [x_start + (x_end - x_start) * 0.33, y_start],  # P1 - control 1
                [x_start + (x_end - x_start) * 0.66, y_end],    # P2 - control 2
                [x_end, y_end]       # P3 - end
            ]
        )
        path.setup_visuals(self.path_separator)
        self.design_paths.append(path)
        self._select_path(path)
    
    def _select_path(self, path):
        """Select a design path."""
        if self._selected_path:
            self._selected_path.unselect()
        self._selected_path = path
        if path:
            path.select()
            # Update UI to show path's cut type
            idx = self.Qpath_cut_type.findText(path.cut_type)
            if idx >= 0:
                self.Qpath_cut_type.blockSignals(True)
                self.Qpath_cut_type.setCurrentIndex(idx)
                self.Qpath_cut_type.blockSignals(False)
        self._update_point_buttons_state()
    
    def path_cut_type_changed(self):
        """Handle path cut type change."""
        if self._selected_path:
            self._selected_path.cut_type = self.Qpath_cut_type.currentText()
    
    def path_selection_changed(self):
        """Handle selection change in path separator - select the path of clicked marker."""
        for obj in self.path_separator.selected_objects:
            if hasattr(obj, '_path') and obj._path in self.design_paths:
                self._select_path(obj._path)
                break
    
    def delete_selected_path(self):
        """Delete the currently selected path."""
        if self._selected_path:
            # Remove from list
            self.design_paths.remove(self._selected_path)
            self._selected_path = None
            
            # Refresh all path visuals - clear and recreate
            self._refresh_path_visuals()
    
    def _refresh_path_visuals(self):
        """Clear and recreate all path visuals."""
        # Clear all visuals from path_separator
        self.path_separator.removeAllChildren()
        self.path_separator.dynamic_objects = []
        
        # Recreate visuals only for paths matching current side
        for path in self.design_paths:
            path.curve_line = None
            path.markers = []
            if path.side == self.side:
                path.setup_visuals(self.path_separator)
    
    def apply_paths_to_cuts(self):
        """Project all design paths onto panel cuts."""
        has_center = self.parametric_glider.shape.has_center_cell
        
        # Build rib bounds from stored front/back points
        rib_bounds = list(zip(
            [pt[1] for pt in self._rib_front_pts],
            [pt[1] for pt in self._rib_back_pts]
        ))
        
        for path in self.design_paths:
            if path.side != self.side:
                continue  # Only apply paths for current side
            
            # Get intersections with rib bounds included for proper center rib handling
            intersections = path.get_rib_intersections(
                self.x_values, 
                rib_bounds=rib_bounds
            )
            
            if len(intersections) < 2:
                continue
            
            # For odd cell count, force the center rib to be perpendicular/symmetric
            # by using the same relative chord position as the first visible rib
            if has_center and len(intersections) > 1:
                # Find if index 0 (center) and index 1 (first visible) are in intersections
                center_found = any(idx == 0 for idx, _ in intersections)
                first_visible_found = any(idx == 1 for idx, _ in intersections)
                
                if center_found and first_visible_found:
                    # Get the first visible rib's y position and compute relative chord position
                    first_visible_y = None
                    for idx, y in intersections:
                        if idx == 1:
                            first_visible_y = y
                            break
                    
                    if first_visible_y is not None:
                        # Compute relative position on first visible rib
                        fv_front, fv_back = self._get_rib_bounds(1)
                        fv_chord = fv_front - fv_back
                        
                        if abs(fv_chord) > 0.001:
                            rel_pos = (fv_front - first_visible_y) / fv_chord
                            
                            # Apply same relative position to center rib
                            c_front, c_back = self._get_rib_bounds(0)
                            c_chord = c_front - c_back
                            center_y_perpendicular = c_front - rel_pos * c_chord
                            
                            # Replace center intersection with perpendicular position
                            intersections = [
                                (0, center_y_perpendicular) if idx == 0 else (idx, y)
                                for idx, y in intersections
                            ]
            
            # Create CutPoints and CutLines from intersections
            cut_points = []
            
            for list_idx, y_pos in intersections:
                try:
                    # Convert list_idx to the correct rib index for CutPoint
                    # list_idx 0 = center for odd cells, needs special handling
                    cp = self._create_cut_point_at_list_idx(list_idx, y_pos)
                    cut_points.append((list_idx, cp))
                except (IndexError, TypeError) as e:
                    print(f"Skipping rib {list_idx}: {e}")
                    continue
            
            # Create lines between consecutive points
            for (i1, cp1), (i2, cp2) in zip(cut_points[:-1], cut_points[1:]):
                if abs(i1 - i2) == 1:  # Adjacent ribs
                    if self.side == "upper":
                        CutLine.upper_point_set.add(cp1)
                        CutLine.upper_point_set.add(cp2)
                    else:
                        CutLine.lower_point_set.add(cp1)
                        CutLine.lower_point_set.add(cp2)
                    
                    cut_line = CutLine(cp1, cp2, path.cut_type)
                    cut_line.replace_points_by_set()
                    cut_line.update_Line()
                    cut_line.setup_visuals()
                    self.event_separator += [cp1, cp2, cut_line]
        
        self.event_separator.color_selected()
    
    def _create_cut_point_at_list_idx(self, list_idx, y_pos):
        """Create a CutPoint for a rib at the given list index.
        
        Handles the conversion from list_idx (which includes center for odd cells)
        to the proper shape index used by CutPoint.
        """
        has_center = self.parametric_glider.shape.has_center_cell
        
        # Get x coordinate and bounds for this rib
        x_value = self.x_values[list_idx]
        front_y, back_y = self._get_rib_bounds(list_idx)
        chord = abs(front_y - back_y)
        
        if chord < 0.001:
            rib_pos = 0
        else:
            # rib_pos is negative for upper, positive for lower
            # It's the normalized position from front (0) to back (1)
            upper = self.side == "upper"
            rib_pos = -(upper * 2.0 - 1.0) * abs(y_pos - front_y) / chord
        
        # CutPoint expects rib_nr to be: list_idx + has_center_cell (then subtracts has_center_cell)
        # After subtraction, rib_nr becomes list_idx, which is correct
        rib_nr_for_cutpoint = list_idx + has_center
        
        # Pass x_value, min_y, max_y explicitly to handle center rib correctly
        return CutPoint(
            rib_nr_for_cutpoint, rib_pos, self.parametric_glider,
            x_value=x_value,
            min_y=front_y,
            max_y=back_y
        )

    def add_cuts_at_percentage(self):
        """Add cut points and lines at a given chord percentage across all ribs."""
        percentage = self.Qpercentage.value() / 100.0  # Convert to 0-1 range
        cut_type = self.Qpath_cut_type.currentText()
        
        cut_points = []
        num_ribs = len(self.x_values)
        
        # Iterate through all ribs (x_values now includes center for odd cells)
        for list_idx in range(num_ribs):
            try:
                # Get rib bounds and compute y position from percentage
                front_y, back_y = self._get_rib_bounds(list_idx)
                chord = front_y - back_y
                y_pos = front_y - percentage * chord
                
                # Create cut point using the helper
                cp = self._create_cut_point_at_list_idx(list_idx, y_pos)
                cut_points.append((list_idx, cp))
            except (IndexError, TypeError) as e:
                print(f"Skipping rib {list_idx}: {e}")
                continue
        
        # Create lines between consecutive points
        for (i1, cp1), (i2, cp2) in zip(cut_points[:-1], cut_points[1:]):
            if abs(i1 - i2) == 1:  # Adjacent ribs
                if self.side == "upper":
                    CutLine.upper_point_set.add(cp1)
                    CutLine.upper_point_set.add(cp2)
                else:
                    CutLine.lower_point_set.add(cp1)
                    CutLine.lower_point_set.add(cp2)
                
                cut_line = CutLine(cp1, cp2, cut_type)
                cut_line.replace_points_by_set()
                cut_line.update_Line()
                cut_line.setup_visuals()
                self.event_separator += [cp1, cp2, cut_line]
        
        self.event_separator.color_selected()

    def select_connected(self):
        """Select all points and lines connected to the current selection.
        
        Uses graph traversal to follow connections through CutLines.
        """
        if not self.event_separator.selected_objects:
            return
        
        # Collect initial points from selection
        visited_points = set()
        visited_lines = set()
        to_visit = []
        
        for elem in self.event_separator.selected_objects:
            if isinstance(elem, CutPoint):
                to_visit.append(elem)
            elif isinstance(elem, CutLine):
                to_visit.append(elem.point1)
                to_visit.append(elem.point2)
        
        # Graph traversal - follow lines to find all connected points
        while to_visit:
            point = to_visit.pop()
            if point in visited_points:
                continue
            visited_points.add(point)
            
            # Find all lines connected to this point
            for line in point.lines:
                if line not in visited_lines:
                    visited_lines.add(line)
                    # Add the other endpoint to visit
                    other = line.point2 if line.point1 == point else line.point1
                    if other not in visited_points:
                        to_visit.append(other)
        
        # Select all connected elements
        for point in visited_points:
            if point not in self.event_separator.selected_objects:
                self.event_separator.select_object(point, multi=True)
        for line in visited_lines:
            if line not in self.event_separator.selected_objects:
                self.event_separator.select_object(line, multi=True)

    def delete_selected_cuts(self):
        """Delete all selected CutPoints and CutLines."""
        # Simply use the native pivy remove_selected which works correctly
        self.event_separator.remove_selected()

    def selection_changed(self):
        points = set()
        lines = []
        for element in self.event_separator.selected_objects:
            if isinstance(element, CutPoint):
                points.add(element)
            elif isinstance(element, CutLine):
                lines.append(element)
                points.add(element.point1)
                points.add(element.point2)

        self.Qcut_type.setEnabled(bool(lines))
        self.QPointPos.setEnabled(bool(points))
        if lines:
            self.set_cut_type(lines[0].cut_type)
        if points:
            self.QPointPos.blockSignals(True)
            self.QPointPos.setValue(
                abs(list(points)[0].rib_pos)
            )  # maybe summing over all points?
            self.QPointPos.blockSignals(False)

    def set_cut_type(self, text):
        index = self.Qcut_type.findText(text)
        if index is not None:
            self.Qcut_type.setCurrentIndex(index)

    def cut_type_changed(self):
        for element in self.event_separator.selected_objects:
            if isinstance(element, CutLine):
                element.cut_type = self.Qcut_type.currentText()

    def point_pos_changed(self):
        points = set()
        lines = set()
        sign = 2.0 * (self.side != "upper") - 1.0
        for element in self.event_separator.selected_objects:
            if isinstance(element, CutPoint):
                points.add(element)
            elif isinstance(element, CutLine):
                lines.add(element)
                points.add(element.point1)
                points.add(element.point2)
        for point in points:
            point.rib_pos = self.QPointPos.value() * sign
            point.update_position()
            for line in point.lines:
                lines.add(line)
        for line in lines:
            line.update_Line()

    def draw_shape(self):
        """draws the shape of the glider"""
        l1 = Line(self.front)
        l2 = Line(self.back)
        l3 = Line([self.back[0], self.front[0]])
        l4 = Line([self.back[-1], self.front[-1]])
        l_ribs = list(map(Line, self.ribs))
        lines = [l1, l2, l3, l4] + l_ribs
        for l in lines:
            l.color.diffuseColor = (0.2, 0.2, 0.2)
        self._shape_lines = lines  # Track lines for redraw
        self.shape += lines

    def redraw_shape(self):
        """Clear and redraw the shape (used when switching modes)"""
        # Remove existing shape lines from the separator
        for line in self._shape_lines:
            try:
                self.shape.removeChild(line)
            except:
                pass  # Line may not be part of shape anymore
        self._shape_lines = []
        # Draw new shape
        self.draw_shape()

    def toggle_side(self):
        self.event_separator.select_object(None)
        self.event_separator.unregister()
        self.task_separator.removeChild(self.event_separator)
        del self.event_separator
        self.event_separator = InteractionSeparator(self.rm)
        self.event_separator.selection_changed = self.selection_changed
        if self.side == "upper":
            self.side = "lower"
            self.Qtoggle_side.setText("show upper side")
            self.event_separator += list(CutLine.lower_point_set)
            self.event_separator += CutLine.lower_line_list
        elif self.side == "lower":
            self.side = "upper"
            self.Qtoggle_side.setText("show lower side")
            self.event_separator += list(CutLine.upper_point_set)
            self.event_separator += CutLine.upper_line_list
        self.task_separator += [self.event_separator]
        self.event_separator.register()
        
        # Update path visibility for new side
        self._refresh_path_visuals()
        self._selected_path = None

    def add_geo(self, event_callback):
        """this function provides some interaction functionality to create points and lines
        press v to start the mode. if a point is selected, the left and right rib will offer the possebility to add
        a point + line, if no point is selected, it's possible to add a point to any rib"""
        event = event_callback.getEvent()
        if event.getKey() == ord("i") and event.getState() == 0:
            if self._add_mode:
                return
            self._add_mode = True
            # first we check if nothing is selected:
            select_obj = self.event_separator.selected_objects
            num_of_obj = len(select_obj)
            action = None
            add_event = None
            close_event = None

            # insert a point
            if num_of_obj == 0:
                add_event = self.view.addEventCallbackPivy(
                    coin.SoLocation2Event.getClassTypeId(), self.add_point
                )
                action = self.add_point

            # insert a line + point
            elif num_of_obj == 1 and isinstance(select_obj[0], CutPoint):
                add_event = self.view.addEventCallbackPivy(
                    coin.SoLocation2Event.getClassTypeId(), self.add_neighbour
                )
                self.add_neighbour(event_callback)
                action = self.add_neighbour

            # join two points with a line
            # add-line
            elif num_of_obj == 2 and all(isinstance(el, CutPoint) for el in select_obj):
                cut_point_1 = select_obj[0]
                cut_point_2 = select_obj[1]
                if abs(cut_point_1.rib_nr - cut_point_2.rib_nr) == 1:
                    cut_line = CutLine(cut_point_1, cut_point_2, "folded")
                    cut_line.replace_points_by_set()
                    cut_line.update_Line()
                    cut_line.setup_visuals()
                    self.event_separator += [cut_line]

            def remove_cb(event_callback=None):
                if event_callback:
                    event = event_callback.getEvent()
                    if not event.getButton() == coin.SoMouseButtonEvent.BUTTON1:
                        return
                if add_event:
                    self.view.removeEventCallbackPivy(
                        coin.SoLocation2Event.getClassTypeId(), add_event
                    )
                if close_event:
                    self.view.removeEventCallbackPivy(
                        coin.SoMouseButtonEvent.getClassTypeId(), close_event
                    )

                if action == self.add_neighbour:
                    assert len(self.add_separator.static_objects) == 2
                    assert isinstance(self.add_separator.static_objects[0], Marker)
                    assert isinstance(self.add_separator.static_objects[1], Line)
                    marker = self.add_separator.static_objects[0]
                    line = self.add_separator.static_objects[1]
                    # Use helper for correct index conversion
                    cut_point_1 = self._create_cut_point_at_list_idx(
                        marker.rib_nr,
                        marker.points[0][1]
                    )
                    cut_point_2 = line.active_point
                    cut_line = CutLine(cut_point_1, cut_point_2, "folded")
                    cut_line.replace_points_by_set()
                    cut_line.update_Line()
                    cut_line.setup_visuals()
                    self.event_separator += [cut_point_1, cut_line]
                    self.event_separator.select_object(cut_point_1)

                elif action == self.add_point:
                    assert len(self.add_separator.static_objects) == 1
                    assert isinstance(self.add_separator.static_objects[0], Marker)
                    marker = self.add_separator.static_objects[0]
                    # Use helper for correct index conversion
                    cut_point = self._create_cut_point_at_list_idx(
                        marker.rib_nr,
                        marker.points[0][1]
                    )
                    self.event_separator += [cut_point]
                    self.event_separator.select_object(cut_point)

                self._add_mode = False
                self.add_separator.removeAllChildren()

            if action in [self.add_neighbour, self.add_point]:
                # these functions need an extra callback for closing on
                # mouse button press
                close_event = self.view.addEventCallbackPivy(
                    coin.SoMouseButtonEvent.getClassTypeId(), remove_cb
                )
            else:  # add line: call remove_callback directly
                remove_cb()

    def add_point(self, event_callback=None):
        event = event_callback.getEvent()
        # first get the closest rib
        pos = event.getPosition()
        pos = list(self.view.getPoint(*pos))
        pos[2] = 0.0
        smallest_diff = None, None

        for index, value in enumerate(self.x_values):
            diff = abs(pos[0] - value)
            if (not smallest_diff[0]) or smallest_diff[0] > diff:
                smallest_diff = diff, index
        index = smallest_diff[1]
        
        # Use stored rib bounds (works correctly for center rib)
        x = self.x_values[index]
        front_y, back_y = self._get_rib_bounds(index)
        min_y = min(front_y, back_y)
        max_y = max(front_y, back_y)
        
        pos[0] = x
        if pos[1] > min_y and pos[1] < max_y:
            if len(self.add_separator.static_objects) == 0:
                self.add_separator.removeAllChildren()
                marker = Marker([pos])
                marker.rib_nr = index  # This is the list index
                self.add_separator += [marker]
            else:
                marker = self.add_separator.static_objects[0]
                marker.points = [pos]
                marker.rib_nr = index
        else:
            self.add_separator.removeAllChildren()

    def add_neighbour(self, event_callback=None):
        event = event_callback.getEvent()
        select_obj = self.event_separator.selected_objects[0]
        rib_nr = select_obj.rib_nr  # This is the list index
        
        # Get bounds for left neighbour (rib_nr - 1)
        x1, min1, max1 = None, None, None
        if rib_nr > 0:
            try:
                x1 = self.x_values[rib_nr - 1]
                front_y, back_y = self._get_rib_bounds(rib_nr - 1)
                min1 = min(front_y, back_y)
                max1 = max(front_y, back_y)
            except (IndexError, KeyError):
                pass
        
        # Get bounds for right neighbour (rib_nr + 1)
        x2, min2, max2 = None, None, None
        if rib_nr < len(self.x_values) - 1:
            try:
                x2 = self.x_values[rib_nr + 1]
                front_y, back_y = self._get_rib_bounds(rib_nr + 1)
                min2 = min(front_y, back_y)
                max2 = max(front_y, back_y)
            except (IndexError, KeyError):
                pass
        
        show_point = False
        pos = event.getPosition()
        pos = list(self.view.getPoint(*pos))
        pos[2] = 0
        
        if not x2 or (x1 and abs(pos[0] - x1) < abs(pos[0] - x2)):
            if x1:
                pos[0] = x1
                if pos[1] > min1 and pos[1] < max1:
                    new_rib_nr = rib_nr - 1
                    show_point = True
        elif not x1 or abs(pos[0] - x1) > abs(pos[0] - x2):
            if x2:
                pos[0] = x2
                if pos[1] > min2 and pos[1] < max2:
                    new_rib_nr = rib_nr + 1
                    show_point = True
        else:
            return
            
        if show_point:
            if not self.add_separator.static_objects:
                self.add_separator.removeAllChildren()
                marker = Marker([pos])
                marker.rib_nr = new_rib_nr
                line = Line([list(select_obj.points[0]), pos])
                line.active_point = select_obj
                self.add_separator += [marker, line]
            else:
                marker = self.add_separator.static_objects[0]
                line = self.add_separator.static_objects[1]
                marker.points = [pos]
                marker.rib_nr = new_rib_nr
                line.points = [list(select_obj.points[0]), pos]
        else:
            self.add_separator.removeAllChildren()

    def accept(self):
        self.event_separator.unregister()
        self.view.removeEventCallbackPivy(
            coin.SoKeyboardEvent.getClassTypeId(), self.add_cb
        )
        # Save design paths
        self._save_design_paths()
        # Get cuts and handle symmetric mirroring if needed
        cuts = CutLine.get_cut_dict()
        #TODO # need to add cuts in symmetric or it is removing the first point
        self.parametric_glider.elements["cuts"] = cuts
        super(DesignTool, self).accept()
        self.update_view_glider()

    def reject(self):
        self.event_separator.unregister()
        self.view.removeEventCallbackPivy(
            coin.SoKeyboardEvent.getClassTypeId(), self.add_cb
        )
        super(DesignTool, self).reject()


class CutPoint(Marker):
    def __init__(self, rib_nr, rib_pos, parametric_glider=None, x_value=None, min_y=None, max_y=None):
        super(CutPoint, self).__init__([[0, 0, 0]], True)
        self.marker.markerIndex = coin.SoMarkerSet.CROSS_7_7
        self.parametric_glider = parametric_glider
        self.rib_nr = rib_nr #- parametric_glider.shape.has_center_cell
        self.rib_pos = rib_pos
        self.lines = []
        
        # Flag to indicate if bounds were explicitly provided (for center rib)
        self._has_explicit_bounds = x_value is not None
        
        # Use provided values if available, otherwise compute from shape
        if self._has_explicit_bounds:
            self.x_value = x_value
            self.min = min_y if min_y is not None else 0
            self.max = max_y if max_y is not None else 0
            # Compute 2D point directly
            chord = self.min - self.max
            y = self.min - abs(rib_pos) * chord
            point = [self.x_value, y, 0]
        else:
            point = self._get_2D_from_shape()
            self.x_value = point[0]
            self.max = self.parametric_glider.shape[self.rib_nr, 1.0][1]
            self.min = self.parametric_glider.shape[self.rib_nr, 0.0][1]
        
        self.points = [point]
        self.on_drag_release.append(self.get_rib_pos)

    def update_position(self):
        self.points = [self.get_2D()]

    def _get_2D_from_shape(self):
        """Get 2D position from shape indexing."""
        try:
            return list(
                self.parametric_glider.shape[self.rib_nr, abs(self.rib_pos)] + [0]
            )
        except IndexError:
            raise IndexError(f"index {self.rib_nr} out of range")

    def get_2D(self):
        """Get 2D position, using stored bounds if available."""
        if self._has_explicit_bounds:
            # Use stored bounds to compute position
            chord = self.min - self.max
            y = self.min - abs(self.rib_pos) * chord
            return [self.x_value, y, 0]
        else:
            return self._get_2D_from_shape()

    def get_rib_pos(self):
        """Update rib_pos from current y position."""
        if self._has_explicit_bounds:
            le = self.min
            te = self.max
        else:
            le = self.parametric_glider.shape[self.rib_nr, 0][1]
            te = self.parametric_glider.shape[self.rib_nr, 1][1]
        chord = le - te
        sign = (self.rib_pos >= 0) * 2 - 1
        self.rib_pos = round(sign * (abs(le - self.pos[1])) / chord, 3)
        return self.rib_pos

    def __eq__(self, other):
        if isinstance(other, CutPoint):
            if self.rib_nr == other.rib_nr:
                if round(self.rib_pos, 3) == round(other.rib_pos, 3):
                    return True
        return False

    def __hash__(self):
        return hash(self.rib_nr) ^ hash(round(self.rib_pos, 2))

    def replace_by_set(self, point_set):
        for point in point_set:
            if point == self:
                return point
        return False

    @property
    def pos(self):
        return [self.x_value, self.points[0][1], 0]

    @pos.setter
    def pos(self, pos):
        self.points = [self.x_value, pos[1], 0]

    def drag(self, mouse_coords, fact=1.0):
        if self.enabled:
            pts = self.points
            for i, pt in enumerate(pts):
                pt[0] = self._tmp_points[i][0]
                y = mouse_coords[1] * fact + self._tmp_points[i][1]
                if y > self.min:
                    pt[1] = self.min
                elif y < self.max:
                    pt[1] = self.max
                else:
                    pt[1] = y
                pt[2] = self._tmp_points[i][2]
            self.points = pts
            for i in self.on_drag:
                i()

    @classmethod
    def from_position_and_rib(cls, rib_nr, y_pos, upper, parametric_glider):
        i = 0
        max_val = parametric_glider.shape[rib_nr, 1.0][1]
        min_val = parametric_glider.shape[rib_nr, 0.0][1]
        rib_pos = -(upper * 2.0 - 1.0) * abs(y_pos - min_val) / abs(max_val - min_val)
        return cls(
            rib_nr + parametric_glider.shape.has_center_cell, rib_pos, parametric_glider
        )


class CutLine(Line):
    upper_point_set = set()
    lower_point_set = set()
    upper_line_list = []
    lower_line_list = []

    def __init__(self, point1, point2, cut_type):
        super(CutLine, self).__init__([point1.get_2D(), point2.get_2D()], dynamic=True)
        self.drawstyle.lineWidth = 1.5
        self.point1 = point1
        self.point2 = point2
        self.parametric_glider = self.point1.parametric_glider
        self.cut_type = cut_type
        if self.is_upper:
            CutLine.upper_point_set.add(point1)
            CutLine.upper_point_set.add(point2)
            CutLine.upper_line_list.append(self)
        else:
            CutLine.lower_point_set.add(point1)
            CutLine.lower_point_set.add(point2)
            CutLine.lower_line_list.append(self)

    def setup_visuals(self):
        self.point1.lines.append(self)
        self.point2.lines.append(self)
        self.point1.on_drag.append(self.update_Line)
        self.point2.on_drag.append(self.update_Line)

    def replace_points_by_set(self):
        # this has to be done once for every line (before the parent Line is initialized)
        if self.is_upper:
            self.point1 = self.point1.replace_by_set(CutLine.upper_point_set)
            self.point2 = self.point2.replace_by_set(CutLine.upper_point_set)
        else:
            self.point1 = self.point1.replace_by_set(CutLine.lower_point_set)
            self.point2 = self.point2.replace_by_set(CutLine.lower_point_set)

    def update_Line(self):
        self.points = [self.point1.pos, self.point2.pos]

    @property
    def is_upper(self):
        return self.point1.rib_pos < 0 and self.point2.rib_pos < 0

    def drag(self, mouse_coords, fact=1.0):
        self.point1.drag(mouse_coords, fact)
        self.point2.drag(mouse_coords, fact)

    @property
    def drag_objects(self):
        return [self.point1, self.point2]

    @property
    def points(self):
        return self.data.point.getValues()

    @points.setter
    def points(self, points):
        p = [[pi[0], pi[1], pi[2] - 0.001] for pi in points]
        self.data.point.setValue(0, 0, 0)
        self.data.point.setValues(0, len(p), p)

    @classmethod
    def cuts_to_lines(cls, parametric_glider, symmetric_only=True):
        """Convert cut dictionary to visual CutLine objects.
        
        Args:
            parametric_glider: The parametric glider with cuts data
            symmetric_only: If True, only load positive cell indices (half wing).
                           If False, load all cell indices including negative (full wing).
        """
        CutLine.upper_point_set = set()
        CutLine.lower_point_set = set()
        CutLine.upper_line_list = []
        CutLine.lower_line_list = []
        for cut in parametric_glider.elements.get("cuts", []):
            for cell_nr in cut["cells"]:
                # Filter based on symmetric mode
                if symmetric_only and cell_nr < 0:
                    continue  # Skip negative (left wing) cells in symmetric mode
                try:
                    if parametric_glider.shape.has_center_cell==True:
                        CutLine(
                            CutPoint(cell_nr - 1, cut["left"], parametric_glider),
                            CutPoint(cell_nr, cut["right"], parametric_glider),
                            cut["type"],
                        )
                    else :
                        CutLine(
                            CutPoint(cell_nr, cut["left"], parametric_glider),
                            CutPoint(cell_nr + 1, cut["right"], parametric_glider),
                            cut["type"],
                        )
                except (TypeError, IndexError):
                    # Skip if cell_nr is out of range
                    pass
        for l in cls.upper_line_list:
            l.replace_points_by_set()
            l.setup_visuals()
        for l in cls.lower_line_list:
            l.replace_points_by_set()
            l.setup_visuals()

    @property
    def cell_nr(self):
        # With the new indexing where center rib is at index 0:
        # - Cell 0 (center) is between ribs 0 and 1
        # - Cell 1 is between ribs 1 and 2
        # - etc.
        # So cell_nr is just the inner rib number
        return self.get_point(inner=True).rib_nr

    def get_point(self, inner=True):
        if (self.point1.rib_nr < self.point2.rib_nr) == inner:
            return self.point1
        else:
            return self.point2

    def get_dict(self):
        return {
            "cells": [self.cell_nr],
            "left": self.get_point(inner=True).get_rib_pos(),
            "right": self.get_point(inner=False).get_rib_pos(),
            "type": self.cut_type,
        }

    @classmethod
    def get_cut_dict(cls):
        cuts = [line.get_dict() for line in cls.upper_line_list + cls.lower_line_list]
        cuts = sorted(cuts, key=lambda x: x["right"])
        if not cuts:
            return []
        sorted_cuts = [cuts[0]]
        for cut in cuts[1:]:
            for key in ["type", "left", "right"]:
                if cut[key] != sorted_cuts[-1][key]:
                    sorted_cuts.append(cut)
                    break
            else:
                sorted_cuts[-1]["cells"].append(cut["cells"][0])
        return sorted_cuts

    def check_dependency(self):
        if (not self._delete) and (self.point1._delete or self.point2._delete):
            self.delete()

    def delete(self):
        # Check if in list before removing (may already be removed)
        if self.is_upper:
            if self in CutLine.upper_line_list:
                CutLine.upper_line_list.remove(self)
        else:
            if self in CutLine.lower_line_list:
                CutLine.lower_line_list.remove(self)
        super(CutLine, self).delete()
