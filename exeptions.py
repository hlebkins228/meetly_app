class BaseException(Exception):
    """Базовый класс ошибки"""
    
    def __init__(self, msg: str = 'Error'):
        super().__init__(msg)

    def __str__(self):
        base_message = super().__str__()
        return base_message


class LoginAlreadyExist(BaseException):
    def __init__(self, msg: str='User with such login already exists'):
        super().__init__(msg)


class EmailAlreadyExist(BaseException):
    def __init__(self, msg: str='User with such email already exists'):
        super().__init__(msg)


class NoDBConnectionError(BaseException):
    def __init__(self, msg: str='No database connection'):
        super().__init__(msg)


class InvalidLoginOrPassoword(BaseException):
    def __init__(self, msg: str='Invalid email or password'):
        super().__init__(msg)