from models.db import db
from datetime import datetime, timezone
from sqlalchemy import Column, String, LargeBinary, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.exc import SQLAlchemyError
from flask import jsonify
from Classes.Queue import Queue
import serial
import serial.tools.list_ports
import time
from tzlocal import get_localzone
import os 
import json 
import requests 
from dotenv import load_dotenv
load_dotenv()

# model for Printer table
class Printer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(50), nullable=False)
    hwid = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).astimezone(), nullable=False)
    
    queue = None
    # queue = Queue()
    ser = None
    status = None  # default setting on printer start. Runs initialization and status switches to "ready" automatically.
    stopPrint = False

    def __init__(self, device, description, hwid, name, status=status, id=None):
        self.device = device
        self.description = description
        self.hwid = hwid
        self.name = name
        self.status = status
        self.date = datetime.now(get_localzone())
        self.queue = Queue()
        self.stopPrint = False 
        if id is not None:
            self.id = id

    # general classes
    @classmethod
    def searchByDevice(cls, hwid):
        try:
            # Query the database to find a printer by device
            printer = cls.query.filter_by(hwid=hwid).first()
            return printer is not None

        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return None

    @classmethod
    def create_printer(cls, device, description, hwid, name, status):
        printerExists = cls.searchByDevice(hwid)
        # if printerExists:
        #     return {"success": False, "message": "Printer already registered."}
        # else:
        try:
            printer = cls(
                device=device,
                description=description,
                hwid=hwid,
                name=name,
                status=status,
            )
            db.session.add(printer)
            db.session.commit()
            return {"success": True, "message": "Printer successfully registered.", "printer_id": printer.id}
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"error": "Failed to register printer. Database error"}),
                500,
            )

    @classmethod
    def get_registered_printers(cls):
        try:
            # Query the database to get all registered printers
            printers = cls.query.all()

            # Convert the list of printers to a list of dictionaries
            printers_data = [
                {   
                    "id": printer.id,
                    "device": printer.device,
                    "description": printer.description,
                    "hwid": printer.hwid,
                    "name": printer.name,
                    "status": printer.status,
                    "date": f"{printer.date.strftime('%a, %d %b %Y %H:%M:%S')} {get_localzone().tzname(printer.date)}",  # Include timezone abbreviation
                }
                for printer in printers
            ]
            # Return the list of printer information in JSON format
            return jsonify({"printers": printers_data}), 200

        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"error": "Failed to retrieve printers. Database error"}),
                500,
            )

    @classmethod
    def getConnectedPorts(cls): 
        ports = serial.tools.list_ports.comports()
        printerList = []
        for port in ports:
            port_info = {
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid,
            }
            supportedPrinters = ["Original Prusa i3 MK3", "Makerbot"]
            # if port.description in supportedPrinters:
            printerList.append(port_info)
        return printerList
    
    @classmethod 
    def findPrinter(cls, id):
        try:
            printer = cls.query.get(id)
            return printer
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"error": "Failed to retrieve printer. Database error"}),
                500,
            )

    def connect(self):
        self.ser = serial.Serial(self.device, 115200, timeout=1)

    def disconnect(self):
        if self.ser:
            self.ser.close()
            self.setSer(None)

    def reset(self):
        self.sendGcode("G28")
        self.sendGcode("G92 E0") 

    # Function to send gcode commands
    def sendGcode(self, message):
        try: 
            if self.getStatus()=="error" or self.getStatus()=='complete': # if any error occurs, do not proceed with printing.
                return
            # Encode and send the message to the printer.
            self.ser.write(f"{message}\n".encode("utf-8"))
            # Sleep the printer to give it enough time to get the instruction.
            time.sleep(0.1)
            # Save and print out the response from the printer. We can use this for error handling and status updates.
            while True:
                response = self.ser.readline().decode("utf-8").strip()
                if "ok" in response:
                    break
            print(f"Command: {message}, Received: {response}")
        except serial.SerialException as e:
            self.setStatus("error")
            return "error" 
        
    def parseGcode(self, path):
        try: 
            with open(path, "r") as g:
                # Replace file with the path to the file. "r" means read mode. 
                for line in g:
                    #remove whitespace
                    line = line.strip() 
                    # Don't send empty lines and comments. ";" is a comment in gcode.
                    if len(line) == 0 or line.startswith(";"): 
                        continue
                    # Send the line to the printer.
                    res = self.sendGcode(line)
                    if res == "error": 
                        return "error"
            return "complete"
        except FileNotFoundError:
            self.setStatus('complete')
            return 

    def printNextInQueue(self):
        job = self.getQueue().getNext() # get next job 
        try:
            if self.getSer():
                job.saveToFolder()
                path = job.generatePath()
                        
                # job.setStatus("printing") # set job status to printing 
                self.setStatus("printing") # set printer status to printing
                self.sendStatusToJob(job, job.id, "printing")
                self.reset()
                
                verdict = self.parseGcode(path) # passes file to code. returns "complete" if successful, "error" if not.

                if verdict =="complete":
                    self.setStatus("complete")
                    self.sendStatusToJob(job, job.id, "complete")
                else: 
                    self.sendStatusToJob(job, job.id, "error")
                    self.setStatus("error")
                    
                self.disconnect()
    
                job.removeFileFromPath() # remove file from folder after job complete
            # WHEN THE USER CLEARS THE JOB: remove job from queue, set printer status to ready. 
            
            else:
                self.setStatus("error")
                self.sendStatusToJob(job, job.id, "error")
        except serial.SerialException as e:
            self.setStatus("error")
            job.setStatus("error")
            return "error" 

    def fileExistsInPath(self, path): 
        if os.path.exists(path):
            return True
        
    # printer-specific classes
    def getDevice(self):
        return self.device

    def getQueue(self):
        return self.queue

    def getStatus(self):
        return self.status

    def getName(self):
        return self.name

    def getSer(self):
        return self.ser
    
    def getId(self):
        return self.id
    
    def getStopPrint(self):
        return self.stopPrint
    
    def setSer(self, port):
        self.ser = port

    def setStatus(self, newStatus):
        if newStatus=='ready': 
            if self.getSer():
                self.status = newStatus
            else: 
                self.status = "offline"
        
    def setStopPrint(self, stopPrint):
        self.stopPrint = stopPrint
        
    def sendStatusToJob(self, job, job_id, status):
        try:
            job.setStatus(status)
            data = {
                "printerid": self.id,
                "jobid": job_id,
                "status": status  # Assuming status is accessible here
            }
            base_url = os.getenv("BASE_URL", "http://localhost:8000")

            response = requests.post(f"{base_url}/updatejobstatus", json=data)
            if response.status_code == 200:
                print("Status sent successfully")
            else:
                print("Failed to send status:", response.text)
        except requests.exceptions.RequestException as e:
            print(f"Failed to send status to job: {e}")