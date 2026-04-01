# -*- coding: utf-8 -*-
"""
Pattern Configuration Dialog for Unwrap Glider tool.
Allows users to modify PatternConfig parameters before export.
"""

from PySide import QtGui, QtCore
import tempfile, os


# Parameter definitions: (attribute_name, default_value, description, value_type, unit)
# unit: 'mm' for millimeters (stored as meters internally), None for no unit
# IMPORTANT: Defaults match OtherPatternConfig (used by PlotMaker.DefaultConfig)
PATTERN_PARAMETERS = [
    # Section: General
    ("complete_glider", False, "Exporter le planeur complet. ATTENTION: True peut causer des erreurs", bool, None),
    ("debug", False, "Mode debug - affiche des lignes de construction supplémentaires", bool, None),
    ("profile_numpoints", 250, "Nombre de points pour discrétiser le profil", int, None),
    
    # Section: Layout
    ("patterns_scale", 1000, "Échelle de sortie (1000 = mètres vers millimètres)", float, None),
    ("patterns_align_dist_x", 100, "Espacement horizontal entre les pièces", float, "mm"),
    ("patterns_align_dist_y", 100, "Espacement vertical entre les pièces", float, "mm"),
    ("layout_seperate_panels", True, "Séparer les panneaux extrados/intrados", bool, None),
    
    # Section: Seam Allowances (displayed in mm, stored in meters)
    ("allowance_general", 10, "Marge de couture générale", float, "mm"),
    ("allowance_trailing_edge", 10, "Marge bord de fuite", float, "mm"),
    ("allowance_entry_open", 21, "Marge entrée d'air ouverte", float, "mm"),
    ("allowance_design", 10, "Marge coupes design", float, "mm"),
    ("allowance_diagonals", 10, "Marge diagonales", float, "mm"),
    ("allowance_parallel", 10, "Marge coupes parallèles", float, "mm"),
    ("allowance_orthogonal", 10, "Marge coupes orthogonales", float, "mm"),
    
    # Section: Diagonals and Straps
    ("drib_allowance_folds", 10, "Marge pour plis des diagonales", float, "mm"),
    ("drib_num_folds", 1, "Nombre de plis pour les diagonales", int, None),
    ("strap_num_folds", 1, "Nombre de plis pour les straps", int, None),
    
    # Section: Labels and Marks
    ("insert_attachment_point_text", True, "Afficher le nom des points d'attache", bool, None),
    ("midribs", 50, "Nombre de nervures intermédiaires pour le ballooning", int, None),
]


