"""Isolated Python analysis worker.

This process will host the Pandas/NumPy analysis sandbox used by the
agent for contribution analysis, statistical calculations, and
cross-query comparisons.

Phase 0: placeholder process that stays alive so Docker Compose stays healthy.
Network access, secrets, and host filesystem access must remain restricted
when real analysis lands in Phase 5.
"""

import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Keep the worker process running until the container stops."""
    logger.info("TraceIQ python-worker started (placeholder)")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
