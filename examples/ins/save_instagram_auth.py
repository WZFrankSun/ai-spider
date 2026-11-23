"""Backward-compatible entry for Instagram auth save."""

import asyncio
from pathlib import Path
import sys

sys.argv = [sys.argv[0], "instagram"]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from save_auth import main

if __name__ == "__main__":
    asyncio.run(main())
