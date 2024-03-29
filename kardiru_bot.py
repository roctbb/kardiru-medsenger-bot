import base64
import uuid

from flask import Flask, request, render_template, abort
import json
import datetime
from config import *
import kardiru_api
from medsenger_api import AgentApiClient
from uuid import uuid4
from manage import *
from models import Contract
from datetime import datetime
from zipfile import ZipFile
from tempfile import TemporaryFile

medsenger_api = AgentApiClient(API_KEY, MAIN_HOST, AGENT_ID, API_DEBUG)


def gts():
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


with app.app_context():
    db.create_all()


@app.route('/status', methods=['POST'])
def status():
    data = request.json

    if data['api_key'] != API_KEY:
        return 'invalid key'

    contract_ids = [l[0] for l in db.session.query(Contract.id).all()]

    answer = {
        "is_tracking_data": True,
        "supported_scenarios": ['heartfailure', 'stenocardia', 'fibrillation'],
        "tracked_contracts": contract_ids
    }
    print(answer)

    return json.dumps(answer)


@app.route('/init', methods=['POST'])
def init():
    data = request.json

    if data['api_key'] != API_KEY:
        return 'invalid key'

    try:
        contract_id = int(data['contract_id'])
        query = Contract.query.filter_by(id=contract_id)
        if query.count() != 0:
            contract = query.first()
            print("{}: Reactivate contract {}".format(gts(), contract.id))
        else:
            contract = Contract(id=contract_id)
            db.session.add(contract)
            print("{}: Add contract {}".format(gts(), contract.id))

        if 'params' in data:
            if data['params'].get('kardiru_model') and data['params'].get('kardiru_serial', ''):
                contract.serial_number = data['params']['kardiru_serial']

        info = medsenger_api.get_patient_info(contract_id)
        contract.email = info['email']
        contract.password = str(uuid.uuid4()).replace('-', '')
        contract.model = "1511"

        birthday = datetime.strptime(info['birthday'], '%d.%m.%Y')

        if contract.model and contract.serial_number:
            result, error = kardiru_api.subscribe(contract.model, contract.serial_number, contract_id, birthday, "{}+cardio@medsenger.ru".format(contract_id),
                                                  contract.password, "Пациент", info['sex'])
            if result:
                print(gts(), "Subscribed {}".format(contract.id))
                medsenger_api.send_message(contract.id, only_patient=True,
                                           text="Создан личный кабинет на <a target='_blank' href='https://kardi.ru'>Kardi.RU</a>. Там можно посмотреть все ЭКГ, снятые прибором Карди.ру, но кроме этого мы будем автоматически пересылать их Вашему врачу прямо в Medsenger. \n\n<b>Логин:</b> {}\n<b>Пароль:</b> {}".format(
                                               info['email'], contract.password))
            else:
                print(gts(), "Not subscribed {}".format(contract.id))

                # if error == 'Данный E-mail уже используется в системе':
                #     medsenger_api.send_message(contract.id, only_patient=True,
                #                                text='Мы попытались создать для Вас личный кабинет для прибора карди.ру, но похоже, что Вы уже использовали такой прибор ранее и у Вас уже есть личный кабинет. Чтобы Ваши ЭКГ автоматически пересылались врачу, пожалуйста, укажите ваш пароль. Если вы не помните его, воспользуйтесь восстановлением пароля на сайте <a href="https://kardi.ru">kardi.ru</a>. Ваш логин - {}.'.format(
                #                                    info['email']), action_name="Настроить", action_link='setup')

        db.session.commit()

        medsenger_api.add_record(data.get('contract_id'), 'doctor_action',
                                 'Подключен прибор "Карди.ру" (серийный номер {}).'.format(contract.serial_number))


    except Exception as e:
        print(e)
        return "error"

    print('sending ok')
    return 'ok'


