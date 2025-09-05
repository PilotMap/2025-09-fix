import logging
import logzero

import admin

from logzero import logger
version = admin.version
loglevel = logging.INFO
logzero.loglevel(logging.INFO)
logzero.logfile("./logfile.log", maxBytes=1e6, backupCount=1)
logger.info("\n\nStartup of metar-v4.py Script, Version " + version)
