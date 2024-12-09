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

@device_bp.route('/device/create_device', methods=['POST'])
def create_device():
    data = request.json
    name = data.get('name')

    if not name:
        return ResponseUtil.error("Device name parameter is required", data=None, status_code=400)
    
    device_id = int(time.time())

    token = ''.join(random.choices(string.ascii_letters + string.digits, k=20))

    device = {
        "createdAt": SERVER_TIMESTAMP,
        "updatedAt": SERVER_TIMESTAMP,
        "name": name,
        "schedules": {},
        "sensors": {
            "lightIntensity": 0,
            "soilMoisture": 0,
            "temperature": 0,
            "waterVol": 0,
        },
        "token": token
    }

    try:
        client.collection('devices').document(str(device_id)).set(device)
        return ResponseUtil.success("Device created successfully", data=token)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)
    
@device_bp.route('/device/update_device', methods=['POST'])
def update_device_name():
    data = request.json
    device_id = data.get('device_id')
    name = data.get('name')

    if not name:
        return ResponseUtil.error("Device name parameter is required", data=None, status_code=400)

    try:
        # Update nama device di Firestore
        device_ref = client.collection('devices').document(device_id)
        device_doc = device_ref.get()

        if device_doc.exists:
            device_ref.update({
                "name": name,
                "updatedAt": SERVER_TIMESTAMP
            })
        else:
            return ResponseUtil.error("Device not found in Firestore", status_code=404)

        return ResponseUtil.success("Device name updated successfully")

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/delete_device/<device_id>', methods=['DELETE'])
def delete_device(device_id):
    try:
        device_ref = client.collection('devices').document(device_id)
        if device_ref.get().exists:
            device_ref.delete()
        else:
            return ResponseUtil.error("Device not found in Firestore", status_code=404)

        return ResponseUtil.success("Device deleted successfully")

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

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

@device_bp.route('/device/my', methods=['GET'])
def my_devices():
    data = request.json
    ids = data.get('ids', [])

    if not isinstance(ids, list) or not ids:
        return ResponseUtil.error("IDs must be a non-empty list", status_code=400)

    try:
        devices_info = []  # List untuk menyimpan semua data perangkat

        for device_id in ids:
            device_ref = client.collection('devices').document(device_id).get()
            if device_ref.exists:
                device_data = device_ref.to_dict() 
                device_data['deviceId'] = device_ref.id 
                devices_info.append(device_data)

        if not devices_info:
            return ResponseUtil.error("No devices found", status_code=404)

        return ResponseUtil.success("Devices retrieved successfully", data=devices_info)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)


@device_bp.route('/device/<device_id>', methods=['GET'])
def device_detail(device_id):
    try:
        # Ambil data dokumen device dari Firestore
        device_ref = client.collection('devices').document(device_id).get()
        if device_ref.exists:
            device_data = device_ref.to_dict()

            # Menghitung total dokumen di dalam koleksi "photos"
            photos_ref = client.collection('devices').document(device_id).collection('photos')
            history_ref = client.collection('devices').document(device_id).collection('histories')
            total_photo = len(list(photos_ref.stream()))
            total_history = len(list(history_ref.stream()))

            # Tambahkan data total ke response
            device_data['total_photo'] = total_photo
            device_data['total_history'] = total_history

            return ResponseUtil.success("Device details retrieved successfully", data=device_data)
        else:
            return ResponseUtil.error("Device not found", status_code=404)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>/photos', methods=['GET'])
def photos(device_id):
    try:
        photos_ref = client.collection('devices') \
                            .document(device_id) \
                            .collection('photos') \
                            .order_by('createdAt', direction=firestore.Query.DESCENDING) \
                            .get()

        photos_data = []

        for photo in photos_ref:
            # Menambahkan document ID ke dalam data photo
            photo_dict = photo.to_dict()
            photo_dict['id'] = photo.id  # Adding document ID
            photos_data.append(photo_dict)

        return ResponseUtil.success("Photos retrieved successfully", data=photos_data)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>/photos/<photo_id>', methods=['GET'])
def detail_photo(device_id, photo_id):
    try:
        photo_ref = client.collection('devices').document(device_id).collection('photos').document(photo_id).get()
        
        if photo_ref.exists:
            photo_data = photo_ref.to_dict()
            return ResponseUtil.success("Photo details retrieved successfully", data=photo_data)
        else:
            return ResponseUtil.error("Photo not found", status_code=404)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

