"""
Configuration module for the GitLab mirroring project.

This module provides configuration classes and validation for the project.
It uses Pydantic for configuration validation and dotenv for loading
environment variables.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import gitlab
from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr, field_validator

from gitlab_mirror.core.exceptions import ConfigError

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class GitLabConfig(BaseModel):
    """Configuration for GitLab connection with validation."""

    url: str
    token: SecretStr

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Validates URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    def get_client(self) -> gitlab.Gitlab:
        """Creates and returns a GitLab client."""
        return gitlab.Gitlab(url=self.url, private_token=self.token.get_secret_value())


class MirrorConfig(BaseModel):
    """Overall configuration for the mirroring process."""

    source: GitLabConfig
    target: GitLabConfig
    projects_file: Path
    assign_users: bool = False

    @field_validator("projects_file")
    @classmethod
    def validate_projects_file(cls, v):
        """Validates integrity of projects file"""
        if not v.exists():
            raise ValueError(f"Projects file does not exist: {v}")
        return v


def get_env_variable(name: str, required: bool = False) -> Optional[str]:
    """
    Retrieve environment variable. Exit if required and missing.

    Args:
        name: Name of the environment variable
        required: Whether the variable is required

    Returns:
        Value of the environment variable or None if not required and not found

    Raises:
        ConfigError: If the variable is required but not found
    """
    value = os.getenv(name)

    if required and not value:
        logger.error("Missing required environment variable: %s", name)
        raise ConfigError(f"Missing required environment variable: {name}")

    return value


def load_config_from_env() -> MirrorConfig:
    """
    Load configuration from environment variables.

    Returns:
        MirrorConfig object with validated configuration

    Raises:
        ConfigError: If any required configuration is missing or invalid
    """
    try:
        source_url = get_env_variable("SOURCE_GITLAB_URL", required=True)
        source_token = get_env_variable("SOURCE_GITLAB_TOKEN", required=True)
        target_url = get_env_variable("TARGET_GITLAB_URL", required=True)
        target_token = get_env_variable("TARGET_GITLAB_TOKEN", required=True)
        projects_file_str = get_env_variable("PROJECTS_FILE", required=True)
        assign_users_str = get_env_variable("ASSIGN_USERS_TO_GROUPS", required=False)

        # Convert assign_users_str to bool
        assign_users = False
        if assign_users_str:
            assign_users = assign_users_str.lower() in ("true", "yes", "1")

        # Validate projects_file
        if not projects_file_str:
            raise ConfigError("PROJECTS_FILE environment variable is empty")

        projects_file = Path(projects_file_str)

        config = MirrorConfig(
            source=GitLabConfig(url=source_url, token=SecretStr(source_token)),
            target=GitLabConfig(url=target_url, token=SecretStr(target_token)),
            projects_file=projects_file,
            assign_users=assign_users,
        )

        return config
    except ValueError as e:
        logger.error("Configuration validation error: %s", e)
        raise ConfigError(f"Configuration validation error: {e}") from e
    except Exception as e:
        logger.error("Unexpected error loading configuration: %s", e)
        raise ConfigError(f"Unexpected error loading configuration: {e}") from e