@app.route('/remove', methods=['POST'])
def remove():
    data = request.json

    if data['api_key'] != API_KEY:
        print('invalid key')
        return 'invalid key'

    try:
        contract_id = str(data['contract_id'])
        query = Contract.query.filter_by(id=contract_id)

        if query.count() != 0:
            contract = query.first()

            if contract.serial_number and contract.model:
                if kardiru_api.unsubscribe(contract.model, contract.serial_number, contract.id):
                    print("{}: Unsubscribed {}".format(gts(), contract.id))
                else:
                    print("{}: Not unsubscribed {}".format(gts(), contract.id))

            print("{}: Deactivate contract {}".format(gts(), contract.id))

            sn = contract.serial_number

            db.session.delete(contract)
            db.session.commit()

            medsenger_api.add_record(data.get('contract_id'), 'doctor_action',
                                     'Отключен прибор "Карди.ру" (серийный номер {}).'.format(sn))

        else:
            print('contract not found')

    except Exception as e:
        print(e)
        return "error"

    return 'ok'


@app.route('/', methods=['GET'])
def index():
    return 'waiting for the thunder!'


@app.route('/receive', methods=['POST'])
def receive():
    data = request.form

    if data.get('channel') != CHANNEL_ID or data.get('pass') != CHANNEL_PASSWORD:
        abort(403)

    if not request.files.get('EMRfile'):
        abort(422)

    file = request.files.get('EMRfile')
    filename = file.filename

    parts = filename.split('_')
    contract_id = parts[2]

    contract = Contract.query.filter_by(id=contract_id).first()
    if not contract:
        abort(200)

    attachments = []

    # file_string = base64.b64encode(file.read())
    with TemporaryFile() as tmp:
        tmp.write(file.read())
        archive = ZipFile(tmp, 'r')
        for file in archive.filelist:
            content = archive.read(file.filename)
            attachments.append([
                file.filename, "application/pdf", base64.b64encode(content)
            ])

    medsenger_api.send_message(contract.id, "ЭКГ от карди.ру", send_from='patient',
                               attachments=attachments)

    return 'ok'


@app.route('/settings', methods=['GET'])
def settings():
    key = request.args.get('api_key', '')

    if key != API_KEY:
        return "<strong>Некорректный ключ доступа.</strong> Свяжитесь с технической поддержкой."

    try:
        contract_id = int(request.args.get('contract_id'))
        query = Contract.query.filter_by(id=contract_id)
        if query.count() != 0:
            contract = query.first()
        else:
            return "<strong>Ошибка. Контракт не найден.</strong> Попробуйте отключить и снова подключить интеллектуальный агент к каналу консультирвоания.  Если это не сработает, свяжитесь с технической поддержкой."

    except Exception as e:
        print(e)
        return "error"

    return render_template('settings.html', contract=contract)


@app.route('/settings', methods=['POST'])
def setting_save():
    key = request.args.get('api_key', '')

    if key != API_KEY:
        return "<strong>Некорректный ключ доступа.</strong> Свяжитесь с технической поддержкой."

    try:
        contract_id = int(request.args.get('contract_id'))
        contract = Contract.query.filter_by(id=contract_id).first()

        if contract:
            if contract.serial_number:
                kardiru_api.unsubscribe(contract.model, contract.serial_number, contract.id)

            contract.model = request.form.get('model')
            contract.serial_number = request.form.get('serial_number')
            contract.password = request.form.get('password')
            info = medsenger_api.get_patient_info(contract_id)
            birthday = datetime.strptime(info['birthday'], '%d.%m.%Y')

            db.session.commit()

            if contract.serial_number and contract.model:
                result, error = kardiru_api.subscribe(contract.model, contract.serial_number, contract_id, birthday, contract.email,
                                                      contract.password, info['name'], info['sex'])

                if result:
                    medsenger_api.send_message(contract.id, only_patient=True,
                                               text="Активирован личный кабинет на <a target='_blank' href='https://kardi.ru'>Kardi.RU</a>. Там можно посмотреть все ЭКГ, снятые прибором Карди.ру, но кроме этого мы будем автоматически пересылать их Вашему врачу прямо в Medsenger. \n\n<b>Логин:</b> {}\n<b>Пароль:</b> {}".format(
                                                   info['email'], contract.password))
                else:
                    # if error == 'Данный E-mail уже используется в системе':
                    #     medsenger_api.send_message(contract.id, only_patient=True,
                    #                                text='Мы попытались создать для Вас личный кабинет для прибора карди.ру, но похоже, что Вы уже использовали такой прибор ранее и у Вас уже есть личный кабинет. Чтобы Ваши ЭКГ автоматически пересылались врачу, пожалуйста, укажите ваш пароль. Если вы не помните его, воспользуйтесь восстановлением пароля на сайте <a href="https://kardi.ru">kardi.ru</a>. Ваш логин - {}.'.format(
                    #                                    info['email']), action_name="Настроить", action_link='setup')
                    #     error += '. Мы отправили пациенту просьбу указать его пароль.'
                    return render_template('settings.html', contract=contract, error=error)
            db.session.commit()
        else:
            return "<strong>Ошибка. Контракт не найден.</strong> Попробуйте отключить и снова подключить интеллектуальный агент к каналу консультирвоания.  Если это не сработает, свяжитесь с технической поддержкой."

    except Exception as e:
        print(e)
        return "error"

    return """
        <strong>Спасибо, окно можно закрыть</strong><script>window.parent.postMessage('close-modal-success','*');</script>
        """


