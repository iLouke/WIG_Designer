"""
src/gui/designer.py

The main GUI implementation for the Plane Designer application.
This module defines the `PlaneDesigner` class, which inherits from QMainWindow.
It orchestrates:
1. The Left Panel (Tree Structure & Properties)
2. The Center Panel (3D Visualization Viewport)
3. The Interaction Logic (Adding/Removing components, updating meshes)
"""

import sys
import numpy as np
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox, 
                             QPushButton, QSplitter, QMessageBox, QFileDialog, 
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QLabel, QCheckBox, QDialog, QProgressBar, QProgressDialog, 
                             QSlider, QScrollArea, QGridLayout) 
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

import pyvista as pv
from pyvistaqt import QtInteractor

# Internal Imports
from src.geometry.components import Vehicle, LiftingSurface, Fuselage, WingStation
from src.geometry.mesher import StructuredMesher
from src.gui.dialogs import MeshPreviewDialog

class PlaneDesigner(QMainWindow):
    """
    Main Application Window.
    Manages the WIG Craft data model (Vehicle) and synchronizes it with 
    the 3D Viewport and Property Panels.
    """
    
    def __init__(self):
        """Constructor: Sets up the UI layout, initializes default data, and starts the 3D plotter."""
        super().__init__()
        self.setWindowTitle("PhD WIG Design Tool (Stable CAD Mode)")
        self.resize(1600, 1000)

        # 1. Initialize Data Model
        self.vehicle = Vehicle("PhD_WIG_Prototype")
        self._init_defaults() # Creates default wing
        
        # 2. Configure PyVista Global Theme
        # Ensures text is white on the dark background
        pv.global_theme.font.color = 'white'
        pv.global_theme.axes.box = False
        
        # Default Meshing Parameters
        self.mesh_params = {
            "chord_res": 30,  # Points along the airfoil curve
            "span_res": 15,   # Points along the span (between stations)
            "fus_long": 50,   # Longitudinal points on fuselage
            "fus_rad": 24,    # Radial points on fuselage
            "opacity": 1.0    # Visual opacity
        }

        # 3. Setup Main UI Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # --- LEFT PANEL: Structure & Settings ---
        self.left_panel = QSplitter(Qt.Orientation.Vertical)
        self.left_panel.setFixedWidth(320)
        
        # A. Structure Tree (Top Left)
        self.group_structure = QGroupBox("Structure")
        self.struct_layout = QVBoxLayout(self.group_structure)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Vehicle Hierarchy")
        self.tree.itemClicked.connect(self.on_tree_select)
        self.tree.itemChanged.connect(self.on_tree_item_changed) # Handles Renaming
        
        # Buttons for adding/removing components
        self.btn_add_wing = QPushButton("Add New Wing")
        self.btn_add_wing.clicked.connect(self.add_new_wing)
        self.btn_add_fuse = QPushButton("Add Fuselage")
        self.btn_add_fuse.clicked.connect(self.add_fuselage)
        self.btn_add_station = QPushButton("Add Station to Wing")
        self.btn_add_station.clicked.connect(self.add_station_to_selected)
        self.btn_add_station.setEnabled(False) # Enabled only when wing selected
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self.remove_component)
        
        self.struct_layout.addWidget(self.tree)
        self.struct_layout.addWidget(self.btn_add_wing)
        self.struct_layout.addWidget(self.btn_add_fuse)
        self.struct_layout.addWidget(self.btn_add_station)
        self.struct_layout.addWidget(self.btn_remove)

        # B. Global Settings (Bottom Left)
        self.group_settings = QGroupBox("Global Settings")
        self.sets_layout = QVBoxLayout(self.group_settings)
        
        # Form for resolution inputs
        mesh_form = QFormLayout()
        self.spin_chord = self._create_int_spin(10, 100, self.mesh_params["chord_res"], "chord_res")
        self.spin_span = self._create_int_spin(5, 100, self.mesh_params["span_res"], "span_res")
        self.spin_fus_long = self._create_int_spin(10, 200, self.mesh_params["fus_long"], "fus_long")
        self.spin_fus_rad = self._create_int_spin(8, 64, self.mesh_params["fus_rad"], "fus_rad")
        self.spin_opacity = QDoubleSpinBox()
        self.spin_opacity.setRange(0.1, 1.0)
        self.spin_opacity.setSingleStep(0.1)
        self.spin_opacity.setValue(self.mesh_params["opacity"])
        self.spin_opacity.valueChanged.connect(lambda v: self.update_mesh_param("opacity", v))
        
        mesh_form.addRow("Chord Res:", self.spin_chord)
        mesh_form.addRow("Span Res:", self.spin_span)
        mesh_form.addRow("Fuselage Long:", self.spin_fus_long)
        mesh_form.addRow("Fuselage Rad:", self.spin_fus_rad)
        mesh_form.addRow("Opacity:", self.spin_opacity)
        self.sets_layout.addLayout(mesh_form)
        
        # Boolean Operations & Export
        self.sets_layout.addWidget(QLabel("<b>Operations</b>"))
        self.chk_unify = QCheckBox("Unify Meshes (Boolean)")
        self.chk_unify.setToolTip("Merges symmetrical parts into one solid.")
        
        self.btn_preview = QPushButton("Preview Union")
        self.btn_preview.setStyleSheet("background-color: #6a4ea8; color: white;")
        self.btn_preview.clicked.connect(self.start_preview_sequence)

        self.btn_export = QPushButton("Export to .OBJ")
        self.btn_export.setStyleSheet("background-color: #d4a517; font-weight: bold; color: black;")
        self.btn_export.clicked.connect(self.export_obj)
        
        self.sets_layout.addWidget(self.chk_unify)
        self.sets_layout.addWidget(self.btn_preview)
        self.sets_layout.addWidget(self.btn_export)
        self.sets_layout.addStretch()

        self.left_panel.addWidget(self.group_structure)
        self.left_panel.addWidget(self.group_settings)
        self.left_panel.setSizes([500, 300])

        # --- CENTER: SINGLE VIEWPORT WITH CAMERA TOOLBAR ---
        self.center_container = QWidget()
        self.center_layout = QVBoxLayout(self.center_container)
        self.center_layout.setContentsMargins(0,0,0,0)
        
        # Camera Quick-Switch Toolbar
        self.cam_toolbar = QWidget()
        cam_layout = QHBoxLayout(self.cam_toolbar)
        cam_layout.setContentsMargins(5, 5, 5, 5)
        
        btn_iso = QPushButton("ISO")
        btn_iso.clicked.connect(lambda: self.set_camera_view('iso'))
        
        btn_top = QPushButton("TOP (XY)")
        btn_top.clicked.connect(lambda: self.set_camera_view('xy'))
        
        btn_side = QPushButton("SIDE (XZ)")
        btn_side.clicked.connect(lambda: self.set_camera_view('xz'))
        
        btn_front = QPushButton("FRONT (ZY)")
        btn_front.clicked.connect(lambda: self.set_camera_view('zy'))
        
        cam_layout.addWidget(QLabel("<b>Camera:</b>"))
        cam_layout.addWidget(btn_iso)
        cam_layout.addWidget(btn_top)
        cam_layout.addWidget(btn_side)
        cam_layout.addWidget(btn_front)
        cam_layout.addStretch()
        
        # Main 3D Plotter
        self.plotter = QtInteractor(self.center_container)
        self.plotter.set_background("#222222")
        self.add_custom_axes()
        
        self.center_layout.addWidget(self.cam_toolbar)
        self.center_layout.addWidget(self.plotter)

        # Shortcut 'R' to reset view
        self.shortcut_reset = QShortcut(QKeySequence("R"), self)
        self.shortcut_reset.activated.connect(self.reset_view)

        # --- RIGHT: PROPERTIES PANEL ---
        self.props_panel = QGroupBox("Properties")
        self.props_panel.setFixedWidth(300)
        self.props_main_layout = QVBoxLayout() 
        self.props_panel.setLayout(self.props_main_layout)

        # Combine Panels into Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.center_container)
        splitter.addWidget(self.props_panel)
        splitter.setStretchFactor(1, 1) # Give Center priority
        self.main_layout.addWidget(splitter)

        # Initial Render
        self.refresh_tree()
        self.update_3d_view()

    # =========================================================================
    #                               VIEW LOGIC
    # =========================================================================

    def set_camera_view(self, mode):
        """Switches the camera to standard engineering views."""
        if mode == 'iso':
            self.plotter.view_isometric()
        elif mode == 'xy':
            self.plotter.view_xy()
        elif mode == 'xz':
            self.plotter.view_xz()
        elif mode == 'zy': # Front
            self.plotter.view_yz()
        self.plotter.reset_camera()

    def reset_view(self):
        """Resets camera to isometric fit-to-screen."""
        self.plotter.view_isometric()
        self.plotter.reset_camera()

    def update_3d_view(self):
        """
        The Core Rendering Pipeline.
        1. Clears the plotter.
        2. Iterates through all vehicle components.
        3. Generates mesh (Surface or Solid) based on properties.
        4. Handles Mirroring and Normal Flipping logic.
        5. Adds helper glyphs (Normals, CSYS) if enabled.
        """
        self.plotter.clear()
        self.plotter.add_custom_axes = self.add_custom_axes
        self.add_custom_axes()
        
        try:
            mesher = self.get_mesher()
            
            # Helper: Manually flips point order for Open StructuredGrids
            def flip_winding(g):
                if isinstance(g, pv.StructuredGrid):
                    d = g.dimensions
                    # Reverse last dimension to invert surface normal
                    g.points = g.points.reshape(d[2], d[1], d[0], 3)[:, :, ::-1, :].reshape(-1, 3)

            # Helper: Adds a single grid to the plotter with all enabled visualizations
            def add_mesh_to_all(grid, obj_viz):
                # Read properties from the object
                use_solid = getattr(obj_viz, 'solid_view', False) # Default Uncapped
                show_norm = getattr(obj_viz, 'show_normals', False)
                show_csys = getattr(obj_viz, 'show_csys', False)
                norm_scale = getattr(obj_viz, 'normal_scale', 1.5)
                axis_scale = getattr(obj_viz, 'axis_scale', 3.0)
                
                # Add Main Mesh
                self.plotter.add_mesh(grid, show_edges=True, edge_color="black", 
                                      color="cyan", opacity=self.mesh_params["opacity"],
                                      smooth_shading=use_solid)
                
                # 1. Visualize Normals (Yellow Arrows)
                if show_norm:
                    if not use_solid:
                        # StructuredGrids need normals calculated on a surface extract
                        surf = grid.extract_surface()
                        surf.compute_normals(inplace=True, cell_normals=True, point_normals=False)
                        ct = surf.cell_centers()
                    else:
                        # Solids (PolyData) have normals natively
                        grid.compute_normals(inplace=True, cell_normals=True, point_normals=False)
                        ct = grid.cell_centers()
                    
                    # Subsample if too dense (Performance)
                    if ct.n_points > 3000:
                        ct = ct.extract_points(np.arange(0, ct.n_points, int(ct.n_points/3000)))
                    
                    if ct.n_points > 0:
                        arrows = ct.glyph(orient='Normals', scale=False, factor=norm_scale)
                        self.plotter.add_mesh(arrows, color="yellow")
                
                # 2. Visualize Local Coordinate System (RGB Arrows)
                if show_csys and hasattr(obj_viz, 'position') and hasattr(obj_viz, 'orientation'):
                    vx, vy, vz = self._get_local_axes(obj_viz.orientation)
                    pos = obj_viz.position
                    self.plotter.add_arrows(np.array([pos]), np.array([vx]), mag=axis_scale, color='red', show_scalar_bar=False)
                    self.plotter.add_arrows(np.array([pos]), np.array([vy]), mag=axis_scale, color='green', show_scalar_bar=False)
                    self.plotter.add_arrows(np.array([pos]), np.array([vz]), mag=axis_scale, color='blue', show_scalar_bar=False)

            # Helper: Process Component (Original & Mirror)
            def process_component(obj, mirrored=False):
                use_solid = getattr(obj, 'solid_view', False) 
                
                # Generate Raw Mesh
                if isinstance(obj, LiftingSurface):
                    grid = mesher._mesh_surface(obj, solid=use_solid)
                elif isinstance(obj, Fuselage):
                    grid = mesher._mesh_fuselage(obj, solid=use_solid)
                else: return

                # Handle Mirroring Logic
                if mirrored:
                    if use_solid:
                        grid.reflect((0,1,0), point=(0,0,0), inplace=True)
                        # Solid Mirror turns inside-out; Flip faces to fix
                        grid.flip_faces(inplace=True)
                    else:
                        grid.points[:, 1] *= -1
                        # Open Mirror needs winding flip to maintain "Out" normal
                        flip_winding(grid)
                
                # Handle User-Requested Flip
                if getattr(obj, 'flip_normals', True):
                    if isinstance(grid, pv.PolyData): 
                        grid.flip_faces(inplace=True)
                    else: 
                        flip_winding(grid)
                
                add_mesh_to_all(grid, obj)

            # --- EXECUTE PIPELINE ---
            for surf in self.vehicle.surfaces:
                process_component(surf, False)
                if surf.mirrored: process_component(surf, True)
            
            if self.vehicle.fuselage:
                process_component(self.vehicle.fuselage, False)
                
        except Exception as e:
            print(f"Viz Error: {e}")
            traceback.print_exc()

    # =========================================================================
    #                            DATA MANAGEMENT
    # =========================================================================

    def _init_defaults(self):
        """Creates the initial default vehicle configuration."""
        # Default wing with Camber (p=0.4) so curvature is visible
        st1 = WingStation(0.0, 2.0, 0.0, 0.0, airfoil_params=[0.0, 0.4, 0.12, 0.0])
        st2 = WingStation(5.0, 1.0, 1.0, 0.5, airfoil_params=[0.0, 0.4, 0.12, 0.0])
        wing = LiftingSurface("Main_Wing", [st1, st2], mirrored=True)
        self._init_component_viz(wing)
        self.vehicle.add_surface(wing)

    def _init_component_viz(self, obj):
        """Injects default visualization attributes into components."""
        if not hasattr(obj, 'flip_normals'): obj.flip_normals = True
        if not hasattr(obj, 'solid_view'): obj.solid_view = False # Start as Open Grid
        if not hasattr(obj, 'show_normals'): obj.show_normals = False
        if not hasattr(obj, 'normal_scale'): obj.normal_scale = 1.5
        if not hasattr(obj, 'show_csys'): obj.show_csys = False
        if not hasattr(obj, 'axis_scale'): obj.axis_scale = 3.0

    def _create_int_spin(self, min_val, max_val, default, key):
        """Creates a generic integer spinbox linked to mesh_params."""
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.valueChanged.connect(lambda v: self.update_mesh_param(key, v))
        return spin

    def update_mesh_param(self, key, value):
        self.mesh_params[key] = value
        self.update_3d_view()

    def add_custom_axes(self):
        """Adds white-labeled axes to the plotter."""
        self.plotter.add_axes(line_width=3, color='white', labels_off=False)

    def get_mesher(self):
        """Factory for the meshing engine."""
        return StructuredMesher(
            chord_res=self.mesh_params["chord_res"], 
            span_res=self.mesh_params["span_res"], 
            fuselage_long_res=self.mesh_params["fus_long"],
            fuselage_radial_res=self.mesh_params["fus_rad"]
        )

    def _get_local_axes(self, rotation_deg):
        """Computes local basis vectors from Euler angles."""
        r, p, y = np.radians(rotation_deg)
        Rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
        Ry = np.array([[np.cos(p), 0, np.sin(p)], [0, 1, 0], [-np.sin(p), 0, np.cos(p)]])
        Rz = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
        R = Rz @ Ry @ Rx
        return R @ np.array([1, 0, 0]), R @ np.array([0, 1, 0]), R @ np.array([0, 0, 1])

    # =========================================================================
    #                            TREE INTERACTIONS
    # =========================================================================

    def refresh_tree(self):
        """Rebuilds the component tree from the vehicle data."""
        self.tree.blockSignals(True)
        self.tree.clear()
        
        # Root Item (Vehicle)
        root = QTreeWidgetItem([self.vehicle.name])
        root.setData(0, Qt.ItemDataRole.UserRole, self.vehicle)
        root.setFlags(root.flags() | Qt.ItemFlag.ItemIsEditable)
        self.tree.addTopLevelItem(root)
        
        # Surfaces
        for surf in self.vehicle.surfaces:
            s_item = QTreeWidgetItem([surf.name])
            s_item.setData(0, Qt.ItemDataRole.UserRole, surf)
            s_item.setFlags(s_item.flags() | Qt.ItemFlag.ItemIsEditable)
            root.addChild(s_item)
            
            # Stations
            for i, st in enumerate(surf.stations):
                st_item = QTreeWidgetItem([f"Station {i} (Y={st.y:.1f})"])
                st_item.setData(0, Qt.ItemDataRole.UserRole, st)
                s_item.addChild(st_item)
                
        # Fuselage
        if self.vehicle.fuselage:
            f_item = QTreeWidgetItem([self.vehicle.fuselage.name])
            f_item.setData(0, Qt.ItemDataRole.UserRole, self.vehicle.fuselage)
            f_item.setFlags(f_item.flags() | Qt.ItemFlag.ItemIsEditable)
            root.addChild(f_item)
            
        self.tree.expandAll()
        self.tree.blockSignals(False)

    def on_tree_item_changed(self, item, column):
        """Handles renaming of components in the tree."""
        obj = item.data(0, Qt.ItemDataRole.UserRole)
        if obj and hasattr(obj, 'name'):
            obj.name = item.text(0)

    def on_tree_select(self, item, column):
        """Updates the property panel when a tree item is clicked."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        self.btn_add_station.setEnabled(isinstance(data, LiftingSurface))
        self.populate_properties(data)

    # =========================================================================
    #                        ADD / REMOVE LOGIC
    # =========================================================================

    def add_new_wing(self):
        st1 = WingStation(0, 1, 0, 0, airfoil_params=[0.0, 0.4, 0.12, 0.0])
        st2 = WingStation(1, 1, 0, 0, airfoil_params=[0.0, 0.4, 0.12, 0.0])
        count = len(self.vehicle.surfaces) + 1
        wing = LiftingSurface(f"Wing_{count}", [st1, st2], position=[0,0,0], mirrored=True)
        self._init_component_viz(wing)
        self.vehicle.add_surface(wing)
        self.refresh_tree()
        self.update_3d_view()

    def add_fuselage(self):
        if self.vehicle.fuselage:
            QMessageBox.warning(self, "Warning", "Fuselage already exists.")
            return
        profile = [(0,0), (0.5, 0.4), (4.0, 0.4), (5.0, 0.0)]
        fuse = Fuselage("Fuselage", profile, position=[0,0,0])
        self._init_component_viz(fuse)
        self.vehicle.add_fuselage(fuse)
        self.refresh_tree()
        self.update_3d_view()

    def add_station_to_selected(self):
        item = self.tree.currentItem()
        if not item: return
        obj = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(obj, LiftingSurface):
            last = obj.stations[-1]
            new_st = WingStation(last.y + 1.0, last.chord, last.x, last.z, last.twist)
            # Copy airfoil settings to keep consistent profile
            new_st.airfoil_params = last.airfoil_params.copy()
            new_st.m, new_st.p, new_st.t = last.m, last.p, last.t
            obj.stations.append(new_st)
            self.refresh_tree()
            self.update_3d_view()

    def remove_component(self):
        item = self.tree.currentItem()
        if not item: return
        obj = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(obj, LiftingSurface) and obj in self.vehicle.surfaces:
            self.vehicle.surfaces.remove(obj)
        elif isinstance(obj, Fuselage):
            self.vehicle.fuselage = None
        elif isinstance(obj, WingStation):
            for surf in self.vehicle.surfaces:
                if obj in surf.stations:
                    if len(surf.stations) > 2: surf.stations.remove(obj)
                    break
        self.refresh_tree()
        self.update_3d_view()
        self.clear_properties()

    # =========================================================================
    #                        PROPERTIES PANEL BUILDER
    # =========================================================================

    def clear_properties(self):
        while self.props_main_layout.count():
            child = self.props_main_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

    def populate_properties(self, obj):
        self.clear_properties()
        # Init viz props in case object is new
        if hasattr(obj, 'name') and not isinstance(obj, WingStation) and not isinstance(obj, Vehicle):
            self._init_component_viz(obj)

        form_widget = QWidget()
        self.form_layout = QFormLayout()
        form_widget.setLayout(self.form_layout)
        self.props_main_layout.addWidget(form_widget)

        # A. VISUALIZATION SETTINGS (Wings/Fuselage only)
        if isinstance(obj, LiftingSurface) or isinstance(obj, Fuselage):
            viz_group = QGroupBox("Visualization")
            viz_form = QFormLayout()
            
            # Solid View Toggle
            chk_solid = QCheckBox("Solid (Capped)")
            chk_solid.setChecked(obj.solid_view)
            chk_solid.toggled.connect(lambda v: self.set_attr_refresh(obj, 'solid_view', v))
            
            # Flip Normals Toggle
            chk_flip = QCheckBox("Flip Normals")
            chk_flip.setChecked(obj.flip_normals)
            chk_flip.toggled.connect(lambda v: self.set_attr_refresh(obj, 'flip_normals', v))
            
            # Normals Display & Scaling
            chk_show_norm = QCheckBox("Show Normals")
            chk_show_norm.setChecked(obj.show_normals)
            
            slider_norm_scale = QSlider(Qt.Orientation.Horizontal)
            slider_norm_scale.setRange(1, 50)
            slider_norm_scale.setValue(int(obj.normal_scale * 10))
            slider_norm_scale.setVisible(obj.show_normals)
            slider_norm_scale.valueChanged.connect(lambda v: self.set_attr_refresh(obj, 'normal_scale', v / 10.0))
            
            def on_norm_toggled(checked):
                obj.show_normals = checked
                slider_norm_scale.setVisible(checked)
                self.update_3d_view()
            
            chk_show_norm.toggled.connect(on_norm_toggled)
            
            # CSYS Display & Scaling
            chk_csys = QCheckBox("Show Local Axis")
            chk_csys.setChecked(getattr(obj, 'show_csys', False))
            
            slider_axis_scale = QSlider(Qt.Orientation.Horizontal)
            slider_axis_scale.setRange(1, 100)
            slider_axis_scale.setValue(int(getattr(obj, 'axis_scale', 3.0) * 10))
            slider_axis_scale.setVisible(getattr(obj, 'show_csys', False))
            slider_axis_scale.valueChanged.connect(lambda v: self.set_attr_refresh(obj, 'axis_scale', v / 10.0))
            
            def on_csys_toggled(checked):
                obj.show_csys = checked
                slider_axis_scale.setVisible(checked)
                self.update_3d_view()
            
            chk_csys.toggled.connect(on_csys_toggled)

            viz_form.addRow(chk_solid)
            viz_form.addRow(chk_flip)
            viz_form.addRow(chk_show_norm)
            viz_form.addRow("Normal Scale:", slider_norm_scale)
            viz_form.addRow(chk_csys)
            viz_form.addRow("Axis Scale:", slider_axis_scale)
            
            viz_group.setLayout(viz_form)
            self.props_main_layout.addWidget(viz_group)

        # B. GEOMETRY PROPERTIES
        if isinstance(obj, LiftingSurface):
            chk_mirror = QCheckBox("Mirrored (Symmetric)")
            chk_mirror.setChecked(obj.mirrored)
            chk_mirror.toggled.connect(lambda v: self.set_attr_refresh(obj, 'mirrored', v))
            self.form_layout.addRow("Symmetry:", chk_mirror)

            self.add_prop("Pos X", obj.position[0], lambda v: self.set_arr(obj.position, 0, v))
            self.add_prop("Pos Y", obj.position[1], lambda v: self.set_arr(obj.position, 1, v))
            self.add_prop("Pos Z", obj.position[2], lambda v: self.set_arr(obj.position, 2, v))
            self.add_prop("Roll", obj.orientation[0], lambda v: self.set_arr(obj.orientation, 0, v))
            self.add_prop("Pitch", obj.orientation[1], lambda v: self.set_arr(obj.orientation, 1, v))
            self.add_prop("Yaw", obj.orientation[2], lambda v: self.set_arr(obj.orientation, 2, v))
        
        elif isinstance(obj, WingStation):
            self.add_prop("Y (Span)", obj.y, lambda v: setattr(obj, 'y', v))
            self.add_prop("Chord", obj.chord, lambda v: setattr(obj, 'chord', v))
            self.add_prop("X (Offset)", obj.x, lambda v: setattr(obj, 'x', v))
            self.add_prop("Z (Height)", obj.z, lambda v: setattr(obj, 'z', v))
            self.add_prop("Twist", obj.twist, lambda v: setattr(obj, 'twist', v))
            if hasattr(obj, 'airfoil_params'):
                self.add_prop("Camber", obj.airfoil_params[0], lambda v: self.set_arr(obj.airfoil_params, 0, v, obj))
                self.add_prop("Cam Pos", obj.airfoil_params[1], lambda v: self.set_arr(obj.airfoil_params, 1, v, obj))
                self.add_prop("Thick", obj.airfoil_params[2], lambda v: self.set_arr(obj.airfoil_params, 2, v, obj))
        
        elif isinstance(obj, Fuselage):
            self.add_prop("Global X", obj.position[0], lambda v: self.set_arr(obj.position, 0, v))
            self.add_prop("Global Z", obj.position[2], lambda v: self.set_arr(obj.position, 2, v))
            self.props_main_layout.addWidget(QLabel("<b>Profile Points (X, Radius)</b>"))
            self.fuse_table = QTableWidget()
            self.fuse_table.setColumnCount(2)
            self.fuse_table.setHorizontalHeaderLabels(["X Position", "Radius"])
            self.fuse_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.update_fuselage_table(obj)
            self.fuse_table.cellChanged.connect(lambda r, c: self.on_fuse_table_change(r, c, obj))
            self.props_main_layout.addWidget(self.fuse_table)
            btn_box = QHBoxLayout()
            btn_add = QPushButton("Add Point")
            btn_add.clicked.connect(lambda: self.add_fuse_point(obj))
            btn_rem = QPushButton("Remove Point")
            btn_rem.clicked.connect(lambda: self.remove_fuse_point(obj))
            btn_box.addWidget(btn_add)
            btn_box.addWidget(btn_rem)
            btns_widget = QWidget()
            btns_widget.setLayout(btn_box)
            self.props_main_layout.addWidget(btns_widget)

    def set_attr_refresh(self, obj, attr, value):
        setattr(obj, attr, value)
        self.refresh_tree()
        self.update_3d_view()

    def update_fuselage_table(self, fuselage):
        self.fuse_table.blockSignals(True)
        self.fuse_table.setRowCount(len(fuselage.profile))
        fuselage.profile = fuselage.profile[fuselage.profile[:, 0].argsort()]
        for i, point in enumerate(fuselage.profile):
            self.fuse_table.setItem(i, 0, QTableWidgetItem(f"{point[0]:.2f}"))
            self.fuse_table.setItem(i, 1, QTableWidgetItem(f"{point[1]:.2f}"))
        self.fuse_table.blockSignals(False)

    def on_fuse_table_change(self, row, col, fuselage):
        try:
            val = float(self.fuse_table.item(row, col).text())
            fuselage.profile[row, col] = val
            self.update_3d_view()
        except ValueError: pass

    def add_fuse_point(self, fuselage):
        last_x = fuselage.profile[-1, 0]
        fuselage.profile = np.vstack([fuselage.profile, np.array([[last_x + 1.0, 0.5]])])
        self.update_fuselage_table(fuselage)
        self.update_3d_view()

    def remove_fuse_point(self, fuselage):
        row = self.fuse_table.currentRow()
        if row == -1: row = len(fuselage.profile) - 1
        if len(fuselage.profile) > 2:
            fuselage.profile = np.delete(fuselage.profile, row, axis=0)
            self.update_fuselage_table(fuselage)
            self.update_3d_view()

    def add_prop(self, label, value, setter):
        spin = QDoubleSpinBox()
        spin.setRange(-1000.0, 1000.0)
        spin.setSingleStep(0.1)
        spin.setValue(float(value))
        spin.setKeyboardTracking(False) # Smoother UX
        spin.valueChanged.connect(lambda v: self.on_change(setter, v))
        self.form_layout.addRow(label, spin)

    def set_arr(self, arr, idx, val, obj=None):
        arr[idx] = val
        if obj and isinstance(obj, WingStation): 
            # Re-pack params into object for clarity
            obj.m, obj.p, obj.t = obj.airfoil_params[:3]

    def on_change(self, setter, value):
        setter(value)
        self.update_3d_view()

    # =========================================================================
    #                        BOOLEAN & EXPORT
    # =========================================================================

    def make_solid(self, mesh):
        """Prepares a mesh for boolean operations (High Res + Clean)."""
        if not mesh or mesh.n_points == 0: return None
        refined = mesh.triangulate().subdivide(2)
        clean = refined.clean(point_merging=True, tolerance=1e-5)
        clean.compute_normals(inplace=True, consistent_normals=True, auto_orient_normals=True)
        return clean

    def run_heavy_union(self, progress_callback):
        """Runs the Union on the main thread with progress updates."""
        try:
            progress_callback("Generating Solids...", 10)
            mesher = self.get_mesher()
            # Force Solid=True for Boolean operations
            multiblock = mesher.mesh_vehicle(self.vehicle, solid=True)
            if not multiblock: raise ValueError("No data")
            
            solids = []
            count = len(multiblock)
            for i, block in enumerate(multiblock):
                if block:
                    progress_callback(f"Refining {i+1}/{count}...", 10+int(i/count*30))
                    solids.append(self.make_solid(block))
            
            if not solids: raise ValueError("No solids")
            solids.sort(key=lambda m: m.n_cells, reverse=True)
            unified = solids[0]
            
            for i in range(1, len(solids)):
                progress_callback(f"Merging {i}/{len(solids)}...", 40+int(i/len(solids)*50))
                try: unified = unified.boolean_union(solids[i])
                except: unified = unified + solids[i]
            
            return unified
        except Exception as e:
            traceback.print_exc()
            raise e

    def start_preview_sequence(self):
        """Launches the boolean calculation and shows result dialog."""
        pd = QProgressDialog("Calculating...", "Cancel", 0, 100, self)
        pd.setWindowModality(Qt.WindowModality.WindowModal)
        pd.setMinimumDuration(0)
        
        def wrapper(t, v):
            pd.setLabelText(t)
            pd.setValue(v)
            QApplication.processEvents()

        try:
            mesh = self.run_heavy_union(wrapper)
            pd.close()
            if mesh: MeshPreviewDialog(mesh, self).exec()
        except:
            pd.close()

    def export_obj(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export", f"{self.vehicle.name}.obj", "OBJ (*.obj)")
        if not path: return
        try:
            mesher = self.get_mesher()
            combined = pv.MultiBlock()
            
            def get_grid(obj, mirrored=False):
                # Respect per-component solid/wireframe setting
                solid = getattr(obj, 'solid_view', False) 
                if isinstance(obj, LiftingSurface): g = mesher._mesh_surface(obj, solid=solid)
                else: g = mesher._mesh_fuselage(obj, solid=solid)
                
                if mirrored:
                    if solid: 
                        g.reflect((0,1,0), point=(0,0,0), inplace=True)
                        g.flip_faces(inplace=True)
                    else: 
                        g.points[:,1]*=-1
                        # Flip winding for structured export
                        d=g.dimensions; g.points=g.points.reshape(d[2],d[1],d[0],3)[:,:,::-1,:].reshape(-1,3)
                
                if getattr(obj, 'flip_normals', True):
                    if solid: g.flip_faces(inplace=True)
                    else: 
                        d=g.dimensions; g.points=g.points.reshape(d[2],d[1],d[0],3)[:,:,::-1,:].reshape(-1,3)
                return g

            for s in self.vehicle.surfaces:
                combined.append(get_grid(s, False))
                if s.mirrored: combined.append(get_grid(s, True))
            if self.vehicle.fuselage:
                combined.append(get_grid(self.vehicle.fuselage, False))
            
            combined.combine().extract_surface().save(path)
            QMessageBox.information(self, "OK", f"Saved {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))