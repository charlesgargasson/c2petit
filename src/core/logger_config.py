#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

logger = logging.getLogger()

def configure_logger():

    level = logging.INFO
    logger.setLevel(level)

    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setLevel(logging.NOTSET)  # Let the logger filter the level

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)