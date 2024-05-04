# get connected serial ports
import serial
import serial.tools.list_ports
import time
from flask_cors import cross_origin
from sqlalchemy.exc import SQLAlchemyError
from flask import Blueprint, jsonify, request, make_response
from models.printers import Printer

ports_bp = Blueprint("ports", __name__)

"""
    Get all connected serial ports. Only return ports that are connected to 3D printers. 
"""
@ports_bp.route("/getports",  methods=["GET"])
def getPorts():
    printerList = Printer.getConnectedPorts()
    return jsonify(printerList)

"""
    Gets all registered printers from the database
"""
@ports_bp.route("/getprinters", methods=["GET"])
def getRegisteredPrinters():  
    try: 
        res = Printer.get_registered_printers()
        return res
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    Register a new printer in the database and create a thread for it. App imported directly in the function 
    to avoid circular import error.
"""
@ports_bp.route("/register", methods=["POST"])
def registerPrinter(): 
    try: 
        from app import printer_status_service
        data = request.get_json() 
        device = data['printer']['device']
        description = data['printer']['description']
        hwid = data['printer']['hwid']
        name = data['printer']['name']
        
        res = Printer.create_printer(device=device, description=description, hwid=hwid, name=name, status='ready')
        if(res["success"] == True):
            id = res['printer_id']
            thread_data = {
                "id": id, 
                "device": device,
                "description": description,
                "hwid": hwid,
                "name": name
            }
            
            printer_status_service.create_printer_threads([thread_data])
        
        return res
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    Deletes printer from database. The thread is removed through a controller in statusService.py 
"""
@ports_bp.route("/deleteprinter", methods=["POST"])
def delete_printer():
    try: 
        data = request.get_json()
        printerid = data['printerid']
        res = Printer.deletePrinter(printerid)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Edits name of printer in database. Name edited in-memory in statusService.py
"""
@ports_bp.route("/editname", methods=["POST"])
def edit_name(): 
    try: 
        data = request.get_json() 
        printerid = data['printerid']
        name = data['name']
        res = Printer.editName(printerid, name)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Tells user if printer is connected to a serial port or not and if the port it is registered under 
    is the port that the printer is currently connected to.
"""
@ports_bp.route("/diagnose", methods=["POST"])
def diagnose_printer():
    try:
        data = request.get_json() 
        device = data['device']
        res = Printer.diagnosePrinter(device)
        return res
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Route to send the "printer home" gcode command while the printer is registering a printer, so the user can tell 
    which printer they have selected. 
"""
@ports_bp.route("/movehead", methods=["POST"])
def moveHead():
    try: 
        data = request.get_json()
        port = data['port']
        
        res = Printer.moveHead(port)
        if res == "none": 
            return {"success": False, "message": "Head move unsuccessful."}
        
        return {"success": True, "message": "Head move successful."}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    Method to change the order of printer threads so the user can rearrange the order of printers on the UI (Main view)
"""
@ports_bp.route("/moveprinterlist", methods=["POST"])
def movePrinterList():
    try:
        from app import printer_status_service
        data = request.get_json()
        printersIds = data['printersIds']

        res = printer_status_service.movePrinterList(printersIds) 
        if res == "none": 
            return {"success": False, "message": "Printer list not updated."}
               
        return jsonify({"success": True, "message": "Printer list successfully updated."})
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500