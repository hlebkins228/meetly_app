from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import smtplib
import psycopg2
from psycopg2 import DatabaseError
from random import randint
from typing_extensions import TypedDict
from exeptions import *
from datetime import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import *
from logger import Logger

# TODO разнести классы по разным модулям

app = FastAPI()


class RegRequest(BaseModel):
    email: EmailStr
    password: str
    login: str


class ConfirmRequest(BaseModel):
    login: str
    email: EmailStr
    password: str
    code: str


class Response(TypedDict):
    status: int
    message: str


class RegistrationManager:
    def __init__(self, sender_email: str, sender_password: str) -> None:
        self.router = APIRouter()
        self.router.add_api_route("/register", self.register_user, methods=["POST"])
        self.router.add_api_route("/confirm", self.confirm_user, methods=["POST"])
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.email = sender_email
        self.password = sender_password

        self.db_client = DBClient(db_name=DB_NAME, user=DB_LOGIN, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        self.logger = Logger()
        
        self.users_on_wait = {}

    @staticmethod
    def gen_confirm_code() -> str:        
        return f'{randint(0, 1000):04d}'

    def add_user_in_wait_list(self, email: str) -> None:
        code = self.gen_confirm_code()
        self.users_on_wait[email] = code

        return code

    async def register_user(self, request: RegRequest) -> Response:
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
            return Response(status=200, message="User data valid. Please check your email")

    async def confirm_user(self, request: ConfirmRequest) -> Response:
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
            self.db_client.add_user(login=request.login, email=request.email, password=request.password)
        except EmailAlreadyExist as e:
            raise HTTPException(status_code=400, detail=e.__str__())
        except LoginAlreadyExist as e:
            raise HTTPException(status_code=400, detail=e.__str__())
        else:
            return Response(status=200, message="Registration successfull")

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
            raise NoDBConnectionError

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
            raise EmailAlreadyExist
        if self.is_login_exist(login=login):
            raise LoginAlreadyExist

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


manager = RegistrationManager(sender_email=SENDER_EMAIL, sender_password=SENDER_PASSWORD)
app.include_router(manager.router)
