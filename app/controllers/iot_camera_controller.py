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

# kirim foto ke server
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

# kirim foto dari mobile ke server
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
                "predictions": predictions,
                'from': 'Mobile'
            }
            # Menyimpan data new_photo ke Firestore
            client.collection('devices').document(device_id).collection('photos').add(new_photo)

            return ResponseUtil.success("Photo uploaded and saved successfully", data=None)
        else:
            return ResponseUtil.error("Failed to upload photo", data=None, status_code=500)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error add_photo: {str(e)}", status_code=500)

# kirim foto dari esp ke server
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
                "predictions": predictions,
                "from": "Camera"
            }
            # Menyimpan data new_photo ke Firestore di koleksi 'photos' pada perangkat yang ditemukan
            client.collection('devices').document(device_id).collection('photos').add(new_photo)

            return ResponseUtil.success("Photo uploaded and saved successfully", data=None)
        else:
            return ResponseUtil.error("Failed to upload photo", data=None, status_code=500)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

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
