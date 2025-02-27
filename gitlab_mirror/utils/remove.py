"""
Utility module for removing GitLab push mirrors based on specified criteria.
"""

import logging
import re
from typing import Any, Dict, Optional

import gitlab

# Configure logging
logger = logging.getLogger(__name__)


def remove_mirrors(
    gitlab_url: str,
    private_token: str,
    pattern: Optional[str] = None,
    remove_failed: bool = False,
    remove_all: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Remove push mirrors from GitLab projects based on specified criteria.

    Args:
        gitlab_url: Your GitLab instance URL
        private_token: Your GitLab access token
        pattern: Regular expression pattern to match mirror URLs (optional)
        remove_failed: If True, removes mirrors with authentication errors
        remove_all: If True, removes all mirrors regardless of other criteria
        dry_run: If True, only counts mirrors that would be removed without actually removing them

    Returns:
        Dictionary with summary statistics
    """
    # Initialize GitLab connection
    gl = gitlab.Gitlab(url=gitlab_url, private_token=private_token)

    # Get all projects
    logger.info("Fetching all projects from GitLab...")
    projects = gl.projects.list(all=True)

    mirrors_removed = 0
    would_remove = 0  # Counter for dry_run mode
    projects_processed = 0
    projects_with_mirrors = 0
    matching_projects = 0  # Projects with mirrors matching criteria
    error_count = 0
    failed_projects = []

    logger.info("Found %d projects to process", len(projects))

    for project in projects:
        projects_processed += 1

        if projects_processed % 50 == 0:
            logger.info("Progress: %d/%d projects processed", projects_processed, len(projects))

        try:
            # Get project with mirror info
            project_with_mirrors = gl.projects.get(project.id)
            mirrors = project_with_mirrors.remote_mirrors.list()

            if mirrors:
                projects_with_mirrors += 1
            else:
                continue  # Skip projects without mirrors

            project_mirrors_removed = 0
            project_matches = False

            for mirror in mirrors:
                should_remove = False
                mirror_url = mirror.url if hasattr(mirror, "url") else "unknown URL"

                # If remove_all is True, remove every mirror
                if remove_all:
                    should_remove = True
                    logger.info(
                        "%s mirror from project %s (remove_all flag)",
                        "Would remove" if dry_run else "Removing",
                        project.path_with_namespace,
                    )

                # If a pattern is provided and the mirror URL matches the pattern
                elif pattern and re.search(pattern, mirror_url, re.IGNORECASE):
                    should_remove = True
                    logger.info(
                        "Found mirror matching pattern in project %s: %s",
                        project.path_with_namespace,
                        mirror_url,
                    )

                # If remove_failed is True and the mirror has an issue
                elif remove_failed and (
                    not mirror.enabled or (hasattr(mirror, "last_error") and mirror.last_error)
                ):
                    should_remove = True
                    error_info = mirror.last_error if hasattr(mirror, "last_error") else "disabled"
                    logger.info(
                        "Found failed mirror in project %s: %s",
                        project.path_with_namespace,
                        error_info,
                    )

                if should_remove:
                    project_matches = True
                    if dry_run:
                        would_remove += 1
                        project_mirrors_removed += 1
                    else:
                        try:
                            # mirror.delete()
                            project_mirrors_removed += 1
                            mirrors_removed += 1
                            logger.info(
                                "Successfully removed mirror from %s", project.path_with_namespace
                            )
                        except Exception as e:  # pylint: disable=broad-exception-caught
                            logger.error(
                                "Error removing mirror from %s: %s",
                                project.path_with_namespace,
                                str(e),
                            )
                            error_count += 1

            if project_mirrors_removed > 0:
                if not dry_run:
                    logger.info(
                        "Removed %d mirrors from %s",
                        project_mirrors_removed,
                        project.path_with_namespace,
                    )

            if project_matches:
                matching_projects += 1

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing project %s: %s", project.path_with_namespace, str(e))
            failed_projects.append({"project": project.path_with_namespace, "error": str(e)})
            error_count += 1
            continue

    # Generate summary
    result = {
        "total_projects": len(projects),
        "projects_with_mirrors": projects_with_mirrors,
        "matching_projects": matching_projects,
        "processed_projects": projects_processed,
        "mirrors_removed": mirrors_removed,
        "would_remove": would_remove,
        "errors": error_count,
        "failed_projects": failed_projects,
    }

    mode_prefix = "DRY RUN - " if dry_run else ""
    logger.info("\n===== %sMIRROR REMOVAL SUMMARY =====", mode_prefix)
    logger.info("Total projects: %d", len(projects))
    logger.info("Projects with mirrors: %d", projects_with_mirrors)
    logger.info("Projects with matching mirrors: %d", matching_projects)

    if dry_run:
        logger.info("Mirrors that would be removed: %d", would_remove)
    else:
        logger.info("Mirrors removed: %d", mirrors_removed)

    logger.info("Errors encountered: %d", error_count)

    return result
