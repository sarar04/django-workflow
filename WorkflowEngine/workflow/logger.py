# -*- coding: utf-8 -*-
import logging

logger = logging.getLogger('workflow')
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('workflow.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