def upload_photo_to_storage(photo, folder):
    if not folder:
        raise ValueError("Folder parameter is required")
    
    if not photo:
        raise ValueError("Photo file is required")
    
    # Define upload and output folder paths
    upload_folder = os.path.abspath(f'files/temp/{folder}/')
    os.makedirs(upload_folder, exist_ok=True)
    output_folder = os.path.abspath(f'files/temp/{folder}/output')
    os.makedirs(output_folder, exist_ok=True)
    output_folder_crops = os.path.abspath(f'files/temp/{folder}/output_crops')
    os.makedirs(output_folder_crops, exist_ok=True)

    # Save the original photo
    filename = secure_filename(photo.filename)
    file_path = os.path.join(upload_folder, filename)
    file_output = os.path.join(upload_folder, 'output.png')  # Output file for processed image
    photo.save(file_path)

    try:
        print("Detect function started")  # Debug log
        # Process the image and save the output
        predictions = detect(file_path, file_output, output_folder, output_folder_crops)

        # print('json : ', str(predictions))

        print("Image processed, starting upload to Firebase Storage")  # Debug log
        # Upload the processed file (not the original one) to Firebase Storage
        file_name = f"{folder}/{uuid.uuid4()}.jpg"
        bucket = storage.bucket("team-5c2-polije.appspot.com")
        blob = bucket.blob(file_name)
        
        # Upload the processed file to Firebase Storage (use file_output here)
        blob.upload_from_filename(file_output, content_type="image/jpeg")
        blob.make_public()

        # Get the URL for the uploaded photo
        photo_url = blob.public_url

        print("Cleaning up temporary files...")  # Debug log
        # Cleanup: Remove all files and folders inside upload_folder
        shutil.rmtree(upload_folder)

        return photo_url, predictions
    except Exception as e:
        # Cleanup in case of failure
        if os.path.exists(upload_folder):
            shutil.rmtree(upload_folder)
        raise RuntimeError(f"Error while uploading photo: {str(e)}")
    
@device_bp.route('/device/add_photo', methods=['POST'])
def add_photo():
    data = request.files
    device_id = request.form.get('device_id')

    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    
    if 'photo' not in data:
        return ResponseUtil.error("Photo file is required", data=None, status_code=400)

    photo = data['photo']

    try:
        # Mengunggah foto dan mendapatkan URL
        photoUrl, predictions = upload_photo_to_storage(photo, device_id)

        print('predict : ', predictions)
        print('predict : ', photoUrl)

        if photoUrl:
            new_photo = {
                "createdAt": SERVER_TIMESTAMP,
                "photoUrl": photoUrl,
                "updatedAt": SERVER_TIMESTAMP,
                "predictions": predictions
            }
            # Menyimpan data new_photo ke Firestore
            client.collection('devices').document(device_id).collection('photos').add(new_photo)

            return ResponseUtil.success("Photo uploaded and saved successfully", data=None)
        else:
            return ResponseUtil.error("Failed to upload photo", data=None, status_code=500)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error add_photo: {str(e)}", status_code=500)

@device_bp.route('/device/add_photo_by_token', methods=['POST'])
def add_photo_by_token():
    data = request.files
    token = request.form.get('token')

    if not token:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)
    
    if 'photo' not in data:
        return ResponseUtil.error("Photo file is required", data=None, status_code=400)

    photo = data['photo']

    try:
        # Cari device berdasarkan token
        device_ref = client.collection('devices').where('token', '==', token).limit(1).get()

        if not device_ref:
            return ResponseUtil.error("Device not found with the provided token", data=None, status_code=404)

        # Ambil device_id dari data device yang ditemukan
        device_data = device_ref[0].to_dict()
        device_id = device_ref[0].id

        # Mengunggah foto dan mendapatkan URL
        photoUrl, predictions = upload_photo_to_storage(photo, device_id)

        print('predict : ', predictions)
        print('predict : ', photoUrl)

        if photoUrl:
            new_photo = {
                "createdAt": SERVER_TIMESTAMP,
                "photoUrl": photoUrl,
                "updatedAt": SERVER_TIMESTAMP,
                "predictions": predictions
            }
            # Menyimpan data new_photo ke Firestore di koleksi 'photos' pada perangkat yang ditemukan
            client.collection('devices').document(device_id).collection('photos').add(new_photo)

            return ResponseUtil.success("Photo uploaded and saved successfully", data=None)
        else:
            return ResponseUtil.error("Failed to upload photo", data=None, status_code=500)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>/histories', methods=['GET'])