class PatternConfigDialog(QtGui.QDialog):
    """Dialog for configuring pattern export parameters."""
    
    def __init__(self, parent=None, config=None, glider_obj=None):
        super(PatternConfigDialog, self).__init__(parent)
        self.setWindowTitle("Configuration Export Patterns")
        self.setMinimumSize(750, 550)
        
        # Store config for loading values
        self.input_config = config or {}
        self.glider_obj = glider_obj  # Pour la prévisualisation
        
        self._setup_ui()
        self._load_values()
    
    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QtGui.QVBoxLayout(self)
        
        # Description label
        desc_label = QtGui.QLabel(
            "Modifiez les paramètres ci-dessous avant l'export. "
            "Les longueurs sont en millimètres."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Create table
        self.table = QtGui.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Paramètre", "Valeur", "Unité", "Description"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 40)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        # Populate table
        self.table.setRowCount(len(PATTERN_PARAMETERS))
        self.widgets = {}  # Store widgets for value retrieval
        
        for row, (name, default, desc, vtype, unit) in enumerate(PATTERN_PARAMETERS):
            # Parameter name
            name_item = QtGui.QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            
            # Value widget - depends on type
            if vtype == bool:
                widget = QtGui.QCheckBox()
                widget.setChecked(default)
                self.table.setCellWidget(row, 1, widget)
            elif vtype == int:
                widget = QtGui.QSpinBox()
                widget.setRange(0, 10000)
                widget.setValue(default)
                self.table.setCellWidget(row, 1, widget)
            elif vtype == float:
                widget = QtGui.QDoubleSpinBox()
                widget.setRange(0, 10000)
                widget.setDecimals(1)
                widget.setSingleStep(1)
                widget.setValue(default)
                self.table.setCellWidget(row, 1, widget)
            else:
                widget = QtGui.QLineEdit(str(default))
                self.table.setCellWidget(row, 1, widget)
            
            self.widgets[name] = (widget, vtype, default, unit)
            
            # Unit column
            unit_item = QtGui.QTableWidgetItem(unit or "")
            unit_item.setFlags(unit_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(row, 2, unit_item)
            
            # Description
            desc_item = QtGui.QTableWidgetItem(desc)
            desc_item.setFlags(desc_item.flags() & ~QtCore.Qt.ItemIsEditable)
            desc_item.setToolTip(desc)
            self.table.setItem(row, 3, desc_item)
        
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QtGui.QHBoxLayout()
        
        reset_btn = QtGui.QPushButton("Réinitialiser les valeurs par défaut")
        reset_btn.clicked.connect(self._reset_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        cancel_btn = QtGui.QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        preview_btn = QtGui.QPushButton("Prévisualiser")
        preview_btn.clicked.connect(self._on_preview)
        button_layout.addWidget(preview_btn)
        
        ok_btn = QtGui.QPushButton("Exporter")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
    
    def _load_values(self):
        """Load values from input_config into widgets (converting m to mm for display)."""
        for name, (widget, vtype, default, unit) in self.widgets.items():
            # Get value from config, or use default
            if name in self.input_config:
                value = self.input_config[name]
                # Convert meters to mm for display if unit is mm
                if unit == "mm" and isinstance(value, (int, float)):
                    value = value * 1000
            else:
                value = default
            
            if vtype == bool:
                widget.setChecked(bool(value))
            elif vtype in (int, float):
                widget.setValue(value)
            else:
                widget.setText(str(value))
    
    def _on_preview(self):
        """Génère et affiche la prévisualisation des patrons."""
        if self.glider_obj is None:
            QtGui.QMessageBox.warning(self, "Prévisualisation",
                "Objet glider non disponible pour la prévisualisation.")
            return

        config_dict = self.get_config_dict()

        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            svg_string = generate_preview_svg(self.glider_obj, config_dict)
        finally:
            QtGui.QApplication.restoreOverrideCursor()

        if svg_string is None:
            QtGui.QMessageBox.critical(self, "Erreur",
                "Erreur lors de la génération de la prévisualisation.")
            return

        preview = PreviewWindow(svg_string, parent=self)
        preview.exec_()

    def _reset_defaults(self):
        """Reset all values to defaults."""
        for name, (widget, vtype, default, unit) in self.widgets.items():
            if vtype == bool:
                widget.setChecked(default)
            elif vtype in (int, float):
                widget.setValue(default)
            else:
                widget.setText(str(default))
    
    def get_config_dict(self):
        """Return a dictionary of all parameter values (converting mm back to meters)."""
        result = {}
        for name, (widget, vtype, default, unit) in self.widgets.items():
            if vtype == bool:
                result[name] = widget.isChecked()
            elif vtype == int:
                result[name] = widget.value()
            elif vtype == float:
                value = widget.value()
                # Convert mm back to meters if unit is mm
                if unit == "mm":
                    value = value / 1000.0
                result[name] = value
            else:
                result[name] = widget.text()
        return result


class PreviewWindow(QtGui.QDialog):
    """Fenêtre de prévisualisation des patrons 2D via QSvgRenderer + QPixmap."""

    def __init__(self, svg_string, parent=None):
        super(PreviewWindow, self).__init__(parent)
        self.setWindowTitle("Prévisualisation des patrons")
        self.setMinimumSize(900, 700)
        self.resize(1200, 900)
        self.scale_factor = 1.0

        layout = QtGui.QVBoxLayout(self)

        # Toolbar
        toolbar = QtGui.QHBoxLayout()
        self.zoom_in_btn = QtGui.QPushButton("+ Zoom")
        self.zoom_out_btn = QtGui.QPushButton("- Zoom")
        self.zoom_fit_btn = QtGui.QPushButton("Ajuster")
        self.zoom_label = QtGui.QLabel("100%")
        toolbar.addWidget(self.zoom_in_btn)
        toolbar.addWidget(self.zoom_out_btn)
        toolbar.addWidget(self.zoom_fit_btn)
        toolbar.addWidget(self.zoom_label)
        toolbar.addStretch()
        close_btn = QtGui.QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        toolbar.addWidget(close_btn)
        layout.addLayout(toolbar)

        # ScrollArea + QLabel pour afficher le pixmap
        self.scroll = QtGui.QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(QtCore.Qt.AlignCenter)
        self.scroll.setStyleSheet("background-color: #888;")
        self.label = QtGui.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.scroll.setWidget(self.label)
        layout.addWidget(self.scroll)

        # Rendre le SVG via QSvgRenderer
        from PySide.QtSvg import QSvgRenderer
        self.renderer = QSvgRenderer(QtCore.QByteArray(svg_string.encode('utf-8')))
        sz = self.renderer.defaultSize()
        self.base_width = sz.width() if sz.width() > 0 else 1000
        self.base_height = sz.height() if sz.height() > 0 else 800

        self._render()

        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_fit_btn.clicked.connect(self.zoom_fit)

        # Activer le zoom molette sur le scroll area
        self.scroll.setFocusPolicy(QtCore.Qt.WheelFocus)
        self.scroll.wheelEvent = self._wheel_event
        self.label.wheelEvent = self._wheel_event

    def _wheel_event(self, event):
        """Zoom avec la molette souris / trackpad."""
        # Essayer angleDelta (PySide2/Qt5) puis delta (PySide/Qt4)
        try:
            delta = event.angleDelta().y()
        except AttributeError:
            delta = event.delta()
        # Trackpad peut envoyer de petits deltas cumulatifs
        if delta == 0:
            try:
                delta = event.pixelDelta().y()
            except AttributeError:
                pass
        if delta > 0:
            self.scale_factor = min(self.scale_factor * 1.1, 10.0)
        elif delta < 0:
            self.scale_factor = max(self.scale_factor / 1.1, 0.05)
        self._render()
        event.accept()

    def _render(self):
        w = max(1, int(self.base_width * self.scale_factor))
        h = max(1, int(self.base_height * self.scale_factor))
        pixmap = QtGui.QPixmap(w, h)
        pixmap.fill(QtGui.QColor("white"))
        painter = QtGui.QPainter(pixmap)
        self.renderer.render(painter)
        painter.end()
        self.label.setPixmap(pixmap)
        self.label.setFixedSize(w, h)
        self.zoom_label.setText(f"{int(self.scale_factor * 100)}%")

    def zoom_in(self):
        self.scale_factor = min(self.scale_factor * 1.25, 10.0)
        self._render()

    def zoom_out(self):
        self.scale_factor = max(self.scale_factor / 1.25, 0.05)
        self._render()

    def zoom_fit(self):
        avail_w = self.scroll.width() - 20
        avail_h = self.scroll.height() - 20
        if self.base_width > 0 and self.base_height > 0:
            self.scale_factor = min(avail_w / self.base_width, avail_h / self.base_height)
        self._render()


def generate_preview_svg(obj, config_dict):
    """
    Génère le SVG de prévisualisation des patrons en mémoire.
    Retourne la chaîne SVG ou None en cas d'erreur.
    """
    try:
        from openglider import plots
        from freecad.glider.tools.airfoilstructure_tool import apply_rod_sleeves_standalone

        glider_instance = obj.Proxy.getGliderInstance()
        apply_rod_sleeves_standalone(obj.Proxy.getParametricGlider(), glider_instance)

        pat = plots.Patterns(obj.Proxy.getParametricGlider(), config=config_dict)
        pat.project.glider_3d = glider_instance

        if config_dict.get('profile_numpoints'):
            pat.glider_2d.num_profile = config_dict['profile_numpoints']

        all_patterns = pat._get_plotfile()
        all_patterns.scale(1000)

        drawing = all_patterns.get_svg_drawing()

        # Taille fixe pour la preview
        drawing["width"] = "1000px"
        drawing["height"] = "800px"

        # Récupérer le SVG brut
        svg_raw = drawing.tostring()

        # Parser le viewBox pour recalculer les dimensions réelles
        import re
        vb_match = re.search(r'viewBox="([^"]+)"', svg_raw)
        if vb_match:
            vb = [float(x) for x in vb_match.group(1).replace(',', ' ').split()]
            vb_x, vb_y, vb_w, vb_h = vb
        else:
            vb_x, vb_y, vb_w, vb_h = 0, 0, 1000, 800

        # Mettre à jour le viewBox pour correspondre exactement au contenu
        new_vb = f"{vb_x} {vb_y} {vb_w} {vb_h}"
        svg_raw = re.sub(r'viewBox="[^"]*"', f'viewBox="{new_vb}"', svg_raw)

        # Recalculer width/height en gardant le ratio
        ratio = vb_h / vb_w if vb_w > 0 else 1.0
        preview_w = 1000
        preview_h = int(preview_w * ratio)
        svg_raw = re.sub(r'width="[^"]*"', f'width="{preview_w}px"', svg_raw, count=1)
        svg_raw = re.sub(r'height="[^"]*"', f'height="{preview_h}px"', svg_raw, count=1)

        # Injecter fond blanc
        white_bg = f'<rect x="{vb_x}" y="{vb_y}" width="{vb_w}" height="{vb_h}" fill="white"/>'
        svg_raw = svg_raw.replace('<defs />', '<defs />' + white_bg, 1)
        if white_bg not in svg_raw:
            svg_raw = svg_raw.replace('<defs>', '<defs>' + white_bg, 1)

        # Forcer couleurs sombres directement dans les attributs SVG
        # Remplacer tous les stroke par noir
        svg_raw = re.sub(r'stroke="[^"]*"', 'stroke="#000000"', svg_raw)
        svg_raw = re.sub(r'stroke-opacity="[^"]*"', 'stroke-opacity="1"', svg_raw)
        # Forcer stroke-width minimum
        svg_raw = re.sub(r'stroke-width="[^"]*"', 'stroke-width="2"', svg_raw)
        # Texte en noir
        svg_raw = re.sub(r'fill="(?!none|white)[^"]*"', 'fill="#000000"', svg_raw)
        # Garder fill=none pour les contours

        return svg_raw

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None


def show_pattern_config_dialog(parent=None, current_config=None, glider_obj=None):
    """
    Show the pattern configuration dialog and return the config dict.
    
    Args:
        parent: Parent widget
        current_config: Dict of current config values (in meters for lengths)
        glider_obj: FreeCAD glider object for preview generation
    
    Returns:
        dict or None: Configuration dict if accepted (lengths in meters), None if cancelled.
    """
    dialog = PatternConfigDialog(parent, current_config, glider_obj=glider_obj)
    if dialog.exec_() == QtGui.QDialog.Accepted:
        return dialog.get_config_dict()
    return None
