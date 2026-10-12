
from logger_config import logger

logger.info("Application started successfully.")
logger.warning("This is a test warning.")

try:
    result = 10 / 0
except ZeroDivisionError:
    logger.exception("Test error occurred.")

print("Logging test completed.")
