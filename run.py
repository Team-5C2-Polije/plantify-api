import os
from app import create_app

app = create_app()

# Mengatur IP dan port menggunakan variabel lingkungan
host = os.environ.get('FLASK_RUN_HOST', '192.168.110.153')
port = int(os.environ.get('FLASK_RUN_PORT', 5000))

if __name__ == '__main__':
    app.run(host=host, port=port)
