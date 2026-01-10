"""
Process individual issue files from the incoming folder.

Handles validation, processing, and file movement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Config
from ..issue_sources import FileIssueSource
from ..logging_setup import get_pipeline_logger
from ..models import Issue
from ..pipeline.run_once import run_pipeline, save_result
from ..util.fs import atomic_move, get_timestamped_filename, ensure_dirs
from ..util.json_schema import IssueValidationError


def process_issue_file(
    file_path: Path,
    config: Config,
    write_dev_files: bool = False,
) -> Optional[Path]:
    """Process a single issue file.

    1. Validates the issue schema
    2. Moves file to processed/ (or processed/invalid/ on error)
    3. Runs the pipeline
    4. Saves result to outgoing/

    Args:
        file_path: Path to the issue JSON file.
        config: Application configuration.
        write_dev_files: Whether to write dev files to disk.

    Returns:
        Path to the output result file, or None on failure.
    """
    logger = get_pipeline_logger()

    logger.info(f"Processing file: {file_path.name}")

    # Ensure directories exist
    ensure_dirs(
        config.processed_dir,
        config.processed_dir / "invalid",
        config.outgoing_dir,
    )

    # Try to load and validate the issue
    try:
        issue = FileIssueSource.from_path(file_path)

    except IssueValidationError as e:
        # Invalid schema - move to invalid folder
        logger.warning(f"Invalid issue schema: {e}")
        for error in e.errors:
            logger.warning(f"  - {error}")

        _move_to_invalid(file_path, config)
        return None

    except Exception as e:
        # Other loading error
        logger.error(f"Failed to load issue: {e}")
        _move_to_invalid(file_path, config)
        return None

    # Move to processed (before running pipeline to prevent reprocessing)
    processed_name = get_timestamped_filename(file_path.stem)
    processed_path = atomic_move(file_path, config.processed_dir, processed_name)
    logger.file_operation("Moved to processed", str(processed_path))

    # Run the pipeline
    try:
        result = run_pipeline(
            issue=issue,
            config=config,
            source_file=str(processed_path),
        )

        # Save result
        output_path = save_result(
            result=result,
            output_dir=config.outgoing_dir,
            write_files=write_dev_files,
        )

        # Log completion
        logger.complete_run(
            run_id=result.run_id,
            issue_id=result.issue.issue_id,
            verdict=result.qa.verdict.value,
            output_file=str(output_path),
        )

        return output_path

    except Exception as e:
        logger.error(f"Pipeline failed for {issue.issue_id}: {e}", e)
        return None


def _move_to_invalid(file_path: Path, config: Config) -> Path:
    """Move an invalid file to the invalid subfolder.

    Args:
        file_path: Path to the invalid file.
        config: Application configuration.

    Returns:
        Path to the moved file.
    """
    logger = get_pipeline_logger()

    invalid_dir = config.processed_dir / "invalid"
    ensure_dirs(invalid_dir)

    invalid_name = get_timestamped_filename(f"invalid_{file_path.stem}")
    moved_path = atomic_move(file_path, invalid_dir, invalid_name)

    logger.file_operation("Quarantined invalid file", str(moved_path))

    return moved_path
