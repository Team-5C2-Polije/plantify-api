import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
    FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "firebase_credential.json")