def histories(device_id):
    try:
        histories_ref = client.collection('devices') \
                               .document(device_id) \
                               .collection('histories') \
                               .order_by('createdAt', direction=firestore.Query.DESCENDING) \
                               .get()

        histories_data = []

        for history in histories_ref:
            # Menambahkan document ID ke dalam data history
            history_dict = history.to_dict()
            history_dict['id'] = history.id  # Adding document ID
            histories_data.append(history_dict)

        return ResponseUtil.success("Histories retrieved successfully", data=histories_data)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

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

@device_bp.route('/device/add_schedule', methods=['POST'])
def add_schedule():
    data = request.json
    device_id = data.get('device_id')
    hour = data.get('hour')

    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    if not hour:
        return ResponseUtil.error("Hour parameter is required", data=None, status_code=400)
    
    try:
        # Ambil data schedules yang ada
        device_doc = client.collection('devices').document(device_id).get()
        if device_doc.exists:
            device_data = device_doc.to_dict()
            existing_schedules = device_data.get('schedules', {})

            # Ubah jam yang dimasukkan dan yang ada menjadi menit total untuk pengecekan
            new_hour_total = int(hour.split(':')[0]) * 60 + int(hour.split(':')[1])
            
            for existing_hour in existing_schedules.keys():
                existing_hour_total = int(existing_hour.split(':')[0]) * 60 + int(existing_hour.split(':')[1])
                
                # Cek apakah `new_hour_total` berada dalam rentang satu jam (60 menit) dari `existing_hour_total`
                if abs(new_hour_total - existing_hour_total) < 60:
                    return ResponseUtil.error(
                        f"Cannot add schedule. There is already a schedule within 60 minutes of {existing_hour}",
                        data=None,
                        status_code=400
                    )

            # Jika tidak ada konflik, tambahkan jadwal baru
            new_data = {
                f"schedules.{hour}": True,
                "updatedAt": SERVER_TIMESTAMP
            }
            client.collection('devices').document(device_id).update(new_data)

            return ResponseUtil.success("Schedule added successfully", data=None)
        else:
            return ResponseUtil.error("Device not found", data=None, status_code=404)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)


@device_bp.route('/device/update_schedule', methods=['POST'])
def update_schedule():
    data = request.json
    device_id = data.get('device_id')
    hour = data.get('hour')
    status = data.get('status')

    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    if not hour:
        return ResponseUtil.error("Hour parameter is required", data=None, status_code=400)
    if not status:
        return ResponseUtil.error("Status parameter is required", data=None, status_code=400)
    
    try:
        new_data = {
            f"schedules.{hour}": True if status == "1" else False,
            "updatedAt": SERVER_TIMESTAMP
        }
        client.collection('devices').document(device_id).update(new_data)
        
        return ResponseUtil.success("Schedule updated successfully", data=None)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)
    
@device_bp.route('/device/delete_schedule', methods=['POST'])
def delete_schedule():
    data = request.json
    device_id = data.get('device_id')
    hour = data.get('hour')

    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    if not hour:
        return ResponseUtil.error("Hour parameter is required", data=None, status_code=400)
    
    try:
        # Hapus field schedule berdasarkan hour dan perbarui updatedAt
        update_data = {
            f"schedules.{hour}": firestore.DELETE_FIELD,
            "updatedAt": firestore.SERVER_TIMESTAMP
        }
        client.collection('devices').document(device_id).update(update_data)

        return ResponseUtil.success("Schedule deleted successfully", data=None)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

def process_image(input_path, output_path, filename):
    with Image.open(input_path).convert("RGB") as img:
        resized_image = img.resize((512, 512))
        output_file_path = os.path.join(output_path, filename)
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        resized_image.save(output_file_path)
    print(f"Processed: {input_path} -> {output_file_path}")

