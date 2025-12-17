import os
import logging

def setup_logging(level=None):
    """
    Sets up default logging for the cardinal_glue library.
    Call this function in your standalone scripts to enable logging to console.
    
    Parameters
    ----------
    level : str, optional
        The logging level (e.g., 'INFO', 'DEBUG'). 
        Defaults to 'INFO' or the CARDINAL_LOGGING env var.
    """
    if level is None:
        level = os.getenv('CARDINAL_LOGGING', 'INFO').upper()
        
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
