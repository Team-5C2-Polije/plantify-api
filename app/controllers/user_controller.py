from flask import Blueprint, jsonify, request, current_app
from ..utils.response_util import ResponseUtil

user_bp = Blueprint('user', __name__)

@user_bp.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    user_ref = current_app.db.collection('users').document(user_id).get()
    if user_ref.exists:
        return ResponseUtil.success("User found", user_ref.to_dict())
    else:
        return ResponseUtil.error("User not found", data=None, status_code=404)

@user_bp.route('/users', methods=['POST'])
def add_user():
    data = request.json
    user_ref = current_app.db.collection('users').document()
    user_ref.set(data)
    return ResponseUtil.success("User created successfully", data)
