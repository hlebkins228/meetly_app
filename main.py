import requests
from requests import Response
from datetime import datetime

from config import *


class Sender:
    def __init__(self, api_key: str, phone: str) -> None:
        self.api_key = api_key
        self.phone = phone
        self.url = 'https://api.exolve.ru/messaging/v1/SendSMS'
        self.headers = {'Authorization': f'Bearer {self.api_key}'}
        self.data = {'number': self.phone,
                     'destination': '',
                     'text': ''
                     }

    def send(self, dst_number: str, text: str) -> int:
        self.data['destination'] = dst_number
        self.data['text'] = text

        response = requests.post(url=self.url, headers=self.headers, json=self.data)
        self.log(response)

        return response.status_code

    @staticmethod
    def log(response: Response) -> None:
        with open('logging.log', 'a') as file:
            file.write(f'\n[INFO] TIME: {datetime.now()} STATUS: {response.status_code} TEXT: {response.text}')


if __name__ == "__main__":
    sender = Sender(api_key=API_KEY, phone=PHONE_NUMBER)

    status = sender.send(dst_number='79152984050', text='hello your code: 1234')

    print(status)

