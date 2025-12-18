# PhD WIG Design Tool

A parametric geometry modeling and meshing tool specifically designed for Wing-in-Ground (WIG) effect vehicles.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green)
![PyVista](https://img.shields.io/badge/Visualization-PyVista-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## ✈️ Overview

This application serves as a bridge between parametric design and aerodynamic analysis. It allows users to define WIG vehicle components (wings, fuselages) using engineering parameters (chord, span, NACA profiles) and generates high-quality structured meshes or watertight solids for CFD/potential flow analysis.

**Key Features:**

- **Parametric Design:** Define wings using rib stations with adjustable chord, twist, and NACA 4-digit airfoil parameters (Camber, Thickness).
- **Real-time Visualization:** \* Professional Quad-View CAD interface (Top, Front, Side, Isometric).
  - Real-time adjustments of geometry.
  - Visualization of Surface Normals and Local Coordinate Systems.
- **Advanced Meshing:** \* Structured grid generation for aerodynamic panels.
  - Watertight Boolean Unions for solid modeling.
  - Automatic mirroring and symmetry handling.
- **Export:** Export geometry to `.OBJ` format for compatibility with external solvers (XFLR5, OpenFOAM, etc.).

## 📸 Screenshots

## 🛠️ Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Setup

1.  **Clone the repository**

    ```bash
    git clone [https://github.com/YOUR_USERNAME/WIG_Designer.git](https://github.com/YOUR_USERNAME/WIG_Designer.git)
    cd WIG_Designer
    ```

2.  **Create a Virtual Environment**

    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # Linux/Mac
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 Usage

To launch the application:

```bash
python main.py
```
