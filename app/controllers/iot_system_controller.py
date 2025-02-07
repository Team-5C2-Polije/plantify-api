import os
import json
import time
import uuid
import shutil
import random
import string
import warnings
import joblib
import pandas as pd
import mahotas as mt
import cv2
from datetime import datetime, timedelta
from threading import Thread
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from firebase_admin import storage, firestore, messaging
from firebase_admin.firestore import SERVER_TIMESTAMP
import pytz
from inference_sdk import InferenceHTTPClient
warnings.filterwarnings("ignore", category=UserWarning, module="PIL")
from ..utils.response_util import ResponseUtil

device_bp = Blueprint('device', __name__)
client = firestore.client()

# update sensor value
@device_bp.route('/device/update_sensors', methods=['POST'])
def update_sensors():
    data = request.json
    token = data.get('token')
    light_intensity = data.get('lightIntensity')
    water_vol = data.get('waterVol')
    soil_moisture = data.get('soilMoisture')
    temperature = data.get('temperature')

    # Validasi input
    if token is None:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)
    if light_intensity is None:
        return ResponseUtil.error("Light intensity parameter is required", data=None, status_code=400)
    if water_vol is None:
        return ResponseUtil.error("Water volume parameter is required", data=None, status_code=400)
    if soil_moisture is None:
        return ResponseUtil.error("Soil moisture parameter is required", data=None, status_code=400)
    if temperature is None:
        return ResponseUtil.error("Temperature parameter is required", data=None, status_code=400)

    # Data sensor baru
    sensors = {
        "lightIntensity": light_intensity,
        "soilMoisture": soil_moisture,
        "temperature": temperature,
        "waterVol": water_vol,
    }

    try:
        # Cari dokumen perangkat berdasarkan token
        devices_ref = client.collection('devices')
        query = devices_ref.where('token', '==', token).get()

        if not query:
            return ResponseUtil.error("Device not found with the given token", data=None, status_code=404)

        # Ambil referensi dokumen
        device_doc = query[0].reference

        # Update data sensors dan updatedAt
        device_doc.update({
            "sensors": sensors,
            "updatedAt": SERVER_TIMESTAMP
        })

        data_input = {
            "token": token,
            "schedule": "00:00",
            "isManually": "1",
            "lightIntensity": light_intensity,
            "soilMoisture": soil_moisture,
            "temperature": temperature,
            "waterVol": water_vol,
        }

        add_history(data_input)

        # Get the actual data of the device document
        device_data = device_doc.get().to_dict()

        if water_vol <= 30.0:
            # Data untuk notifikasi
            print('send notif')
            send_notif = {
                "deviceName": device_data['name'],
                'waterVol': water_vol,
                'token': token,
                'title': 'Volume air tinggal ' + str(water_vol) + '%',
                'body': 'Segera lakukan pengisian air agar penyiraman dapat berlanjut'
            }

            response = send_notifications_util(token, send_notif)
            print('response : ', response)

        return ResponseUtil.success("Sensors updated successfully", data=None)
    except Exception as e:
        return ResponseUtil.error(f"An error occurred: {str(e)}", data=None, status_code=500)

