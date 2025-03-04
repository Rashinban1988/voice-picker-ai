# APIのテスト
import requests
from decouple import config
import time
APP_HOST = config("APP_HOST")
APP_PORT = config("APP_PORT")

APP_URL = f"{APP_HOST}:{APP_PORT}"

def result(response):
    print(response.status_code)
    print(response.json())
    print('--------------------------------')

def get_token():
    response = requests.post(f"{APP_URL}/api/token/", json={"username": "rashinban1988@gmail.com", "password": "otomamay"})
    result(response)
    return response.json()["access"]

def get_organizations(token):
    response = requests.get(f"{APP_URL}/api/organizations/", headers={"Authorization": f"Bearer {token}"})
    result(response)
    return response.json()

def get_organization(token, organization_id):
    response = requests.get(f"{APP_URL}/api/organizations/{organization_id}/", headers={"Authorization": f"Bearer {token}"})
    result(response)
    return response.json()

def get_users(token):
    response = requests.get(f"{APP_URL}/api/users/", headers={"Authorization": f"Bearer {token}"})
    result(response)
    return response.json()

def get_user(token, user_id):
    response = requests.get(f"{APP_URL}/api/users/{user_id}/", headers={"Authorization": f"Bearer {token}"})
    result(response)
    return response.json()

token = get_token()
# token = "test"
organizations = get_organizations(token)
users = get_users(token)

for organization in organizations:
    get_organization(token, organization["id"])

for user in users:
    get_user(token, user["id"])


