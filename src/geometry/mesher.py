import numpy as np
import pyvista as pv
from src.geometry.components import Vehicle, LiftingSurface, Fuselage

class StructuredMesher:
    """
    Generates grids for WIG vehicles.
    Can produce either StructuredGrids (for aero analysis) or Watertight PolyData (for booleans).
    """
    def __init__(self, chord_res=30, span_res=15, fuselage_radial_res=36, fuselage_long_res=50):
        self.chord_res = chord_res           # Panels wrapping around airfoil
        self.span_res = span_res             # Panels between ribs
        self.fus_rad_res = fuselage_radial_res # Panels around fuselage ring
        self.fus_long_res = fuselage_long_res  # Panels along fuselage length

    def mesh_vehicle(self, vehicle: Vehicle, solid: bool = False) -> pv.MultiBlock:
        """
        Main entry point.
        """
        parts = pv.MultiBlock()
        
        # 1. Mesh Lifting Surfaces
        for surface in vehicle.surfaces:
            # Generate right-hand side
            mesh = self._mesh_surface(surface, solid=solid)
            parts.append(mesh, name=surface.name)
            
            # Generate left-hand side if mirrored
            if surface.mirrored:
                if solid:
                    mirrored_mesh = mesh.copy()
                    mirrored_mesh.reflect((0, 1, 0), point=(0, 0, 0), inplace=True)
                    # For solids, reflection turns them inside-out. Flip faces to fix.
                    mirrored_mesh.flip_faces(inplace=True)
                else:
                    mirrored_mesh = mesh.copy()
                    mirrored_mesh.points[:, 1] *= -1 
                    # For structured grids, we need to flip winding to fix normals
                    # (This logic is usually handled in the view, but here for completeness)
                    
                parts.append(mirrored_mesh, name=f"{surface.name}_Mirror")
        
        # 2. Mesh Fuselage
        if vehicle.fuselage:
            fus_mesh = self._mesh_fuselage(vehicle.fuselage, solid=solid)
            parts.append(fus_mesh, name=vehicle.fuselage.name)
            
        return parts

    def _mesh_fuselage(self, fuselage: Fuselage, solid: bool = False):
        """ Generates a body of revolution. """
        profile = fuselage.profile # (x, radius)
        
        # Interpolate profile
        x_sparse, r_sparse = profile[:, 0], profile[:, 1]
        x_dense = np.linspace(x_sparse[0], x_sparse[-1], self.fus_long_res)
        r_dense = np.interp(x_dense, x_sparse, r_sparse)
        
        # Create cylindrical grid
        theta = np.linspace(0, 2 * np.pi, self.fus_rad_res)
        
        T, _ = np.meshgrid(theta, x_dense) 
        X = np.tile(x_dense[:, np.newaxis], (1, self.fus_rad_res))
        R = np.tile(r_dense[:, np.newaxis], (1, self.fus_rad_res))
        
        Y = R * np.cos(T)
        Z = R * np.sin(T)
        
        grid_points = np.column_stack((X.flatten(), Y.flatten(), Z.flatten()))
        grid = pv.StructuredGrid()
        grid.points = grid_points
        grid.dimensions = [self.fus_rad_res, self.fus_long_res, 1]
        
        if hasattr(fuselage, 'position'):
            grid.translate(fuselage.position, inplace=True)
            
        if not solid:
            return grid
        
        # --- SOLID CAPPING ---
        poly = grid.extract_surface()
        
        # Cap Front (if open)
        if r_dense[0] > 1e-6:
            
            front_ring = grid.points[:self.fus_rad_res]
            poly = self._add_cap(poly, front_ring, flip=True)

        # Cap Back (if open)
        if r_dense[-1] > 1e-6:
            back_ring = grid.points[-self.fus_rad_res:]
            poly = self._add_cap(poly, back_ring, flip=False)

        return poly.triangulate().clean()

    def _mesh_surface(self, surface: LiftingSurface, solid: bool = False):
        """ Lofts a wing between its defined stations. """
        all_points = []
        stations = surface.stations
        
        for i in range(len(stations) - 1):
            st_in = stations[i]
            st_out = stations[i+1]
            segment_points = self._loft_segment(st_in, st_out)
            
            if i > 0:
                segment_points = segment_points[1:, :, :] 
            all_points.append(segment_points)
            
        grid_points = np.concatenate(all_points, axis=0)
        n_span, n_chord, _ = grid_points.shape
        
        grid = pv.StructuredGrid()
        grid.points = grid_points.reshape(-1, 3)
        grid.dimensions = [n_chord, n_span, 1] 
        
        self._transform_grid(grid, surface)
        
        if not solid:
            return grid

        # --- SOLID CAPPING LOGIC ---
        poly = grid.extract_surface()
        
        # 1. Cap Root? (Span index 0)
        # Check if Root is on the Symmetry Plane (Y=0)
        # We calculate the average Y of the root chord.
        # n_chord is the number of points in one airfoil section.
        root_pts = grid.points[:n_chord]
        root_y_avg = np.mean(root_pts[:, 1])
        
        # TOLERANCE CHECK:
        # If the root is basically at Y=0, we leave it OPEN.
        # This ensures that when mirrored, the two halves connect seamlessly.
        if abs(root_y_avg) > 1e-3:
             #  - Only added if offset from center
             poly = self._add_cap(poly, root_pts, flip=True)

        # 2. Cap Tip (Always cap the tip)
        tip_pts = grid.points[-n_chord:]
        poly = self._add_cap(poly, tip_pts, flip=False)

        return poly.triangulate().clean()

    def _add_cap(self, poly_body, ring_points, flip=False):
        """ Helper: Creates a polygon face from a ring of points. """
        n_pts = len(ring_points)
        cap = pv.PolyData(ring_points)
        indices = np.arange(n_pts)
        if flip:
            indices = indices[::-1]
        face = np.hstack([[n_pts], indices])
        cap.faces = face
        return poly_body + cap

    def _loft_segment(self, st1, st2):
        """ Interpolates linearly between two WingStations. """
        af1 = self._get_airfoil_coords(st1)
        af2 = self._get_airfoil_coords(st2)
        
        p1 = self._position_profile(af1, st1)
        p2 = self._position_profile(af2, st2)
        
        t = np.linspace(0, 1, self.span_res).reshape(-1, 1, 1)
        
        p1_exp = p1[np.newaxis, :, :]
        p2_exp = p2[np.newaxis, :, :]
        
        return (1 - t) * p1_exp + t * p2_exp

    def _get_airfoil_coords(self, station):
        """ Generates NACA 4-digit coordinates. """
        m, p, t_max, r = station.m, station.p, station.t, station.r
        
        beta = np.linspace(0, np.pi, self.chord_res)
        x = (1 - np.cos(beta)) / 2 
        
        term5 = -0.1015
        yt = 5 * t_max * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 + term5 * x**4)
        yt[-1] = 0.0
        
        yc = np.zeros_like(x)
        dyc_dx = np.zeros_like(x)
        if m > 0 and p > 0:
            mask1 = x <= p
            mask2 = x > p
            yc[mask1] = (m / p**2) * (2 * p * x[mask1] - x[mask1]**2)
            dyc_dx[mask1] = (2 * m / p**2) * (p - x[mask1])
            yc[mask2] = (m / (1 - p)**2) * ((1 - 2 * p) + 2 * p * x[mask2] - x[mask2]**2)
            dyc_dx[mask2] = (2 * m / (1 - p)**2) * (p - x[mask2])
            
        if r != 0:
             yc += r * (x**3 - x**2) * 4.0
        
        theta = np.arctan(dyc_dx)
        
        xu = x - yt * np.sin(theta)
        zu = yc + yt * np.cos(theta)
        xl = x + yt * np.sin(theta)
        zl = yc - yt * np.cos(theta)
        
        x_loop = np.concatenate([xu[::-1], xl[1:]])
        z_loop = np.concatenate([zu[::-1], zl[1:]])
        
        # Force TE closure
        x_te = (x_loop[0] + x_loop[-1]) / 2
        z_te = (z_loop[0] + z_loop[-1]) / 2
        x_loop[0] = x_loop[-1] = x_te
        z_loop[0] = z_loop[-1] = z_te
        
        coords = np.zeros((len(x_loop), 3))
        coords[:, 0] = x_loop
        coords[:, 2] = z_loop
        return coords

    def _position_profile(self, coords, station):
        """ Applies Scaling, Twist, and Translation. """
        new_coords = coords * station.chord
        
        theta = np.radians(-station.twist)
        c, s = np.cos(theta), np.sin(theta)
        x_vals = new_coords[:, 0]
        z_vals = new_coords[:, 2]
        
        new_coords[:, 0] = x_vals * c - z_vals * s
        new_coords[:, 2] = x_vals * s + z_vals * c
        
        new_coords[:, 0] += station.x
        new_coords[:, 1] += station.y
        new_coords[:, 2] += station.z
        return new_coords

    def _transform_grid(self, grid, surface):
        """ Applies global rigid body transformations. """
        if hasattr(surface, 'orientation'):
            grid.rotate_x(surface.orientation[0], inplace=True)
            grid.rotate_y(surface.orientation[1], inplace=True)
            grid.rotate_z(surface.orientation[2], inplace=True)
        if hasattr(surface, 'position'):
            grid.translate(surface.position, inplace=True)