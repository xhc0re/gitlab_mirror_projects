"""
Utility module for updating or removing GitLab push mirrors based on specified criteria.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import gitlab
from gitlab.exceptions import GitlabError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def normalize_mirror_url(url: str) -> str:
    """Normalize mirror URL by removing credentials for comparison."""
    return url.rsplit("@", 1)[-1] if "@" in url else url


def is_mirror_failing(mirror) -> bool:
    """Check if mirror is failing with authentication error."""
    return not mirror.enabled or "HTTP Basic: Access denied" in getattr(mirror, "last_error", "")


def update_mirror_auth(
    mirror, new_token: str, old_domain: str = None, new_domain: str = None
) -> bool:
    """Update mirror authentication by replacing the token and optionally the domain."""
    try:
        base_url = mirror.url.rsplit("@", 1)[-1]
        if old_domain and new_domain:
            base_url = base_url.replace(old_domain, new_domain)

        new_url = f"https://oauth2:{new_token}@{base_url}"
        mirror.url = new_url
        mirror.enabled = True
        mirror.save()
        return True
    except GitlabError as e:
        logger.error("Failed to update mirror authentication: %s", str(e))
        return False


def process_project_mirrors(
    project,
    new_token: str,
    pattern: Optional[str] = None,
    update_failed: bool = False,
    old_domain: Optional[str] = None,
    new_domain: Optional[str] = None,
    dry_run: bool = False,
) -> Tuple[int, int]:
    """Process mirrors in a single project - update or remove based on criteria."""
    mirrors_updated, mirrors_removed = 0, 0

    try:
        mirrors = project.remote_mirrors.list()
        for mirror in mirrors:
            mirror_url = normalize_mirror_url(mirror.url)
            if (pattern and re.search(pattern, mirror_url, re.IGNORECASE)) or (
                update_failed and is_mirror_failing(mirror)
            ):
                logger.info(
                    "Processing mirror in project %s: %s", project.path_with_namespace, mirror_url
                )
                if not dry_run:
                    if update_mirror_auth(mirror, new_token, old_domain, new_domain):
                        mirrors_updated += 1
                    else:
                        try:
                            mirror.delete()
                            mirrors_removed += 1
                            logger.info(
                                "Removed failed mirror from project %s", project.path_with_namespace
                            )
                        except GitlabError as e:
                            logger.error(
                                "Failed to remove mirror from project %s: %s",
                                project.path_with_namespace,
                                str(e),
                            )
                else:
                    logger.info(
                        "[DRY RUN] Would update mirror in project %s", project.path_with_namespace
                    )
                    mirrors_updated += 1
    except GitlabError as e:
        logger.error(
            "Error processing mirrors for project %s: %s", project.path_with_namespace, str(e)
        )

    return mirrors_updated, mirrors_removed


def update_mirrors(
    gitlab_url: str,
    private_token: str,
    new_mirror_token: str,
    pattern: Optional[str] = None,
    update_failed: bool = False,
    old_domain: Optional[str] = None,
    new_domain: Optional[str] = None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Update push mirrors in GitLab projects based on specified criteria."""
    gl = gitlab.Gitlab(url=gitlab_url, private_token=private_token)
    total_updated, total_removed, total_projects = 0, 0, 0
    failed_projects = []

    try:
        projects = gl.projects.list(iterator=True)
        for project in projects:
            total_projects += 1
            try:
                project_with_mirrors = gl.projects.get(project.id)
                updated, removed = process_project_mirrors(
                    project_with_mirrors,
                    new_mirror_token,
                    pattern,
                    update_failed,
                    old_domain,
                    new_domain,
                    dry_run,
                )
                total_updated += updated
                total_removed += removed
            except GitlabError as e:
                logger.error("Error processing project %s: %s", project.path_with_namespace, str(e))
                failed_projects.append({"project": project.path_with_namespace, "error": str(e)})
    except GitlabError as e:
        logger.error("Failed to list projects: %s", str(e))
        return []

    logger.info("\n===== MIRROR UPDATE SUMMARY =====")
    logger.info("Total projects processed: %d", total_projects)
    logger.info("Mirrors updated: %d", total_updated)
    logger.info("Mirrors removed (due to update failure): %d", total_removed)
    logger.info("Failed projects: %d", len(failed_projects))

    if failed_projects:
        logger.info("\nFailed projects details:")
        for fail in failed_projects[:10]:
            logger.info("- %s: %s", fail["project"], fail["error"])

        with open("05-update-failed-projects.csv", "w", encoding="utf-8") as f:
            f.write("project,error\n")
            for fail in failed_projects:
                sanitized_error = fail["error"].replace(",", ";")
                f.write(f"{fail['project']},{sanitized_error}\n")
        logger.info(
            "Exported %d failed projects to 05-update-failed-projects.csv", len(failed_projects)
        )

    return failed_projects
