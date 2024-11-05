import requests


url = "http://127.0.0.1:8000/confirm"
data = {
    "login": "hlebikus228",
    "email": "kozinmisha2345@gmail.com",
    "password": "12345",
    "code": "0343"
}

response = requests.post(url, json=data)

# Выводим ответ
print(response.status_code)
print(response.json())
