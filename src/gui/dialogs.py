"""
src/gui/dialogs.py

This module contains secondary dialog windows used by the main application.
Primarily, it hosts the MeshPreviewDialog, which provides a dedicated 
PyVista plotter for inspecting heavy boolean operations (Union/Cut) 
without freezing the main design window.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from pyvistaqt import QtInteractor

class MeshPreviewDialog(QDialog):
    """
    A modal dialog window that embeds a PyVista plotter.
    Used to display the result of the 'Boolean Union' operation.
    """
    def __init__(self, mesh, parent=None):
        """
        Initialize the preview window.

        Args:
            mesh (pyvista.PolyData): The result mesh to display.
            parent (QWidget, optional): The parent widget (usually PlaneDesigner).
        """
        super().__init__(parent)
        self.setWindowTitle("Unified Mesh Preview")
        self.resize(1000, 700)
        
        # Main vertical layout
        layout = QVBoxLayout(self)
        
        # Informational Label
        lbl = QLabel("<b>Unified Mesh Result</b><br>Magenta = Solid Surface. Black Lines = Edges.")
        layout.addWidget(lbl)
        
        # --- PyVista Plotter Integration ---
        # QtInteractor is a QWidget wrapper around vtkRenderWindowInteractor
        self.plotter = QtInteractor(self)
        self.plotter.set_background("#222222") # Dark grey for professional CAD look
        self.plotter.add_axes(color='white')   # Contrast against dark background
        layout.addWidget(self.plotter)
        
        # Add the provided mesh to the scene immediately
        if mesh:
            # Opacity=1.0 ensures we see the solid skin (watertight check)
            self.plotter.add_mesh(mesh, color="magenta", show_edges=True, opacity=1.0)
            self.plotter.view_isometric()
            self.plotter.reset_camera()
        
        # Close Button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)