"""
Utility module for verifying GitLab project mirroring status.
"""

import logging
from typing import Tuple

from gitlab_mirror.core.config import GitLabConfig

logger = logging.getLogger(__name__)


def normalize_mirror_url(url: str) -> str:
    """Normalize mirror URL by removing credentials for comparison."""
    if "@" in url:
        return url.split("@", 1)[-1]
    return url


class MirrorVerifier:
    def __init__(self, source_gl: GitLabConfig, target_gl: GitLabConfig, project_mappings):
        """
        Initialize verifier with GitLab connections and project mappings.

        Args:
            source_gl: Source GitLab connection
            target_gl: Target GitLab connection
            project_mappings: List of tuples (source_path, target_group)
        """
        self.source_gl: GitLabConfig = source_gl
        self.target_gl: GitLabConfig = target_gl
        self.project_mappings = project_mappings

        # Cache for GitLab projects to avoid repeated API calls
        self.source_projects_cache = {}
        self.target_projects_cache = {}

        # Results
        self.missing_in_target = []
        self.missing_mirrors = []
        self.failed_mirrors = []
        self.success_count = 0

    def cache_all_projects(self):
        """Cache all projects from both GitLab instances for faster lookups."""
        logger.info("Caching all source projects...")
        source_projects = self.source_gl.get_client().projects.list(iterator=True)
        for project in source_projects:
            self.source_projects_cache[project.path_with_namespace] = project.id

        logger.info("Caching all target projects...")
        target_projects = self.target_gl.get_client().projects.list(iterator=True)
        for project in target_projects:
            self.target_projects_cache[project.path_with_namespace] = project.id

    def get_target_path(self, source_path: str, target_group: str) -> str:
        """
        Convert source project path to target project path based on mapping.

        Args:
            source_path: Source project path (e.g., "group/subgroup/project")
            target_group: Target group path (e.g., "new-group/new-subgroup")

        Returns:
            Target project path (e.g., "new-group/new-subgroup/project")
        """
        if not target_group:
            # Preserve original structure
            return source_path

        project_name = source_path.split("/")[-1]
        return f"{target_group}/{project_name}"

    def check_mirror_exists(self, source_project_id: int, target_path: str) -> Tuple[bool, str]:
        """
        Check if mirror from source to target exists and is working.

        Args:
            source_project_id: ID of source project
            target_path: Path of target project

        Returns:
            Tuple of (mirror_exists, error_message)
        """
        try:
            project = self.source_gl.projects.get(source_project_id)
            mirrors = project.remote_mirrors.list()

            target_domain = self.target_gl.url.split("//")[1].split("/")[0]
            expected_mirror_path = f"{target_domain}/{target_path}.git"

            for mirror in mirrors:
                mirror_url = normalize_mirror_url(mirror.url)
                if expected_mirror_path in mirror_url:
                    # Mirror exists, check if it's working
                    if not mirror.enabled or hasattr(mirror, "last_error") and mirror.last_error:
                        return True, (
                            mirror.last_error
                            if hasattr(mirror, "last_error")
                            else "Mirror is disabled"
                        )
                    return True, ""

            return False, "No mirror configured"

        except Exception as e:
            return False, str(e)

    def verify_all_projects(self):
        """Verify that all projects from mappings are properly mirrored."""
        self.cache_all_projects()
        total = len(self.project_mappings)
        processed = 0
        skipped = 0

        logger.info(f"Starting verification of {total} projects...")

        for index, mapping in enumerate(self.project_mappings):
            source_path = mapping.source_path
            target_group = mapping.target_group
            if index % 50 == 0:
                logger.info(f"Progress: {index}/{total}")

            target_path = self.get_target_path(source_path, target_group)

            # Check if source project exists
            if source_path not in self.source_projects_cache:
                # Skip projects that don't exist in source
                skipped += 1
                continue

            processed += 1

            # Check if target project exists
            if target_path not in self.target_projects_cache:
                self.missing_in_target.append((source_path, target_path, target_group))
                continue

            # Check if mirror exists and is working
            source_id = self.source_projects_cache[source_path]
            mirror_exists, error = self.check_mirror_exists(source_id, target_path)

            if not mirror_exists:
                self.missing_mirrors.append((source_path, target_path, target_group))
            elif error:
                self.failed_mirrors.append((source_path, target_path, error, target_group))
            else:
                self.success_count += 1

        logger.info(f"Processed {processed} projects, skipped {skipped} projects missing in source")

    def print_report(self):
        """Print verification report."""
        total_processed = (
            self.success_count
            + len(self.missing_in_target)
            + len(self.missing_mirrors)
            + len(self.failed_mirrors)
        )

        logger.info("\n===== MIRROR VERIFICATION REPORT =====")
        logger.info(f"Total projects processed: {total_processed}")
        logger.info(f"Successfully mirrored: {self.success_count}")

        if self.missing_in_target:
            logger.warning(f"Projects missing in target ({len(self.missing_in_target)}):")
            for source, target, _ in self.missing_in_target[:10]:
                logger.warning(f"  - {source} -> {target}")
            if len(self.missing_in_target) > 10:
                logger.warning(f"  ... and {len(self.missing_in_target) - 10} more")

        if self.missing_mirrors:
            logger.warning(f"Projects without mirrors ({len(self.missing_mirrors)}):")
            for source, target, _ in self.missing_mirrors[:10]:
                logger.warning(f"  - {source} -> {target}")
            if len(self.missing_mirrors) > 10:
                logger.warning(f"  ... and {len(self.missing_mirrors) - 10} more")

        if self.failed_mirrors:
            logger.warning(f"Projects with failed mirrors ({len(self.failed_mirrors)}):")
            for source, target, error, _ in self.failed_mirrors[:10]:
                logger.warning(f"  - {source} -> {target}: {error}")
            if len(self.failed_mirrors) > 10:
                logger.warning(f"  ... and {len(self.failed_mirrors) - 10} more")

        # Export detailed reports to files if there are issues
        if self.missing_in_target or self.missing_mirrors or self.failed_mirrors:
            self.export_reports()

    def export_reports(self):
        """Export detailed reports to CSV files with numerical prefixes."""
        if self.missing_in_target:
            with open("01-missing-in-target.csv", "w") as f:
                f.write("source_path,target_path\n")
                for source, target, _ in self.missing_in_target:
                    f.write(f"{source},{target}\n")
            logger.info("Exported missing target projects to 01-missing-in-target.csv")

        if self.missing_mirrors:
            with open("02-missing-mirrors.csv", "w") as f:
                f.write("source_path,target_path\n")
                for source, target, _ in self.missing_mirrors:
                    f.write(f"{source},{target}\n")
            logger.info("Exported missing mirrors to 02-missing-mirrors.csv")

        if self.failed_mirrors:
            with open("03-failed-mirrors.csv", "w") as f:
                f.write("source_path,target_path,error\n")
                for source, target, error, _ in self.failed_mirrors:
                    # Replace commas in error message to avoid CSV issues
                    sanitized_error = error.replace(",", ";")
                    f.write(f"{source},{target},{sanitized_error}\n")
            logger.info("Exported failed mirrors to 03-failed-mirrors.csv")

        # Generate fix.csv with the format matching projects.csv
        fix_projects = []

        # Add projects missing in target
        for source_path, _, target_group in self.missing_in_target:
            fix_projects.append((source_path, target_group))

        # Add projects without mirrors
        for source_path, _, target_group in self.missing_mirrors:
            fix_projects.append((source_path, target_group))

        # Add projects with failed mirrors
        for source_path, _, _, target_group in self.failed_mirrors:
            fix_projects.append((source_path, target_group))

        # Remove duplicates while preserving order
        seen = set()
        unique_fix_projects = []
        for item in fix_projects:
            if item not in seen:
                seen.add(item)
                unique_fix_projects.append(item)

        # Write fix.csv
        if unique_fix_projects:
            with open("00-fix.csv", "w") as f:
                for source_path, target_group in unique_fix_projects:
                    f.write(f"{source_path},{target_group}\n")
            logger.info(
                f"Exported {len(unique_fix_projects)} projects to 00-fix.csv in projects.csv format"
            )
