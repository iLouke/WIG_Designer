import sys
import traceback
from PyQt6.QtWidgets import QApplication
from src.gui.designer import PlaneDesigner

def main():
    try:
        app = QApplication(sys.argv)
        window = PlaneDesigner()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()