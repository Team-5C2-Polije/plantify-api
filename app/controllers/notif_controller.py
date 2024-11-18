from flask import request, jsonify, Blueprint
import firebase_admin
from firebase_admin import messaging, credentials, firestore

notification_bp = Blueprint('notif', __name__)
client = firestore.client()

@notification_bp.route('/notif/send', methods=['POST'])
def send_notifications():
    data = request.json
    device_id = data.get('device_id')
    title = data.get('title')
    body = data.get('body')

    if not device_id:
        return jsonify({"error": "Device ID is required"}), 400
    if not title:
        return jsonify({"error": "Title is required"}), 400
    if not body:
        return jsonify({"error": "Body is required"}), 400

    try:
        # Ambil semua user dari koleksi 'users'
        user_refs = client.collection('users').stream()
        fcm_tokens = []

        # Iterasi setiap user untuk memeriksa device_id di field 'devices'
        for user_ref in user_refs:
            user_data = user_ref.to_dict()
            devices = user_data.get('devices', {})

            if device_id in devices:
                fcm_token = user_data.get('fcmToken')
                if fcm_token:
                    fcm_tokens.append(fcm_token)

        if not fcm_tokens:
            return jsonify({"error": "No users found with the specified device ID"}), 404

        # Kirim notifikasi ke setiap fcmToken dalam list
        for token in fcm_tokens:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=token
            )
            response = messaging.send(message)
        
        return jsonify({"success": True, "message": "Notifications sent successfully"}), 200

    except Exception as e:
        return jsonify({"error": f"Failed to send notifications: {str(e)}"}), 500