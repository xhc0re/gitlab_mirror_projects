#!/usr/bin/env python
"""Setup script for GitLab mirror environment."""

import os
import shutil
import sys
from pathlib import Path


def create_env_file():
    """Create .env file if it doesn't exist."""
    env_path = Path(".env")
    if env_path.exists():
        print(".env file already exists.")
        overwrite = input("Do you want to overwrite it? (y/n): ").lower()
        if overwrite != "y":
            return

    # Check if .env.example exists
    example_path = Path(".env.example")
    if example_path.exists():
        # Copy example as starting point
        shutil.copy(example_path, env_path)
        print(f"Created .env file from .env.example at {env_path.absolute()}")
    else:
        # Create from scratch
        print("Creating new .env file...")

        source_url = input("SOURCE_GITLAB_URL: ")
        source_token = input("SOURCE_GITLAB_TOKEN: ")
        target_url = input("TARGET_GITLAB_URL: ")
        target_token = input("TARGET_GITLAB_TOKEN: ")
        projects_file = input("PROJECTS_FILE [projects.csv]: ") or "projects.csv"
        assign_users = input("ASSIGN_USERS_TO_GROUPS [true/false]: ").lower() in (
            "true",
            "yes",
            "1",
            "y",
            "",
        )

        with open(env_path, "w") as f:
            f.write(f'SOURCE_GITLAB_URL="{source_url}"\n')
            f.write(f'SOURCE_GITLAB_TOKEN="{source_token}"\n')
            f.write(f'TARGET_GITLAB_URL="{target_url}"\n')
            f.write(f'TARGET_GITLAB_TOKEN="{target_token}"\n')
            f.write(f'PROJECTS_FILE="{projects_file}"\n')
            f.write(f'ASSIGN_USERS_TO_GROUPS={"true" if assign_users else "false"}\n')

        print(f".env file created at {env_path.absolute()}")


def create_example_projects_file():
    """Create an example projects.csv file if it doesn't exist."""
    file_path = Path("projects.example.csv")
    if file_path.exists():
        print("projects.example.csv already exists.")
        return

    with open(file_path, "w") as f:
        f.write("# Source project path, Target group path\n")
        f.write("group1/project1,newgroup1\n")
        f.write("group2/subgroup1/project2,\n")
        f.write("group3/project3,othergroup\n")

    print(f"Created example projects file at {file_path.absolute()}")


def check_dependencies():
    """Check if required Python packages are installed."""
    try:
        import gitlab
        import pandas
        import pydantic
        from dotenv import load_dotenv
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install required dependencies:")
        print("pip install -r requirements.txt")
        return False

    return True


def setup():
    """Run the setup process."""
    print("Setting up GitLab Mirror environment...\n")

    # Check dependencies
    if not check_dependencies():
        return

    # Create .env file
    create_env_file()

    # Create example projects file
    create_example_projects_file()

    print("\nSetup complete!")
    print("Next steps:")
    print("1. Edit .env file if needed")
    print("2. Create your projects.csv file (or use the example)")
    print("3. Run the tool: gitlab-mirror")


if __name__ == "__main__":
    setup()
