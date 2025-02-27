"""
Basic tests to verify that imports work correctly in the project.
"""

import pytest  # noqa: F401


def test_core_imports():
    """Test that core modules can be imported."""
    from gitlab_mirror.core import config, exceptions  # noqa: F401
    from gitlab_mirror.core.config import GitLabConfig, MirrorConfig, get_env_variable  # noqa: F401
    from gitlab_mirror.core.exceptions import ApiError, ConfigError, MirrorError  # noqa: F401

    assert True, "Core imports successful"  # nosec B101


def test_utils_imports():
    """Test that utility modules can be imported."""
    from gitlab_mirror.utils import trigger, update, verify  # noqa: F401
    from gitlab_mirror.utils.trigger import process_file  # noqa: F401
    from gitlab_mirror.utils.update import update_mirrors  # noqa: F401
    from gitlab_mirror.utils.verify import MirrorVerifier  # noqa: F401

    assert True, "Utils imports successful"  # nosec B101


def test_cli_imports():
    """Test that CLI modules can be imported."""
    from gitlab_mirror.cli import main  # noqa: F401
    from gitlab_mirror.cli.commands import mirror_command  # noqa: F401

    assert True, "CLI imports successful"  # nosec B101


if __name__ == "__main__":
    # Run tests directly when file is executed
    test_core_imports()
    test_utils_imports()
    test_cli_imports()
    print("All import tests passed!")
