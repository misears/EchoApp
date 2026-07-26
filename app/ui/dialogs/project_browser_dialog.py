from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QTextEdit, QVBoxLayout

from app_paths import PROJECTS_DIR


class ProjectBrowserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Project from Library")

        layout = QVBoxLayout()

        self.list_box = QTextEdit()
        self.list_box.setReadOnly(True)

        projects = []
        for f in PROJECTS_DIR.glob("*.eproj"):
            projects.append(str(f))
        if projects:
            self.list_box.setText("\n".join(projects))
        else:
            self.list_box.setText("No projects found in:\n" + str(PROJECTS_DIR))

        layout.addWidget(self.list_box)

        self.selected_path = None

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Paste or type full path to project")
        layout.addWidget(self.path_input)

        open_btn = QPushButton("Open this project")
        open_btn.clicked.connect(self.choose_project)
        layout.addWidget(open_btn)

        self.setLayout(layout)

    def choose_project(self):
        text = self.path_input.text().strip()
        if text:
            self.selected_path = text
            self.accept()
