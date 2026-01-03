#!/usr/bin/env python3
"""
FPL Analytics Data Pipeline
Main CLI entry point for fetching and storing FPL data
"""

import argparse
import sys
from src.pipeline.fetcher import DataFetcher
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


def fetch_all(args):
    """Fetch all players (force mode)"""
    logger.info("Running fetch-all command")
    fetcher = DataFetcher()
    try:
        report = fetcher.run_full_pipeline(date=args.date, force_all=True)
        print(report)
        return 0 if report.failed_fetches == 0 else 1
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        return 1
    finally:
        fetcher.close()


def fetch_updates(args):
    """Fetch only changed players (incremental mode)"""
    logger.info("Running fetch-updates command")
    fetcher = DataFetcher()
    try:
        report = fetcher.run_full_pipeline(date=args.date, force_all=False)
        print(report)
        return 0 if report.failed_fetches == 0 else 1
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        return 1
    finally:
        fetcher.close()


def fetch_player(args):
    """Fetch a specific player"""
    logger.info(f"Fetching player {args.id}")
    print(f"Fetching player {args.id}...")
    print("Note: Use fetch-all or fetch-updates for full pipeline.")
    print("Single player fetch not yet implemented.")
    return 0


def show_status(_args):
    """Show pipeline status"""
    fetcher = DataFetcher()
    try:
        status = fetcher.get_status()

        print("\n" + "="*60)
        print("FPL Data Pipeline - Status")
        print("="*60)
        print(f"Last fetch: {status['last_fetch_time']}")
        print(f"Total players tracked: {status['total_players_tracked']}")
        print(f"Successful fetches: {status['successful_fetches']}")
        print(f"Failed fetches: {status['failed_fetches']}")
        print(f"Latest data date: {status['latest_data_date']}")

        if status['checkpoint_active']:
            print(f"\nCheckpoint active: {status['checkpoint_remaining']} players remaining")
            print("Run fetch-updates to resume")

        print("="*60 + "\n")
        return 0
    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}")
        return 1
    finally:
        fetcher.close()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='FPL Analytics Data Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py fetch-all              Fetch all players (initial run)
  python main.py fetch-updates          Fetch only changed players
  python main.py status                 Show pipeline status
  python main.py fetch-player --id 123  Fetch specific player
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # fetch-all command
    parser_fetch_all = subparsers.add_parser(
        'fetch-all',
        help='Fetch all players (force mode)'
    )
    parser_fetch_all.add_argument(
        '--date',
        type=str,
        default=None,
        help='Date in YYYY-MM-DD format (default: today)'
    )
    parser_fetch_all.set_defaults(func=fetch_all)

    # fetch-updates command
    parser_fetch_updates = subparsers.add_parser(
        'fetch-updates',
        help='Fetch only changed players (incremental mode)'
    )
    parser_fetch_updates.add_argument(
        '--date',
        type=str,
        default=None,
        help='Date in YYYY-MM-DD format (default: today)'
    )
    parser_fetch_updates.set_defaults(func=fetch_updates)

    # fetch-player command
    parser_fetch_player = subparsers.add_parser(
        'fetch-player',
        help='Fetch a specific player'
    )
    parser_fetch_player.add_argument(
        '--id',
        type=int,
        required=True,
        help='Player ID to fetch'
    )
    parser_fetch_player.set_defaults(func=fetch_player)

    # status command
    parser_status = subparsers.add_parser(
        'status',
        help='Show pipeline status'
    )
    parser_status.set_defaults(func=show_status)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Run command
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())