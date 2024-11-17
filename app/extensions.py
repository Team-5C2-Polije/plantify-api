import os
from firebase_admin import credentials, firestore, initialize_app

cred_path = os.getenv("FIREBASE_CREDENTIALS", "firebase_credential.json")
cred = credentials.Certificate(cred_path)
initialize_app(cred)

db = firestore.client()
