from flask import request, jsonify, Blueprint
import firebase_admin
from firebase_admin import messaging, firestore
from datetime import datetime, timedelta
import pytz

notification_bp = Blueprint('notif', __name__)

# Initialize Firestore client (make sure Firebase app is initialized)
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
        # Get all documents from the 'users' collection
        user_refs = db.collection('users').stream()
        fcm_tokens = []

        # Get the current time in Asia/Jakarta timezone
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        now = datetime.now(jakarta_tz)  # Current time in Asia/Jakarta timezone

        # Iterate through each user document
        for user_ref in user_refs:
            user_data = user_ref.to_dict()
            devices = user_data.get('devices', {})

            # Ensure 'devices' is a dictionary
            if isinstance(devices, dict):
                # Get FCM token if available
                fcm_token = user_data.get('fcmToken')

                # If FCM token exists, proceed to check the last notification time
                if fcm_token:
                    # Get the most recent notification for the user (ordered by sendAt)
                    user_doc_ref = db.collection('users').document(user_ref.id)
                    notifications_ref = user_doc_ref.collection('notifications').order_by('sendAt', direction=firestore.Query.DESCENDING).limit(1)
                    
                    latest_notification = notifications_ref.stream()

                    last_sent_time = None
                    for notification in latest_notification:
                        notification_data = notification.to_dict()
                        last_sent_time = notification_data.get('sendAt')

                    # If there is a last sent time, compare it to the current time
                    if last_sent_time:
                        # Convert last_sent_time (which is in UTC) to Asia/Jakarta timezone
                        last_sent_time = last_sent_time.astimezone(jakarta_tz)  # Convert to Asia/Jakarta timezone

                        # Calculate the time difference
                        time_diff = now - last_sent_time

                        # Round to seconds (ignores microseconds)
                        time_diff_seconds = time_diff.total_seconds()

                        # Check if time difference is less than 1 hour (3600 seconds)
                        if time_diff_seconds < 3600:
                            continue  # Skip sending notification if less than 1 hour has passed
                        else:
                            # If we get here, it means the notification can be sent
                            fcm_tokens.append(fcm_token)


        if not fcm_tokens:
            return jsonify({"error": "No users found with the specified token"}), 404

        # Send notifications to the collected FCM tokens
        for fcm_token in fcm_tokens:
            print('send to ' + fcm_token)
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=fcm_token
            )
            messaging.send(message)

            print("fcmToken : ", fcm_token)
            user_ref =  db.collection('users').where('fcmToken', '==', fcm_token).limit(1).get()
            
            print('user ref : ', user_data)
            if user_ref:
                # Check if user_ref contains any results
                if user_ref:
                    user_doc_ref = user_ref[0].reference  # Get the document reference of the first result
                    history_ref = user_doc_ref.collection('notifications')  # Access the user's 'notifications' subcollection

                    # Add the new notification to the history
                    history_ref.add({
                        'title': title,
                        'body': body,
                        'sendAt': firestore.SERVER_TIMESTAMP  # This will set the server's timestamp
                    })
            else:
                print('user not found')

        return jsonify({"message": "Notifications sent successfully!"}), 200

    except Exception as e:
        return jsonify({"error": f"Failed to send notifications: {str(e)}"}), 500
