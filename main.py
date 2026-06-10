import sys
# pyrefly: ignore [missing-import]
from PyQt6 import QtWidgets
from ui import ZaloGroupGUI

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = ZaloGroupGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
