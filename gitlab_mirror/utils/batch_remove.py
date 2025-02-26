"""
Utility module for removing GitLab push mirrors for projects in a CSV file.
"""

import csv
import logging
from typing import Dict

import gitlab
from gitlab.exceptions import GitlabGetError

from gitlab_mirror.core.exceptions import ConfigError

# Configure logging
logger = logging.getLogger(__name__)


def remove_mirrors_from_csv(
    gitlab_url: str, private_token: str, csv_file: str, dry_run: bool = False
) -> Dict:
    """
    Remove mirrors for projects listed in a CSV file.

    Args:
        gitlab_url: GitLab URL
        private_token: GitLab token
        csv_file: Path to CSV file with project paths
        dry_run: If True, only show what would be removed

    Returns:
        Dictionary with summary statistics
    """
    # Read projects from CSV
    projects = []
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            # Skip header if present
            first_line = next(reader, None)
            if (
                first_line
                and not first_line[0].startswith("#")
                and "source_path" not in str(first_line[0]).lower()
            ):
                projects.append(first_line[0].strip())

            for row in reader:
                if row and len(row) >= 1 and not row[0].startswith("#"):
                    source_path = row[0].strip()
                    projects.append(source_path)

        logger.info("Found %d projects in CSV file", len(projects))
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error reading CSV file: %s", e)
        raise ConfigError(f"Failed to read CSV file: {e}") from e

    # Initialize GitLab client
    gl = gitlab.Gitlab(url=gitlab_url, private_token=private_token)

    mirrors_removed = 0
    would_remove = 0
    processed_projects = 0
    skipped_projects = 0
    failed_projects = []

    for project_path in projects:
        try:
            logger.info("Processing project: %s", project_path)

            # Get project
            try:
                project = gl.projects.get(project_path)
            except GitlabGetError:
                logger.warning("Project not found: %s", project_path)
                skipped_projects += 1
                continue

            processed_projects += 1

            # Get mirrors
            mirrors = project.remote_mirrors.list()

            if not mirrors:
                logger.info("No mirrors found for project: %s", project_path)
                continue

            # Remove mirrors
            for mirror in mirrors:
                if dry_run:
                    logger.info("Would remove mirror %s from %s", mirror.id, project_path)
                    would_remove += 1
                else:
                    try:
                        mirror.delete()
                        mirrors_removed += 1
                        logger.info("Removed mirror %s from %s", mirror.id, project_path)
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.error(
                            "Failed to remove mirror %s from %s: %s", mirror.id, project_path, e
                        )
                        failed_projects.append(
                            {"project": project_path, "mirror_id": mirror.id, "error": str(e)}
                        )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing project %s: %s", project_path, e)
            failed_projects.append({"project": project_path, "error": str(e)})

    # Generate summary
    result = {
        "total_projects_in_csv": len(projects),
        "processed_projects": processed_projects,
        "skipped_projects": skipped_projects,
        "mirrors_removed": mirrors_removed,
        "would_remove": would_remove,
        "failed_projects": failed_projects,
    }

    return result
