from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import smtplib
import psycopg2
from psycopg2 import DatabaseError
from random import randint, choice
from typing_extensions import TypedDict
from exeptions import *
from datetime import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import *
from logger import Logger
from encryption import SHA256

# TODO разнести классы по разным модулям

app = FastAPI()

LOGGER = Logger()

# temp
def gen_token() -> str:
    chars = [chr(i) for i in range(ord('a'), ord('z') + 1)] + [str(i) for i in range(10)]
    return '-'.join([''.join([choice(chars) for i in range(5)]) for j in range(5)])


class RegRequest(BaseModel):
    email: EmailStr
    password: str
    login: str


class ConfirmRequest(BaseModel):
    login: str
    email: EmailStr
    password: str
    code: str

class AuthRequest(BaseModel):
    email: EmailStr
    password: str

class Response(TypedDict):
    status: int
    message: str
    data: dict


class UserSession:
    def __init__(self, login: str, email: str):
        self.login = login
        self.email = email
        self.token = gen_token()
        self.create_time = datetime.now().ctime()
        self.logger = LOGGER

    def get_token(self) -> str:
        return self.token
    
    def get_email(self) -> str:
        return self.email

    def log_info(self) -> None:
        self.logger.info(f"-- session created -- login: {self.login} - token: {self.token} - time: {self.create_time} -")
    
    def close(self) -> None:
        self.logger.info(f"-- session closed -- login: {self.login} - token: {self.token} - time: {datetime.now().ctime()} -")

class UserSessionsPull:
    def __init__(self):
        self.token_session_pull = dict()
        self.email_token_pull = dict()

    def add_session(self, session: UserSession) -> None:
        token = session.get_token()
        email = session.get_email()
        self.token_session_pull[token] = session
        self.email_token_pull[email] = token
    
    def close_session(self, email: str) -> None:
        if not (email in self.email_token_pull.keys()):
            return
        token = self.email_token_pull[email]
        self.email_token_pull.pop(email, None)
        self.token_session_pull[token].close()
        self.token_session_pull.pop(token, None)

class RegistrationManager:
    def __init__(self, sender_email: str, sender_password: str) -> None:
        self.router = APIRouter()
        self.router.add_api_route('/register', self.user_reg, methods=['POST'])
        self.router.add_api_route('/confirm', self.user_confirm, methods=['POST'])
        self.router.add_api_route('/auth', self.user_auth, methods=['GET'])
        self.smtp_server = 'smtp.gmail.com'
        self.smtp_port = 587
        self.email = sender_email
        self.password = sender_password

        self.db_client = DBClient(db_name=DB_NAME, user=DB_LOGIN, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        self.logger = LOGGER
        self.encrypter = SHA256()

        self.sessions = UserSessionsPull()
        
        self.users_on_wait = {}

    @staticmethod
    def gen_confirm_code() -> str:        
        return f'{randint(0, 1000):04d}'

    def add_user_in_wait_list(self, email: str) -> None:
        code = self.gen_confirm_code()
        self.users_on_wait[email] = code

        return code

    async def user_reg(self, request: RegRequest) -> Response:
        try:
            self.db_client.is_user_exist(login=request.login, email=request.email)
        except EmailAlreadyExist as e:
            raise HTTPException(status_code=400, detail=e.__str__())
        except LoginAlreadyExist as e:
            raise HTTPException(status_code=400, detail=e.__str__())
        
        # сохраняет код подтверждения в словарь и возвращает его в виде строки
        code = self.add_user_in_wait_list(email=request.email)

        msg = self.create_msg(dst_email=request.email, code=code)
        try:
            self.send_email(dst_email=request.email, msg=msg)
        except Exception as e:
            self.logger.error(e)
            raise HTTPException(status_code=500, detail="Unable to send confirm code")
        else:
            return Response(status=200, message="User data valid. Please check your email", data={})

    async def user_confirm(self, request: ConfirmRequest) -> Response:
        # повторная проверка что такого пользователя не существует (мб переделать)
        try:
            self.db_client.is_user_exist(login=request.login, email=request.email)
        except EmailAlreadyExist as e:
            raise HTTPException(status_code=400, detail=e.__str__())
        except LoginAlreadyExist as e:
            raise HTTPException(status_code=400, detail=e.__str__())

        if not(request.email in self.users_on_wait.keys()):
            raise HTTPException(status_code=400, detail="Confirm code expired")
        
        if not(self.users_on_wait[request.email] == request.code):
            raise HTTPException(status_code=400, detail="incorrect confirm code")
        
        try:
            self.db_client.add_user(login=request.login, email=request.email, password=self.encrypter.str_to_hash(request.password))    # сохраняем хэш от пароля вместо самого пароля
        except EmailAlreadyExist as e:
            raise HTTPException(status_code=400, detail=e.__str__())
        except LoginAlreadyExist as e:
            raise HTTPException(status_code=400, detail=e.__str__())
        else:
            return Response(status=200, message="Registration successfull", data={})
    
    async def user_auth(self, request: AuthRequest) -> Response:
        try:
            session_token = self.create_session(email=request.email, password=self.encrypter.str_to_hash(request.password))
        except InvalidLoginOrPassoword as e:
            return Response(status=200, message=e.__str__(), data={})
        else:
            return Response(status=200, message='success', data={'session_token': session_token})
    
    def create_session(self, email: str, password: str) -> str:
        login = self.db_client.verify_user(email=email, password=password)
        if not login:
            raise InvalidLoginOrPassoword()
        else:
            self.sessions.close_session(email=email)    # close old session if exists else nothing
            session = UserSession(login=login, email=email)
            session_token = session.get_token()
            self.sessions.add_session(session)

            return session_token

    def send_email(self, dst_email: str, msg: str) -> None:
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.email, self.password)
            server.sendmail(self.email, dst_email, msg)

    def create_msg(self, dst_email: str, code: str) -> str:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Код подтверждения Meetly"
        msg["From"] = self.email
        msg["To"] = dst_email

        html = f"""\
        <html>
        <body>
            <p>Здравствуйте,<br>
            Ваш код подтверждения: <b>{code}</b></p>
        </body>
        </html>
        """

        part = MIMEText(html, "html")
        msg.attach(part)

        return msg.as_string()


