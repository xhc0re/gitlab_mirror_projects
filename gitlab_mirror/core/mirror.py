"""
Core module for GitLab mirroring functionality.
Provides abstraction for GitLab connections and mirroring operations.
"""

import csv
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from gitlab.exceptions import GitlabCreateError, GitlabGetError, GitlabHttpError, GitlabListError

from gitlab_mirror.core.config import GitLabConfig, MirrorConfig
from gitlab_mirror.core.exceptions import ApiError, ConfigError

# Configure logging
logger = logging.getLogger(__name__)


# Core data models
@dataclass
class ProjectMapping:
    """Represents a mapping between source and target projects."""

    source_path: str
    target_group: str

    @property
    def project_name(self) -> str:
        """Extract project name from source path."""
        return self.source_path.split("/")[-1]

    @property
    def source_group(self) -> str:
        """Extract source group path."""
        if "/" in self.source_path:
            return self.source_path.rsplit("/", 1)[0]
        return ""

    @property
    def should_preserve_structure(self) -> bool:
        """
        Determine if we should preserve the original group structure.
        This is true when target_group is empty.
        """
        return not self.target_group

    @property
    def target_path(self) -> str:
        """
        Construct the full target path.
        - If target_group is empty, use source structure as-is
        - Otherwise use the specified target group
        """
        if self.should_preserve_structure:
            # No target group specified, use source structure as-is
            return self.source_path
        else:
            # Use specified target group
            return "%s/%s" % (self.target_group, self.project_name)


class GitLabConnector:
    """Handles connection and operations with GitLab API."""

    def __init__(self, config: GitLabConfig):
        """Initialize with GitLab configuration."""
        self.config = config
        self.client = config.get_client()

    def get_project(self, project_path: str) -> Any:
        """Get a project by its path."""
        try:
            return self.client.projects.get(project_path)
        except GitlabGetError as e:
            logger.error("Failed to get project %s: %s", project_path, e)
            raise ApiError(f"Failed to get project {project_path}") from e

    def get_group(self, group_path: str) -> Any:
        """Get a group by its path."""
        try:
            logger.debug("Attempting to get group with path: %s", group_path)
            return self.client.groups.get(group_path)
        except GitlabGetError as e:
            logger.info("Failed to get group %s: %s, creating", group_path, e)
            return None

    def create_group(self, name: str, path: str, parent_id: Optional[int] = None) -> Any:
        """Create a new group."""
        try:
            return self.client.groups.create({"name": name, "path": path, "parent_id": parent_id})
        except GitlabCreateError as e:
            logger.error("Failed to create group %s: %s", path, e)
            raise ApiError(f"Failed to create group {path}") from e

    def create_project(self, name: str, namespace_id: int) -> Any:
        """Create a new project."""
        try:
            return self.client.projects.create(
                {
                    "name": name,
                    "path": name,
                    "namespace_id": namespace_id,
                    "visibility": "private",
                    "initialize_with_readme": False,
                }
            )
        except GitlabCreateError as e:
            logger.error("Failed to create project %s: %s", name, e)
            raise ApiError(f"Failed to create project {name}") from e

    def normalize_mirror_url(self, url: str) -> str:
        """Normalize mirror URL by removing credentials for comparison."""
        if "@" in url:
            return url.split("@", 1)[-1]
        return url


