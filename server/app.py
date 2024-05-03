from flask import Flask, jsonify, request, Response, url_for
from threading import Thread
from flask_cors import CORS 
import os 
from models.db import db
from models.printers import Printer
from models.PrinterStatusService import PrinterStatusService
from flask_migrate import Migrate
from dotenv import load_dotenv
from controllers.ports import getRegisteredPrinters
import shutil
from flask_socketio import SocketIO
from datetime import datetime, timedelta
from sqlalchemy import text

"""
This is the main entry point for the backend server. It initializes the Flask app,
    
"""
app = Flask(__name__)
app.config.from_object(__name__) 


"""
Initializing web sockets 
"""
printer_status_service = PrinterStatusService(app)
socketio = SocketIO(app, cors_allowed_origins="*", engineio_logger=False, socketio_logger=False, async_mode='threading') # Initialize SocketIO with the Flask app
app.socketio = socketio 


"""
 Importing blueprints for the controllers
"""
from controllers.ports import ports_bp
from controllers.jobs import jobs_bp
from controllers.statusService import status_bp, getStatus 
from controllers.issues import issue_bp

"""
    Enabling CORS for the app
"""
CORS(app)


"""
    Handles preflight reqiests apart of CORS
"""
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        res = Response()
        res.headers['X-Content-Type-Options'] = '*'
        return res

"""
    Load environment variables and initialize database/database migartion tool 
"""
load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))
database_file = os.path.join(basedir, os.environ.get('SQLALCHEMY_DATABASE_URI'))
database_uri = 'sqlite:///' + database_file
app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
migrate = Migrate(app, db)


"""
    Register blueprints 
"""
app.register_blueprint(ports_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(status_bp)
app.register_blueprint(issue_bp)

"""
    On server start, retrieve registered printers from database & get JSON. 
    Create printer threads based on registered printers. 
    Create & empty "uploads" folder. Used for temp. file storage while print is printing. 

"""
with app.app_context(): # On server start 
    try:
        res = getRegisteredPrinters() 
        data = res[0].get_json()
        printers_data = data.get("printers", []) 
        printer_status_service.create_printer_threads(printers_data)
        
        uploads_folder = os.path.join('../uploads')
        tempcsv = os.path.join('../tempcsv')

        if os.path.exists(uploads_folder):
            # Remove the uploads folder and all its contents
            shutil.rmtree(uploads_folder)
            shutil.rmtree(tempcsv)

            # Recreate it as an empty directory
            os.makedirs(uploads_folder)
            os.makedirs(tempcsv)

            print("Uploads folder recreated as an empty directory.")
        else:
            # Create the uploads folder if it doesn't exist
            os.makedirs(uploads_folder)
            print("Uploads folder created successfully.")  
    except Exception as e:
        print(f"Unexpected error: {e}")
            
"""
    Run sockets, start server 
"""
if __name__ == "__main__":
    socketio.run(app, port=8000, debug=True)  # Replace app.run with socketio.run