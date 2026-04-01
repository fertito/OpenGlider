"""
DesignPath - Vector path classes for the Design Tool.

Provides Bezier and line paths that can be edited on the plan view
and projected onto panel cuts.
"""

from __future__ import division
import numpy as np
from pivy.graphics import Line, Marker


class DesignPath:
    """Base class for design paths on the plan view.
    
    A design path represents a curve that can be edited and then
    projected onto panel cuts. Paths are saved with the project
    in parametric_glider.elements["design_paths"].
    """
    
    def __init__(self, path_id, path_type, cut_type, side, control_points):
        """
        Args:
            path_id: Unique identifier for this path
            path_type: "bezier" or "line"
            cut_type: Type of cut when projected (e.g., "folded", "orthogonal")
            side: "upper" or "lower" surface
            control_points: List of [x, y] control points
        """
        self.path_id = path_id
        self.path_type = path_type
        self.cut_type = cut_type
        self.side = side
        self.control_points = [list(p) for p in control_points]
        
        # Visual elements (created by setup_visuals)
        self.curve_line = None  # Line showing the path curve
        self.markers = []  # Draggable control point markers
        self._selected = False
    
    def setup_visuals(self, separator):
        """Create visual elements and add to separator.
        
        Args:
            separator: The pivy separator to add visuals to
        """
        # Create curve visualization
        curve_points = self.get_curve_points()
        self.curve_line = Line(curve_points, dynamic=False)
        self.curve_line.drawstyle.lineWidth = 2.0
        self._update_curve_color()
        separator += [self.curve_line]
        
        # Create control point markers
        for i, pt in enumerate(self.control_points):
            marker = Marker([[pt[0], pt[1], -0.005]], dynamic=True)
            # Use larger marker type: CIRCLE_FILLED_9_9 = 12 (bigger than CROSS)
            marker.marker.markerIndex = 12
            marker._path = self
            marker._point_index = i
            marker.on_drag.append(lambda m=marker: self._on_marker_drag(m))
            marker.on_drag_release.append(lambda m=marker: self._on_marker_release(m))
            # Add click handler to select this path
            if hasattr(marker, 'on_drag'):
                marker.on_drag.insert(0, lambda m=marker: self._on_marker_click(m))
            self.markers.append(marker)
            separator += [marker]
        
        # Store reference to separator for later removal
        self._separator = separator
    
    def _on_marker_click(self, marker):
        """Called when a marker is clicked - notify design tool to select this path."""
        # The design tool will check marker._path to find us
        pass  # The selection is handled by InteractionSeparator
    
    def _update_curve_color(self):
        """Update curve color based on selection state."""
        if self.curve_line:
            if self._selected:
                self.curve_line.color.diffuseColor = (0.9, 0.5, 0.2)  # Orange when selected
            else:
                self.curve_line.color.diffuseColor = (0.2, 0.6, 0.9)  # Blue normally
    
    def _on_marker_drag(self, marker):
        """Called when a control point marker is dragged."""
        idx = marker._point_index
        pos = marker.points[0]
        self.control_points[idx] = [float(pos[0]), float(pos[1])]
        self._update_curve()
    
    def _on_marker_release(self, marker):
        """Called when drag is released."""
        pass  # Can be used for undo/redo later
    
    def _update_curve(self):
        """Update the curve visualization after control point changes."""
        if self.curve_line:
            curve_points = self.get_curve_points()
            self.curve_line.points = curve_points
    
    def select(self):
        """Mark this path as selected."""
        self._selected = True
        self._update_curve_color()
        for marker in self.markers:
            marker.color.diffuseColor = (0.9, 0.5, 0.2)  # Orange when selected
    
    def unselect(self):
        """Unmark this path as selected."""
        self._selected = False
        self._update_curve_color()
        for marker in self.markers:
            marker.color.diffuseColor = (1, 1, 1)  # White normally
    
    def get_curve_points(self, num_samples=50):
        """Get points along the curve for visualization.
        
        Returns:
            List of [x, y, z] points along the curve
        """
        raise NotImplementedError("Subclass must implement get_curve_points")
    
    def get_rib_intersections(self, x_values, shape=None, symmetric_mode=True, rib_bounds=None):
        """Find intersections of the curve with rib lines.
        
        Args:
            x_values: List of rib x positions
            shape: The parametric shape for bounds checking (optional if rib_bounds provided)
            symmetric_mode: Ignored, kept for API compatibility (always symmetric)
            rib_bounds: Optional list of (front_y, back_y) tuples for each rib.
                       If provided, these are used for bounds checking instead of shape.
            
        Returns:
            List of (rib_nr, y_position) tuples where rib_nr is the list index
        """
        curve_points = self.get_curve_points(num_samples=200)
        intersections = []
        
        for list_idx, x in enumerate(x_values):
            # list_idx is the rib number in the x_values list
            rib_nr = list_idx
            
            # Find where curve crosses this x value
            for i in range(len(curve_points) - 1):
                p1 = curve_points[i]
                p2 = curve_points[i + 1]
                
                # Check if x is between p1 and p2
                if (p1[0] <= x <= p2[0]) or (p2[0] <= x <= p1[0]):
                    if abs(p2[0] - p1[0]) > 0.001:
                        t = (x - p1[0]) / (p2[0] - p1[0])
                        y_intersect = p1[1] + t * (p2[1] - p1[1])
                        
                        # Check if within rib bounds
                        try:
                            if rib_bounds is not None and list_idx < len(rib_bounds):
                                # Use provided bounds
                                front_y, back_y = rib_bounds[list_idx]
                                min_y = min(front_y, back_y)
                                max_y = max(front_y, back_y)
                            elif shape is not None:
                                # Fall back to shape for bounds
                                min_y = shape[rib_nr, 1.0][1]
                                max_y = shape[rib_nr, 0.0][1]
                            else:
                                # No bounds checking, accept all
                                min_y = float('-inf')
                                max_y = float('inf')
                            
                            if min_y <= y_intersect <= max_y:
                                intersections.append((rib_nr, y_intersect))
                        except (IndexError, TypeError):
                            pass
                        break  # Only one intersection per rib
        
        return intersections
    
    def to_dict(self):
        """Serialize to dictionary for saving."""
        return {
            "id": self.path_id,
            "type": self.path_type,
            "cut_type": self.cut_type,
            "side": self.side,
            "control_points": self.control_points
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create path from dictionary data."""
        path_type = data.get("type", "bezier")
        if path_type == "line":
            return LinePath(
                data["id"],
                data["cut_type"],
                data["side"],
                data["control_points"]
            )
        else:
            return BezierPath(
                data["id"],
                data["cut_type"],
                data["side"],
                data["control_points"]
            )
    
    def remove_visuals(self, separator):
        """Remove visual elements from separator."""
        if self.curve_line:
            idx = separator.findChild(self.curve_line)
            if idx >= 0:
                separator.removeChild(idx)
            self.curve_line = None
        
        for marker in self.markers:
            idx = separator.findChild(marker)
            if idx >= 0:
                separator.removeChild(idx)
        self.markers = []


class BezierPath(DesignPath):
    """Cubic Bezier path with multiple segments.
    
    Control points format for cubic Bezier:
    - First segment: 4 points (P0, P1, P2, P3)
    - Each additional segment: 3 points (shares end point with previous)
    
    For N segments: 4 + 3*(N-1) = 3*N + 1 control points
    """
    
    def __init__(self, path_id, cut_type, side, control_points):
        super().__init__(path_id, "bezier", cut_type, side, control_points)
    
    def get_curve_points(self, num_samples=50):
        """Sample the cubic Bezier curve."""
        if len(self.control_points) < 4:
            # Not enough for Bezier, return line
            return [[p[0], p[1], -0.005] for p in self.control_points]
        
        points = []
        
        # Process each Bezier segment
        num_segments = (len(self.control_points) - 1) // 3
        samples_per_segment = max(num_samples // num_segments, 10)
        
        for seg in range(num_segments):
            start_idx = seg * 3
            p0 = self.control_points[start_idx]
            p1 = self.control_points[start_idx + 1]
            p2 = self.control_points[start_idx + 2]
            p3 = self.control_points[start_idx + 3]
            
            for i in range(samples_per_segment):
                t = i / (samples_per_segment - 1) if samples_per_segment > 1 else 0
                
                # Cubic Bezier formula
                u = 1 - t
                x = u**3 * p0[0] + 3*u**2*t * p1[0] + 3*u*t**2 * p2[0] + t**3 * p3[0]
                y = u**3 * p0[1] + 3*u**2*t * p1[1] + 3*u*t**2 * p2[1] + t**3 * p3[1]
                
                points.append([x, y, -0.005])
        
        return points


class LinePath(DesignPath):
    """Simple straight line path with 2 control points."""
    
    def __init__(self, path_id, cut_type, side, control_points):
        super().__init__(path_id, "line", cut_type, side, control_points)
    
    def get_curve_points(self, num_samples=50):
        """Get points along the line."""
        if len(self.control_points) < 2:
            return [[p[0], p[1], -0.005] for p in self.control_points]
        
        p0 = self.control_points[0]
        p1 = self.control_points[-1]
        
        points = []
        for i in range(num_samples):
            t = i / (num_samples - 1) if num_samples > 1 else 0
            x = p0[0] + t * (p1[0] - p0[0])
            y = p0[1] + t * (p1[1] - p0[1])
            points.append([x, y, -0.005])
        
        return points
