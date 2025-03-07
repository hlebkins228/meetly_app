import logging
from config import LOGFILE_PATH


logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования

# Создаем обработчик для записи логов в файл
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)  # Уровень для обработчика файла

# Создаем обработчик для вывода логов в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # Уровень для обработчика консоли

# Формат логов
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Добавляем обработчики к логгеру
logger.addHandler(file_handler)
logger.addHandler(console_handler)


class Logger:
    def __init__(self) -> None:
        logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s\n',
        filename=LOGFILE_PATH,
        filemode='a')

        self.logger = logging.getLogger('meetly_logger')
    
    def error(self, msg: str) -> None:
        self.logger.error(msg)
        print(msg)
    
    def error(self, e: Exception) -> None:
        self.logger.error(f"Error: {e}")
        print("error: ", e)
    
    def info(self, msg: str) -> None:
        self.logger.info(msg)
