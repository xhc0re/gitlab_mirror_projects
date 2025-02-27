"""
Utility module for triggering GitLab push mirror synchronization.
"""

import csv
import logging
import os
import time

import gitlab

from gitlab_mirror.core.config import get_env_variable

# Configure logging
logger = logging.getLogger(__name__)


def trigger_mirror_sync(source_gl, project_path):
    """
    Trigger push mirror synchronization for a project.
    """
    try:
        # Get project by path
        logger.info("Getting project: %s", project_path)
        project = source_gl.projects.get(project_path)

        # Get all mirrors for this project
        logger.info("Listing mirrors for project: %s", project_path)
        mirrors = project.remote_mirrors.list()

        if not mirrors:
            logger.warning("No mirrors found for project %s", project_path)
            return False

        for mirror in mirrors:
            logger.info("Processing mirror %s for %s", mirror.id, project_path)

            # Toggle mirror to force update
            if mirror.enabled:
                # Disable and re-enable mirror
                mirror.enabled = False
                mirror.save()
                time.sleep(1)  # Small delay

                mirror.enabled = True
                mirror.save()
                logger.info("Toggled mirror %s for %s", mirror.id, project_path)
            else:
                # Enable disabled mirror
                mirror.enabled = True
                mirror.save()
                logger.info("Enabled mirror %s for %s", mirror.id, project_path)

            # Try to trigger sync via API
            try:
                url = f"/projects/{project.id}/remote_mirrors/{mirror.id}/sync"
                logger.info("Attempting direct sync trigger for %s", project_path)
                source_gl.http_post(url)
                logger.info("Successfully triggered sync via API for mirror %s", mirror.id)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Could not trigger direct sync (may require Premium): %s", e)
                logger.info("Relying on toggle to trigger sync for %s", project_path)

        return True

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to process mirror for %s: %s", project_path, str(e))
        return False


def process_file(file_path, batch_size=5, delay_between_projects=2):
    """
    Process list of projects from a file.
    """
    # Check if file exists
    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        logger.info("Available files in current directory:")
        for file in os.listdir("."):
            if file.endswith(".csv"):
                logger.info("  - %s", file)
        return

    # Setup GitLab connection
    source_url = get_env_variable("SOURCE_GITLAB_URL", required=True)
    source_token = get_env_variable("SOURCE_GITLAB_TOKEN", required=True)

    source_gl = gitlab.Gitlab(url=source_url, private_token=source_token)

    # Read projects from file
    projects = []
    logger.info("Reading project paths from %s", file_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Try to determine file format
            first_line = f.readline().strip()
            f.seek(0)  # Reset file pointer

            if "," in first_line:  # Assume CSV
                logger.info("Detected CSV format for %s", file_path)
                reader = csv.reader(f)

                # Check if first line is header
                if "source_path" in first_line.lower() or "project" in first_line.lower():
                    logger.info("Skipping header row")
                    next(reader)
                else:
                    f.seek(0)  # Reset if no header

                for row in reader:
                    if row and len(row) >= 1:
                        projects.append(row[0])  # First column is source_path
            else:
                # Plain text file, one project per line
                logger.info("Detected text format for %s", file_path)
                projects = [line.strip() for line in f if line.strip()]
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error reading file %s: %s", file_path, e)
        return

    total = len(projects)
    logger.info("Found %d projects to process", total)

    if total == 0:
        logger.warning("No projects found in %s", file_path)
        return

    success_count = 0
    failed_projects = []

    # Process in batches
    for i in range(0, total, batch_size):
        batch = projects[i : i + batch_size]  # noqa E203
        logger.info(
            "Processing batch %d/%d", i // batch_size + 1, (total + batch_size - 1) // batch_size
        )

        for project_path in batch:
            logger.info("Triggering mirror sync for %s", project_path)
            if trigger_mirror_sync(source_gl, project_path):
                success_count += 1
            else:
                failed_projects.append(project_path)

            # Delay between projects
            time.sleep(delay_between_projects)

        # Longer delay between batches
        if i + batch_size < total:
            batch_delay = 5
            logger.info("Batch complete. Pausing for %d seconds before next batch...", batch_delay)
            time.sleep(batch_delay)

    logger.info("Finished processing: triggered sync for %d/%d projects", success_count, total)

    # Export failed projects to a file for another run if needed
    if failed_projects:
        with open("04-trigger-failed.csv", "w", encoding="utf-8") as f:
            for project in failed_projects:
                f.write(f"{project}\n")
        logger.info(
            "Exported %d failed trigger attempts to 04-trigger-failed.csv", len(failed_projects)
        )
