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
