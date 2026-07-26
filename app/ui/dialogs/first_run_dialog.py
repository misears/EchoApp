from PySide6.QtWidgets import QDialog, QPushButton, QTextEdit, QVBoxLayout

from app_paths import PROJECTS_DIR


class FirstRunDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome to Echo Pro")

        layout = QVBoxLayout()

        text = QTextEdit()
        text.setReadOnly(True)
        text.setText(
            "Welcome to Echo Pro!\n\n"
            "This app lets you:\n"
            "- Create and save multitrack projects\n"
            "- Split songs into stems\n"
            "- Record and manage your own voice profiles\n"
            "- Generate music clips with the installed local music backend\n\n"
            "Projects will be stored in:\n"
            f"{PROJECTS_DIR}\n\n"
            "Click 'Close' to start using Echo Pro."
        )
        layout.addWidget(text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)
