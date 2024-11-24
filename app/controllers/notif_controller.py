from flask import request, jsonify, Blueprint
import firebase_admin
from firebase_admin import messaging, credentials, firestore

notification_bp = Blueprint('notif', __name__)
client = firestore.client()

from flask import request, jsonify
from firebase_admin import messaging
from firebase_admin import firestore

# Inisialisasi Firestore client
db = firestore.client()

@notification_bp.route('/notif/send', methods=['POST'])
def send_notifications():
    data = request.json
    token = data.get('token') 
    title = data.get('title')  
    body = data.get('body')    

    if not token:
        return jsonify({"error": "Token is required"}), 400
    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not body:
        return jsonify({"error": "Body is required"}), 400

    try:
        # Ambil semua dokumen dari koleksi 'users'
        user_refs = db.collection('users').stream()
        fcm_tokens = []

        # Iterasi setiap dokumen user
        for user_ref in user_refs:
            user_data = user_ref.to_dict()
            devices = user_data.get('devices', {})  # Ambil field 'devices'

            # Pastikan devices adalah dictionary
            if isinstance(devices, dict):
                # Iterasi setiap device dalam field 'devices'
                for device_id, device_info in devices.items():
                    # Pastikan device_info adalah dictionary
                    if isinstance(device_info, dict) and device_info.get('token') == token:
                        fcm_token = user_data.get('fcmToken')  # Ambil FCM token user
                        if fcm_token:
                            fcm_tokens.append(fcm_token)

        if not fcm_tokens:
            return jsonify({"error": "No users found with the specified token"}), 404

        # Kirim notifikasi ke setiap fcmToken dalam list
        for fcm_token in fcm_tokens:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=fcm_token
            )
            messaging.send(message)

        return jsonify({"success": True, "message": "Notifications sent successfully"}), 200

    except Exception as e:
        return jsonify({"error": f"Failed to send notifications: {str(e)}"}), 500
