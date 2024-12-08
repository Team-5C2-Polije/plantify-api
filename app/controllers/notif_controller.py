from flask import request, jsonify, Blueprint
import firebase_admin
from firebase_admin import messaging, firestore
from datetime import datetime, timedelta
import pytz

notification_bp = Blueprint('notif', __name__)

# Initialize Firestore client (make sure Firebase app is initialized)
db = firestore.client()

# @notification_bp.route('/notif/send', methods=['POST'])
# def send_notifications():
#     data = request.json
#     device_name = data.get('deviceName')
#     waterVol = data.get('waterVol')
#     token = data.get('token') 
#     title = data.get('title')  
#     body = data.get('body')    

#     if not device_name:
#         return jsonify({"error": "Device Name is required"}), 400
#     if not waterVol:
#         return jsonify({"error": "WaterVol is required"}), 400
#     if not token:
#         return jsonify({"error": "Token is required"}), 400
#     if not title:
#         return jsonify({"error": "Title is required"}), 400
#     if not body:
#         return jsonify({"error": "Body is required"}), 400

    # try:
    #     # Ambil device berdasarkan token
    #     device_query = db.collection('devices').where('token', '==', token).limit(1).stream()
    #     device_id = None

    #     for device in device_query:
    #         device_id = device.id
    #         break

    #     if not device_id:
    #         return jsonify({"error": "Device not found for the provided token"}), 404
    
    #     print('device id : ', device_id)

    #     # Query users who might have the device in their 'devices' field
    #     user_refs = db.collection('users').stream()

    #     fcm_tokens = []

    #     jakarta_tz = pytz.timezone('Asia/Jakarta')
    #     now = datetime.now(jakarta_tz)

    #     # Iterate through each user document
    #     for user_ref in user_refs:
    #         user_data = user_ref.to_dict()
    #         fcm_token = user_data.get('fcmToken')
    #         device_ids = user_data.get('devices', {}).keys()
            
    #         if device_id in device_ids:

    #             # If FCM token exists, proceed to check the last notification time
    #             if fcm_token:
    #                 # Get the most recent notification for the user (ordered by sendAt)
    #                 user_doc_ref = db.collection('users').document(user_ref.id)
    #                 notifications_ref = user_doc_ref.collection('notifications').order_by('sendAt', direction=firestore.Query.DESCENDING).limit(1)

    #                 notifications = notifications_ref.stream()
    #                 is_empty = not any(notifications)

    #                 if not is_empty:
    #                     latest_notification = notifications_ref.stream()

    #                     last_sent_time = None
    #                     for notification in latest_notification:
    #                         notification_data = notification.to_dict()
    #                         last_sent_time = notification_data.get('sendAt')

    #                     # If there is a last sent time, compare it to the current time
    #                     if last_sent_time:
    #                         # Convert last_sent_time (which is in UTC) to Asia/Jakarta timezone
    #                         last_sent_time = last_sent_time.astimezone(jakarta_tz)  # Convert to Asia/Jakarta timezone

    #                         # Calculate the time difference
    #                         time_diff = now - last_sent_time

    #                         # Round to seconds (ignores microseconds)
    #                         time_diff_seconds = time_diff.total_seconds()

    #                         # Check if time difference is less than 1 hour (3600 seconds)
    #                         if time_diff_seconds < 3600:
    #                             continue  # Skip sending notification if less than 1 hour has passed
    #                         else:
    #                             # If we get here, it means the notification can be sent
    #                             fcm_tokens.append(fcm_token)
    #                 else:
    #                     fcm_tokens.append(fcm_token)

    #     if not fcm_tokens:
    #         return jsonify({"success": "No users found with the specified token"}), 200

    #     # Send notifications to the collected FCM tokens
    #     fcm_tokens = list(set(fcm_tokens))
    #     for fcm_token in fcm_tokens:
    #         message = messaging.Message(
    #             notification=messaging.Notification(
    #                 title=title,
    #                 body=body
    #             ),
    #             token=fcm_token
    #         )
    #         messaging.send(message)

    #         user_ref =  db.collection('users').where('fcmToken', '==', fcm_token).limit(1).get()
            
    #         if user_ref:
    #             # Check if user_ref contains any results
    #             if user_ref:
    #                 user_doc_ref = user_ref[0].reference  # Get the document reference of the first result
    #                 history_ref = user_doc_ref.collection('notifications')  # Access the user's 'notifications' subcollection

    #                 # Add the new notification to the history
    #                 history_ref.add({
    #                     'title': title,
    #                     'body': body,
    #                     'sendAt': firestore.SERVER_TIMESTAMP,
    #                     'deviceName': device_name,
    #                     'waterVol': waterVol,
    #                 })
    #         else:
    #             print('user not found')

    #     return jsonify({"message": "Notifications sent successfully!"}), 200

    # except Exception as e:
    #     return jsonify({"error": f"Failed to send notifications: {str(e)}"}), 500
