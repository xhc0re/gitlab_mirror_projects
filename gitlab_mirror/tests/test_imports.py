"""
Basic tests to verify that imports work correctly in the project.
"""

import pytest

def test_core_imports():
    """Test that core modules can be imported."""
    from gitlab_mirror.core import exceptions, config
    from gitlab_mirror.core.exceptions import MirrorError, ConfigError, ApiError
    from gitlab_mirror.core.config import GitLabConfig, MirrorConfig, get_env_variable
    
    assert True, "Core imports successful"

def test_utils_imports():
    """Test that utility modules can be imported."""
    from gitlab_mirror.utils import verify, trigger, update
    from gitlab_mirror.utils.verify import MirrorVerifier
    from gitlab_mirror.utils.trigger import process_file
    from gitlab_mirror.utils.update import update_mirrors
    
    assert True, "Utils imports successful"

def test_cli_imports():
    """Test that CLI modules can be imported."""
    from gitlab_mirror.cli import main
    from gitlab_mirror.cli.commands import mirror_command
    
    assert True, "CLI imports successful"

if __name__ == "__main__":
    # Run tests directly when file is executed
    test_core_imports()
    test_utils_imports()
    test_cli_imports()
    print("All import tests passed!")