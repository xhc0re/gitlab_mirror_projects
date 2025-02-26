"""
Command-line implementation for the mirror command.

This module provides the CLI command for mirroring GitLab projects between instances.
It preserves the project structure or maps projects to new group paths as specified
in a CSV file.
"""

import logging
import sys
import traceback
from pathlib import Path

from pydantic import SecretStr

from gitlab_mirror.core.config import GitLabConfig, MirrorConfig
from gitlab_mirror.core.exceptions import ConfigError, MirrorError
from gitlab_mirror.core.mirror import MirrorService

logger = logging.getLogger(__name__)


def mirror_command(
    source_url: str,
    source_token: str,
    target_url: str,
    target_token: str,
    projects_file: str,
    assign_users: bool = False,
) -> None:
    """
    Mirror GitLab projects from source to target instance.

    This function copies projects from the source GitLab instance to the target instance
    and sets up push mirroring to keep them in sync. Projects will be created in the target
    instance if they don't exist, and push mirrors will be configured in the source
    to keep the repositories synchronized.

    CSV file format:
        First column: Source project path (e.g., "group/project")
        Second column: Target group path (optional)

    Target mapping behavior:
        - If second column is empty: preserve original group structure
        - If second column has value: place project in the specified target group

    Examples:
        group1/project1,newgroup1    -> Creates in newgroup1/project1
        group2/subgroup1/project2,   -> Creates in group2/subgroup1/project2 (preserved)
        group3/project3,othergroup   -> Creates in othergroup/project3

    Args:
        source_url: URL of the source GitLab instance (e.g., "https://gitlab.source.com")
        source_token: API token for the source GitLab instance with read/API access
        target_url: URL of the target GitLab instance (e.g., "https://gitlab.target.com")
        target_token: API token for the target GitLab instance with read/write/API access
        projects_file: Path to CSV file with project mappings
        assign_users: Whether to assign users from source to target groups

    Returns:
        None

    Raises:
        ConfigError: If configuration is invalid
        MirrorError: If mirror operation fails
        Exception: For unexpected errors

    Exit codes:
        0 - Success
        1 - Configuration error
        2 - Mirror operation error
        3 - Unexpected error
    """
    # Print initialization message
    print("Initializing GitLab mirror with:")
    print(f"  Source: {source_url}")
    print(f"  Target: {target_url}")
    print(f"  Projects file: {projects_file}")
    print(f"  Assign users: {assign_users}")

    try:
        config = MirrorConfig(
            source=GitLabConfig(url=source_url, token=SecretStr(source_token)),
            target=GitLabConfig(url=target_url, token=SecretStr(target_token)),
            projects_file=Path(projects_file),
            assign_users=assign_users,
        )

        service = MirrorService(config)
        success, failures = service.mirror_all_projects()

        print("\n===== MIRROR SUMMARY =====")
        print(f"Total projects: {success + failures}")
        print(f"Successfully mirrored: {success}")
        print(f"Failed: {failures}")

        if failures > 0:
            print("\nCheck logs for details on failures.")

    except ConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except MirrorError as e:
        print(f"Mirror operation failed: {e}")
        sys.exit(2)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(3)
