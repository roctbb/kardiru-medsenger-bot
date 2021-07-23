from datetime import datetime

from config import *
import requests


def register_device(model, serial_number):
    data = {
        "model": model,
        "serialNumber": serial_number,
        "exporterId": EXPORTER_ID,
        "deviceAgentCode": DEVICE_AGENT_CODE
    }

    print("Send to {}: {}".format(KARDIRU_HOST + 'rest/device', data))

    try:
        answer = requests.post(KARDIRU_HOST + 'rest/device', json=data)
        print(answer.text)

        return True
    except Exception as e:
        print(e)
        return False


def subscribe(model, serial_number, contract_id, birthday, email, password, name, gender):
    data = {
        "model": model,
        "serialNumber": serial_number,
        "exporterId": EXPORTER_ID,
        "clientCode": str(contract_id),
        "birthday": birthday.strftime('%Y-%m-%dT00:00:00.000+03:00'),
        "email": email,
        "password": password,
        "dateOfDeviceGoToClient": datetime.now().strftime('%Y-%m-%dT00:00:00.000+03:00'),
        "name": name,
        "deviceUsingType": "1",
        "lang": "ru",
        "deviceAgentCode": DEVICE_AGENT_CODE,
        "gender": "1" if gender == "male" else "2"
    }

    print("Send to {}: {}".format(KARDIRU_HOST + 'rest/device/issue', data))

    try:
        try:
            unsubscribe(model, serial_number, contract_id)
        except:
            pass

        answer = requests.post(KARDIRU_HOST + 'rest/device/issue', json=data)
        print(answer.text)

        if answer.json().get('code') != 0:
            return False, answer.json().get('message')

        return True, answer.json().get('message')

    except Exception as e:
        print(e)
        return False, "Ошибка соединения"


def unsubscribe(model, serial_number, contract_id):
    data = {
        "model": model,
        "serialNumber": serial_number,
        "exporterId": EXPORTER_ID,
        "dateOfDeviceComeBackFromClient": datetime.now().strftime('%Y-%m-%dT00:00:00.000+03:00'),
        "clientCode": contract_id,
        "deviceAgentCode": DEVICE_AGENT_CODE
    }

    print("Send to {}: {}".format(KARDIRU_HOST + 'rest/device/return', data))

    try:
        answer = requests.post(KARDIRU_HOST + 'rest/device/return', json=data)

        if answer.json().get('code') != 0:
            return False, answer.json().get('message')

        return True, answer.json().get('message')
    except Exception as e:
        print(e)
        return False, "Ошибка соединения"
