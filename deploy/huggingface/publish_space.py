"""Publish the Streamlit app to a Hugging Face Space (used by .github/workflows/deploy-space.yml).

Needs HF_TOKEN (write token) and HF_SPACE ("user/space-name"). Creates the Space if needed,
uploads only what the app needs, and stores OPENAI_API_KEY as a Space secret when given.
"""
from pathlib import Path
import os
import shutil
import tempfile

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ["Code", "data", ".streamlit", "streamlit_app.py", "requirements.txt"]


def main() -> None:
    token, space = os.environ["HF_TOKEN"], os.environ["HF_SPACE"]
    api = HfApi(token=token)
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder)
        for name in INCLUDE:
            source = ROOT / name
            if source.is_dir():
                shutil.copytree(source, target / name,
                                ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"))
            else:
                shutil.copy2(source, target / name)
        shutil.copy2(ROOT / "deploy" / "huggingface" / "Dockerfile", target / "Dockerfile")
        shutil.copy2(ROOT / "deploy" / "huggingface" / "README.md", target / "README.md")
        api.upload_folder(folder_path=str(target), repo_id=space, repo_type="space",
                          commit_message="Deploy Course Compass from GitHub")
    key = os.getenv("OPENAI_API_KEY")
    if key:
        api.add_space_secret(space, "OPENAI_API_KEY", key)
    for name, value in (("DAILY_BUDGET_USD", os.getenv("DAILY_BUDGET_USD", "2")),):
        api.add_space_variable(space, name, value)
    print(f"Deployed: https://huggingface.co/spaces/{space}")


if __name__ == "__main__":
    main()