class MirrorService:
    """Core service for mirroring projects between GitLab instances."""

    def __init__(self, config: MirrorConfig):
        """Initialize with mirror configuration."""
        self.config = config
        self.source = GitLabConnector(config.source)
        self.target = GitLabConnector(config.target)
        self.group_cache: Dict[str, int] = {}
        self.errors: List[Dict[str, str]] = []

    def load_project_mappings(self) -> List[ProjectMapping]:
        """
        Load project mappings from CSV file.

        The CSV file can have the following formats:
        1. source_path,target_group - Standard mapping to a specific target group
        2. source_path - No target group means preserve original structure

        Returns:
            List of ProjectMapping objects.
        """
        mappings = []

        try:
            # First try reading with pandas
            try:
                df = pd.read_csv(self.config.projects_file, header=None)

                for _, row in df.iterrows():
                    # Get source path from first column
                    source_path = row[0].strip()

                    # Default empty target group
                    target_group = ""

                    # Check for target group in second column
                    if len(row) >= 2 and pd.notna(row[1]):
                        target_group = row[1].strip()

                    mappings.append(
                        ProjectMapping(source_path=source_path, target_group=target_group)
                    )

            # Fallback to manual CSV parsing if pandas fails
            except OSError as pandas_error:
                logger.warning("Pandas parsing failed, fallback to manual CSV: %s", pandas_error)
                with open(self.config.projects_file, "r", encoding="utf-8") as file:
                    reader = csv.reader(file)
                    for row in reader:
                        if row:  # Skip empty rows
                            source_path = row[0].strip()
                            target_group = row[1].strip() if len(row) > 1 else ""

                            mappings.append(
                                ProjectMapping(source_path=source_path, target_group=target_group)
                            )

            if not mappings:
                logger.warning("No project mappings found in the CSV file")

            return mappings

        except Exception as e:
            logger.error("Failed to load project mappings: %s", e)
            raise ConfigError(
                f"Failed to load project mappings from {self.config.projects_file}"
            ) from e

    def ensure_group_exists(self, group_path: str) -> int:
        """Ensure a group exists, creating it if necessary."""
        if not group_path:
            raise ValueError("Group path cannot be empty")

        # Check cache first
        if group_path in self.group_cache:
            return self.group_cache[group_path]

        # Try to find existing group
        existing_group = self.target.get_group(group_path)
        if existing_group:
            self.group_cache[group_path] = existing_group.id
            return existing_group.id

        # Create parent groups recursively if needed
        parent_id = None
        if "/" in group_path:
            parent_path = group_path.rsplit("/", 1)[0]
            parent_id = self.ensure_group_exists(parent_path)

        # Create the group
        group_name = group_path.rsplit("/", 1)[-1]
        new_group = self.target.create_group(name=group_name, path=group_name, parent_id=parent_id)
        self.group_cache[group_path] = new_group.id
        return new_group.id

    def setup_push_mirror(self, source_project, mirror_url: str) -> None:
        """Set up push mirroring for a project."""
        try:
            mirrors = source_project.remote_mirrors.list()

            # Check if mirror already exists
            normalized_url = self.source.normalize_mirror_url(mirror_url)
            if any(self.source.normalize_mirror_url(m.url) == normalized_url for m in mirrors):
                logger.info("Mirror already exists for %s", source_project.path_with_namespace)
                return

            # Create mirror
            source_project.remote_mirrors.create(
                {
                    "url": mirror_url,
                    "enabled": True,
                    "only_protected_branches": False,
                }
            )

            logger.info("Created push mirror for %s", source_project.path_with_namespace)

        except GitlabListError as e:
            logger.error("Failed to list mirrors: %s", e)
            raise ApiError(
                f"Failed to list mirrors for {source_project.path_with_namespace}"
            ) from e
        except GitlabCreateError as e:
            logger.error("Failed to create mirror: %s", e)
            raise ApiError(
                f"Failed to create mirror for {source_project.path_with_namespace}"
            ) from e

    def trigger_mirror_sync(self, project_id: int) -> None:
        """Trigger synchronization for a project's mirrors."""
        try:
            project = self.source.client.projects.get(project_id)
            mirrors = project.remote_mirrors.list()

            for mirror in mirrors:
                try:
                    url = f"/projects/{project_id}/remote_mirrors/{mirror.id}/sync"
                    self.source.client.http_post(url)
                    logger.info("Triggered sync for mirror %s", mirror.id)
                except GitlabHttpError as e:
                    logger.error("Failed to trigger sync for mirror %s: %s", mirror.id, e)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("Unexpected error triggering sync for mirror %s: %s", mirror.id, e)
        except GitlabGetError as e:
            logger.error("Failed to get project %s for mirror sync: %s", project_id, e)
        except GitlabListError as e:
            logger.error("Failed to list mirrors for project %s: %s", project_id, e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Unexpected error in trigger_mirror_sync for project %s: %s", project_id, e
            )

    def mirror_project(self, mapping: ProjectMapping) -> bool:
        """Mirror a single project according to its mapping."""
        try:
            # Get source project
            source_project = self.source.get_project(mapping.source_path)
            logger.info("Found source project: %s", mapping.source_path)

            # Determine the appropriate target group path
            target_group_path = ""
            if mapping.should_preserve_structure:
                # Use source group structure as-is
                target_group_path = mapping.source_group
            else:
                # Use specified target group
                target_group_path = mapping.target_group

            # Dodaj log dla debugowania
            logger.debug("Target group path: %s", target_group_path)

            # Ensure target group exists (if any)
            group_id = None
            if target_group_path:
                group_id = self.ensure_group_exists(target_group_path)

            # Determine final target path
            project_name = mapping.project_name
            target_path = (
                f"{target_group_path}/{project_name}" if target_group_path else project_name
            )

            # Zapisz poprawną ścieżkę do logów i obiektów błędów
            logger.info("Target path will be: %s", target_path)

            # Check if target project exists
            try:
                self.target.get_project(target_path)
                logger.info("Target project already exists: %s", target_path)
            except ApiError:
                if not group_id:
                    logger.error(
                        "Cannot create project without a group. Target group path is empty."
                    )
                    return False

                # Create target project
                self.target.create_project(name=project_name, namespace_id=group_id)
                logger.info("Created target project: %s", target_path)

            # Set up mirroring
            target_domain = self.target.config.url.split("//")[1].split("/")[0]
            mirror_url = f"https://oauth2:{self.target.config.token.get_secret_value()}@{target_domain}/{target_path}.git"

            self.setup_push_mirror(source_project, mirror_url)

            # Trigger initial sync
            self.trigger_mirror_sync(source_project.id)

            return True
        except ApiError as e:
            logger.error("API error mirroring project %s: %s", mapping.source_path, e)
            self.errors.append(
                {
                    "source": mapping.source_path,
                    "target": (
                        mapping.target_path
                        if "mapping_target_path" in locals()
                        else mapping.target_path
                    ),
                    "error_type": "ApiError",
                    "message": str(e),
                }
            )
            return False
        except ValueError as e:
            logger.error("Value error mirroring project %s: %s", mapping.source_path, e)
            self.errors.append(
                {
                    "source": mapping.source_path,
                    "target": (
                        mapping.target_path
                        if "mapping_target_path" in locals()
                        else mapping.target_path
                    ),
                    "error_type": "ValueError",
                    "message": str(e),
                }
            )
            return False
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error mirroring project %s: %s", mapping.source_path, e)
            self.errors.append(
                {
                    "source": mapping.source_path,
                    "target": (
                        mapping.target_path
                        if "mapping_target_path" in locals()
                        else mapping.target_path
                    ),
                    "error_type": "UnexpectedError",
                    "message": str(e),
                }
            )
            return False

    def mirror_all_projects(self) -> Tuple[int, int]:
        """Mirror all projects defined in mappings."""
        mappings = self.load_project_mappings()

        success_count = 0
        failure_count = 0

        for mapping in mappings:
            logger.info(
                "Processing: %s -> %s",
                mapping.source_path,
                mapping.target_group if mapping.target_group else "(preserve structure)",
            )

            if self.mirror_project(mapping):
                success_count += 1
            else:
                failure_count += 1

        logger.info("Mirroring complete. Success: %d, Failures: %d", success_count, failure_count)
        self._print_errors_summary()
        return success_count, failure_count

    def _print_errors_summary(self) -> None:
        """Prints all collected errors in a formatted way."""
        if not self.errors:
            return

        print("\nMirroring Errors Summary:")
        print("=" * 50)
        for idx, error in enumerate(self.errors, 1):
            print(f"Error #{idx}:")
            print(f"  Source Project: {error['source']}")
            print(f"  Target Path:    {error['target']}")
            print(f"  Error Type:     {error['error_type']}")
            print(f"  Message:        {error['message']}")
            print("-" * 50)
        print(f"Total Errors: {len(self.errors)}")
        print("=" * 50 + "\n")
