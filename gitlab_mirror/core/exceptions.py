"""
Custom exceptions for the GitLab mirroring project.

This module provides a hierarchy of exceptions used throughout the project.
"""

class MirrorError(Exception):
    """Base exception for mirroring operations."""

class ConfigError(MirrorError):
    """Configuration related errors."""

class ApiError(MirrorError):
    """GitLab API related errors."""

class UserMigrationError(MirrorError):
    """User migration related errors."""
