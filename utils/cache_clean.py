import os
import shutil

project_root = os.path.abspath(".")  # Change this if you want a specific path

deleted = 0
for root, dirs, files in os.walk(project_root):
    for dir_name in dirs:
        if dir_name == "__pycache__":
            full_path = os.path.join(root, dir_name)
            shutil.rmtree(full_path)
            print(f"Deleted: {full_path}")
            deleted += 1

print(f"\n✅ Deleted {deleted} __pycache__ folders.")
