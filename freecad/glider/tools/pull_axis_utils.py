"""
Shared utility for computing pull axis projections from 3D lineset data
to 2D profile coordinates.

Used by:
- cell_tool.py (diagonal auto-fill: axis-relative positioning)
- holedesign_tool.py (exclusion cone geometry)
"""

import numpy as np


def compute_pull_axis_projection(rib, glider_instance):
    """
    Compute line direction and extrados intersection for each attachment point.

    Projects the pilot point (main lower attachment) through each AP
    onto the rib's 2D profile coordinate system, then intersects
    the pull axis with the extrados curve.

    Args:
        rib: A Rib instance with profile_2d, profile_3d, chord.
        glider_instance: The 3D glider instance (has lineset, attachment_points).

    Returns:
        list of dicts, one per valid attachment point, with keys:
            - ap: the attachment point object
            - line_direction_2d: normalized 2D direction vector (profile coords)
            - extrados_intersection_x: x-coordinate where pull axis crosses extrados
            - angle_offset: angle of the pull axis in radians (atan2)
            - pilot_2d_norm: pilot point in normalized 2D profile coords
        Returns empty list if pilot point cannot be determined.
    """
    # Get pilot point 3D from lineset
    pilot_point_3d = None
    if hasattr(glider_instance, 'lineset') and glider_instance.lineset:
        try:
            main_ap = glider_instance.lineset.get_main_attachment_point()
            if main_ap is not None and hasattr(main_ap, 'vec') and main_ap.vec is not None:
                pilot_point_3d = np.array(main_ap.vec)
        except Exception:
            pass

    if pilot_point_3d is None:
        return []

    # Establish rib coordinate frame from 3D profile
    le_3d = np.array(rib.profile_3d.data[rib.profile_2d.noseindex])
    te_3d = (np.array(rib.profile_3d.data[0]) + np.array(rib.profile_3d.data[-1])) / 2

    chord_3d = le_3d - te_3d
    chord_length = np.linalg.norm(chord_3d)
    if chord_length < 1e-9:
        return []
    chord_dir = chord_3d / chord_length

    # Span direction (perpendicular to chord, in the rib plane)
    upper_idx = len(rib.profile_3d.data) // 4
    upper_3d = np.array(rib.profile_3d.data[upper_idx])

    # Normal to rib plane
    v1_3d = upper_3d - te_3d
    normal = np.cross(chord_3d, v1_3d)
    norm_len = np.linalg.norm(normal)
    normal = normal / norm_len if norm_len > 0 else np.array([1, 0, 0])

    # Up direction (perpendicular to chord, in rib plane)
    up_dir = np.cross(normal, chord_dir)
    up_norm = np.linalg.norm(up_dir)
    up_dir = up_dir / up_norm if up_norm > 0 else np.array([0, 0, 1])

    # Project pilot point to 2D profile coords
    pilot_rel_3d = pilot_point_3d - te_3d
    pilot_chord_pos = np.dot(pilot_rel_3d, chord_dir) / chord_length  # 0=TE, 1=LE
    pilot_up_pos = np.dot(pilot_rel_3d, up_dir) / chord_length

    # Map to profile_2d coordinate system
    te_2d_x = (rib.profile_2d.data[0][0] + rib.profile_2d.data[-1][0]) / 2
    le_2d_x = rib.profile_2d.data[rib.profile_2d.noseindex][0]
    pilot_2d_x = te_2d_x + pilot_chord_pos * (le_2d_x - te_2d_x)
    pilot_2d_y = pilot_up_pos
    pilot_2d_norm = np.array([pilot_2d_x, pilot_2d_y])

    # Get attachment points (exclude brake tabs)
    all_aps = glider_instance.get_rib_attachment_points(rib)
    valid_aps = [ap for ap in all_aps if hasattr(ap, 'rib_pos') and ap.rib_pos <= 0.9]

    extrados_poly = rib.profile_2d.get_extrados_poly()

    results = []
    for ap in valid_aps:
        # AP position in normalized 2D coords (intrados side)
        ap_pos_norm = rib.profile_2d.align([ap.rib_pos, -1.0])

        # Direction from pilot to AP (normalized coords)
        line_direction = ap_pos_norm - pilot_2d_norm
        dir_norm = np.linalg.norm(line_direction)
        if dir_norm > 1e-9:
            line_direction = line_direction / dir_norm
        else:
            line_direction = np.array([0, 1])

        angle_offset = np.arctan2(line_direction[1], line_direction[0])

        # Intersect pull axis with extrados
        far_factor = rib.chord * 100
        intersection = extrados_poly.line_intersection(
            ap_pos_norm, ap_pos_norm + line_direction * far_factor
        )

        if intersection is not None:
            ext_x = intersection[0]
        else:
            # Clamp to extrados bounds (edge case: stabilo, high camber)
            ext_x = max(le_2d_x, min(te_2d_x, ap_pos_norm[0]))

        results.append({
            'ap': ap,
            'line_direction_2d': line_direction,
            'extrados_intersection_x': ext_x,
            'angle_offset': angle_offset,
            'pilot_2d_norm': pilot_2d_norm,
        })

    return results
