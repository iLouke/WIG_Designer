import numpy as np

def get_rotation_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """
    Calculates the 3x3 rotation matrix for a given Euler angle set (ZYX sequence).
    
    Args:
        roll (float): Rotation around X-axis in degrees.
        pitch (float): Rotation around Y-axis in degrees.
        yaw (float): Rotation around Z-axis in degrees.
        
    Returns:
        np.ndarray: A 3x3 rotation matrix.
    """
    phi, theta, psi = np.radians([roll, pitch, yaw])
    
    # Rotation matrices around individual axes
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(phi), -np.sin(phi)],
        [0, np.sin(phi), np.cos(phi)]
    ])
    
    Ry = np.array([
        [np.cos(theta), 0, np.sin(theta)],
        [0, 1, 0],
        [-np.sin(theta), 0, np.cos(theta)]
    ])
    
    Rz = np.array([
        [np.cos(psi), -np.sin(psi), 0],
        [np.sin(psi), np.cos(psi), 0],
        [0, 0, 1]
    ])
    
    # Combined rotation: Rz * Ry * Rx
    return Rz @ Ry @ Rx