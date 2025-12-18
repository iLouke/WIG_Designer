import numpy as np
from typing import List, Optional, Tuple
from src.utils.helpers import get_rotation_matrix

class WingStation:
    """ 
    Defines a 2D cross-section of a lifting surface (Rib). 
    Contains geometric data and airfoil parameters.
    """
    def __init__(self, y_pos: float, chord: float, x_leading_edge: float, z_pos: float, 
                 twist: float = 0.0, airfoil_params: Optional[List[float]] = None):
        """
        Args:
            y_pos (float): Spanwise location (Y).
            chord (float): Length of the chord.
            x_leading_edge (float): Longitudinal location of the LE (X).
            z_pos (float): Vertical location (Z).
            twist (float): Geometric twist (incidence) in degrees.
            airfoil_params (list): NACA 4-digit params [m, p, t, reflex]. 
                                   Default is NACA 0012 [0, 0, 0.12, 0].
        """
        self.y = y_pos
        self.chord = chord
        self.x = x_leading_edge
        self.z = z_pos
        self.twist = twist
        
        # Default to NACA 0012 if None
        # Format: [Max Camber, Max Camber Pos, Thickness, Reflex(optional)]
        self.airfoil_params = airfoil_params if airfoil_params is not None else [0.0, 0.0, 0.12, 0.0]
        
        # Unpack parameters for easier access
        self.m, self.p, self.t = self.airfoil_params[:3]
        self.r = self.airfoil_params[3] if len(self.airfoil_params) > 3 else 0.0

class LiftingSurface:
    """ 
    A wing, tail, or canard defined by a list of WingStations.
    """
    def __init__(self, name: str, stations: List[WingStation], 
                 position: Optional[List[float]] = None, 
                 orientation: Optional[List[float]] = None, 
                 mirrored: bool = True):
        """
        Args:
            name (str): Name of the component (e.g., "Main Wing").
            stations (List[WingStation]): List of station objects defining the shape.
            position (list): Global origin [x, y, z].
            orientation (list): Global rotation [roll, pitch, yaw] in degrees.
            mirrored (bool): If True, a symmetric copy is generated across the XZ plane.
        """
        self.name = name
        self.stations = stations
        self.position = np.array(position) if position else np.zeros(3)
        self.orientation = np.array(orientation) if orientation else np.zeros(3)
        self.mirrored = mirrored

class Fuselage:
    """ 
    A body of revolution defined by a profile curve along the X-axis.
    """
    def __init__(self, name: str, profile_points: List[Tuple[float, float]], position: Optional[List[float]] = None):
        """
        Args:
            name (str): Name of the component.
            profile_points (list): List of (x, radius) tuples defining the shape.
            position (list): Global origin [x, y, z].
        """
        self.name = name
        self.profile = np.array(profile_points) # Shape (N, 2)
        self.position = np.array(position) if position else np.zeros(3)

class Vehicle:
    """
    Container class for the entire WIG craft configuration.
    """
    def __init__(self, name: str = "WIG Prototype"):
        self.name = name
        self.surfaces: List[LiftingSurface] = []
        self.fuselage: Optional[Fuselage] = None
        
    def add_surface(self, s: LiftingSurface):
        self.surfaces.append(s)
        
    def add_fuselage(self, f: Fuselage):
        self.fuselage = f