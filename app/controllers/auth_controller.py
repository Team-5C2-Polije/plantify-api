from flask import Blueprint, jsonify, request
from ..utils.response_util import ResponseUtil
from firebase_admin import initialize_app, storage, credentials, firestore
from firebase_admin.firestore import SERVER_TIMESTAMP

auth_bp = Blueprint('auth', __name__)
client = firestore.client()

@auth_bp.route('/auth', methods=['POST'])
def auth():
    data = request.json
    email = data.get('email')
    uid = data.get('uid')
    fullname = data.get('fullname')

    if not email:
        return ResponseUtil.error("Email parameter is required", data=None, status_code=400)
    if not uid:
        return ResponseUtil.error("UID parameter is required", data=None, status_code=400)
    if not fullname:
        return ResponseUtil.error("Fullname parameter is required", data=None, status_code=400)

    try:
        user_ref = client.collection('users').where('email', '==', email).limit(1).get()

        if user_ref:
            user_data = user_ref[0].to_dict()
            return ResponseUtil.success("Autentikasi Berhasil", user_data)
        else:
            uid_check_ref = client.collection('users').document(uid).get()
            if uid_check_ref.exists:
                return ResponseUtil.error("UID already exists", status_code=400)

            user_ref = client.collection('users').document(uid)
            data['createdAt'] = SERVER_TIMESTAMP
            data['devices'] = {}
            user_ref.set(data)

            user_ref = client.collection('users').where('email', '==', email).limit(1).get()
            if user_ref:
                user_data = user_ref[0].to_dict()
                return ResponseUtil.success("Autentikasi Berhasil", user_data)
            else:
                return ResponseUtil.error("Autentikasi Gagal", status_code=400)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@auth_bp.route('/add_device', methods=['POST'])
def addDevice():
    data = request.json
    email = data.get('email')
    token = data.get('token')

    if not email:
        return ResponseUtil.error("Email parameter is required", data=None, status_code=400)
    if not token:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)
    
    try:
        # Cek apakah perangkat dengan token tertentu sudah ada
        device_ref = client.collection('devices').where('token', '==', token).limit(1).get()
        createdAt = SERVER_TIMESTAMP 
        
        if device_ref:
            device_data = device_ref[0].to_dict()
            device_id = device_ref[0].id
            my_device = {
                device_id: {
                    "name": device_data['name'],
                    "createdAt": createdAt
                }
            }

            # Cari user berdasarkan email
            user_ref = client.collection('users').where('email', '==', email).limit(1).get()
            if not user_ref:
                return ResponseUtil.error("User not found", data=None, status_code=400)

            user_doc = user_ref[0]
            user_data = user_doc.to_dict()
            user_devices = user_data.get('devices', {})

            # Cek apakah device_id sudah ada di field devices
            if device_id in user_devices:
                return ResponseUtil.error("Device already exists", data=None, status_code=400)

            # Update field devices dengan my_device
            user_devices.update(my_device)
            client.collection('users').document(user_doc.id).update({'devices': user_devices})

            return ResponseUtil.success("Device added successfully", [])
        
        else:
            return ResponseUtil.error("Device not found", data=None, status_code=400)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)
