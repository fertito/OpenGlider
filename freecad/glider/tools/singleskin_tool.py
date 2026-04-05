from __future__ import division

import copy
import numpy as np
from pivy import coin
from PySide import QtGui, QtCore

from openglider.glider.rib.rib import SingleSkinRib
from openglider.glider.rib import RibHole

from .glider import draw_glider, draw_lines
from .tools import BaseTool, input_field, text_field


def refresh():
    pass


class SingleSkinTool(BaseTool):
    hide = True
    turn = False
    widget_name = "Single Skin"

    # Style pour les headers de section
    HEADER_STYLE = "font-weight: bold; font-size: 12px; margin-top: 8px; color: #cccccc;"
    # Style pour champs lecture seule (standard V3)
    READONLY_STYLE = "background-color: #1a3a5c; color: #ffffff; border: 1px solid #2a5a8c;"

    def __init__(self, obj):
        super(SingleSkinTool, self).__init__(obj)

        # Infos glider
        glider = self.parametric_glider.get_glider_3d()
        self.num_cells = self.parametric_glider.shape.half_cell_num
        self.num_ribs = len(glider.ribs)

        # Charger la config existante
        self._load_existing_config()

        # Construire l'UI
        self._build_ui()

        # Prévisualisation initiale
        self.draw_glider()

    # ── Config ────────────────────────────────────────────────────

    def _load_existing_config(self):
        """Charger la config SS existante ou initialiser les défauts."""
        pg = self.parametric_glider
        ss = getattr(pg, 'single_skin_config', None) or {}

        # height: liste (une valeur par bow, répétée si plus court)
        raw_height = ss.get("height", [0.5])
        if isinstance(raw_height, (int, float)):
            raw_height = [float(raw_height)]
        self._height_list = list(raw_height)

        # te_end: liste par nervure (une valeur par rib)
        raw_te_end = ss.get("te_end", [1.0] * self.num_ribs)
        if isinstance(raw_te_end, (int, float)):
            raw_te_end = [float(raw_te_end)] * self.num_ribs
        self._te_end_list = list(raw_te_end)

        # xrot: liste par nervure (degrés)
        raw_xrot = ss.get("xrot", [0.0] * self.num_ribs)
        if isinstance(raw_xrot, (int, float)):
            raw_xrot = [float(raw_xrot)] * self.num_ribs
        # Convertir radians → degrés si nécessaire (V1 stocke en radians)
        if raw_xrot and max(abs(x) for x in raw_xrot) < 0.5:
            raw_xrot = [np.degrees(x) for x in raw_xrot]
        self._xrot_list = list(raw_xrot)

        self.config = {
            "cells": ss.get("cells", []),
            "att_dist": ss.get("att_dist", 0.02),
            "num_points": ss.get("num_points", 20),
            "le_gap": ss.get("le_gap", True),
            "te_gap": ss.get("te_gap", True),
            "double_first": ss.get("double_first", False),
            "straight_te": ss.get("straight_te", True),
            "camber": ss.get("camber", 0.1),
            "holes": ss.get("holes", False),
            "hole_width": ss.get("hole_width", 0.3),
            "hole_height": ss.get("hole_height", 0.7),
            "min_hole_pos": ss.get("min_hole_pos", 0.2),
            "max_hole_pos": ss.get("max_hole_pos", 1.0),
            "vertical_shift": ss.get("vertical_shift", 0.2),
            "continued_min": ss.get("continued_min", False),
            "continued_min_end": ss.get("continued_min_end", 0.9),
            "continued_min_angle": ss.get("continued_min_angle", 0.0),
            "continued_min_delta_y": ss.get("continued_min_delta_y", 0.0),
            "continued_min_x": ss.get("continued_min_x", 0.0),
        }

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        """Construire l'interface Qt complète."""
        row = 0

        # ── Section: Cell Selection ──────────────────────────────
        header_cells = QtGui.QLabel("Cell Selection")
        header_cells.setStyleSheet(self.HEADER_STYLE)
        self.layout.setWidget(row, text_field, header_cells)
        row += 1

        # Boutons rapides All / None / Tips
        btn_layout = QtGui.QHBoxLayout()
        self.btn_all = QtGui.QPushButton("All")
        self.btn_none = QtGui.QPushButton("None")
        self.btn_tips = QtGui.QPushButton("Tips")
        self.tip_count_spin = QtGui.QSpinBox()
        self.tip_count_spin.setRange(1, self.num_cells)
        self.tip_count_spin.setValue(min(3, self.num_cells))
        self.tip_count_spin.setPrefix("last ")
        self.tip_count_spin.setSuffix(" cells")

        self.btn_all.clicked.connect(self._select_all_cells)
        self.btn_none.clicked.connect(self._select_no_cells)
        self.btn_tips.clicked.connect(self._select_tip_cells)

        btn_layout.addWidget(self.btn_all)
        btn_layout.addWidget(self.btn_none)
        btn_layout.addWidget(self.btn_tips)
        btn_layout.addWidget(self.tip_count_spin)
        btn_widget = QtGui.QWidget()
        btn_widget.setLayout(btn_layout)
        self.layout.setWidget(row, input_field, btn_widget)
        row += 1

        # Grille de cases à cocher par cellule
        self.cell_checks = []
        cell_grid = QtGui.QGridLayout()
        cols = min(6, self.num_cells)
        for i in range(self.num_cells):
            cb = QtGui.QCheckBox("C{}".format(i + 1))
            cb.setChecked(i in self.config["cells"])
            cb.stateChanged.connect(self._on_cells_changed)
            self.cell_checks.append(cb)
            cell_grid.addWidget(cb, i // cols, i % cols)
        cell_grid_widget = QtGui.QWidget()
        cell_grid_widget.setLayout(cell_grid)
        self.layout.setWidget(row, input_field, cell_grid_widget)
        row += 1

        # ── Section: Leading Edge ─────────────────────────────────
        header_le = QtGui.QLabel("Leading Edge")
        header_le.setStyleSheet(self.HEADER_STYLE)
        self.layout.setWidget(row, text_field, header_le)
        row += 1

        self.double_first_cb = QtGui.QCheckBox("Keep first panel double-surface (A-B)")
        self.double_first_cb.setChecked(self.config["double_first"])
        self.layout.setWidget(row, input_field, self.double_first_cb)
        row += 1

        self.le_gap_cb = QtGui.QCheckBox("Gap at leading edge")
        self.le_gap_cb.setChecked(self.config["le_gap"])
        self.layout.setWidget(row, input_field, self.le_gap_cb)
        row += 1

        # ── Section: Bow Shape ────────────────────────────────────
        header_bow = QtGui.QLabel("Bow Shape")
        header_bow.setStyleSheet(self.HEADER_STYLE)
        self.layout.setWidget(row, text_field, header_bow)
        row += 1

        # Table height (une valeur par bow)
        self.layout.setWidget(row, text_field, QtGui.QLabel("Height per bow:"))
        self.height_table = QtGui.QTableWidget()
        self.height_table.setColumnCount(2)
        self.height_table.setHorizontalHeaderLabels(["Bow #", "Height (0-1)"])
        self.height_table.horizontalHeader().setStretchLastSection(True)
        self.height_table.setColumnWidth(0, 50)
        self.height_table.setMaximumHeight(120)
        self._populate_height_table()
        self.layout.setWidget(row, input_field, self.height_table)
        row += 1

        # Boutons +/- pour ajouter/supprimer des bows
        bow_btn_layout = QtGui.QHBoxLayout()
        self.btn_add_bow = QtGui.QPushButton("+ Bow")
        self.btn_remove_bow = QtGui.QPushButton("- Bow")
        self.btn_add_bow.clicked.connect(self._add_bow)
        self.btn_remove_bow.clicked.connect(self._remove_bow)
        bow_btn_layout.addWidget(self.btn_add_bow)
        bow_btn_layout.addWidget(self.btn_remove_bow)
        bow_btn_widget = QtGui.QWidget()
        bow_btn_widget.setLayout(bow_btn_layout)
        self.layout.setWidget(row, input_field, bow_btn_widget)
        row += 1

        # att_dist
        self.layout.setWidget(row, text_field, QtGui.QLabel("Attachment gap (m):"))
        self.att_dist_spin = QtGui.QDoubleSpinBox()
        self.att_dist_spin.setRange(0.0, 0.5)
        self.att_dist_spin.setDecimals(3)
        self.att_dist_spin.setSingleStep(0.005)
        self.att_dist_spin.setValue(self.config["att_dist"])
        self.layout.setWidget(row, input_field, self.att_dist_spin)
        row += 1

        # num_points
        self.layout.setWidget(row, text_field, QtGui.QLabel("Points per bow:"))
        self.num_points_spin = QtGui.QSpinBox()
        self.num_points_spin.setRange(5, 50)
        self.num_points_spin.setValue(self.config["num_points"])
        self.layout.setWidget(row, input_field, self.num_points_spin)
        row += 1

        # ── Section: Trailing Edge ────────────────────────────────
        header_te = QtGui.QLabel("Trailing Edge")
        header_te.setStyleSheet(self.HEADER_STYLE)
        self.layout.setWidget(row, text_field, header_te)
        row += 1

        self.te_gap_cb = QtGui.QCheckBox("Gap at trailing edge")
        self.te_gap_cb.setChecked(self.config["te_gap"])
        self.layout.setWidget(row, input_field, self.te_gap_cb)
        row += 1

        self.straight_te_cb = QtGui.QCheckBox("Straight last bow")
        self.straight_te_cb.setChecked(self.config["straight_te"])
        self.layout.setWidget(row, input_field, self.straight_te_cb)
        row += 1

        # camber
        self.layout.setWidget(row, text_field, QtGui.QLabel("Closure camber:"))
        self.camber_spin = QtGui.QDoubleSpinBox()
        self.camber_spin.setRange(-1.0, 1.0)
        self.camber_spin.setDecimals(3)
        self.camber_spin.setSingleStep(0.01)
        self.camber_spin.setValue(self.config["camber"])
        self.camber_spin.setToolTip("Courbure de la ligne de fermeture SS (0=droit, >0=bombé vers l'extérieur)")
        self.layout.setWidget(row, input_field, self.camber_spin)
        row += 1

        # Table te_end (une valeur par nervure SS)
        self.layout.setWidget(row, text_field, QtGui.QLabel("TE end per rib:"))
        self.te_end_table = QtGui.QTableWidget()
        self.te_end_table.setColumnCount(3)
        self.te_end_table.setHorizontalHeaderLabels(["Rib", "SS?", "te_end"])
        self.te_end_table.horizontalHeader().setStretchLastSection(True)
        self.te_end_table.setColumnWidth(0, 50)
        self.te_end_table.setColumnWidth(1, 40)
        self.te_end_table.setMaximumHeight(150)
        self.te_end_table.setToolTip("Coupure extrados (1.0=TE, 0.7=70% corde)")
        self._populate_te_end_table()
        self.layout.setWidget(row, input_field, self.te_end_table)
        row += 1

        # ── Section: Xrot ─────────────────────────────────────────
        header_xrot = QtGui.QLabel("Rib Rotation (Xrot)")
        header_xrot.setStyleSheet(self.HEADER_STYLE)
        self.layout.setWidget(row, text_field, header_xrot)
        row += 1

        self.xrot_table = QtGui.QTableWidget()
        self.xrot_table.setColumnCount(3)
        self.xrot_table.setHorizontalHeaderLabels(["Rib", "SS?", "Xrot (°)"])
        self.xrot_table.horizontalHeader().setStretchLastSection(True)
        self.xrot_table.setColumnWidth(0, 50)
        self.xrot_table.setColumnWidth(1, 40)
        self.xrot_table.setMaximumHeight(150)
        self.xrot_table.setToolTip("Angle de rotation de la nervure autour de l'axe de corde")
        self._populate_xrot_table()
        self.layout.setWidget(row, input_field, self.xrot_table)
        row += 1

        # ── Section: Holes ────────────────────────────────────────
        header_holes = QtGui.QLabel("Holes")
        header_holes.setStyleSheet(self.HEADER_STYLE)
        self.layout.setWidget(row, text_field, header_holes)
        row += 1

        self.holes_cb = QtGui.QCheckBox("Enable rib holes")
        self.holes_cb.setChecked(self.config["holes"])
        self.holes_cb.stateChanged.connect(self._on_holes_toggled)
        self.layout.setWidget(row, input_field, self.holes_cb)
        row += 1

        self.holes_widget = QtGui.QWidget()
        holes_layout = QtGui.QFormLayout(self.holes_widget)

        self.hole_width_spin = QtGui.QDoubleSpinBox()
        self.hole_width_spin.setRange(0.05, 1.0)
        self.hole_width_spin.setDecimals(2)
        self.hole_width_spin.setValue(self.config["hole_width"])
        holes_layout.addRow("Width:", self.hole_width_spin)

        self.hole_height_spin = QtGui.QDoubleSpinBox()
        self.hole_height_spin.setRange(0.1, 1.0)
        self.hole_height_spin.setDecimals(2)
        self.hole_height_spin.setValue(self.config["hole_height"])
        holes_layout.addRow("Height:", self.hole_height_spin)

        self.min_hole_pos_spin = QtGui.QDoubleSpinBox()
        self.min_hole_pos_spin.setRange(0.0, 1.0)
        self.min_hole_pos_spin.setDecimals(2)
        self.min_hole_pos_spin.setValue(self.config["min_hole_pos"])
        holes_layout.addRow("Min chord pos:", self.min_hole_pos_spin)

        self.max_hole_pos_spin = QtGui.QDoubleSpinBox()
        self.max_hole_pos_spin.setRange(0.0, 1.0)
        self.max_hole_pos_spin.setDecimals(2)
        self.max_hole_pos_spin.setValue(self.config["max_hole_pos"])
        holes_layout.addRow("Max chord pos:", self.max_hole_pos_spin)

        self.vert_shift_spin = QtGui.QDoubleSpinBox()
        self.vert_shift_spin.setRange(-0.5, 0.5)
        self.vert_shift_spin.setDecimals(2)
        self.vert_shift_spin.setValue(self.config["vertical_shift"])
        holes_layout.addRow("Vertical shift:", self.vert_shift_spin)

        self.holes_widget.setVisible(self.config["holes"])
        self.layout.setWidget(row, input_field, self.holes_widget)
        row += 1

        # ── Section: Advanced ─────────────────────────────────────
        self.advanced_toggle = QtGui.QPushButton("▶ Advanced (continued_min)")
        self.advanced_toggle.setFlat(True)
        self.advanced_toggle.setStyleSheet("text-align: left; color: #888; font-size: 11px; margin-top: 8px;")
        self.advanced_toggle.clicked.connect(self._toggle_advanced)
        self.layout.setWidget(row, input_field, self.advanced_toggle)
        row += 1

        self.advanced_widget = QtGui.QWidget()
        adv_layout = QtGui.QFormLayout(self.advanced_widget)

        self.continued_min_cb = QtGui.QCheckBox("Enable continued_min")
        self.continued_min_cb.setChecked(self.config["continued_min"])
        adv_layout.addRow(self.continued_min_cb)

        self.cont_min_end_spin = QtGui.QDoubleSpinBox()
        self.cont_min_end_spin.setRange(0.0, 1.0)
        self.cont_min_end_spin.setDecimals(2)
        self.cont_min_end_spin.setValue(self.config["continued_min_end"])
        adv_layout.addRow("End position:", self.cont_min_end_spin)

        self.cont_min_angle_spin = QtGui.QDoubleSpinBox()
        self.cont_min_angle_spin.setRange(-1.0, 1.0)
        self.cont_min_angle_spin.setDecimals(3)
        self.cont_min_angle_spin.setValue(self.config["continued_min_angle"])
        adv_layout.addRow("Angle:", self.cont_min_angle_spin)

        self.advanced_widget.setVisible(False)
        self.layout.setWidget(row, input_field, self.advanced_widget)
        row += 1

        # ── Update Preview ────────────────────────────────────────
        self.update_button = QtGui.QPushButton("Update Preview")
        self.update_button.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.update_button.clicked.connect(self.update_preview)
        self.layout.setWidget(row, input_field, self.update_button)
        row += 1

    # ── Tables ────────────────────────────────────────────────────

    def _populate_height_table(self):
        """Remplir la table height avec les valeurs actuelles."""
        self.height_table.blockSignals(True)
        self.height_table.setRowCount(len(self._height_list))
        for i, val in enumerate(self._height_list):
            # Colonne 0: numéro bow (lecture seule, bleu)
            num_item = QtGui.QTableWidgetItem("B{}".format(i + 1))
            num_item.setFlags(num_item.flags() & ~QtCore.Qt.ItemIsEditable)
            num_item.setBackground(QtGui.QColor(26, 58, 92))
            num_item.setForeground(QtGui.QColor(255, 255, 255))
            num_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.height_table.setItem(i, 0, num_item)
            # Colonne 1: valeur éditable
            val_spin = QtGui.QDoubleSpinBox()
            val_spin.setRange(0.0, 1.0)
            val_spin.setDecimals(3)
            val_spin.setSingleStep(0.01)
            val_spin.setValue(val)
            self.height_table.setCellWidget(i, 1, val_spin)
        self.height_table.blockSignals(False)

    def _populate_te_end_table(self):
        """Remplir la table te_end — toutes les nervures, SS éditables."""
        self.te_end_table.blockSignals(True)
        selected_cells = self._get_selected_cells()
        rib_indices, _ = self._get_rib_indices_from_cells(selected_cells)
        ss_set = set(rib_indices)

        self.te_end_table.setRowCount(self.num_ribs)
        for i in range(self.num_ribs):
            is_ss = i in ss_set
            # Col 0: rib name (lecture seule, bleu)
            name_item = QtGui.QTableWidgetItem("R{}".format(i + 1))
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            name_item.setBackground(QtGui.QColor(26, 58, 92))
            name_item.setForeground(QtGui.QColor(255, 255, 255))
            name_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.te_end_table.setItem(i, 0, name_item)
            # Col 1: SS? (lecture seule)
            ss_item = QtGui.QTableWidgetItem("SS" if is_ss else "-")
            ss_item.setFlags(ss_item.flags() & ~QtCore.Qt.ItemIsEditable)
            ss_item.setTextAlignment(QtCore.Qt.AlignCenter)
            if is_ss:
                ss_item.setBackground(QtGui.QColor(26, 58, 92))
                ss_item.setForeground(QtGui.QColor(255, 255, 255))
            else:
                ss_item.setBackground(QtGui.QColor(50, 50, 50))
                ss_item.setForeground(QtGui.QColor(120, 120, 120))
            self.te_end_table.setItem(i, 1, ss_item)
            # Col 2: valeur te_end
            val = self._te_end_list[i] if i < len(self._te_end_list) else 1.0
            val_spin = QtGui.QDoubleSpinBox()
            val_spin.setRange(0.1, 1.0)
            val_spin.setDecimals(3)
            val_spin.setSingleStep(0.01)
            val_spin.setValue(val)
            val_spin.setEnabled(is_ss)
            if not is_ss:
                val_spin.setStyleSheet(self.READONLY_STYLE)
            self.te_end_table.setCellWidget(i, 2, val_spin)
        self.te_end_table.blockSignals(False)

    def _populate_xrot_table(self):
        """Remplir la table xrot — toutes les nervures, SS éditables."""
        self.xrot_table.blockSignals(True)
        selected_cells = self._get_selected_cells()
        rib_indices, _ = self._get_rib_indices_from_cells(selected_cells)
        ss_set = set(rib_indices)

        self.xrot_table.setRowCount(self.num_ribs)
        for i in range(self.num_ribs):
            is_ss = i in ss_set
            # Col 0: rib name
            name_item = QtGui.QTableWidgetItem("R{}".format(i + 1))
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            name_item.setBackground(QtGui.QColor(26, 58, 92))
            name_item.setForeground(QtGui.QColor(255, 255, 255))
            name_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.xrot_table.setItem(i, 0, name_item)
            # Col 1: SS?
            ss_item = QtGui.QTableWidgetItem("SS" if is_ss else "-")
            ss_item.setFlags(ss_item.flags() & ~QtCore.Qt.ItemIsEditable)
            ss_item.setTextAlignment(QtCore.Qt.AlignCenter)
            if is_ss:
                ss_item.setBackground(QtGui.QColor(26, 58, 92))
                ss_item.setForeground(QtGui.QColor(255, 255, 255))
            else:
                ss_item.setBackground(QtGui.QColor(50, 50, 50))
                ss_item.setForeground(QtGui.QColor(120, 120, 120))
            self.xrot_table.setItem(i, 1, ss_item)
            # Col 2: angle xrot en degrés
            val = self._xrot_list[i] if i < len(self._xrot_list) else 0.0
            val_spin = QtGui.QDoubleSpinBox()
            val_spin.setRange(-45.0, 45.0)
            val_spin.setDecimals(2)
            val_spin.setSingleStep(0.5)
            val_spin.setSuffix(" °")
            val_spin.setValue(val)
            val_spin.setEnabled(is_ss)
            if not is_ss:
                val_spin.setStyleSheet(self.READONLY_STYLE)
            self.xrot_table.setCellWidget(i, 2, val_spin)
        self.xrot_table.blockSignals(False)

    def _read_height_table(self):
        """Lire les valeurs de la table height."""
        result = []
        for i in range(self.height_table.rowCount()):
            w = self.height_table.cellWidget(i, 1)
            if w:
                result.append(w.value())
        return result if result else [0.5]

    def _read_te_end_table(self):
        """Lire les valeurs de la table te_end."""
        result = []
        for i in range(self.te_end_table.rowCount()):
            w = self.te_end_table.cellWidget(i, 2)
            result.append(w.value() if w else 1.0)
        return result

    def _read_xrot_table(self):
        """Lire les valeurs de la table xrot (degrés → radians)."""
        result = []
        for i in range(self.xrot_table.rowCount()):
            w = self.xrot_table.cellWidget(i, 2)
            val_deg = w.value() if w else 0.0
            result.append(np.radians(val_deg))
        return result

    # ── Callbacks UI ──────────────────────────────────────────────

    def _on_cells_changed(self, *args):
        """Quand la sélection de cellules change, mettre à jour les tables SS."""
        # Sauvegarder les valeurs actuelles avant de régénérer
        self._te_end_list = self._read_te_end_table()
        xrot_rad = self._read_xrot_table()
        self._xrot_list = [np.degrees(x) for x in xrot_rad]
        # Régénérer les tables
        self._populate_te_end_table()
        self._populate_xrot_table()

    def _on_holes_toggled(self, state):
        self.holes_widget.setVisible(bool(state))

    def _toggle_advanced(self):
        visible = not self.advanced_widget.isVisible()
        self.advanced_widget.setVisible(visible)
        self.advanced_toggle.setText(
            "▼ Advanced (continued_min)" if visible else "▶ Advanced (continued_min)"
        )

    def _select_all_cells(self):
        for cb in self.cell_checks:
            cb.setChecked(True)

    def _select_no_cells(self):
        for cb in self.cell_checks:
            cb.setChecked(False)

    def _select_tip_cells(self):
        n = self.tip_count_spin.value()
        for i, cb in enumerate(self.cell_checks):
            cb.setChecked(i >= self.num_cells - n)

    def _add_bow(self):
        """Ajouter un bow avec la valeur du dernier bow."""
        vals = self._read_height_table()
        last_val = vals[-1] if vals else 0.5
        self._height_list = vals + [last_val]
        self._populate_height_table()

    def _remove_bow(self):
        """Supprimer le dernier bow (minimum 1)."""
        vals = self._read_height_table()
        if len(vals) > 1:
            self._height_list = vals[:-1]
            self._populate_height_table()

    # ── Config gathering ──────────────────────────────────────────

    def _get_selected_cells(self):
        return [i for i, cb in enumerate(self.cell_checks) if cb.isChecked()]

    def _get_rib_indices_from_cells(self, cells):
        """Convertir les indices de cellules en indices de nervures SS et scellées."""
        cells_set = set(cells)
        total_ribs = self.num_ribs
        total_cells = self.num_cells
        ribs = []
        sealed_ribs = set()
        boundary_full_cells = set()
        for rib_idx in range(total_ribs):
            adjacent_cells = []
            if rib_idx > 0:
                adjacent_cells.append(rib_idx - 1)
            if rib_idx < total_cells:
                adjacent_cells.append(rib_idx)
            ss_adjacent = [c for c in adjacent_cells if c in cells_set]
            non_ss_adjacent = [c for c in adjacent_cells if c not in cells_set]
            if ss_adjacent and not non_ss_adjacent:
                ribs.append(rib_idx)
            elif ss_adjacent and non_ss_adjacent:
                sealed_ribs.add(rib_idx)
                for c in non_ss_adjacent:
                    boundary_full_cells.add(c)
        for cell_idx in boundary_full_cells:
            sealed_ribs.add(cell_idx)
            sealed_ribs.add(cell_idx + 1)
        return ribs, sealed_ribs

    def _get_single_skin_par(self):
        """Collecter tous les paramètres SS depuis l'UI."""
        height_list = self._read_height_table()
        return {
            "height": height_list,
            "att_dist": self.att_dist_spin.value(),
            "num_points": self.num_points_spin.value(),
            "le_gap": self.le_gap_cb.isChecked(),
            "te_gap": self.te_gap_cb.isChecked(),
            "double_first": self.double_first_cb.isChecked(),
            "straight_te": self.straight_te_cb.isChecked(),
            "camber": self.camber_spin.value(),
            "continued_min": self.continued_min_cb.isChecked(),
            "continued_min_end": self.cont_min_end_spin.value(),
            "continued_min_angle": self.cont_min_angle_spin.value(),
            "continued_min_delta_y": 0.0,
            "continued_min_x": 0.0,
        }

    def _get_full_config(self):
        """Retourner la config complète pour persistance."""
        config = self._get_single_skin_par()
        config["cells"] = self._get_selected_cells()
        config["te_end"] = self._read_te_end_table()
        config["xrot"] = self._read_xrot_table()  # stocké en radians
        config["holes"] = self.holes_cb.isChecked()
        config["hole_width"] = self.hole_width_spin.value()
        config["hole_height"] = self.hole_height_spin.value()
        config["min_hole_pos"] = self.min_hole_pos_spin.value()
        config["max_hole_pos"] = self.max_hole_pos_spin.value()
        config["vertical_shift"] = self.vert_shift_spin.value()
        return config

    # ── Apply SingleSkin ──────────────────────────────────────────

    def _apply_singleskin(self, glider):
        """Appliquer les modifications SingleSkin sur une instance glider."""
        selected_cells = self._get_selected_cells()
        if not selected_cells:
            return glider

        cells_set = set(selected_cells)
        rib_indices, sealed_rib_indices = self._get_rib_indices_from_cells(selected_cells)
        rib_indices_set = set(rib_indices)
        single_skin_par = self._get_single_skin_par()

        # te_end par nervure
        te_end_list = self._read_te_end_table()

        # Remplacer les nervures par SingleSkinRib
        new_ribs = []
        for i, rib in enumerate(glider.ribs):
            if i in rib_indices_set:
                par = dict(single_skin_par)
                par["te_end"] = te_end_list[i] if i < len(te_end_list) else 1.0
                if not isinstance(rib, SingleSkinRib):
                    new_ribs.append(SingleSkinRib.from_rib(rib, par))
                else:
                    rib.single_skin_par = par
                    new_ribs.append(rib)
            else:
                new_ribs.append(rib)

        # Gérer les nervures miroir
        for rib, ss_rib in zip(glider.ribs, new_ribs):
            if hasattr(rib, "mirrored_rib") and rib.mirrored_rib:
                nr = glider.ribs.index(rib.mirrored_rib)
                ss_rib.mirrored_rib = new_ribs[nr]

        glider.replace_ribs(new_ribs)

        # Vider les trous sur les nervures SS et scellées
        for i, rib in enumerate(glider.ribs):
            if isinstance(rib, SingleSkinRib):
                rib.holes = []
            elif i in sealed_rib_indices:
                rib.holes = []

        # Ajouter les trous SS si activés
        if self.holes_cb.isChecked():
            hole_size = np.array([self.hole_width_spin.value(),
                                  self.hole_height_spin.value()])
            min_pos = self.min_hole_pos_spin.value()
            max_pos = self.max_hole_pos_spin.value()
            v_shift = self.vert_shift_spin.value()
            for att_pnt in glider.lineset.attachment_points:
                if (isinstance(att_pnt.rib, SingleSkinRib)
                        and att_pnt.rib_pos > min_pos
                        and att_pnt.rib_pos < max_pos):
                    att_pnt.rib.holes.append(
                        RibHole(att_pnt.rib_pos, size=hole_size, vertical_shift=v_shift)
                    )

        # Appliquer hull modification
        for rib in glider.ribs:
            if isinstance(rib, SingleSkinRib):
                hull_profile = rib.get_hull(glider)
                rib.profile_2d = hull_profile

        # Retirer les panneaux intrados des cellules SS
        double_first = self.double_first_cb.isChecked()
        for cell_idx, cell in enumerate(glider.cells):
            if cell_idx in cells_set:
                if double_first:
                    extrados = [p for p in cell.panels if not p.is_lower()]
                    intrados = [p for p in cell.panels if p.is_lower()]
                    intrados.sort(key=lambda p: p.mean_x())
                    cell.panels = extrados + intrados[:1]
                else:
                    cell.panels = [p for p in cell.panels if not p.is_lower()]

        # Appliquer xrot manuels
        xrot_list = self._read_xrot_table()
        for i, rib in enumerate(glider.ribs):
            if i < len(xrot_list):
                rib.xrot = xrot_list[i]

        return glider

    # ── Preview / Drawing ─────────────────────────────────────────

    def draw_glider(self):
        """Dessiner le glider avec les paramètres SS actuels."""
        _rot = coin.SbRotation()
        _rot.setValue(coin.SbVec3f(0, 1, 0), coin.SbVec3f(1, 0, 0))
        rot = coin.SoRotation()
        rot.rotation.setValue(_rot)
        self.task_separator += rot

        glider = self.parametric_glider.get_glider_3d()
        glider = self._apply_singleskin(glider)

        draw_glider(
            glider,
            self.task_separator,
            hull="panels",
            ribs=True,
            fill_ribs=False,
        )
        draw_lines(
            glider,
            vis_lines=self.task_separator,
            line_num=1,
        )

    def update_preview(self):
        """Reconstruire la prévisualisation 3D."""
        self.task_separator.removeAllChildren()
        self.draw_glider()

    # ── Accept / Reject ───────────────────────────────────────────

    def accept(self):
        """Sauvegarder la config et mettre à jour le glider."""
        full_config = self._get_full_config()
        # Persister dans le ParametricGlider réel (pas la deepcopy)
        pg_real = self.obj.Proxy.getParametricGlider()
        pg_real.single_skin_config = full_config
        # Aussi dans la copie locale pour cohérence
        self.parametric_glider.single_skin_config = full_config
        super(SingleSkinTool, self).accept()
        self.update_view_glider()

    def reject(self):
        """Annuler les modifications."""
        super(SingleSkinTool, self).reject()
