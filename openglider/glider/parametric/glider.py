from __future__ import division

import math
import logging
import numpy as np
import copy
try:
    import matplotlib.path as mpl_path
except ImportError:
    mpl_path = None

from openglider.glider.parametric.shape import ParametricShape
from openglider.airfoil import Profile2D
from openglider.glider.glider import Glider
from openglider.glider.cell import Panel, DiagonalRib, TensionStrap, TensionLine, Cell
from openglider.glider.cell.elements import PanelRigidFoil, LeadingEdgeClosure
from openglider.glider.parametric.arc import ArcCurve
from openglider.glider.parametric.export_ods import export_ods_2d
from openglider.glider.parametric.import_ods import import_ods_2d
from openglider.glider.parametric.lines import LineSet2D, UpperNode2D
from openglider.glider.rib import RibHole, RigidFoil, Rib, MiniRib
from openglider.glider.parametric.fitglider import fit_glider_3d
from openglider.utils.distribution import Distribution
from openglider.utils.table import Table
from openglider.utils import ZipCmp
from openglider.utils.geometry import is_inside_triangle


class ParametricGlider(object):
    """
    A parametric (2D) Glider object used for gui input
    """

    num_arc_positions = 60
    num_shape = 30
    num_interpolate_ribs = 40
    num_cell_dist = 30
    num_depth_integral = 100
    num_interpolate = 30
    num_profile = None

    def __init__(
        self,
        shape,
        arc,
        aoa,
        profiles,
        profile_merge_curve,
        balloonings,
        ballooning_merge_curve,
        lineset,
        speed,
        glide,
        zrot,
        elements=None,
        **kwargs
    ):
        self.zrot = zrot or aoa
        self.shape: ParametricShape = shape
        self.arc = arc
        self.aoa = aoa
        self.profiles = profiles or []
        self.profile_merge_curve = profile_merge_curve
        self.balloonings = balloonings or []
        self.ballooning_merge_curve = ballooning_merge_curve
        self.lineset = lineset or LineSet2D([])
        self.speed = speed
        self.glide = glide
        self.elements = elements or {}

        # Hole properties
        self.holes = kwargs.get('holes', True)
        self.hole_shape_ns = kwargs.get('hole_shape_ns', 0)  # Default to Ellipse
        self.num_holes_ns = kwargs.get('num_holes_ns', 30)
        self.hole_width_ns = kwargs.get('hole_width_ns', 0.003)
        self.hole_height_ns = kwargs.get('hole_height_ns', 0.8)
        self.vertical_shift_ns = kwargs.get('vertical_shift_ns', 0.0)
        self.min_hole_pos_ns = kwargs.get('min_hole_pos_ns', 0.2)
        self.max_hole_pos_ns = kwargs.get('max_hole_pos_ns', 0.8)
        self.hole_height_mode_ns = kwargs.get('hole_height_mode_ns', 0)  # 0: Percent, 1: Margin
        self.hole_margin_ns = kwargs.get('hole_margin_ns', 0.02)    # 20mm
        self.hole_corner_radius_ns = kwargs.get('hole_corner_radius_ns', 0.25)  # Ratio of min dimension (0.25 = 25%)

        self.hole_shape_s = kwargs.get('hole_shape_s', 0)  # Default to Ellipse
        self.num_holes_s = kwargs.get('num_holes_s', 30)
        self.hole_width_s = kwargs.get('hole_width_s', 0.003)
        self.hole_height_s = kwargs.get('hole_height_s', 0.8)
        self.vertical_shift_s = kwargs.get('vertical_shift_s', 0.0)
        self.min_hole_pos_s = kwargs.get('min_hole_pos_s', 0.2)
        self.max_hole_pos_s = kwargs.get('max_hole_pos_s', 0.8)
        self.hole_height_mode_s = kwargs.get('hole_height_mode_s', 0)   # 0: Percent, 1: Margin
        self.hole_margin_s = kwargs.get('hole_margin_s', 0.02)     # 20mm
        self.hole_corner_radius_s = kwargs.get('hole_corner_radius_s', 0.25)  # Ratio of min dimension (0.25 = 25%)

        # No-hole zone parameters for suspended ribs
        self.hole_free_angle_s = kwargs.get('hole_free_angle_s', 30.0)  # degrees

        # Airfoil Structure - Extrados Sleeve (suspended)
        self.extrados_sleeve_enabled_s = kwargs.get('extrados_sleeve_enabled_s', False)
        self.extrados_sleeve_width_s = kwargs.get('extrados_sleeve_width_s', 0.015)
        self.extrados_sleeve_offset_s = kwargs.get('extrados_sleeve_offset_s', 0.003)
        self.extrados_sleeve_start_s = kwargs.get('extrados_sleeve_start_s', 0.0)
        self.extrados_sleeve_end_s = kwargs.get('extrados_sleeve_end_s', 0.9)
        self.extrados_sleeve_le_angle_s = kwargs.get('extrados_sleeve_le_angle_s', 80.0)
        self.extrados_sleeve_le_length_s = kwargs.get('extrados_sleeve_le_length_s', 0.03)
        self.extrados_sleeve_te_angle_s = kwargs.get('extrados_sleeve_te_angle_s', 80.0)
        self.extrados_sleeve_te_length_s = kwargs.get('extrados_sleeve_te_length_s', 0.03)
        
        # Airfoil Structure - Intrados Sleeve (suspended)
        self.intrados_sleeve_enabled_s = kwargs.get('intrados_sleeve_enabled_s', False)
        self.intrados_sleeve_width_s = kwargs.get('intrados_sleeve_width_s', 0.015)
        self.intrados_sleeve_offset_s = kwargs.get('intrados_sleeve_offset_s', 0.003)
        self.intrados_sleeve_start_s = kwargs.get('intrados_sleeve_start_s', 0.0)
        self.intrados_sleeve_end_s = kwargs.get('intrados_sleeve_end_s', 0.9)
        self.intrados_sleeve_le_angle_s = kwargs.get('intrados_sleeve_le_angle_s', 100.0)
        self.intrados_sleeve_le_length_s = kwargs.get('intrados_sleeve_le_length_s', 0.03)
        self.intrados_sleeve_te_angle_s = kwargs.get('intrados_sleeve_te_angle_s', 100.0)
        self.intrados_sleeve_te_length_s = kwargs.get('intrados_sleeve_te_length_s', 0.03)
        
        # Airfoil Structure - Extrados Sleeve (non-suspended)
        self.extrados_sleeve_enabled_ns = kwargs.get('extrados_sleeve_enabled_ns', False)
        self.extrados_sleeve_width_ns = kwargs.get('extrados_sleeve_width_ns', 0.015)
        self.extrados_sleeve_offset_ns = kwargs.get('extrados_sleeve_offset_ns', 0.003)
        self.extrados_sleeve_start_ns = kwargs.get('extrados_sleeve_start_ns', 0.0)
        self.extrados_sleeve_end_ns = kwargs.get('extrados_sleeve_end_ns', 0.9)
        self.extrados_sleeve_le_angle_ns = kwargs.get('extrados_sleeve_le_angle_ns', 80.0)
        self.extrados_sleeve_le_length_ns = kwargs.get('extrados_sleeve_le_length_ns', 0.03)
        self.extrados_sleeve_te_angle_ns = kwargs.get('extrados_sleeve_te_angle_ns', 80.0)
        self.extrados_sleeve_te_length_ns = kwargs.get('extrados_sleeve_te_length_ns', 0.03)
        
        # Airfoil Structure - Intrados Sleeve (non-suspended)
        self.intrados_sleeve_enabled_ns = kwargs.get('intrados_sleeve_enabled_ns', False)
        self.intrados_sleeve_width_ns = kwargs.get('intrados_sleeve_width_ns', 0.015)
        self.intrados_sleeve_offset_ns = kwargs.get('intrados_sleeve_offset_ns', 0.003)
        self.intrados_sleeve_start_ns = kwargs.get('intrados_sleeve_start_ns', 0.0)
        self.intrados_sleeve_end_ns = kwargs.get('intrados_sleeve_end_ns', 0.9)
        self.intrados_sleeve_le_angle_ns = kwargs.get('intrados_sleeve_le_angle_ns', 100.0)
        self.intrados_sleeve_le_length_ns = kwargs.get('intrados_sleeve_le_length_ns', 0.03)
        self.intrados_sleeve_te_angle_ns = kwargs.get('intrados_sleeve_te_angle_ns', 100.0)
        self.intrados_sleeve_te_length_ns = kwargs.get('intrados_sleeve_te_length_ns', 0.03)
        
        # Airfoil Structure - Reinforcements (suspended only)
        self.reinforcement_enabled_s = kwargs.get('reinforcement_enabled_s', True)  # Enabled by default
        self.reinforcement_apply_all_s = kwargs.get('reinforcement_apply_all_s', False)  # Individual config by default
        self.reinforcement_master_s = kwargs.get('reinforcement_master_s', {
            'enabled': True,
            'surface_offset': 0.0005,  # 0.5mm
            'halfmoon_radius': 0.1,    # 100mm
            'rod_enabled': True,
            'rod_offset': 0.008,       # 8mm
            'rod_width': 0.009,        # 9mm
            'rod_end_offset': 1.0,     # 1°
        })
        self.reinforcement_configs_s = kwargs.get('reinforcement_configs_s', [])
        self.reinforcement_excluded_ribs_s = kwargs.get('reinforcement_excluded_ribs_s', [])

        # Multi-rod sleeves (NEW FORMAT - list of configs)
        # Suspended ribs
        self.extrados_sleeves_enabled_s = kwargs.get('extrados_sleeves_enabled_s', True)
        self.extrados_sleeves_s = kwargs.get('extrados_sleeves_s', [])
        self.intrados_sleeves_enabled_s = kwargs.get('intrados_sleeves_enabled_s', True)
        self.intrados_sleeves_s = kwargs.get('intrados_sleeves_s', [])
        # Non-suspended ribs
        self.extrados_sleeves_enabled_ns = kwargs.get('extrados_sleeves_enabled_ns', True)
        self.extrados_sleeves_ns = kwargs.get('extrados_sleeves_ns', [])
        self.intrados_sleeves_enabled_ns = kwargs.get('intrados_sleeves_enabled_ns', True)
        self.intrados_sleeves_ns = kwargs.get('intrados_sleeves_ns', [])

        # Edit Cells - Diagonals Auto-fill configuration
        self.diagonal_autofill_params = kwargs.get('diagonal_autofill_params', {
            "A": (4.0, 5.0, 15.0, 1),   # (intrados_cm, extrados_start_%, extrados_end_%, num_bands)
            "B": (4.0, 15.0, 30.0, 1),
            "C": (4.0, 30.0, 50.0, 1),
            "D": (4.0, 50.0, 75.0, 1),
        })
        self.diagonal_autofill_offset = kwargs.get('diagonal_autofill_offset', 0)  # mm

        # Lines Auto-Placement configuration
        self.lines_placement_config = kwargs.get('lines_placement_config', {
            "demi_ecartement": 0.2,
            "profondeur": 0.5,
            "hauteur_cone": 7.0,
            "riser_length": 0.47,
            "basses_auto": True,
            "basses_length": 2.0,
            "inter_auto": True,
            "inter_length": 1.0,
            "include_stabilo": True,
            "stabilo_position": 50.0,
            "line_type_name": "default",
            "line_types": {
                "A": {"enabled": True, "position": 8.5, "interval": 1, "start_cell": 0, "patterns": "3:1, 2:2:1"},
                "B": {"enabled": True, "position": 27.5, "interval": 2, "start_cell": 0, "patterns": "2:2:1, 2:1"},
                "C": {"enabled": True, "position": 53.0, "interval": 2, "start_cell": 0, "patterns": "2:1"},
                "D": {"enabled": True, "position": 77.0, "interval": 3, "start_cell": 0, "patterns": "2:1"},
                "F": {"enabled": True, "position": 100.0, "interval": 1, "start_cell": 0, "patterns": "1:1"},
            }
        })

        # =====================================================================
        # Profile Control - Unified airfoil management
        # =====================================================================
        
        # Thickness curve: controls relative thickness scaling along span
        # Values: 1.0 = original thickness, 0.8 = 80%, 1.2 = 120%
        self.thickness_curve = kwargs.get('thickness_curve', None)  # SymmetricBSpline or None
        self.thickness_curve_enabled = kwargs.get('thickness_curve_enabled', False)
        
        # Shark nose: procedural intrados modification
        self.sharknose_enabled = kwargs.get('sharknose_enabled', False)
        self.sharknose_x1 = kwargs.get('sharknose_x1', 0.06)  # Start position (% chord)
        self.sharknose_x2 = kwargs.get('sharknose_x2', 0.09)  # Max shift position (% chord)
        self.sharknose_x3 = kwargs.get('sharknose_x3', 0.90)  # End position (% chord)
        self.sharknose_y_max = kwargs.get('sharknose_y_max', 0.03)  # Max shift amount (% chord)
        self.sharknose_curve = kwargs.get('sharknose_curve', None)  # SymmetricBSpline for amount variation
        self.sharknose_cells = kwargs.get('sharknose_cells', None)  # List of cell indices to apply sharknose (None = all)
        
        # Profile overrides: rib-specific profile assignment
        # Format: {rib_index: profile_index} - overrides the distribution curve for specific ribs
        self.profile_overrides = kwargs.get('profile_overrides', {})
        self.profile_overrides_enabled = kwargs.get('profile_overrides_enabled', False)
        
        # Last rib profile (stabilo/wingtip) - applied to the very last rib
        self.last_profile_enabled = kwargs.get('last_profile_enabled', False)
        self.last_profile_type = kwargs.get('last_profile_type', 'line')  # 'line', 'thin', 'custom'
        self.last_profile_thickness = kwargs.get('last_profile_thickness', 0.3)  # Relative thickness (0.3 = 30% of original)
        self.last_profile_custom = kwargs.get('last_profile_custom', None)  # Custom Profile2D

    def get_sleeve_exclusion_zones(self, rib, rib_idx, is_suspended):
        """
        Get chord ranges that should be excluded from hole placement due to rod sleeves.
        Returns list of (start_chord, end_chord) tuples.
        """
        suffix = '_s' if is_suspended else '_ns'
        exclusion_zones = []
        
        # Check extrados sleeves
        if getattr(self, f'extrados_sleeves_enabled{suffix}', True):
            for config in getattr(self, f'extrados_sleeves{suffix}', []):
                excluded_ribs = config.get('excluded_ribs', [])
                if rib_idx not in excluded_ribs:
                    start = config.get('start_chord', 0.0)
                    end = config.get('end_chord', 0.7)
                    if start < end:
                        exclusion_zones.append((start, end))
        
        # Check intrados sleeves
        if getattr(self, f'intrados_sleeves_enabled{suffix}', True):
            for config in getattr(self, f'intrados_sleeves{suffix}', []):
                excluded_ribs = config.get('excluded_ribs', [])
                if rib_idx not in excluded_ribs:
                    start = config.get('start_chord', 0.06)
                    end = config.get('end_chord', 0.5)
                    if start < end:
                        exclusion_zones.append((start, end))
        
        return exclusion_zones
    
    def get_reinforcement_exclusion_zones(self, rib, glider):
        """
        Get chord ranges that should be excluded from hole placement due to attachment reinforcements.
        Returns list of (start_chord, end_chord) tuples.
        """
        exclusion_zones = []
        
        if not getattr(self, 'reinforcement_enabled_s', False):
            return exclusion_zones
        
        apply_all = getattr(self, 'reinforcement_apply_all_s', False)
        master_config = getattr(self, 'reinforcement_master_s', {})
        configs = getattr(self, 'reinforcement_configs_s', [])
        
        attachment_points = glider.get_rib_attachment_points(rib)
        valid_aps = [ap for ap in attachment_points if ap.rib_pos <= 0.90]
        valid_aps.sort(key=lambda x: x.rib_pos)
        
        for i, ap in enumerate(valid_aps):
            if apply_all:
                config = master_config
            else:
                config = configs[i] if i < len(configs) else master_config
            
            if config.get('enabled', True):
                radius_normalized = config.get('halfmoon_radius', 0.03) / rib.chord
                start = max(0.0, ap.rib_pos - radius_normalized)
                end = min(1.0, ap.rib_pos + radius_normalized)
                exclusion_zones.append((start, end))
        
        return exclusion_zones
    
    def subtract_exclusion_zones(self, allowed_ranges, exclusion_zones):
        """
        Remove exclusion zones from allowed ranges.
        Both inputs are lists of (start, end) tuples.
        Returns a new list of allowed (start, end) tuples.
        """
        if not exclusion_zones:
            return allowed_ranges
        
        # Sort exclusion zones by start position
        exclusions = sorted(exclusion_zones, key=lambda x: x[0])
        
        result = []
        for start, end in allowed_ranges:
            current_start = start
            for ex_start, ex_end in exclusions:
                if ex_end <= current_start or ex_start >= end:
                    # No overlap with this exclusion
                    continue
                if ex_start > current_start:
                    # Add the gap before this exclusion
                    result.append((current_start, min(ex_start, end)))
                current_start = max(current_start, ex_end)
                if current_start >= end:
                    break
            if current_start < end:
                result.append((current_start, end))
        
        return result

    def apply_holes(self, glider):
        if not self.holes:
            return

        # Filter suspended ribs - exclude brake attachments (>90% chord position)
        # Only consider true suspension attachments (A/B/C lines), not brake tab attachments
        suspended_ribs = {
            att.rib for att in glider.lineset.attachment_points 
            if hasattr(att, 'rib') and hasattr(att, 'rib_pos') and att.rib_pos <= 0.9
        }

        NO_HOLE_ZONE_BASE_CHORD_FRACTION = 0.05
        
        # Minimum chord for hole generation - skip tiny ribs (stabilos) that cause mesh issues
        MIN_CHORD_FOR_HOLES = 0.15  # 15cm minimum chord (reduced from 30cm)

        for rib_idx, rib in enumerate(glider.ribs):
            # Skip the last rib if last_profile_enabled (should be solid, no holes)
            if getattr(self, 'last_profile_enabled', False) and rib_idx == len(glider.ribs) - 1:
                print(f"[apply_holes] Skipping last rib {rib.name}: last_profile_enabled")
                continue
            
            # Skip ribs with chord too small for reliable hole generation
            if rib.chord < MIN_CHORD_FOR_HOLES:
                print(f"[apply_holes] Skipping rib {rib.name}: chord {rib.chord:.3f}m < {MIN_CHORD_FOR_HOLES}m")
                continue
                
            is_suspended = rib in suspended_ribs

            if is_suspended:
                shape_idx, num_holes, w_factor, h_factor, v_shift_factor, start_pos, end_pos, hole_height_mode, hole_margin, corner_radius = (
                    getattr(self, 'hole_shape_s', 0), self.num_holes_s, self.hole_width_s,
                    self.hole_height_s, self.vertical_shift_s, self.min_hole_pos_s, self.max_hole_pos_s,
                    self.hole_height_mode_s, self.hole_margin_s, getattr(self, 'hole_corner_radius_s', 0.005)
                )
                no_hole_zones = []
                attachment_points = glider.get_rib_attachment_points(rib)
                
                # Get pilot point 2D coordinates (same method as preview)
                pilot_2d = None
                if hasattr(glider, 'lineset') and glider.lineset:
                    for node in glider.lineset.nodes:
                        if hasattr(node, 'name') and node.name is not None and 'pilot' in node.name.lower():
                            pilot_point_3d = np.array(node.vec) if hasattr(node, 'vec') else None
                            if pilot_point_3d is not None:
                                # Project pilot to rib's 2D coordinate frame
                                le_3d = np.array(rib.profile_3d.data[rib.profile_2d.noseindex])
                                te_3d = (np.array(rib.profile_3d.data[0]) + np.array(rib.profile_3d.data[-1])) / 2
                                chord_3d = le_3d - te_3d
                                chord_length = np.linalg.norm(chord_3d)
                                if chord_length > 1e-9:
                                    chord_dir = chord_3d / chord_length
                                    upper_idx = rib.profile_2d.noseindex + 1 if rib.profile_2d.noseindex + 1 < len(rib.profile_3d.data) else 0
                                    upper_3d = np.array(rib.profile_3d.data[upper_idx])
                                    normal = np.cross(chord_3d, upper_3d - te_3d)
                                    normal = normal / np.linalg.norm(normal) if np.linalg.norm(normal) > 0 else np.array([1, 0, 0])
                                    up_dir = np.cross(normal, chord_dir)
                                    up_dir = up_dir / np.linalg.norm(up_dir) if np.linalg.norm(up_dir) > 0 else np.array([0, 0, 1])
                                    pilot_rel_3d = pilot_point_3d - te_3d
                                    pilot_chord_pos = np.dot(pilot_rel_3d, chord_dir) / chord_length
                                    pilot_up_pos = np.dot(pilot_rel_3d, up_dir) / chord_length
                                    te_2d_x = (rib.profile_2d.data[0][0] + rib.profile_2d.data[-1][0]) / 2
                                    le_2d_x = rib.profile_2d.data[rib.profile_2d.noseindex][0]
                                    pilot_2d_x = te_2d_x + pilot_chord_pos * (le_2d_x - te_2d_x)
                                    pilot_2d_y = pilot_up_pos
                                    pilot_2d = np.array([pilot_2d_x, pilot_2d_y])
                            break
                
                for ap in attachment_points:
                    v1 = rib.profile_2d.align([ap.rib_pos, -1.0]) # Apex on intrados

                    angle_rad = np.deg2rad(self.hole_free_angle_s)

                    # Calculate angle_offset based on direction toward pilot (like preview does)
                    if pilot_2d is not None:
                        line_direction = v1 - pilot_2d
                        if np.linalg.norm(line_direction) > 1e-9:
                            line_direction = line_direction / np.linalg.norm(line_direction)
                        else:
                            line_direction = np.array([0, 1])
                        angle_offset = np.arctan2(line_direction[1], line_direction[0])
                    else:
                        # Fallback to local vertical if no pilot point
                        upper_point = rib.profile_2d.align([ap.rib_pos, 1.0])
                        angle_offset = np.pi/2 # Default vertical

                        # Try to get pilot point for smarter alignment (match preview)
                        pilot_point_3d = None
                        if hasattr(glider, 'lineset') and glider.lineset:
                            try:
                                main_ap = glider.lineset.get_main_attachment_point()
                                if main_ap is not None and hasattr(main_ap, 'vec'):
                                    pilot_point_3d = np.array(main_ap.vec)
                            except:
                                pass
                        
                        if pilot_point_3d is not None:
                             try:
                                 # 3D Project logic
                                 le_3d = np.array(rib.profile_3d.data[rib.profile_2d.noseindex])
                                 te_3d = (np.array(rib.profile_3d.data[0]) + np.array(rib.profile_3d.data[-1])) / 2
                                 chord_3d = le_3d - te_3d
                                 chord_len = np.linalg.norm(chord_3d)
                                 
                                 if chord_len > 1e-6:
                                     chord_dir = chord_3d / chord_len
                                     
                                     # Normal to rib plane (using upper surface point)
                                     upper_idx = len(rib.profile_3d.data) // 4
                                     upper_3d = np.array(rib.profile_3d.data[upper_idx])
                                     v1_3d = upper_3d - te_3d
                                     normal = np.cross(chord_3d, v1_3d)
                                     if np.linalg.norm(normal) > 1e-6:
                                          normal /= np.linalg.norm(normal)
                                          up_dir = np.cross(normal, chord_dir)
                                          if np.linalg.norm(up_dir) > 1e-6:
                                               up_dir /= np.linalg.norm(up_dir)
                                               
                                               # Project pilot
                                               pilot_rel = pilot_point_3d - te_3d
                                               pilot_chord_pos = np.dot(pilot_rel, chord_dir) / chord_len
                                               pilot_up_pos = np.dot(pilot_rel, up_dir) / chord_len
                                               
                                               # Map to normalized 2D
                                               te_2d_x = (rib.profile_2d.data[0][0] + rib.profile_2d.data[-1][0])/2
                                               le_2d_x = rib.profile_2d.data[rib.profile_2d.noseindex][0]
                                               
                                               pilot_2d_x = te_2d_x + pilot_chord_pos * (le_2d_x - te_2d_x)
                                               pilot_2d_y = pilot_up_pos
                                               pilot_2d = np.array([pilot_2d_x, pilot_2d_y])
                                               
                                               # Vector from pilot to AP
                                               line_dir = v1 - pilot_2d
                                               if np.linalg.norm(line_dir) > 1e-9:
                                                    angle_offset = np.arctan2(line_dir[1], line_dir[0])
                             except Exception as e:
                                  print("Angle calculation error: {}".format(e))
                                  # Fallback to local vertical
                                  local_vertical = upper_point - v1
                                  if np.linalg.norm(local_vertical) > 1e-9:
                                       angle_offset = np.arctan2(local_vertical[1], local_vertical[0])
                        else:
                             # Fallback
                             local_vertical = upper_point - v1
                             if np.linalg.norm(local_vertical) > 1e-9:
                                  angle_offset = np.arctan2(local_vertical[1], local_vertical[0])

                    dir2 = np.array([np.cos(angle_offset - angle_rad), np.sin(angle_offset - angle_rad)])
                    dir3 = np.array([np.cos(angle_offset + angle_rad), np.sin(angle_offset + angle_rad)])

                    # Find intersection of these lines with the upper surface (extrados)
                    extrados_poly = rib.profile_2d.get_extrados_poly()

                    far_factor = 10.0  # Normalized coordinates
                    v2 = extrados_poly.line_intersection(v1, v1 + dir2 * far_factor)
                    v3 = extrados_poly.line_intersection(v1, v1 + dir3 * far_factor)

                    if v2 is not None and v3 is not None:
                        no_hole_zones.append((v1, v2, v3))
                        

            else:
                shape_idx, num_holes, w_factor, h_factor, v_shift_factor, start_pos, end_pos, hole_height_mode, hole_margin, corner_radius = (
                    getattr(self, 'hole_shape_ns', 0), self.num_holes_ns, self.hole_width_ns,
                    self.hole_height_ns, self.vertical_shift_ns, self.min_hole_pos_ns, self.max_hole_pos_ns,
                    self.hole_height_mode_ns, self.hole_margin_ns, getattr(self, 'hole_corner_radius_ns', 0.005)
                )
                no_hole_zones = []

            hole_shape = 'ellipse' if shape_idx == 0 else 'rounded_rectangle'

            if num_holes == 0:
                continue

            allowed_ranges = [(start_pos, end_pos)]

            total_allowable_length = sum(end - start for start, end in allowed_ranges)
            if total_allowable_length <= 1e-6:
                continue

            holes_to_distribute = num_holes
            for i, (start, end) in enumerate(allowed_ranges):
                range_length = end - start
                if range_length <= 0: continue

                is_last_range = (i == len(allowed_ranges) - 1)
                if is_last_range:
                    num_holes_in_range = holes_to_distribute
                else:
                    num_holes_in_range = int(round(num_holes * (range_length / total_allowable_length)))

                if num_holes_in_range <= 0:
                    continue

                holes_to_distribute -= num_holes_in_range

                if num_holes_in_range == 1:
                    potential_positions = [start + range_length / 2] # Center the single hole
                else:
                    potential_positions = np.linspace(start, end, num_holes_in_range)

                for pos_x in potential_positions:
                    upper = rib.profile_2d.profilepoint(-pos_x)
                    lower = rib.profile_2d.profilepoint(pos_x)
                    local_thickness = upper[1] - lower[1]
                    if local_thickness < 1e-6:
                        continue

                    if is_suspended:
                        hole_center_x = (upper[0] + lower[0]) / 2.0
                        min_y_ceiling = upper[1]

                        for v1, v2, v3 in no_hole_zones:
                            if min(v1[0], v2[0], v3[0]) <= hole_center_x <= max(v1[0], v2[0], v3[0]):
                                for p1, p2 in [(v1, v2), (v2, v3), (v3, v1)]:
                                    if p1[0] != p2[0] and ((p1[0] <= hole_center_x <= p2[0]) or (p2[0] <= hole_center_x <= p1[0])):
                                        y_intersect = p1[1] + (p2[1] - p1[1]) * (hole_center_x - p1[0]) / (p2[0] - p1[0])
                                        if y_intersect < min_y_ceiling: # Constrain ceiling from above
                                             min_y_ceiling = min(min_y_ceiling, y_intersect)

                        available_height = min_y_ceiling - lower[1]
                        hole_center_y = lower[1] + available_height / 2
                        new_lower_bound = np.array([hole_center_x, lower[1]]) # Base for vertical shift calculation logic
                        eff_upper_bound = np.array([hole_center_x, min_y_ceiling])
                    else:
                        available_height = upper[1] - lower[1]
                        new_lower_bound = lower
                        eff_upper_bound = upper

                    if available_height < 1e-4:
                        continue

                    # vertical shift is relative to LOCAL THICKNESS if we wanted to maintain consistent offset logic,
                    # but here we want to center in the AVAILABLE space usually.
                    # The original code used new_lower_bound + (available_height)/2 * (1+shift).
                    # Let's align with that.
                    
                    hole_center = np.array([hole_center_x if is_suspended else (upper[0]+lower[0])/2, lower[1] + available_height / 2])
                    
                    if not is_suspended: # Respect original shift logic for non-suspended
                         hole_center = lower + (upper - lower) / 2 * (1 + v_shift_factor)

                    # For suspended, we might want to respect vertical shift within the NEW available height?
                    if is_suspended:
                         hole_center[1] += available_height / 2 * v_shift_factor
                    
                    # Calculate final_vertical_shift relative to full local thickness
                    full_thickness = upper[1] - lower[1]
                    if full_thickness < 1e-6: continue
                    
                    original_center_y = (upper[1] + lower[1]) / 2.0
                    final_vertical_shift = (hole_center[1] - original_center_y) / full_thickness

                    width_param = (w_factor * rib.chord) / available_height if available_height > 1e-6 else 0
                    
                    # Calculate height parameter based on mode
                    # RibHole interprets size[1] as a factor of available_height (or local_thickness)
                    if hole_height_mode == 1: # Margin mode
                        target_height = available_height - 2 * hole_margin
                        if target_height <= 0:
                            continue
                        height_param = target_height / available_height
                    else: # Percent mode
                        height_param = h_factor

                    rib.holes.append(
                        RibHole(
                            pos_x,
                            size=np.array([width_param, height_param]),
                            vertical_shift=final_vertical_shift,
                            rotation=0.0,
                            shape=hole_shape,
                            available_height=available_height,
                            corner_radius=corner_radius
                        )
                    )

    def apply_reinforcements(self, glider):
        """Apply reinforcement configurations to ribs for 2D export."""
        from openglider.glider.rib.elements import AttachmentReinforcement
        
        if not getattr(self, 'reinforcement_enabled_s', False):
            # Clear reinforcements from all ribs
            for rib in glider.ribs:
                rib.reinforcements = []
            return
        
        apply_all = getattr(self, 'reinforcement_apply_all_s', False)
        master_config = getattr(self, 'reinforcement_master_s', {})
        configs = getattr(self, 'reinforcement_configs_s', [])
        excluded_ribs = getattr(self, 'reinforcement_excluded_ribs_s', [])
        
        # Identify suspended ribs
        suspended_ribs = {att.rib for att in glider.lineset.attachment_points if hasattr(att, 'rib')}
        
        for rib_idx, rib in enumerate(glider.ribs):
            if rib in suspended_ribs:
                # Check if this rib is excluded from reinforcements
                if rib_idx in excluded_ribs:
                    rib.reinforcements = []
                    continue
                
                # Get attachment points for this rib
                attachment_points = glider.get_rib_attachment_points(rib)
                # Filter to valid attachment points (< 90% chord)
                valid_aps = [ap for ap in attachment_points if ap.rib_pos <= 0.90]
                valid_aps.sort(key=lambda x: x.rib_pos)
                
                reinforcements = []
                for i, ap in enumerate(valid_aps):
                    # Get config
                    if apply_all:
                        config = master_config
                    else:
                        config = configs[i] if i < len(configs) else master_config
                    
                    if config.get('enabled', True):
                        # Generate name: rib index + attachment point name
                        name = f"{rib_idx + 1}{ap.name}" if ap.name else f"{rib_idx + 1}_{i + 1}"
                        
                        reinforcement = AttachmentReinforcement(
                            position=ap.rib_pos,
                            surface_offset=config.get('surface_offset', 0.0005),  # 0.5mm
                            halfmoon_radius=config.get('halfmoon_radius', 0.1),   # 100mm
                            rod_enabled=config.get('rod_enabled', True),
                            rod_offset=config.get('rod_offset', 0.008),           # 8mm
                            rod_width=config.get('rod_width', 0.009),             # 9mm
                            rod_end_offset=config.get('rod_end_offset', 1.0),     # 1°
                            name=name,
                        )
                        reinforcements.append(reinforcement)

                
                rib.reinforcements = reinforcements
            else:
                # Non-suspended ribs don't get reinforcements
                rib.reinforcements = []

    def apply_rod_sleeves(self, glider):
        """Apply rod sleeve configurations to ribs for 2D export."""
        from openglider.glider.rib.elements import RodSleeve
        
        # Identify suspended ribs
        suspended_ribs = {att.rib for att in glider.lineset.attachment_points if hasattr(att, 'rib')}
        
        for rib_idx, rib in enumerate(glider.ribs):
            is_suspended = rib in suspended_ribs
            suffix = '_s' if is_suspended else '_ns'
            
            rod_sleeves = []
            
            # Get extrados sleeves
            extrados_enabled = getattr(self, f'extrados_sleeves_enabled{suffix}', True)
            extrados_configs = getattr(self, f'extrados_sleeves{suffix}', [])
            
            if extrados_enabled and extrados_configs:
                for i, config in enumerate(extrados_configs):
                    # Check if this rib is excluded for this config
                    excluded_ribs = config.get('excluded_ribs', [])
                    if rib_idx in excluded_ribs:
                        continue
                    
                    sleeve = RodSleeve(
                        surface='extrados',
                        width=config.get('width', 0.015),
                        offset=config.get('offset', 0.005),
                        start_chord=config.get('start_chord', 0.0),
                        end_chord=config.get('end_chord', 0.7),
                        le_angle=config.get('start_angle', 350.0),
                        te_angle=config.get('end_angle', 325.0),
                        le_length=config.get('start_length', 0.1),
                        te_length=config.get('end_length', 0.075),
                    )
                    rod_sleeves.append(sleeve)
            
            # Get intrados sleeves
            intrados_enabled = getattr(self, f'intrados_sleeves_enabled{suffix}', True)
            intrados_configs = getattr(self, f'intrados_sleeves{suffix}', [])
            
            if intrados_enabled and intrados_configs:
                for i, config in enumerate(intrados_configs):
                    # Check if this rib is excluded for this config
                    excluded_ribs = config.get('excluded_ribs', [])
                    if rib_idx in excluded_ribs:
                        continue
                    
                    sleeve = RodSleeve(
                        surface='intrados',
                        width=config.get('width', 0.015),
                        offset=config.get('offset', 0.005),
                        start_chord=config.get('start_chord', 0.06),
                        end_chord=config.get('end_chord', 0.5),
                        le_angle=config.get('start_angle', 100.0),
                        te_angle=config.get('end_angle', 20.0),
                        le_length=config.get('start_length', 0.1),
                        te_length=config.get('end_length', 0.09),
                    )
                    rod_sleeves.append(sleeve)
            
            rib.rod_sleeves = rod_sleeves

    def remap_cell_indices(self, old_cell_num):
        """
        Remap all cell/rib indices proportionally after cell count change.
        Call this after changing shape.cell_num.
        """
        new_cell_num = self.shape.cell_num
        if old_cell_num == new_cell_num:
            return

        old_half = old_cell_num // 2 + (old_cell_num % 2)
        new_half = new_cell_num // 2 + (new_cell_num % 2)

        # number of ribs in the half-wing
        old_half_ribs = old_half + 1 - (old_cell_num % 2)
        new_half_ribs = new_half + 1 - (new_cell_num % 2)

        def remap_cell(idx, old_n, new_n):
            """Proportionally remap a cell index."""
            if old_n <= 0 or new_n <= 0:
                return 0
            return min(int(round(idx * new_n / old_n)), new_n - 1)

        def remap_cells_list(cells, old_n, new_n):
            """Remap a list of cell indices, removing duplicates."""
            remapped = []
            seen = set()
            for c in cells:
                new_c = remap_cell(c, old_n, new_n)
                if new_c not in seen:
                    remapped.append(new_c)
                    seen.add(new_c)
            return remapped

        count_lineset = 0
        count_elements = 0

        # 1. Remap lineset nodes (UpperNode2D.cell_no)
        from openglider.glider.parametric.lines import UpperNode2D
        for node in self.lineset.nodes:
            if isinstance(node, UpperNode2D):
                old_no = node.cell_no
                node.cell_no = remap_cell(old_no, old_half, new_half)
                if node.cell_no != old_no:
                    count_lineset += 1

        # 2. Remap elements with "cells" key
        cell_keys = [
            "cuts", "diagonals", "straps", "miniribs",
            "cell_rigidfoils", "le_panel_splits"
        ]
        for key in cell_keys:
            for item in self.elements.get(key, []):
                if "cells" in item:
                    old_cells = item["cells"]
                    item["cells"] = remap_cells_list(
                        old_cells, old_half, new_half
                    )
                    count_elements += 1

        # 3. Remap elements with "ribs" key (rib index = half_rib count)
        rib_keys = ["holes", "rigidfoils"]
        for key in rib_keys:
            for item in self.elements.get(key, []):
                if "ribs" in item:
                    old_ribs = item["ribs"]
                    item["ribs"] = remap_cells_list(
                        old_ribs, old_half_ribs, new_half_ribs
                    )
                    count_elements += 1

        # 4. Remap materials (list indexed by cell_no)
        if "materials" in self.elements:
            old_mats = self.elements["materials"]
            if isinstance(old_mats, list) and old_mats:
                new_mats = []
                for new_c in range(new_half):
                    old_c = remap_cell(new_c, new_half, old_half)
                    if old_c < len(old_mats):
                        new_mats.append(old_mats[old_c])
                    else:
                        new_mats.append(old_mats[-1] if old_mats else {})
                self.elements["materials"] = new_mats
                count_elements += 1

        logging.info(
            f"Remapped cell indices: {old_cell_num} -> {new_cell_num} cells "
            f"({count_lineset} lineset nodes, {count_elements} element entries)"
        )

    def __json__(self):
        return {
            "shape": self.shape,
            "arc": self.arc,
            "aoa": self.aoa,
            "zrot": self.zrot,
            "profiles": self.profiles,
            "profile_merge_curve": self.profile_merge_curve,
            "balloonings": self.balloonings,
            "ballooning_merge_curve": self.ballooning_merge_curve,
            "lineset": self.lineset,
            "speed": self.speed,
            "glide": self.glide,
            "elements": self.elements,
            "hole_shape_ns": getattr(self, "hole_shape_ns", 0),
            "num_holes_ns": getattr(self, "num_holes_ns", 30),
            "hole_width_ns": getattr(self, "hole_width_ns", 0.003),
            "hole_height_ns": getattr(self, "hole_height_ns", 0.8),
            "vertical_shift_ns": getattr(self, "vertical_shift_ns", 0.0),
            "min_hole_pos_ns": getattr(self, "min_hole_pos_ns", 0.2),
            "max_hole_pos_ns": getattr(self, "max_hole_pos_ns", 0.8),
            "hole_height_mode_ns": getattr(self, "hole_height_mode_ns", 0),
            "hole_margin_ns": getattr(self, "hole_margin_ns", 0.02),
            "hole_corner_radius_ns": getattr(self, "hole_corner_radius_ns", 0.005),
            "hole_shape_s": getattr(self, "hole_shape_s", 0),
            "num_holes_s": getattr(self, "num_holes_s", 30),
            "hole_width_s": getattr(self, "hole_width_s", 0.003),
            "hole_height_s": getattr(self, "hole_height_s", 0.8),
            "vertical_shift_s": getattr(self, "vertical_shift_s", 0.0),
            "min_hole_pos_s": getattr(self, "min_hole_pos_s", 0.2),
            "max_hole_pos_s": getattr(self, "max_hole_pos_s", 0.8),
            "hole_height_mode_s": getattr(self, "hole_height_mode_s", 0),
            "hole_margin_s": getattr(self, "hole_margin_s", 0.02),
            "hole_corner_radius_s": getattr(self, "hole_corner_radius_s", 0.005),
            "hole_free_angle_s": getattr(self, "hole_free_angle_s", 30.0),
            # Airfoil Structure - Extrados Sleeve (suspended)
            "extrados_sleeve_enabled_s": getattr(self, "extrados_sleeve_enabled_s", False),
            "extrados_sleeve_width_s": getattr(self, "extrados_sleeve_width_s", 0.015),
            "extrados_sleeve_offset_s": getattr(self, "extrados_sleeve_offset_s", 0.003),
            "extrados_sleeve_start_s": getattr(self, "extrados_sleeve_start_s", 0.0),
            "extrados_sleeve_end_s": getattr(self, "extrados_sleeve_end_s", 0.9),
            "extrados_sleeve_le_angle_s": getattr(self, "extrados_sleeve_le_angle_s", 80.0),
            "extrados_sleeve_le_length_s": getattr(self, "extrados_sleeve_le_length_s", 0.03),
            "extrados_sleeve_te_angle_s": getattr(self, "extrados_sleeve_te_angle_s", 80.0),
            "extrados_sleeve_te_length_s": getattr(self, "extrados_sleeve_te_length_s", 0.03),
            # Airfoil Structure - Intrados Sleeve (suspended)
            "intrados_sleeve_enabled_s": getattr(self, "intrados_sleeve_enabled_s", False),
            "intrados_sleeve_width_s": getattr(self, "intrados_sleeve_width_s", 0.015),
            "intrados_sleeve_offset_s": getattr(self, "intrados_sleeve_offset_s", 0.003),
            "intrados_sleeve_start_s": getattr(self, "intrados_sleeve_start_s", 0.0),
            "intrados_sleeve_end_s": getattr(self, "intrados_sleeve_end_s", 0.9),
            "intrados_sleeve_le_angle_s": getattr(self, "intrados_sleeve_le_angle_s", 100.0),
            "intrados_sleeve_le_length_s": getattr(self, "intrados_sleeve_le_length_s", 0.03),
            "intrados_sleeve_te_angle_s": getattr(self, "intrados_sleeve_te_angle_s", 100.0),
            "intrados_sleeve_te_length_s": getattr(self, "intrados_sleeve_te_length_s", 0.03),
            # Airfoil Structure - Extrados Sleeve (non-suspended)
            "extrados_sleeve_enabled_ns": getattr(self, "extrados_sleeve_enabled_ns", False),
            "extrados_sleeve_width_ns": getattr(self, "extrados_sleeve_width_ns", 0.015),
            "extrados_sleeve_offset_ns": getattr(self, "extrados_sleeve_offset_ns", 0.003),
            "extrados_sleeve_start_ns": getattr(self, "extrados_sleeve_start_ns", 0.0),
            "extrados_sleeve_end_ns": getattr(self, "extrados_sleeve_end_ns", 0.9),
            "extrados_sleeve_le_angle_ns": getattr(self, "extrados_sleeve_le_angle_ns", 80.0),
            "extrados_sleeve_le_length_ns": getattr(self, "extrados_sleeve_le_length_ns", 0.03),
            "extrados_sleeve_te_angle_ns": getattr(self, "extrados_sleeve_te_angle_ns", 80.0),
            "extrados_sleeve_te_length_ns": getattr(self, "extrados_sleeve_te_length_ns", 0.03),
            # Airfoil Structure - Intrados Sleeve (non-suspended)
            "intrados_sleeve_enabled_ns": getattr(self, "intrados_sleeve_enabled_ns", False),
            "intrados_sleeve_width_ns": getattr(self, "intrados_sleeve_width_ns", 0.015),
            "intrados_sleeve_offset_ns": getattr(self, "intrados_sleeve_offset_ns", 0.003),
            "intrados_sleeve_start_ns": getattr(self, "intrados_sleeve_start_ns", 0.0),
            "intrados_sleeve_end_ns": getattr(self, "intrados_sleeve_end_ns", 0.9),
            "intrados_sleeve_le_angle_ns": getattr(self, "intrados_sleeve_le_angle_ns", 100.0),
            "intrados_sleeve_le_length_ns": getattr(self, "intrados_sleeve_le_length_ns", 0.03),
            "intrados_sleeve_te_angle_ns": getattr(self, "intrados_sleeve_te_length_ns", 100.0),
            "intrados_sleeve_te_length_ns": getattr(self, "intrados_sleeve_te_length_ns", 0.03),
            # Airfoil Structure - Reinforcements (suspended only)
            "reinforcement_enabled_s": getattr(self, "reinforcement_enabled_s", True),
            "reinforcement_apply_all_s": getattr(self, "reinforcement_apply_all_s", False),
            "reinforcement_master_s": getattr(self, "reinforcement_master_s", {
                'enabled': True, 'surface_offset': 0.0005, 'halfmoon_radius': 0.1,
                'rod_enabled': True, 'rod_offset': 0.008, 'rod_width': 0.009, 'rod_end_offset': 1.0
            }),
            "reinforcement_configs_s": getattr(self, "reinforcement_configs_s", []),
            "reinforcement_excluded_ribs_s": getattr(self, "reinforcement_excluded_ribs_s", []),
            # Multi-rod sleeves (NEW FORMAT)
            "extrados_sleeves_enabled_s": getattr(self, "extrados_sleeves_enabled_s", True),
            "extrados_sleeves_s": getattr(self, "extrados_sleeves_s", []),
            "intrados_sleeves_enabled_s": getattr(self, "intrados_sleeves_enabled_s", True),
            "intrados_sleeves_s": getattr(self, "intrados_sleeves_s", []),
            "extrados_sleeves_enabled_ns": getattr(self, "extrados_sleeves_enabled_ns", True),
            "extrados_sleeves_ns": getattr(self, "extrados_sleeves_ns", []),
            "intrados_sleeves_enabled_ns": getattr(self, "intrados_sleeves_enabled_ns", True),
            "intrados_sleeves_ns": getattr(self, "intrados_sleeves_ns", []),
            # Edit Cells - Diagonals Auto-fill configuration
            "diagonal_autofill_params": getattr(self, "diagonal_autofill_params", {
                "A": (4.0, 5.0, 15.0, 1),
                "B": (4.0, 15.0, 30.0, 1),
                "C": (4.0, 30.0, 50.0, 1),
                "D": (4.0, 50.0, 75.0, 1),
            }),
            "diagonal_autofill_offset": getattr(self, "diagonal_autofill_offset", 0),
            # Lines Auto-Placement configuration
            "lines_placement_config": getattr(self, "lines_placement_config", {
                "demi_ecartement": 0.2,
                "profondeur": 0.5,
                "hauteur_cone": 7.0,
                "riser_length": 0.47,
                "basses_auto": True,
                "basses_length": 2.0,
                "inter_auto": True,
                "inter_length": 1.0,
                "include_stabilo": True,
                "stabilo_position": 50.0,
                "line_type_name": "default",
                "line_types": {
                    "A": {"enabled": True, "position": 8.5, "interval": 1, "start_cell": 0, "patterns": "3:1, 2:2:1"},
                    "B": {"enabled": True, "position": 27.5, "interval": 2, "start_cell": 0, "patterns": "2:2:1, 2:1"},
                    "C": {"enabled": True, "position": 53.0, "interval": 2, "start_cell": 0, "patterns": "2:1"},
                    "D": {"enabled": True, "position": 77.0, "interval": 3, "start_cell": 0, "patterns": "2:1"},
                    "F": {"enabled": True, "position": 100.0, "interval": 1, "start_cell": 0, "patterns": "1:1"},
                }
            }),
            # =====================================================================
            # Profile Control - Unified airfoil management
            # =====================================================================
            "thickness_curve": getattr(self, "thickness_curve", None),
            "thickness_curve_enabled": getattr(self, "thickness_curve_enabled", False),
            "sharknose_enabled": getattr(self, "sharknose_enabled", False),
            "sharknose_x1": getattr(self, "sharknose_x1", 0.06),
            "sharknose_x2": getattr(self, "sharknose_x2", 0.09),
            "sharknose_x3": getattr(self, "sharknose_x3", 0.90),
            "sharknose_y_max": getattr(self, "sharknose_y_max", 0.03),
            "sharknose_curve": getattr(self, "sharknose_curve", None),
            "sharknose_cells": getattr(self, "sharknose_cells", None),
            "profile_overrides": getattr(self, "profile_overrides", {}),
            "profile_overrides_enabled": getattr(self, "profile_overrides_enabled", False),
            "last_profile_enabled": getattr(self, "last_profile_enabled", False),
            "last_profile_type": getattr(self, "last_profile_type", "line"),
            "last_profile_thickness": getattr(self, "last_profile_thickness", 0.3),
            "last_profile_custom": getattr(self, "last_profile_custom", None),
        }


    def __setstate__(self, state):
        """
        Restore state and ensure new attributes are initialized with defaults.
        This fixes persistence issues when loading old objects that lack new fields.
        """
        self.__dict__.update(state)
        # Initialize default values for missing attributes (e.g. from schema updates)
        # Using the same defaults as in __init__
        self.hole_free_angle_s = getattr(self, 'hole_free_angle_s', 30.0)


    @classmethod
    def import_ods(cls, path):
        return import_ods_2d(cls, path)

    export_ods = export_ods_2d

    def copy(self):
        return copy.deepcopy(self)

    def get_geomentry_table(self):
        table = Table()
        table.insert_row(
            [
                "",
                "Ribs",
                "Chord",
                "X",
                "Y",
                "%",
                "Arc",
                "Arc_diff",
                "AOA",
                "Z-rotation",
                "Y-rotation",
                "profile-merge",
                "ballooning-merge",
            ]
        )
        shape = self.shape.get_half_shape()
        for rib_no in range(self.shape.half_rib_num):
            table[1 + rib_no, 1] = rib_no + 1

        for rib_no, chord in enumerate(shape.chords):
            table[1 + rib_no, 2] = chord

        for rib_no, p in enumerate(self.shape.baseline):
            table[1 + rib_no, 3] = p[0]
            table[1 + rib_no, 4] = p[1]
            table[1 + rib_no, 5] = self.shape.baseline_pos

        last_angle = 0
        for cell_no, angle in enumerate(self.get_arc_angles()):
            angle = angle * 180 / math.pi
            table[1 + cell_no, 6] = angle
            table[1 + cell_no, 7] = angle - last_angle
            last_angle = angle

        for rib_no, aoa in enumerate(self.get_aoa()):
            table[1 + rib_no, 8] = aoa * 180 / math.pi
            table[1 + rib_no, 9] = 0
            table[1 + rib_no, 10] = 0

        return table

    @property
    def arc_positions(self):
        return self.arc.get_arc_positions(self.shape.rib_x_values)

    def get_arc_angles(self, arc_curve=None):
        """
        Get rib rotations
        :param arc_curve:
        :return: rotation angles
        """
        # arc_curve = ArcCurve(self.arc)
        arc_curve = self.arc

        return arc_curve.get_rib_angles(self.shape.rib_x_values)

    @property
    def attachment_points(self):
        """coordinates of the attachment_points"""
        return [
            a_p.get_2D(self.shape)
            for a_p in self.lineset.nodes
            if isinstance(a_p, UpperNode2D)
        ]

    def merge_ballooning(self, factor):
        factor = max(0, min(len(self.balloonings) - 1, factor))
        k = factor % 1
        i = int(factor // 1)
        first = self.balloonings[i]
        if k > 0:
            second = self.balloonings[i + 1]
            return first * (1 - k) + second * k
        else:
            return first.copy()

    def get_merge_profile(self, factor, pos_x=None, rib_index=None):
        """
        Get merged profile with optional profile control modifications.
        
        Args:
            factor: Interpolation factor from profile_merge_curve
            pos_x: Position along span (for thickness/sharknose curves)
            rib_index: Rib index (for profile overrides)
        
        Returns:
            Profile2D with all modifications applied
        """
        # 1. Check for rib-specific override
        if (getattr(self, 'profile_overrides_enabled', False) and 
            rib_index is not None and 
            str(rib_index) in getattr(self, 'profile_overrides', {})):
            override_idx = self.profile_overrides[str(rib_index)]
            if 0 <= override_idx < len(self.profiles):
                profile = self.profiles[override_idx].copy()
            else:
                profile = self._interpolate_profiles(factor)
        else:
            # 2. Standard interpolation
            profile = self._interpolate_profiles(factor)
        
        # 3. Apply thickness scaling
        if getattr(self, 'thickness_curve_enabled', False) and pos_x is not None:
            thickness_factor = self._get_thickness_factor(pos_x)
            if thickness_factor != 1.0:
                profile = self._apply_thickness_scaling(profile, thickness_factor)
        
        # 4. Apply shark nose if enabled AND rib belongs to a selected cell
        if getattr(self, 'sharknose_enabled', False):
            sharknose_cells = getattr(self, 'sharknose_cells', None)
            # Check if rib_index corresponds to a cell in sharknose_cells
            # A rib at index i borders cells i-1 and i (for i > 0)
            # We apply sharknose if either adjacent cell is selected
            apply_sharknose = True
            if sharknose_cells is not None and rib_index is not None:
                # Check if either adjacent cell is in the selected list
                cell_indices = []
                if rib_index > 0:
                    cell_indices.append(rib_index - 1)
                if rib_index < len(self.shape.rib_x_values) - 1:
                    cell_indices.append(rib_index)
                apply_sharknose = any(c in sharknose_cells for c in cell_indices)
            
            if apply_sharknose:
                sharknose_amount = self._get_sharknose_amount(pos_x)
                if sharknose_amount > 0:
                    profile = self._apply_sharknose(profile, sharknose_amount)
        
        # 5. Override last rib profile if enabled (stabilo/wingtip)
        last_enabled = getattr(self, 'last_profile_enabled', False)
        if rib_index is not None:
            last_rib_index = len(self.shape.rib_x_values) - 1
            is_last = rib_index == last_rib_index
            if is_last:
                print(f"[DEBUG] Last rib check: enabled={last_enabled}, rib_index={rib_index}, last_rib_index={last_rib_index}")
            if last_enabled and is_last:
                profile = self._get_last_profile(profile)
        
        return Profile2D(profile.data)
    
    def _interpolate_profiles(self, factor):
        """Standard profile interpolation between adjacent profiles."""
        factor = max(0, min(len(self.profiles) - 1, factor))
        k = factor % 1
        i = int(factor // 1)
        first = self.profiles[i].copy()
        if k > 0:
            second = self.profiles[i + 1]
            return first * (1 - k) + second * k
        return first
    
    def _get_thickness_factor(self, pos_x):
        """Get thickness scaling factor at given span position."""
        if not hasattr(self, 'thickness_curve') or self.thickness_curve is None:
            return 1.0
        try:
            interp = self.thickness_curve.interpolation(num=self.num_interpolate)
            return interp(abs(pos_x))
        except Exception:
            return 1.0
    
    def _apply_thickness_scaling(self, profile, factor):
        """Scale profile thickness by given factor."""
        if factor == 1.0:
            return profile
        new_profile = profile.copy()
        # Scale Y values relative to camber line
        data = np.array(new_profile.data)
        camber_line = dict(profile.camber_line)
        for i, (x, y) in enumerate(data):
            camber_y = camber_line.get(abs(x), 0)
            delta = y - camber_y
            data[i, 1] = camber_y + delta * factor
        new_profile.data = data
        return new_profile
    
    def _get_sharknose_amount(self, pos_x):
        """Get shark nose amount at given span position."""
        if not getattr(self, 'sharknose_enabled', False):
            return 0.0
        y_max = getattr(self, 'sharknose_y_max', 0.03)
        if hasattr(self, 'sharknose_curve') and self.sharknose_curve is not None:
            try:
                interp = self.sharknose_curve.interpolation(num=self.num_interpolate)
                return y_max * interp(abs(pos_x))
            except Exception:
                return y_max
        return y_max
    
    def _apply_sharknose(self, profile, y_add):
        """Apply shark nose deformation to profile intrados."""
        if y_add <= 0:
            return profile
        x1 = getattr(self, 'sharknose_x1', 0.06)
        x2 = getattr(self, 'sharknose_x2', 0.09)
        x3 = getattr(self, 'sharknose_x3', 0.90)
        
        new_data = []
        for x, y in profile.data:
            if y < 0:  # Only intrados (negative Y)
                if x > x1 and x < x2:
                    # Rising transition zone
                    y -= y_add * (x - x1) / (x2 - x1)
                elif x > x2 and x < x3:
                    # Falling transition zone
                    y -= y_add * (x3 - x) / (x3 - x2)
            new_data.append([x, y])
        
        new_profile = profile.copy()
        new_profile.data = np.array(new_data)
        return new_profile
    
    def _get_last_profile(self, base_profile):
        """Get the profile to use for the last rib (stabilo/wingtip).
        
        Options:
        - 'line': Zero thickness (flat line)
        - 'thin': Scaled down version of base profile
        - 'custom': User-imported profile
        """
        last_profile_type = getattr(self, 'last_profile_type', 'line')
        print(f"[DEBUG] _get_last_profile called with type='{last_profile_type}'")
        print(f"[DEBUG] base_profile.thickness = {base_profile.thickness}")
        
        if last_profile_type == 'line':
            return self._create_line_profile(base_profile)
        elif last_profile_type == 'thin':
            relative_thickness = getattr(self, 'last_profile_thickness', 0.3)  # 30% of original
            target = base_profile.thickness * relative_thickness
            print(f"[DEBUG] Creating thin profile: relative={relative_thickness}, target_thickness={target}")
            result = self._create_thin_profile(base_profile, target)
            print(f"[DEBUG] Result thin profile thickness = {result.thickness}")
            return result
        elif last_profile_type == 'custom':
            custom = getattr(self, 'last_profile_custom', None)
            if custom is not None:
                custom_copy = custom.copy()
                custom_copy.x_values = base_profile.x_values
                return custom_copy
        
        # Fallback to line
        print(f"[DEBUG] Fallback to line profile")
        return self._create_line_profile(base_profile)
    
    def _create_line_profile(self, base_profile):
        """Create a flat (zero thickness) profile based on given profile's x values."""
        data = [[x, 0.0] for x, _ in base_profile.data]
        return Profile2D(data, name="line_profile")
    
    def _create_thin_profile(self, base_profile, target_thickness):
        """Create a thin version of the profile with given thickness."""
        current_thickness = base_profile.thickness
        if current_thickness <= 0:
            return base_profile.copy()
        # Scale Y values to achieve target thickness
        factor = target_thickness / current_thickness
        new_data = [[x, y * factor] for x, y in base_profile.data]
        return Profile2D(new_data, name="thin_profile")

    def get_panels(self, glider_3d=None):
        """
        Create Panels Objects and apply on gliders cells if provided, otherwise create a list of panels
        :param glider_3d: (optional)
        :return: list of "cells"
        """

        def is_greater(cut_1, cut_2):
            if cut_1["left"] >= cut_2["left"] and cut_1["right"] >= cut_2["left"]:
                return True
            return False

        if glider_3d is None:
            cells = [[] for _ in range(self.shape.half_cell_num)]
        else:
            cells = [cell.panels for cell in glider_3d.cells]
            for cell in cells:
                cell = []

        for cell_no, panel_lst in enumerate(cells):
            _cuts = self.elements.get("cuts", [])
            cuts = [cut.copy() for cut in _cuts if cell_no in cut["cells"]]
            for cut in cuts:
                cut.pop("cells")

            # add trailing edge (2x)
            all_values = [c["left"] for c in cuts] + [c["right"] for c in cuts]

            if -1 not in all_values:
                cuts.append({"type": "parallel", "left": -1, "right": -1})
            if 1 not in all_values:
                cuts.append({"type": "parallel", "left": 1, "right": 1})

            cuts.sort(key=lambda cut: cut["left"])

            for cut1, cut2 in ZipCmp(cuts):
                part_no = len(panel_lst)

                if cut1["right"] > cut2["right"]:
                    error_str = "Invalid cut: C{} {:.02f}/{:.02f}/{} + {:.02f}/{:.02f}/{}".format(
                        cell_no + 1,
                        cut1["left"],
                        cut1["right"],
                        cut1["type"],
                        cut2["left"],
                        cut2["right"],
                        cut2["type"],
                    )
                    raise ValueError(error_str)

                if (
                    cut1["type"] == cut2["type"] == "folded"
                    or cut1["type"] == cut2["type"] == "singleskin"
                ):
                    # entry
                    continue

                try:
                    material_code = self.elements["materials"][cell_no][part_no]
                except (KeyError, IndexError):
                    material_code = "unknown"

                panel = Panel(
                    cut1,
                    cut2,
                    name="c{}p{}".format(cell_no + 1, part_no + 1),
                    material_code=material_code,
                )
                
                # Check if this is an LE panel that should be split chordwise
                le_splits = self.elements.get("le_panel_splits", [])
                should_split = False
                
                for le_split in le_splits:
                    if cell_no in le_split.get("cells", []):
                        cut_limit = le_split.get("cut_limit", 0.1)
                        # The LE panel is the one where:
                        # - cut_front (cut1) is at -cut_limit (our cut_3d on extrados)
                        # - cut_back (cut2) is at the LE entry (close to 0 or slightly positive)
                        front_left = cut1.get("left", 0)
                        back_left = cut2.get("left", 0)
                        
                        # Only match extrados (front_left negative) panels
                        # Match if:
                        # 1. front is near -cut_limit
                        # 2. back is at LE entry (close to 0 or positive, i.e. > -0.02)
                        is_extrados = front_left < 0
                        front_matches = abs(abs(front_left) - cut_limit) < 0.02
                        back_at_le_entry = back_left > -0.02  # At or past the leading edge
                        
                        if is_extrados and front_matches and back_at_le_entry:
                            should_split = True
                            break
                
                if should_split:
                    # Split into 2 panels at y=0.5 using y_start/y_end
                    # Lookup colors by panel name if available
                    materials_by_name = self.elements.get("materials_by_name", {})
                    name_L = "c{}p{}_L".format(cell_no + 1, part_no + 1)
                    name_R = "c{}p{}_R".format(cell_no + 1, part_no + 1)
                    
                    # Panel L: from rib1 (y=0) to mid (y=0.5)
                    panel_left = Panel(
                        cut1,
                        cut2,
                        name=name_L,
                        material_code=materials_by_name.get(name_L, material_code),
                        y_start=0.0,
                        y_end=0.5,
                    )
                    
                    # Panel R: from mid (y=0.5) to rib2 (y=1)
                    panel_right = Panel(
                        cut1,
                        cut2,
                        name=name_R,
                        material_code=materials_by_name.get(name_R, material_code),
                        y_start=0.5,
                        y_end=1.0,
                    )
                    
                    panel_lst.append(panel_left)
                    panel_lst.append(panel_right)
                else:
                    panel_lst.append(panel)

        return cells

    def _get_cell_straps(self, name, _cls):
        elements = []
        for cell_no in range(self.shape.half_cell_num):
            cell_elements = []
            for strap in self.elements.get(name, []):
                if cell_no in strap["cells"]:
                    dct = strap.copy()
                    dct.pop("cells")
                    cell_elements.append(_cls(**dct))

            cell_elements.sort(key=lambda strap: strap.get_average_x())

            for strap_no, strap in enumerate(cell_elements):
                strap.name = "c{}{}{}".format(cell_no + 1, name[0], strap_no)

            elements.append(cell_elements)

        return elements

    def get_cell_diagonals(self):
        return self._get_cell_straps("diagonals", DiagonalRib)

    def get_cell_straps(self):
        return self._get_cell_straps("straps", TensionStrap)

    def get_cell_tension_lines(self):
        return self._get_cell_straps("tension_lines", TensionLine)

    def apply_diagonals(self, glider):
        cell_straps = self.get_cell_straps()
        cell_diagonals = self.get_cell_diagonals()
        cell_tensionlines = self.get_cell_tension_lines()

        for cell_no, cell in enumerate(glider.cells):
            cell.diagonals = cell_diagonals[cell_no]
            cell.straps = cell_straps[cell_no]
            cell.straps += cell_tensionlines[cell_no]

    @classmethod
    def fit_glider_3d(cls, glider, numpoints=3):
        return fit_glider_3d(cls, glider, numpoints)

    def get_front_line(self):
        """
        Get Nose Positions for cells
        :return:
        """

    def get_aoa(self, interpolation_num=None):
        aoa_interpolation = self.aoa.interpolation(
            num=interpolation_num or self.num_interpolate
        )

        return [aoa_interpolation(x) for x in self.shape.rib_x_values]

    def apply_aoa(self, glider, interpolation_num=50):
        aoa_interpolation = self.aoa.interpolation(num=interpolation_num)
        aoa_values = [aoa_interpolation(x) for x in self.shape.rib_x_values]

        if self.shape.has_center_cell:
            aoa_values.insert(0, aoa_values[0])

        for rib, aoa in zip(glider.ribs, aoa_values):
            rib.aoa_relative = aoa

    def get_profile_merge(self):
        profile_merge_curve = self.profile_merge_curve.interpolation(
            num=self.num_interpolate
        )
        return [profile_merge_curve(abs(x)) for x in self.shape.rib_x_values]

    def get_ballooning_merge(self):
        ballooning_merge_curve = self.ballooning_merge_curve.interpolation(
            num=self.num_interpolate
        )
        return [ballooning_merge_curve(abs(x) for x in self.shape.cell_x_values)]

    def apply_shape_and_arc(self, glider):
        x_values = self.shape.rib_x_values
        shape_ribs = self.shape.ribs
        arc_pos = list(self.arc.get_arc_positions(x_values))
        offset_x = shape_ribs[0][0][1]

        line = []
        chords = []

        for rib_no, x in enumerate(x_values):
            front, back = shape_ribs[rib_no]
            arc = arc_pos[rib_no]
            startpoint = np.array([-front[1] + offset_x, arc[0], arc[1]])

            line.append(startpoint)
            chords.append(abs(front[1] - back[1]))

        if self.shape.has_center_cell:
            line.insert(0, line[0] * [1, -1, 1])
            chords.insert(0, chords[0])

        for rib_no, p in enumerate(line):
            glider.ribs[rib_no].pos = p
            glider.ribs[rib_no].chord = chords[rib_no]

    def get_glider_3d(self, glider=None, num=50, num_profile=None):
        """returns a new glider from parametric values"""
        glider = glider or Glider()
        ribs = []

        self.rescale_curves()

        x_values = self.shape.rib_x_values
        shape_ribs = self.shape.ribs

        profile_merge_curve = self.profile_merge_curve.interpolation(num=num)
        ballooning_merge_curve = self.ballooning_merge_curve.interpolation(num=num)
        aoa_int = self.aoa.interpolation(num=num)
        zrot_int = self.zrot.interpolation(num=num)

        arc_pos = list(self.arc.get_arc_positions(x_values))
        rib_angles = self.arc.get_rib_angles(x_values)

        if self.num_profile is not None:
            num_profile = self.num_profile

        if num_profile is not None:
            profile_x_values = Distribution.from_cos_distribution(num_profile)
        else:
            profile_x_values = self.profiles[0].x_values

        rib_holes = self.elements.get("holes", [])
        rigids = self.elements.get("rigidfoils", [])

        cell_centers = [(p1 + p2) / 2 for p1, p2 in zip(x_values[:-1], x_values[1:])]
        offset_x = shape_ribs[0][0][1]

        rib_material = None
        if "rib_material" in self.elements:
            rib_material = self.elements["rib_material"]

        # Track previous chord for stabilo handling
        prev_chord = None
        last_rib_index = len(x_values) - 1
        
        print(f"[DEBUG] ===== get_glider_3d: {len(x_values)} ribs, last_rib_index={last_rib_index} =====")
        print(f"[DEBUG] last_profile_enabled={getattr(self, 'last_profile_enabled', False)}")
        print(f"[DEBUG] last_profile_type={getattr(self, 'last_profile_type', 'line')}")
        print(f"[DEBUG] last_profile_thickness={getattr(self, 'last_profile_thickness', 0.3)}")
        
        for rib_no, pos in enumerate(x_values):
            front, back = shape_ribs[rib_no]
            arc = arc_pos[rib_no]
            startpoint = np.array([-front[1] + offset_x, arc[0], arc[1]])

            chord = abs(front[1] - back[1])
            original_chord = chord
            
            # Debug for last few ribs
            if rib_no >= last_rib_index - 2:
                print(f"[DEBUG] Rib {rib_no}: front[1]={front[1]:.4f}, back[1]={back[1]:.4f}, chord={chord:.4f}, prev_chord={prev_chord}")
            
            # For last rib with last_profile_enabled: use previous rib's chord if current is 0
            # This ensures the thin/custom profile is visible instead of collapsed to a line
            if rib_no == last_rib_index and getattr(self, 'last_profile_enabled', False):
                print(f"[DEBUG] Processing LAST RIB: chord={chord}, prev_chord={prev_chord}")
                if chord < 0.01 and prev_chord is not None:  # Chord is essentially zero
                    chord = prev_chord * getattr(self, 'last_profile_thickness', 0.3)
                    print(f"[DEBUG] OVERRIDE: Using scaled chord for last rib: {chord}")
                elif chord >= 0.01:
                    print(f"[DEBUG] NOT OVERRIDING: chord ({chord}) >= 0.01")
                else:
                    print(f"[DEBUG] NOT OVERRIDING: prev_chord is None")
            
            factor = profile_merge_curve(abs(pos))
            profile = self.get_merge_profile(factor, pos_x=pos, rib_index=rib_no)
            profile.name = "Profile{}".format(rib_no)
            profile.x_values = profile_x_values
            
            # Debug profile thickness for last rib
            if rib_no == last_rib_index:
                print(f"[DEBUG] Last rib profile.thickness={profile.thickness}, final chord={chord}")
            
            prev_chord = chord if chord > 0.01 else prev_chord

            this_rib_holes = []
            this_rigid_foils = [
                RigidFoil(rigid["start"], rigid["end"], rigid["distance"])
                for rigid in rigids
                if rib_no in rigid["ribs"]
            ]

            ribs.append(
                Rib(
                    profile_2d=profile,
                    startpoint=startpoint,
                    chord=chord,
                    arcang=rib_angles[rib_no],
                    glide=self.glide,
                    aoa_absolute=aoa_int(pos),
                    zrot=zrot_int(pos),
                    holes=this_rib_holes,
                    rigidfoils=this_rigid_foils,
                    name="rib{}".format(rib_no),
                    material_code=rib_material,
                )
            )
            ribs[-1].aoa_relative = aoa_int(pos)

        if self.shape.has_center_cell:
            new_rib = ribs[0].copy()
            new_rib.name = "rib0"
            new_rib.mirror()
            new_rib.mirrored_rib = ribs[0]
            ribs.insert(0, new_rib)
            cell_centers.insert(0, 0.0)

        glider.cells = []
        for cell_no, (rib1, rib2) in enumerate(zip(ribs[:-1], ribs[1:])):
            ballooning_factor = ballooning_merge_curve(cell_centers[cell_no])
            ballooning = self.merge_ballooning(ballooning_factor)

            cell = Cell(rib1, rib2, ballooning, name="c{}".format(cell_no + 1))

            glider.cells.append(cell)

        # Only close the last rib (collapse to line) if NOT using custom last profile
        if not getattr(self, 'last_profile_enabled', False):
            glider.close_rib()
        else:
            print(f"[DEBUG] Skipping close_rib() because last_profile_enabled=True")

        # CELL-ELEMENTS
        self.get_panels(glider)
        self.apply_diagonals(glider)

        for minirib in self.elements.get("miniribs", []):
            data = minirib.copy()
            cells = data.pop("cells")
            count = data.pop("count", 1)
            base_y = data.get("yvalue", 0.5)
            
            # Generate y_values for multiple mini ribs
            if count > 1:
                # Distribute evenly across the cell span
                # For count=3: y_values = [0.25, 0.5, 0.75]
                y_values = [(i + 1) / (count + 1) for i in range(count)]
            else:
                y_values = [base_y]
            
            # Apply global minirib hole settings if enabled
            if getattr(self, 'minirib_holes', False):
                data['num_holes'] = getattr(self, 'minirib_num_holes', 1)
                data['hole_width'] = getattr(self, 'minirib_hole_width', 0.5)
                data['hole_height'] = getattr(self, 'minirib_hole_height', 0.7)
                data['hole_shape'] = getattr(self, 'minirib_hole_shape', 0)
                data['hole_corner_radius'] = getattr(self, 'minirib_hole_corner_radius', 0.25)
                data['hole_max_pos'] = getattr(self, 'minirib_hole_max_pos', 0.9)
            else:
                data['num_holes'] = 0  # Disable holes
            
            for cell_no in cells:
                for idx, y_val in enumerate(y_values):
                    mr_data = data.copy()
                    mr_data["yvalue"] = y_val
                    base_name = data.get('name', 'minirib')
                    if count > 1:
                        mr_data["name"] = f"{base_name}_{idx + 1}"
                    glider.cells[cell_no].miniribs.append(MiniRib(**mr_data))

        for rigidfoil in self.elements.get("cell_rigidfoils", []):
            data = rigidfoil.copy()
            for cell_no in data.pop("cells"):
                glider.cells[cell_no].rigidfoils.append(PanelRigidFoil(**data))

        # LE Panel Splits - create LeadingEdgeClosure for spanwise split
        for le_split in self.elements.get("le_panel_splits", []):
            cut_limit = le_split.get("cut_limit", 0.1)
            material = le_split.get("material_code", "")
            cells = le_split.get("cells", [])
            
            for cell_no in cells:
                if 0 <= cell_no < len(glider.cells):
                    # Initialize le_closures list if needed
                    if not hasattr(glider.cells[cell_no], 'le_closures'):
                        glider.cells[cell_no].le_closures = []
                    
                    closure = LeadingEdgeClosure(
                        cut_back_x=cut_limit,
                        y_position=0.5,  # Center split
                        material_code=material,
                        name=f"le_split_c{cell_no+1}"
                    )
                    glider.cells[cell_no].le_closures.append(closure)

        # RIB-ELEMENTS

        glider.rename_parts()

        glider.lineset = self.lineset.return_lineset(glider, self.v_inf)
        self.apply_holes(glider)
        self.apply_reinforcements(glider)
        self.apply_rod_sleeves(glider)
        glider.lineset.glider = glider

        glider.lineset.calculate_sag = False
        for _ in range(3):
            glider.lineset.recalc()
        glider.lineset.calculate_sag = True
        glider.lineset.recalc()

        return glider

    def apply_ballooning(self, glider3d):
        for ballooning in self.balloonings:
            ballooning.apply_splines()
        cell_centers = self.shape.cell_x_values
        ballooning_merge_curve = self.ballooning_merge_curve.interpolation(
            num=self.num_interpolate
        )
        for cell_no, cell in enumerate(glider3d.cells):
            ballooning_factor = ballooning_merge_curve(cell_centers[cell_no])
            ballooning = self.merge_ballooning(ballooning_factor)
            cell.ballooning = ballooning

        return glider3d

    @property
    def v_inf(self):
        angle = np.arctan(1 / self.glide)
        return np.array([np.cos(angle), 0, np.sin(angle)]) * self.speed

    def set_area(self, area):
        factor = math.sqrt(area / self.shape.area)
        self.shape.scale(factor)
        self.lineset.scale(factor, scale_lower_floor=False)
        self.rescale_curves()

    def set_aspect_ratio(self, aspect_ratio, remain_area=True):
        ar0 = self.shape.aspect_ratio
        area0 = self.shape.area

        self.shape.scale(y=ar0 / aspect_ratio)

        for p in self.lineset.get_lower_attachment_points():
            p.pos_2D[1] *= ar0 / aspect_ratio

        if remain_area:
            self.set_area(area0)

        return self.shape.aspect_ratio

    ##############################################################
    # is this used?
    def scale(self, x=1, y=1):
        self.shape.scale(x, y)
        if x != 1:
            self.rescale_curves()

    ##############################################################

    def rescale_curves(self):
        span = self.shape.span

        def rescale(curve):
            span_orig = curve.controlpoints[-1][0]
            factor = span / span_orig
            curve._data[:, 0] *= factor

        rescale(self.ballooning_merge_curve)
        rescale(self.profile_merge_curve)
        rescale(self.aoa)
        rescale(self.zrot)
        self.arc.rescale(self.shape.rib_x_values)

    def get_line_bbox(self):
        points = []
        for point in self.lineset.nodes:
            points.append(point.get_2D(self.shape))

        return [
            [min([p[0] for p in points]), min([p[1] for p in points])],
            [max([p[0] for p in points]), max([p[1] for p in points])],
        ]

    def export_lines2D_as_svg(self, file_name=None):
        # sollte im lineset2D sein, aber des lineset hat keine moeglichkeit auf diese Klasse
        # zuzugreifen...
        border = 0.1
        bbox = self.get_line_bbox()
        width = bbox[1][0] - bbox[0][0]
        height = bbox[1][1] - bbox[0][1]

        import svgwrite
        import svgwrite.container

        drawing = svgwrite.Drawing(size=[800, 800 * height / width])

        drawing.viewbox(
            bbox[0][0] - border * width,
            -bbox[1][1] - border * height,
            width * (1 + 2 * border),
            height * (1 + 2 * border),
        )
        lines = svgwrite.container.Group()
        lines.scale(1, -1)
        for line in self.lineset.lines:
            p1 = line.lower_node.get_2D(self.shape)
            p2 = line.upper_node.get_2D(self.shape)
            drawing_line = drawing.polyline(
                [p1, p2],
                style="stroke:black; vector-effect: fill: none; stroke-width:0.01px",
            )
            lines.add(drawing_line)
        drawing.add(lines)

        ribs = svgwrite.container.Group()

        ribs.scale(1, -1)
        p1_old, p2_old = None, None
        for rib in self.shape.ribs:
            p1 = rib[0]
            p2 = rib[1]
            ribs.add(
                drawing.polyline(
                    [p1, p2],
                    style="stroke:black; vector-effect: fill: none; stroke-width:0.01px",
                )
            )
            if p1_old and p2_old:
                ribs.add(
                    drawing.polyline(
                        [p1_old, p1],
                        style="stroke:black; vector-effect: fill: none; stroke-width:0.01px",
                    )
                )
                ribs.add(
                    drawing.polyline(
                        [p2_old, p2],
                        style="stroke:black; vector-effect: fill: none; stroke-width:0.01px",
                    )
                )
            p1_old, p2_old = p1, p2

        drawing.add(ribs)
        if file_name:
            drawing.saveas(file_name)
        return drawing.tostring()
