from flask import Blueprint, jsonify, request
from ..utils.response_util import ResponseUtil
from firebase_admin import initialize_app, storage, credentials, firestore
from firebase_admin.firestore import SERVER_TIMESTAMP

device_bp = Blueprint('device', __name__)
client = firestore.client()

@device_bp.route('/device/my', methods=['GET'])
def my_devices():
    data = request.json
    ids = data.get('ids', [])

    if not isinstance(ids, list) or not ids:
        return ResponseUtil.error("IDs must be a non-empty list", status_code=400)

    try:
        devices_data = []
        for device_id in ids:
            device_ref = client.collection('devices').document(device_id).get()
            if device_ref.exists:
                devices_data.append(device_ref.to_dict())

        return ResponseUtil.success("Devices retrieved successfully", data=devices_data)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>', methods=['GET'])
def device_detail(device_id):
    try:
        device_ref = client.collection('devices').document(device_id).get()
        if device_ref.exists:
            device_data = device_ref.to_dict()
            return ResponseUtil.success("Device details retrieved successfully", data=device_data)
        else:
            return ResponseUtil.error("Device not found", status_code=404)
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

@device_bp.route('/device/<device_id>/histories', methods=['GET'])

@device_bp.route('/device/<device_id>/photos', methods=['GET'])
def photos(device_id):
    try:
        photos_ref = client.collection('devices').document(device_id).collection('photos').get()
        photos_data = []

        for photo in photos_ref:
            # Include the document ID in the photo data
            photo_dict = photo.to_dict()
            photo_dict['id'] = photo.id  # Adding document ID
            photos_data.append(photo_dict)

        return ResponseUtil.success("Photos retrieved successfully", data=photos_data)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>/histories', methods=['GET'])
def histories(device_id):
    try:
        histories_ref = client.collection('devices').document(device_id).collection('histories').get()
        histories_data = []

        for history in histories_ref:
            # Include the document ID in the history data
            history_dict = history.to_dict()
            history_dict['id'] = history.id  # Adding document ID
            histories_data.append(history_dict)

        return ResponseUtil.success("Histories retrieved successfully", data=histories_data)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)