# update history penyiraman
def add_history(data):
    # Ambil data dari input
    token = data.get('token')
    schedule = data.get('schedule')
    is_manually = data.get('isManually')
    light_intensity = data.get('lightIntensity')
    water_vol = data.get('waterVol')
    soil_moisture = data.get('soilMoisture')
    temperature = data.get('temperature')

    # Validasi input
    if not token:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)
    if schedule is None:
        return ResponseUtil.error("Schedule parameter is required", data=None, status_code=400)
    if is_manually is None:
        return ResponseUtil.error("isManually parameter is required", data=None, status_code=400)
    if light_intensity is None:
        return ResponseUtil.error("Light intensity parameter is required", data=None, status_code=400)
    if water_vol is None:
        return ResponseUtil.error("Water volume parameter is required", data=None, status_code=400)
    if soil_moisture is None:
        return ResponseUtil.error("Soil moisture parameter is required", data=None, status_code=400)
    if temperature is None:
        return ResponseUtil.error("Temperature parameter is required", data=None, status_code=400)

    try:
        # Cari device berdasarkan token
        device_ref = client.collection('devices').where('token', '==', token).limit(1).get()

        if not device_ref:
            return ResponseUtil.error("Device not found with the provided token", data=None, status_code=404)

        # Ambil device_id dari data device yang ditemukan
        device_data = device_ref[0].to_dict()
        device_id = device_ref[0].id

        # Membuat history baru
        new_history = {
            "createdAt": SERVER_TIMESTAMP,
            "schedule": schedule,
            "isManually": True if is_manually == "1" else False,
            "lightIntensity": light_intensity,
            "waterVol": water_vol,
            "soilMoisture": soil_moisture,
            "temperature": temperature,
        }

        # Menambahkan history ke dalam subkoleksi 'histories' dari device yang ditemukan
        client.collection('devices').document(device_id).collection('histories').add(new_history)

        return ResponseUtil.success("History added successfully", data=None)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

# mengirim notifikasi
def send_notifications_util(token, notif_data):

    if not token:
        return jsonify({"error": "Token is required"}), 400

    if not notif_data or not isinstance(notif_data, dict):
        return jsonify({"error": "Notif Data must be a valid dictionary"}), 400

    if 'title' not in notif_data or 'body' not in notif_data:
        return jsonify({"error": "Notif Data must include 'title' and 'body'"}), 400

    try:
        # Ambil device berdasarkan token
        device_query = client.collection('devices').where('token', '==', token).limit(1).stream()
        device_id = None

        for device in device_query:
            device_id = device.id
            break

        if not device_id:
            return jsonify({"error": "Device not found for the provided token"}), 404
    
        print('device id : ', device_id)

        # Query users who might have the device in their 'devices' field
        user_refs = client.collection('users').stream()

        fcm_tokens = []

        jakarta_tz = pytz.timezone('Asia/Jakarta')
        now = datetime.now(jakarta_tz)

        # Iterate through each user document
        for user_ref in user_refs:
            user_data = user_ref.to_dict()
            fcm_token = user_data.get('fcmToken')
            device_ids = user_data.get('devices', {}).keys()
            
            if device_id in device_ids:

                # If FCM token exists, proceed to check the last notification time
                if fcm_token:
                    # Get the most recent notification for the user (ordered by sendAt)
                    user_doc_ref = client.collection('users').document(user_ref.id)
                    notifications_ref = user_doc_ref.collection('notifications').order_by('sendAt', direction=firestore.Query.DESCENDING).limit(1)

                    notifications = notifications_ref.stream()
                    is_empty = not any(notifications)

                    if not is_empty:
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
                    else:
                        fcm_tokens.append(fcm_token)

        if not fcm_tokens:
            return jsonify({"success": "No users found with the specified token"}), 200

        # Send notifications to the collected FCM tokens
        fcm_tokens = list(set(fcm_tokens))
        for fcm_token in fcm_tokens:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notif_data['title'],
                    body=notif_data['body']
                ),
                token=fcm_token
            )
            messaging.send(message)

            user_ref =  client.collection('users').where('fcmToken', '==', fcm_token).limit(1).get()
            
            if user_ref:
                # Check if user_ref contains any results
                if user_ref:
                    user_doc_ref = user_ref[0].reference  # Get the document reference of the first result
                    history_ref = user_doc_ref.collection('notifications')  # Access the user's 'notifications' subcollection

                    # Add the new notification to the history
                    notif_data['sendAt'] = SERVER_TIMESTAMP
                    history_ref.add(notif_data)
            else:
                print('user not found')

        return jsonify({"message": "Notifications sent successfully!"}), 200

    except Exception as e:
        return jsonify({"error": f"Failed to send notifications: {str(e)}"}), 500
