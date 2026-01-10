"""Interactive CLI menu for the O'Reilly Agent MVP."""

import json
import sys
from pathlib import Path
from typing import Optional

from ..config import Config
from ..issue_sources import FileIssueSource
from ..logging_setup import get_pipeline_logger, setup_logging
from ..pipeline.run_once import run_pipeline, save_result

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def display_menu() -> None:
    """Display the main menu options."""
    print("\n" + "=" * 50)
    print("O'Reilly Agent MVP - Interactive Menu")
    print("=" * 50)
    print("\n1. Request an issue from GitHub")
    print("2. Load a mock issue")
    print("3. Start the folder watcher")
    print("4. Start MCP server")
    print("5. Start MCP Inspector (web UI)")
    print("q. Quit")
    print()


def handle_github_issue() -> Optional[Path]:
    """Fetch an issue from GitHub and save to incoming/."""
    from ..integrations.github_issue_fetcher import fetch_github_issue

    print("\n--- GitHub Issue Request ---")
    print("Repository: timothywarner-org/agents2")
    issue_number = input("Enter issue number: ").strip()

    if not issue_number.isdigit():
        print("Error: Issue number must be numeric.")
        return None

    try:
        print(f"\nFetching issue #{issue_number} from GitHub...")
        issue_data = fetch_github_issue(
            owner="timothywarner-org",
            repo="agents2",
            issue_number=int(issue_number),
        )

        incoming_dir = PROJECT_ROOT / "incoming"
        incoming_dir.mkdir(exist_ok=True)

        issue_file = incoming_dir / f"github_issue_{issue_number}.json"

        with open(issue_file, "w", encoding="utf-8") as f:
            json.dump(issue_data, f, indent=2)

        print(f"OK: Issue #{issue_number} saved to {issue_file}")
        print(f"  Title: {issue_data['title']}")
        return issue_file

    except Exception as e:
        print(f"\nError fetching issue: {e}")
        return None


def handle_mock_issue() -> Optional[Path]:
    """Let user select a mock issue file."""
    print("\n--- Mock Issue Selection ---")
    mock_dir = PROJECT_ROOT / "mock_issues"

    if not mock_dir.exists():
        print("Error: mock_issues/ directory not found.")
        return None

    mock_files = sorted(mock_dir.glob("*.json"))

    if not mock_files:
        print("Error: No mock issues found in mock_issues/")
        return None

    print("\nAvailable mock issues:")
    for idx, file in enumerate(mock_files, start=1):
        print(f"  {idx}. {file.name}")

    choice = input("\nSelect a mock issue (number): ").strip()

    if not choice.isdigit() or not (1 <= int(choice) <= len(mock_files)):
        print("Error: Invalid selection.")
        return None

    selected = mock_files[int(choice) - 1]
    print(f"OK: Selected: {selected}")
    return selected


def handle_watcher() -> None:
    """Start the folder watcher."""
    from ..watcher.folder_watcher import main as run_watcher

    print("\n--- Folder Watcher ---")
    print("Starting watcher...")
    print(f"Drop issue JSON files into {PROJECT_ROOT / 'incoming'} to trigger processing")
    print("Press Ctrl+C to stop\n")
    try:
        run_watcher()
    except KeyboardInterrupt:
        print("\n\nWatcher stopped.")


def handle_mcp_server() -> None:
    """Start the MCP server."""
    from ..mcp_server import main as run_mcp_server

    print("\n--- MCP Server ---")
    print("Starting MCP server...")
    print("This exposes tools, resources, and prompts via stdio transport.")
    print("Use with Claude Desktop or VS Code Copilot.")
    print("Press Ctrl+C to stop\n")
    try:
        run_mcp_server()
    except KeyboardInterrupt:
        print("\n\nMCP server stopped.")


def handle_mcp_inspector() -> None:
    """Start the MCP Inspector."""
    import subprocess
    import shutil

    print("\n--- MCP Inspector ---")
    print("Starting MCP Inspector with web UI...")
    print("This opens a browser for interactive testing of tools, resources, and prompts.")
    print("")

    # Check if Node.js is available
    if not shutil.which("node"):
        print("ERROR: Node.js not found!")
        print("")
        print("MCP Inspector requires Node.js.")
        print("Install from: https://nodejs.org/")
        print("")
        input("Press Enter to return to menu...")
        return

    print("Inspector will open in your browser at http://localhost:5173")
    print("Press Ctrl+C to stop\n")

    try:
        subprocess.run(
            ["npx", "@modelcontextprotocol/inspector", "python", "-m", "agent_mvp.mcp_server"],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n\nMCP Inspector stopped.")
    except subprocess.CalledProcessError as e:
        print(f"\nError starting inspector: {e}")
        input("Press Enter to return to menu...")


def process_issue_file(issue_file: Path) -> None:
    """Run the pipeline for a single issue file and write output."""
    config = Config.from_env(PROJECT_ROOT)
    setup_logging(level=config.log_level)
    logger = get_pipeline_logger()

    issue = FileIssueSource.from_path(issue_file)
    result = run_pipeline(issue, config, source_file=str(issue_file))

    output_dir = config.outgoing_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = save_result(result, output_dir)
    logger.complete_run(
        run_id=result.run_id,
        issue_id=result.issue.issue_id,
        verdict=result.qa.verdict.value,
        output_file=str(output_path),
    )
    print(f"\nOK: Pipeline complete. Output: {output_path}")


def main() -> None:
    """Run the interactive menu loop."""
    print("\nWelcome to O'Reilly Agent MVP!")
    print(f"Project root: {PROJECT_ROOT}")

    while True:
        display_menu()
        choice = input("Enter your choice: ").strip().lower()

        if choice == "q":
            print("\nGoodbye!")
            sys.exit(0)

        elif choice == "1":
            issue_file = handle_github_issue()
            if issue_file:
                proceed = input("\nProcess this issue now? (y/n): ").strip().lower()
                if proceed == "y":
                    try:
                        process_issue_file(issue_file)
                    except Exception as e:
                        print(f"\nPipeline failed: {e}")

        elif choice == "2":
            issue_file = handle_mock_issue()
            if issue_file:
                proceed = input(f"\nProcess {issue_file.name}? (y/n): ").strip().lower()
                if proceed == "y":
                    try:
                        process_issue_file(issue_file)
                    except Exception as e:
                        print(f"\nPipeline failed: {e}")

        elif choice == "3":
            handle_watcher()

        elif choice == "4":
            handle_mcp_server()

        elif choice == "5":
            handle_mcp_inspector()

        else:
            print("\nInvalid choice. Please enter 1, 2, 3, 4, 5, or q.")


if __name__ == "__main__":
    main()
