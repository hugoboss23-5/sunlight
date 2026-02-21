#!/usr/bin/env python3
"""
SUNLIGHT Webhook Worker Entrypoint
====================================

Standalone entrypoint that avoids ``python -m code.jobs`` (which fails
because ``code`` shadows Python's built-in ``code`` module).

Usage:
    python worker.py --worker             # start polling loop
    python worker.py --worker --poll 5    # custom poll interval
"""

import os
import sys
import signal
import threading
import argparse

# Ensure sibling modules in code/ are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "code"))

from sunlight_logging import get_logger
from jobs import init_jobs_schema, ScanWorker, run_scan_pipeline

logger = get_logger("worker")


def main():
    parser = argparse.ArgumentParser(description="SUNLIGHT Webhook Worker")
    parser.add_argument("--worker", action="store_true", help="Run as background worker")
    parser.add_argument("--db", default=None, help="Database path")
    parser.add_argument("--poll", type=float, default=2.0, help="Poll interval (seconds)")
    args = parser.parse_args()

    if not args.worker:
        parser.print_help()
        sys.exit(0)

    db_path = args.db or os.environ.get(
        "SUNLIGHT_DB_PATH",
        os.path.join(os.path.dirname(__file__), "data", "sunlight.db"),
    )

    logger.info("Starting webhook worker", extra={"db_path": db_path})
    init_jobs_schema(db_path)

    worker = ScanWorker(
        db_path=db_path,
        pipeline_fn=run_scan_pipeline,
        poll_interval=args.poll,
    )

    def shutdown(sig, frame):
        logger.info("Shutting down worker")
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    worker.start()

    # Keep main thread alive
    stop_event = threading.Event()
    stop_event.wait()


if __name__ == "__main__":
    main()
