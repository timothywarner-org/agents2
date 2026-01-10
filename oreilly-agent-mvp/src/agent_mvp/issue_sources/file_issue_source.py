"""
File-based issue source for loading issues from JSON files.

This is used for both:
- Loading from the incoming/ folder (watcher mode)
- Loading from specific files (CLI mode)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from ..models import Issue, IssueSource
from ..util.json_schema import validate_issue, IssueValidationError


class FileIssueSource:
    """Load issues from JSON files.

    Validates the issue against the schema and converts to Issue model.
    """

    def __init__(self, file_path: Union[str, Path]):
        """Initialize with a file path.

        Args:
            file_path: Path to the JSON file containing the issue.
        """
        self.file_path = Path(file_path)

    def load(self) -> Issue:
        """Load and validate the issue from the file.

        Returns:
            Validated Issue model.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            IssueValidationError: If the JSON is invalid or doesn't match schema.
            json.JSONDecodeError: If the file isn't valid JSON.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"Issue file not found: {self.file_path}")

        # Read and parse JSON
        with open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate against schema
        validate_issue(data)

        # Ensure source is set (default to manual if from file without explicit source)
        if "source" not in data:
            data["source"] = IssueSource.MANUAL.value

        # Create and return Issue model
        return Issue(**data)

    @classmethod
    def from_path(cls, path: Union[str, Path]) -> Issue:
        """Convenience method to load an issue from a path.

        Args:
            path: Path to the JSON file.

        Returns:
            Validated Issue model.
        """
        return cls(path).load()
