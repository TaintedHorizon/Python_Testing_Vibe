#!/usr/bin/env python3
"""
Manual database path consistency diagnostic (archived).
"""
from doc_processor.config_manager import app_config
import os


def run():
    print('DATABASE_PATH:', app_config.DATABASE_PATH)
    print('Exists:', os.path.exists(app_config.DATABASE_PATH))


if __name__ == '__main__':
    run()
