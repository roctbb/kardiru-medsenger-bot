from kardiru_api import register_device

model = input("model: ")
serial = input("serial: ")

register_device(model, serial)