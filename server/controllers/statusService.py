from flask import Blueprint, jsonify
from app import printer_status_service  # import the instance from app.py
from flask import Blueprint, jsonify, request
from models.jobs import Job 

status_bp = Blueprint("status", __name__)

"""
    Returns all printer threads to frontend. This is the main method to display in-memory data and printer queues. 
"""
@status_bp.route('/getprinterinfo', methods=["GET"])
def getPrinterInfo():
    try: 
        printer_info = printer_status_service.retrieve_printer_info()  # call the method on the instance
        return jsonify(printer_info)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    route to delete thread from in-memory data and recreate it. 
"""
@status_bp.route('/hardreset', methods=["POST"])
def hardreset():
    try: 
        data = request.get_json() 
        id = data['printerid']
        res = printer_status_service.resetThread(id)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
@status_bp.route('/hardresetqueue', methods=["POST"])
def hardresetQueue():
    try: 
        data = request.get_json() 
        id = data['printerid']
        res = printer_status_service.resetThread(printer_id=id, restore=1)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Deletes printer thread. This is used when the user deregisters a printer. 
"""
@status_bp.route("/removethread", methods=["POST"])
def removeThread():
    try:
        data = request.get_json() # get json data
        printerid = data['printerid']
        res = printer_status_service.deleteThread(printerid)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Edits name of printer in-memory. When the user edits the name of the printer, the in-memory printer name
    is also updated. In-database name also updated in ports.py 
"""
@status_bp.route("/editNameInThread", methods=["POST"])
def editName(): 
    try: 
        data = request.get_json() 
        printerid = data['printerid']
        name = data['newname']
        res = printer_status_service.editName(printerid, name)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
