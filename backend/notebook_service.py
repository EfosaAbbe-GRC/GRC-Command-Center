import os

class NotebookService:
    def __init__(self, root_path):
        self.root_path = root_path
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)

    def get_structure(self):
        """
        Recursively builds a tree of the notebook directory.
        """
        def build_tree(path):
            tree = []
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        if entry.is_dir():
                            tree.append({
                                "type": "folder",
                                "name": entry.name,
                                "path": entry.name, # Relative name for navigation
                                "children": build_tree(entry.path)
                            })
                        elif entry.is_file() and entry.name.endswith(('.md', '.txt', '.html')):
                            tree.append({
                                "type": "file",
                                "name": entry.name,
                                "path": entry.name, # Relative name
                                "size": entry.stat().st_size
                            })
            except Exception as e:
                print(f"Error scanning {path}: {e}")
            return tree

        return build_tree(self.root_path)

    def get_content(self, file_path):
        """
        Safely reads file content.
        """
        # Security check: Ensure file is within root_path
        abs_root = os.path.abspath(self.root_path)
        abs_file = os.path.abspath(file_path)
        if not abs_file.startswith(abs_root):
            raise ValueError("Access denied: File outside notebook root.")

        with open(abs_file, 'r', encoding='utf-8') as f:
            return f.read()

# Initialize with the standard path
notebook_service = NotebookService(
    root_path=os.path.join(os.path.dirname(__file__), "knowledge_base", "notebooks")
)
