#!/usr/bin/env python3
"""CLI for version update checking."""

import argparse
import logging
import sys
from pathlib import Path

import yaml

from .automation.merge_decision import should_auto_merge
from .config.updater import ConfigUpdater
from .orchestrator import SectionType, VersionUpdateOrchestrator
from .reporters.console import ConsoleReporter
from .reporters.github import GitHubActionsReporter

logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Check for version updates in AIDB infrastructure and adapters",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to versions.yaml configuration file",
    )
    parser.add_argument(
        "--section",
        choices=[SectionType.INFRASTRUCTURE, SectionType.ADAPTERS, SectionType.ALL],
        default=SectionType.ALL,
        help="Section to check for updates (default: all)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Apply updates to configuration file",
    )
    parser.add_argument(
        "--output-github",
        action="store_true",
        help="Output in GitHub Actions format",
    )
    return parser.parse_args()


def main():
    """Main CLI entry point.

    Returns
    -------
    int
        Exit code: 0 if no updates, 1 if updates found, 2 on error
    """
    try:
        args = parse_arguments()

        if not args.config.exists():
            print(f"Error: Config file not found: {args.config}")
            return 1

        try:
            orchestrator = VersionUpdateOrchestrator(args.config, args.section)
        except yaml.YAMLError as e:
            print(f"Error: Invalid YAML in config file: {e}")
            return 1

        all_updates = orchestrator.check_all_updates()

        has_updates = bool(all_updates)
        auto_merge = should_auto_merge(all_updates)

        reporter = GitHubActionsReporter() if args.output_github else ConsoleReporter()

        report = reporter.generate_report(all_updates)
        reporter.output(all_updates, has_updates, auto_merge, report)

        if args.update and has_updates:
            updater = ConfigUpdater(args.config)
            updater.apply_updates(all_updates)
            updater.save()
            print(f"\nUpdated {args.config}")

        return 0 if not has_updates else 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130

    except Exception as e:
        logger.exception("Unexpected error occurred")
        print(f"Error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