class DBClient:
    def __init__(self, user: str, password: str, host: str, port: str, db_name: str) -> None:
        self.db_name = db_name
        self.user = user
        self.password = password
        self.host = host
        self.port = port

        self.conn = None
        self.cursor = None

        self.logger = Logger()

        self.connect_db()
    
    def connect_db(self) -> None:
        try:
            self.conn = psycopg2.connect(database=self.db_name, user=self.user, password=self.password, host=self.host,
                                         port=self.port)
        except DatabaseError as e:
            self.logger.error(e)
        else:
            self.cursor = self.conn.cursor()
        
    def close_connection(self) -> None:
        self.cursor.close()
        self.conn.close()
    
    def is_connected(self) -> None:
        if self.cursor is None or self.conn is None:
            raise NoDBConnectionError()

    def add_user(self, login: str, email: str, password: str) -> None:
        self.is_connected()

        self.is_user_exist(login=login, email=email)
        
        self.cursor.execute(f'''INSERT INTO users (login, email, password, reg_date) VALUES
                            ('{login}',
                            '{email}',
                            '{password}',
                            '{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')''')
        
        self.conn.commit()

    def is_user_exist(self, login: str, email: str) -> None:
        if self.is_email_exist(email=email):
            raise EmailAlreadyExist()
        if self.is_login_exist(login=login):
            raise LoginAlreadyExist()

    def is_email_exist(self, email: str) -> bool:
        self.is_connected()

        self.cursor.execute("SELECT 1 FROM users WHERE email = %s", (email, ))
        result = self.cursor.fetchone()
        if result is None:
            return False
        else:
            return True
    
    def is_login_exist(self, login: str) -> bool:
        self.is_connected()

        self.cursor.execute("SELECT 1 FROM users WHERE login = %s", (login, ))
        result = self.cursor.fetchone()
        if result is None:
            return False
        else:
            return True
    
    def get_user(self, email=None, login=None) -> str | None:
        self.is_connected()

        if login:
            self.cursor.execute("SELECT * FROM users WHERE login = %s", (login, ))
        elif email:
            self.cursor.execute("SELECT * FROM users WHERE email = %s", (email, ))
        else:
            raise TypeError('no str login or email')
        
        result = self.cursor.fetchone()
        if result:
            return f'{result}'
        else:
            return None
    
    def verify_user(self, email: EmailStr, password: str) -> str:
        self.is_connected()

        self.cursor.execute("SELECT login FROM users WHERE email = %s, password = %s", (str(email), password))      # что то тут поправить

        result = self.cursor.fetchone()
        if result:
            return result[0]
        else:
            return ""


manager = RegistrationManager(sender_email=SENDER_EMAIL, sender_password=SENDER_PASSWORD)
app.include_router(manager.router)
