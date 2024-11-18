import os
import firebase_admin
from firebase_admin import credentials, firestore, db

# Pastikan kredensial diinisialisasi hanya sekali
if not firebase_admin._apps:
    cred_path = os.getenv("FIREBASE_CREDENTIALS", "firebase_credential.json")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://team-5c2-polije-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

# Inisialisasi Firestore
db = firestore.client()
