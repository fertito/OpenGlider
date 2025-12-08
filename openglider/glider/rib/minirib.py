from openglider.airfoil import Profile3D
from openglider.mesh import Mesh, triangulate
import numpy as np


class MiniRib:
    def __init__(
        self,
        yvalue,
        intrados_start=0.8,
        extrados_start=0.75,
        end_distance=0.02,  # Fixed distance from TE in meters (2cm default)
        transition_length=0.05,  # Length of progressive transition zone (in chord %)
        name="minirib",
    ):
        self.y_value = yvalue
        self.intrados_start = intrados_start
        self.extrados_start = extrados_start
        self.end_distance = end_distance  # in meters (e.g., 0.02 = 2cm)
        self.transition_length = transition_length  # e.g., 0.05 = 5% chord
        self.name = name

    def get_end_percentage(self, chord):
        """
        Calculate end percentage based on fixed distance from TE.
        """
        if chord > 0:
            # Convert fixed distance to percentage of chord
            end_pct = 1.0 - (self.end_distance / chord)
            return max(0.0, min(1.0, end_pct))
        return 0.99  # Fallback

    def function(self, x, chord=None):
        """
        Returns ballooning factor:
        0 = Constrained (Rib shape)
        1 = Unconstrained (Ballooned shape)
        Values between 0-1 for progressive transition (smooth S-curve)
        
        x is signed coordinate from Profile2D:
        x < 0: Upper / Extrados
        x >= 0: Lower / Intrados
        
        chord: used to calculate end position from fixed distance
        """
        import math
        
        # Calculate end percentage from fixed distance
        end_pct = self.get_end_percentage(chord) if chord else 0.99
        
        if x < 0:  # Upper / Extrados
            pos = -x
            start = self.extrados_start
            
            if pos > end_pct:
                return 1.0  # Beyond end: fully ballooned
            elif pos >= start:
                # In the transition zone at the start?
                if self.transition_length > 0 and pos < start + self.transition_length:
                    # Smooth S-curve transition using cosine
                    t = (pos - start) / self.transition_length
                    # Use cosine for asymptotic curve: 0.5 * (1 + cos(pi * t))
                    return 0.5 * (1.0 + math.cos(math.pi * t))
                return 0.0  # Constrained zone
            else:
                return 1.0  # Before start: fully ballooned
        else:  # Lower / Intrados
            pos = x
            start = self.intrados_start
            
            if pos > end_pct:
                return 1.0  # Beyond end: fully ballooned
            elif pos >= start:
                # In the transition zone at the start?
                if self.transition_length > 0 and pos < start + self.transition_length:
                    # Smooth S-curve transition using cosine
                    t = (pos - start) / self.transition_length
                    # Use cosine for asymptotic curve: 0.5 * (1 + cos(pi * t))
                    return 0.5 * (1.0 + math.cos(math.pi * t))
                return 0.0  # Constrained zone
            else:
                return 1.0  # Before start: fully ballooned

    def get_3d(self, cell):
        """
        Get the 3D profile for the mini rib.
        Generates points uniformly distributed within the mini rib range,
        with progressive ballooning in the transition zone.
        """
        import numpy as np
        
        rib1 = cell.rib1
        rib2 = cell.rib2
        y = self.y_value
        
        # Interpolate chord for fixed distance calculations
        chord = rib1.chord * (1 - y) + rib2.chord * y
        
        # Calculate end percentage from fixed distance
        end_pct = self.get_end_percentage(chord)
        
        # Number of points per side (extrados/intrados)
        num_points = 40
        
        # Generate x_values to form a closed loop:
        # Extrados: from start toward trailing edge (negative x values), but stop just before TE
        # Then add a single shared TE point (average of upper/lower)
        # Intrados: from just after TE back toward start (positive x values)
        extrados_x = np.linspace(-self.extrados_start, -end_pct, num_points)[:-1]  # Exclude last (TE)
        intrados_x = np.linspace(end_pct, self.intrados_start, num_points)[1:]    # Exclude first (TE)
        
        # Add a special marker for the shared TE point (we'll handle it separately)
        # x=0 at end_pct means "use trailing edge point"
        te_x = end_pct  # Trailing edge x position (will use midpoint of upper/lower)
        
        # Combine: extrados (toward TE), TE point, intrados (back from TE)
        x_values_extrados = list(extrados_x)
        x_values_intrados = list(intrados_x)
        
        # Get the profiles - note that profile_2d and profile_3d have the same number of points
        # and the same point ordering, so we can use profile_2d(x) as index into profile_3d
        prof2d_1 = rib1.profile_2d
        prof2d_2 = rib2.profile_2d
        prof3d_1 = rib1.profile_3d
        prof3d_2 = rib2.profile_3d
        
        # Get ballooned midrib - same point count as profile_3d
        ballooned_midrib = cell.basic_cell.midrib(y, ballooning=True)
        
        def get_point_3d(x):
            """Helper to get a 3D point at position x with ballooning."""
            fakt = self.function(x, chord=chord)
            ik = prof2d_1(x)
            pt1 = prof3d_1[ik]
            pt2 = prof3d_2[ik]
            pt_unballooned = pt1 * (1 - y) + pt2 * y
            pt_ballooned = ballooned_midrib[ik]
            return pt_unballooned + fakt * (pt_ballooned - pt_unballooned)
        
        # Build 3D points: extrados, then TE point, then intrados
        points_3d = []
        
        # Extrados points
        for x in x_values_extrados:
            try:
                points_3d.append(get_point_3d(x))
            except Exception as e:
                continue
        
        # Trailing edge points: add BOTH upper and lower to create flat truncated edge
        # (not average, which would create a pointed tip)
        try:
            pt_upper = get_point_3d(-te_x)  # Extrados at TE position
            pt_lower = get_point_3d(te_x)   # Intrados at TE position
            points_3d.append(pt_upper)  # End of extrados at TE
            points_3d.append(pt_lower)  # Start of intrados at TE
        except Exception as e:
            pass
        
        # Intrados points
        for x in x_values_intrados:
            try:
                points_3d.append(get_point_3d(x))
            except Exception as e:
                continue
        
        return Profile3D(points_3d)

    def get_2d_shape(self, cell):
        """
        Get the 2D profile shape for the mini rib.
        Includes transition zone with ballooning:
        - Front: ballooned thickness (wider)
        - Transition: progressively thinner
        - Back: exact profile thickness (flat)
        """
        from openglider.vector import PolyLine2D
        import numpy as np
        
        rib1 = cell.rib1
        rib2 = cell.rib2
        y = self.y_value
        
        # Interpolate chord
        chord = rib1.chord * (1 - y) + rib2.chord * y
        
        # Calculate end percentage from fixed distance
        end_pct = self.get_end_percentage(chord)
        
        # Number of points per side
        num_points = 40
        
        # Generate x_values to form a closed loop (same as get_3d):
        # Extrados: from start toward TE (exclude last point at TE)
        # Intrados: from TE back toward start (exclude first point at TE)
        extrados_x = np.linspace(-self.extrados_start, -end_pct, num_points)[:-1]
        intrados_x = np.linspace(end_pct, self.intrados_start, num_points)[1:]
        te_x = end_pct  # Trailing edge x position
        
        x_values_extrados = list(extrados_x)
        x_values_intrados = list(intrados_x)
        
        # Get the flat 2D profile for interpolation
        prof_2d = rib1.profile_2d
        
        # Get the 3D ballooned midrib and flatten it for 2D ballooning effect
        try:
            midrib_3d = cell.basic_cell.midrib(y, ballooning=True)
            midrib_flat = midrib_3d.flatten()
            has_ballooned = True
        except Exception as e:
            has_ballooned = False
        
        def get_point_2d(x):
            """Helper to get a 2D point at position x with ballooning."""
            ik = prof_2d(x)
            pt_flat = np.array(prof_2d[ik]) * chord
            fakt = self.function(x, chord=chord)
            if fakt > 0 and has_ballooned:
                pt_ballooned = np.array(midrib_flat[ik])
                return pt_flat + fakt * (pt_ballooned - pt_flat)
            return pt_flat
        
        # Build 2D points: extrados, then TE point, then intrados
        points_2d = []
        
        # Extrados points
        for x in x_values_extrados:
            try:
                points_2d.append(get_point_2d(x))
            except Exception as e:
                continue
        
        # Trailing edge points: add BOTH upper and lower to create flat truncated edge
        # (not average, which would create a pointed tip)
        try:
            pt_upper = get_point_2d(-te_x)  # Extrados at TE position
            pt_lower = get_point_2d(te_x)   # Intrados at TE position
            points_2d.append(pt_upper)  # End of extrados at TE
            points_2d.append(pt_lower)  # Start of intrados at TE
        except Exception as e:
            pass
        
        # Intrados points
        for x in x_values_intrados:
            try:
                points_2d.append(get_point_2d(x))
            except Exception as e:
                continue
        
        if len(points_2d) < 2:
            return None
        
        # Filter out duplicate consecutive points
        filtered_points = [points_2d[0]]
        for pt in points_2d[1:]:
            if not np.allclose(pt, filtered_points[-1], atol=1e-10):
                filtered_points.append(pt)
        
        if len(filtered_points) < 2:
            return None
        
        return PolyLine2D(filtered_points)

    def get_flattened(self, cell, close=True):
        """Get flattened 2D profile using exact airfoil shape."""
        from openglider.vector import PolyLine2D
        
        shape = self.get_2d_shape(cell)
        if shape is None or len(shape.data) < 2:
            return PolyLine2D([])
        
        if close and len(shape.data) > 2:
            # Close the curve by adding the first point at the end
            closed_data = list(shape.data) + [shape.data[0]]
            return PolyLine2D(closed_data)
        return shape

    def get_flattened_with_allowance(self, cell, allowance=0.006):
        """Get flattened 2D profile with seam allowance as outer cut line."""
        from openglider.vector import PolyLine2D
        import numpy as np
        
        shape = self.get_2d_shape(cell)
        if shape is None or len(shape.data) < 3:
            return None, None
        
        inner = PolyLine2D(shape.data)
        
        # Close the inner curve
        inner_closed = PolyLine2D(list(inner.data) + [inner.data[0]])
        
        # Create outer curve with proper parallel offset
        # Calculate perpendicular offset at each point
        points = list(shape.data)
        n = len(points)
        outer_points = []
        
        for i in range(n):
            # Get previous and next points (with wrapping for closed curve)
            prev_pt = np.array(points[(i - 1) % n])
            curr_pt = np.array(points[i])
            next_pt = np.array(points[(i + 1) % n])
            
            # Calculate tangent vectors
            t1 = curr_pt - prev_pt
            t2 = next_pt - curr_pt
            
            # Calculate perpendicular normals (rotate 90 degrees)
            # For 2D: perpendicular of (x, y) is (-y, x) for left turn
            n1 = np.array([-t1[1], t1[0]])
            n2 = np.array([-t2[1], t2[0]])
            
            # Normalize
            len1 = np.linalg.norm(n1)
            len2 = np.linalg.norm(n2)
            if len1 > 1e-10:
                n1 = n1 / len1
            if len2 > 1e-10:
                n2 = n2 / len2
            
            # Average normal at this point
            avg_normal = (n1 + n2) / 2.0
            len_avg = np.linalg.norm(avg_normal)
            if len_avg > 1e-10:
                avg_normal = avg_normal / len_avg
            
            # Offset point
            outer_pt = curr_pt + avg_normal * allowance
            outer_points.append(outer_pt)
        
        outer_closed = PolyLine2D(outer_points + [outer_points[0]])
        
        return inner_closed, outer_closed

    def get_mesh(self, cell, filled=True):
        profile = self.get_3d(cell)
        points_3d = list(profile.data)
        
        # Robustness checks
        if len(points_3d) < 2:
             return Mesh.from_indexed([], {}, {})
        if filled and len(points_3d) < 3:
             return Mesh.from_indexed([], {}, {})
        
        n = len(points_3d)
        
        if not filled:
            # Just the boundary segments
            segments = [[i, (i + 1) % n] for i in range(n)]
            return Mesh.from_indexed(points_3d, {"rib": segments}, {})
        else:
            # Simple fan triangulation from centroid
            # Add centroid as the last point
            import numpy as np
            centroid = np.mean(np.array(points_3d), axis=0)
            points_3d.append(centroid)
            centroid_idx = n  # index of centroid
            
            # Create triangles: each connects two adjacent boundary points to centroid
            triangles = []
            for i in range(n):
                j = (i + 1) % n
                triangles.append([i, j, centroid_idx])
            
            return Mesh.from_indexed(
                points_3d,
                polygons={"ribs": triangles},
                boundaries={self.name: list(range(n))},
            )

    def __json__(self):
        return {
            "yvalue": self.y_value,
            "intrados_start": self.intrados_start,
            "extrados_start": self.extrados_start,
            "end_distance": self.end_distance,
            "transition_length": self.transition_length,
            "name": self.name,
        }
