import random
import requests
import time

def generate_random_data():
    """Generate random sensor data as integers."""
    return {
        "lightIntensity": random.randint(0, 4000),
        "waterVol": random.randint(0, 100),  # Integer untuk water volume
        "temperature": random.randint(-8, 40),  # Integer untuk temperature
        "soilMoisture": random.randint(0, 4000)
    }

def call_update_sensors():
    """Call the update_sensors API with random data."""
    url = "http://192.168.34.152:5000/device/update_sensors"
    token = "h6zhsIrshy80iXMIcawg"

    data = generate_random_data()
    data["token"] = token

    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print(f"Success: {response.json()}")
        else:
            print(f"Failed: {response.status_code}, Response: {response.json()}")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == '__main__':
    while True:
        call_update_sensors()
        time.sleep(10)
