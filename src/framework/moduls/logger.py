from moduls.schemaSpecificAttr import *
import logging

class AKEPLogger:
    def initialize(fileName, title = None):
        # create AKEP logger
        logger = logging.getLogger(LOGGER_ID if title is None else (LOGGER_ID + '-' + title))
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # create file handler which logs even debug messages
        fh = logging.FileHandler(fileName)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        ch.setFormatter(formatter)
        
        for handler in logger.handlers:
            logger.removeHandler(handler)
        logger.addHandler(fh)
        logger.addHandler(ch)        
        return logger


    def getLogger(postTitle):
        return logging.getLogger(LOGGER_ID+'.'+postTitle)