def extract_features(image_path):
    try:
        img = cv2.imread(image_path)
        avg_color_per_row = cv2.mean(img)[:3]
        R, G, B = avg_color_per_row

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        glcm = mt.features.haralick(img_gray).mean(axis=0)
        contrast = glcm[1]
        homogeneity = glcm[4]
        energy = glcm[8]
        correlation = glcm[2]

        return [R, G, B, contrast, homogeneity, energy, correlation]
    except Exception as e:
        print(f"Gagal memproses {image_path}: {e}")
        return None


def predict_image(image_path, model):
    features = extract_features(image_path)
    if features is None:
        print(f"Gagal mengekstraksi fitur dari gambar {image_path}.")
        return None
    
    feature_names = ["R", "G", "B", "Kontras", "Homogenitas", "Energi", "Korelasi"]
    features_df = pd.DataFrame([features], columns=feature_names)

    prediction = model.predict(features_df)
    return prediction[0]

def predict_single_image(image_file):
    file_path = os.path.join(f'files/', 'model.pkl')
    model = joblib.load(file_path)

    result = predict_image(image_file, model)
    if result is not None:
        label = "Sehat" if result == 1 else "Sakit"
        return label
    else:
        return "Error dalam prediksi"

# input gambar
def detect(image_input, output_image, output_folder="output_crops", output_folder_procs="output_procs"):
    
    # setting font untuk bounding box
    font_path = os.path.join(f'files/', 'poppins_bold.ttf')

    try:
        font = ImageFont.truetype(font_path, size=20)
    except IOError:
        print(f"Font '{font_path}' tidak ditemukan, menggunakan default font.")
        font = ImageFont.load_default()

    # list color bounding box
    color_list = ["red", "blue", "purple", "navy", "magenta"]

    # create output folder
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(output_folder_procs, exist_ok=True)

    # Load image
    image = Image.open(image_input)

    # Create a copy for annotation
    annotated_image = image.copy()
    draw = ImageDraw.Draw(annotated_image)

    # Load font
    try:
        font = ImageFont.truetype(font_path, 20)
    except IOError:
        font = ImageFont.load_default()

    # Call API
    CLIENT = InferenceHTTPClient(
        api_url="https://detect.roboflow.com",
        api_key="MIebZflR9bJdmpmXovTj"
    )
    result = CLIENT.infer(image_input, model_id="tomato-leaf-disease-rxcft/3?confidence=0.20")
    print("PAYLOAD:", result)

    predictions = []

    # Process predictions
    for idx, prediction in enumerate(result.get("predictions", [])):
        x = prediction["x"]
        y = prediction["y"]
        width = prediction["width"]
        height = prediction["height"]

        # Calculate bounding box
        left = x - width / 2
        top = y - height / 2
        right = x + width / 2
        bottom = y + height / 2

        # Crop image
        cropped_image = image.crop((left, top, right, bottom))
        os.makedirs(output_folder, exist_ok=True)
        filename = f"crop_{idx + 1:02d}.png"
        crop_output_path = os.path.join(output_folder, filename)
        cropped_image.save(crop_output_path)

        # Preprocessing and prediction
        print('Preprocessing image:', crop_output_path)
        os.makedirs(output_folder_procs, exist_ok=True)
        process_image(crop_output_path, output_folder_procs, filename)
        label = predict_single_image(crop_output_path)

        predictions.append({
            "x": prediction["x"],
            "y": prediction["y"],
            "width": prediction["width"],
            "height": prediction["height"],
            "label": label,
        })

        # Add bounding box
        color = random.choice(color_list)
        draw.rectangle([(left, top), (right, bottom)], outline=color, width=3)
        label_position = (left, top - 25)
        draw.text(label_position, label, fill=color, font=font)

    # Save annotated image
    annotated_image.save(output_image)
    print(f"Annotated image with bounding boxes and labels saved at: {output_image}")

    return predictions

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


@device_bp.route('/notif/send', methods=['POST'])
def send_notifications():
    data = request.json
    token = data.get('token')

    # Pastikan semua parameter yang diperlukan tersedia
    if not token:
        return jsonify({"error": "Token parameter is required"}), 400

    # Data notifikasi yang akan dikirim
    send_notif = {
        "deviceName": 'Testing',
        'waterVol': '1000',
        'token': token,
        'title': 'Testing Notif',
        'body': 'Developer Mode'
    }

    # Panggil utilitas pengiriman notifikasi
    response, status_code = send_notifications_util(token, send_notif)

    # Kembalikan response secara langsung dengan status code yang sesuai
    return response, status_code
