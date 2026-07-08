#!/usr/bin/env python3
"""Inicia o bot Telegram real com as configurações do frontend."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ag_06_telegram.bot_real import main

if __name__ == "__main__":
    main()