# @app.route('/setup', methods=['GET'])
# def setup():
#     key = request.args.get('api_key', '')
#
#     if key != API_KEY:
#         return "<strong>Некорректный ключ доступа.</strong> Свяжитесь с технической поддержкой."
#
#     try:
#         contract_id = int(request.args.get('contract_id'))
#         query = Contract.query.filter_by(id=contract_id)
#         if query.count() != 0:
#             contract = query.first()
#         else:
#             return "<strong>Ошибка. Контракт не найден.</strong> Попробуйте отключить и снова подключить интеллектуальный агент к каналу консультирвоания.  Если это не сработает, свяжитесь с технической поддержкой."
#
#     except Exception as e:
#         print(e)
#         return "error"
#
#     return render_template('setup.html', contract=contract)
#
#
# @app.route('/setup', methods=['POST'])
# def setup_save():
#     key = request.args.get('api_key', '')
#
#     if key != API_KEY:
#         return "<strong>Некорректный ключ доступа.</strong> Свяжитесь с технической поддержкой."
#
#     try:
#         contract_id = int(request.args.get('contract_id'))
#         contract = Contract.query.filter_by(id=contract_id).first()
#
#         if contract:
#             if contract.serial_number:
#                 kardiru_api.unsubscribe(contract.model, contract.serial_number, contract.id)
#
#             info = medsenger_api.get_patient_info(contract_id)
#             birthday = datetime.strptime(info['birthday'], '%d.%m.%Y')
#             contract.password = request.form.get('password')
#
#             if contract.serial_number and contract.model:
#                 result, error = kardiru_api.subscribe(contract.model, contract.serial_number, contract_id, birthday, contract.email,
#                                                       contract.password, info['name'], info['sex'])
#
#                 if not result:
#                     return render_template('setup.html', contract=contract, error=error)
#                 else:
#                     medsenger_api.send_message(contract_id=contract.id, text="Пациент подключил кабинет Карди.Ру.", only_doctor=True)
#                     medsenger_api.send_message(contract_id=contract.id, text="Кабинет Карди.Ру подключен, теперь Ваши ЭКГ автоматически пересылаются врачу.", only_patient=True)
#             db.session.commit()
#         else:
#             return "<strong>Ошибка. Контракт не найден.</strong> Попробуйте отключить и снова подключить интеллектуальный агент к каналу консультирвоания.  Если это не сработает, свяжитесь с технической поддержкой."
#
#     except Exception as e:
#         print(e)
#         return "error"
#
#     return """
#         <strong>Спасибо, окно можно закрыть</strong><script>window.parent.postMessage('close-modal-success','*');</script>
#         """


@app.route('/message', methods=['POST'])
def save_message():
    data = request.json
    key = data['api_key']

    if key != API_KEY:
        return "<strong>Некорректный ключ доступа.</strong> Свяжитесь с технической поддержкой."

    return "ok"


if __name__ == "__main__":
    app.run(port=PORT, host=HOST)
