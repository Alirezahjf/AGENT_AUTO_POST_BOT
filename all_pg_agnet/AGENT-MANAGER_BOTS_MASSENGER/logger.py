# logger.py
import logging

_all_file_handler = logging.FileHandler('bot.log', encoding='utf-8')
_all_file_handler.setLevel(logging.INFO)
_error_file_handler = logging.FileHandler('errors.log', encoding='utf-8', delay=True)
_error_file_handler.setLevel(logging.ERROR)
_stream_handler = logging.StreamHandler()
_stream_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[_all_file_handler, _error_file_handler, _stream_handler]
)

logger = logging.getLogger(__name__)
