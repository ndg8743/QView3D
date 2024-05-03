import re
from models.db import db
from datetime import datetime, timezone
from sqlalchemy import Column, String, LargeBinary, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.exc import SQLAlchemyError
from flask import jsonify, current_app
from Classes.Queue import Queue
import serial
import serial.tools.list_ports
import time
from datetime import datetime, timezone, timedelta 
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
    hwid = db.Column(db.String(150), nullable=False) # hardware ID 
    name = db.Column(db.String(50), nullable=False)
    date = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).astimezone(),
        nullable=False,
    )
    queue = None
    ser = None
    status = None
    responseCount = 0  # if count == 10 & no response from printer, set status to error 
    error = ""
    extruder_temp = 0
    bed_temp = 0
    canPause = 0 # Flag that allows user to pause print (can't pause during printer calibraton stages)
    prevMes = "" # Stores previous line sent to printer 
    colorbuff = 0 # Color buffer; When this == 1 and status is color change, the color change sequence will be initiated. (Only when current layer finishes)
    terminated = 0 # Set to 1 when the user does a "hard reset" of the thread in Registered View

    def __init__(self, device, description, hwid, name, status=status, id=None):
        self.device = device
        self.description = description
        self.hwid = hwid
        self.name = name
        self.status = status
        self.date = datetime.now(get_localzone())
        self.queue = Queue()
        self.stopPrint = False
        self.error = ""
        self.extruder_temp = 0
        self.bed_temp = 0
        self.canPause = 0
        self.prevMes=""
        self.colorbuff=0
        self.terminated = 0 
        
        # If ID is specified, set ID 
        if id is not None:
            self.id = id
            
        self.responseCount = 0


    """
        Locate printer in database based on HWID. Returns printer object
    """
    @classmethod
    def searchByDevice(cls, hwid):
        try:
            printer = cls.query.filter_by(hwid=hwid).first()
            return printer is not None
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return None


    """
        Duplicate method. Leaving for now because I don't remember where I called which function. 
    """
    @classmethod
    def getPrinterByHwid(cls, hwid):
        try:
            # Query the database to find a printer by device
            printer = cls.query.filter_by(hwid=hwid).first()
            if printer:
                return printer
            else:
                return None
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return None

    """
        Locate printer object based on PK
    """
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
            
    """
        Register a new printer in the database. Return an error if already registered. Check by HWID. 
    """
    @classmethod
    def create_printer(cls, device, description, hwid, name, status):
        try:                
            printerExists = cls.searchByDevice(hwid)
            if printerExists:
                printer = cls.query.filter_by(hwid=hwid).first()
                return {
                    "success": False,
                    "message": "Printer already registered.",
                }
            else:
                printer = cls(
                    device=device,
                    description=description,
                    hwid=hwid,
                    name=name,
                    status=status,
                )
                db.session.add(printer)
                db.session.commit()
                return {
                    "success": True,
                    "message": "Printer successfully registered.",
                    "printer_id": printer.id,
                }
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"success": False, "error": "Failed to register printer. Database error"}),
                500
            )


    """ 
        Retrieve all registered printers from database and return JSON 
    """
    @classmethod
    def get_registered_printers(cls):
        try:
            printers = cls.query.all()
            printers_data = [
                {
                    "id": printer.id,
                    "device": printer.device,
                    "description": printer.description,
                    "hwid": printer.hwid,
                    "name": printer.name,
                    "status": printer.status,
                    "date": f"{printer.date.strftime('%a, %d %b %Y %H:%M:%S')} {get_localzone().tzname(printer.date)}",
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

    """
        Get all ports connected to the machine. Append all ports that are 3D printers to an array and return so user can 
        select from a dropdown menu in Registered Printers and register a new printer based on selected serial ports.
    """
    @classmethod
    def getConnectedPorts(cls):
        ports = serial.tools.list_ports.comports()
        printerList = []
        for port in ports:
            hwid = port.hwid # get hwid 
            hwid_without_location = hwid.split(' LOCATION=')[0]  # Split at ' LOCATION=' and take the first part
            port_info = {
                "device": port.device,
                "description": port.description,
                "hwid": hwid_without_location,
            }


            if (("original" in port.description.lower()) or ("prusa" in port.description.lower())) and (Printer.getPrinterByHwid(hwid_without_location) is None) : # filtering out non-3D printers
                printerList.append(port_info)

        return printerList


    """
        In Registered Printers view. Allows the user to view if the serial port the 3D printer is registered under is the 
        same as the port it is currently connected to. 
        
        Also tells the user if the port the printer is registered under is now connected to a DIFFERENT registered 3D printer. 
        
        Not super necessary since we now check ports before printing, but it's a good diagnostic tool anyway to see if a registered printer 
        is/is not connected. 
    """
    @classmethod
    def diagnosePrinter(cls, deviceToDiagnose):  # deviceToDiagnose = port
        try:
            diagnoseString = ""
            ports = serial.tools.list_ports.comports()
            for port in ports:
                if port.device == deviceToDiagnose:
                    diagnoseString += f"The system has found a <b>matching port</b> with the following details: <br><br> <b>Device:</b> {port.device}, <br> <b>Description:</b> {port.description}, <br> <b>HWID:</b> {port.hwid}"
                    hwid = port.hwid 
                    hwid_without_location = hwid.split(' LOCATION=')[0]
                    printerExists = cls.searchByDevice(hwid_without_location)
                    if printerExists:
                        printer = cls.query.filter_by(hwid=hwid_without_location).first()
                        diagnoseString += f"<hr><br>Device <b>{port.device}</b> is registered with the following details: <br><br> <b>Name:</b> {printer.name} <br> <b>Device:</b> {printer.device}, <br> <b>Description:</b> {printer.description}, <br><b> HWID:</b> {printer.hwid}"
            if diagnoseString == "":
                diagnoseString = "The port this printer is registered under is <b>not found</b>. Please check the connection and try again."
            # return diagnoseString
            return {
                "success": True,
                "message": "Printer successfully diagnosed.",
                "diagnoseString": diagnoseString,
            }

        except Exception as e:
            print(f"Unexpected error: {e}")
            return jsonify({"error": "Unexpected error occurred"}), 500

    """
        Closes serial port associated with selected printer and then deletes printer from database. 
    """
    @classmethod
    def deletePrinter(cls, printerid):
        try:
            ports = Printer.getConnectedPorts()
            for port in ports:
                hwid = port["hwid"] # get hwid 
                if hwid == cls.query.get(printerid).hwid:
                    ser = serial.Serial(port["device"], 115200, timeout=1)
                    ser.close()
                    break 

            printer = cls.query.get(printerid)
            db.session.delete(printer)
            db.session.commit()
            return {"success": True, "message": "Printer successfully deleted."}
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"error": "Failed to delete printer. Database error"}),
                500,
            )

    """
        Edits the name of the printer in the database. Name is also edited in the in-memory thread in PrinterStatusService model. 
    """
    @classmethod
    def editName(cls, printerid, name):
        try:
            printer = cls.query.get(printerid)
            printer.name = name
            db.session.commit()
            return {"success": True, "message": "Printer name successfully updated."}
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"error": "Failed to update printer name. Database error"}),
                500,
            )

    """
        Edits port in the database for specified printer. Hardware ports are not static so we need to consistently update 
        the port before printing. 
    """
    @classmethod
    def editPort(cls, printerid, printerport):
        try:
            ports = Printer.getConnectedPorts()
            for port in ports:
                hwid = port['hwid'] # get hwid 
                if hwid == cls.query.get(printerid).hwid:
                    ser = serial.Serial(port["device"], 115200, timeout=1)
                    ser.close()
                    break 
            printer = cls.query.get(printerid)
            printer.device = printerport
            db.session.commit()
            
            current_app.socketio.emit(
                "port_repair", {"printer_id": printerid, "device": printerport}
            )
            return {"success": True, "message": "Printer port successfully updated."}
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"error": "Failed to update printer port. Database error"}),
                500,
            )
 
    """
        When the user is registering a printer, they can click the "move head" button to "home" the printer so they 
        know which printer they are currently registering if they are selecting from a long array of ports. 
    """    
    @classmethod 
    def moveHead(cls, device):
        ser = serial.Serial(device, 115200, timeout=1)
        message = "G28"
        ser.write(f"{message}\n".encode("utf-8"))

        response = ser.readline().decode("utf-8").strip()
        if("error" in response):
            return "none"
        ser.close()
        return 
       
    """
        Opens the serial port.
        Sends GCode command to report extruder/bed temperatures. 
    """ 
    def connect(self):
        try:
            self.ser = serial.Serial(self.device, 115200, timeout=10)
            self.ser.write(f"M155 S5\n".encode("utf-8"))
        except Exception as e:
            self.setError(e)
            return "error"

    """
        Closes serial port connection. 
    """
    def disconnect(self):
        if self.ser:
            self.ser.close()
            self.setSer(None)

    """ 
        Resets printer. 
    """
    def reset(self):
        self.sendGcode("G28")
        self.sendGcode("G92 E0")

    """
        Function to send gcode commands to printer. 
        
        The terminated flag is set to 1 when the user does a hard reset of the printer. 
        
        If the server is recieving an empty response from the printer, and the previous message was NOT M602 (in a calibration sequence), 
        add to the response count. Set the status to error if the printer has not responded after 10 attempts. 
        
        If there is an error in the response itself, set status to error. 
        
        Return bed/nozzle temperature updates. 
        
        Only break from loop when an "ok" response is received. 
        
    """
    def sendGcode(self, message):
        try:
            self.ser.write(f"{message}\n".encode("utf-8"))
            while True:
                if(self.terminated==1): 
                    return 
                
                response = self.ser.readline().decode("utf-8").strip()
                if response == "": 
                    if self.prevMes == "M602":
                        self.responseCount = 0
                        # break
                    else: 
                        self.responseCount+=1 
                        if(self.responseCount>=10):
                            self.setError("No response from printer")
                            raise Exception("No response from printer")

                elif "error" in response.lower():
                    self.setError(response)
                    break
                else:
                    self.responseCount = 0

                if ("T:" in response) and ("B:" in response):
                    # Extract the temperature values using regex
                    temp_t = re.search(r'T:(\d+.\d+)', response)
                    temp_b = re.search(r'B:(\d+.\d+)', response)
                    if temp_t and temp_b:
                        self.setTemps(temp_t.group(1), temp_b.group(1))

                if "ok" in response:
                    break

                print(f"Command: {message}, Received: {response}")
        except Exception as e: 
            self.setError(e)
            return "error"

    def gcodeEnding(self, message):
        try: 
            self.ser.write(f"{message}\n".encode("utf-8"))
            # Save and print out the response from the printer. We can use this for error handling and status updates.
            while True:
                if(self.terminated==1): 
                    return 
                # logic here about time elapsed since last response
                response = self.ser.readline().decode("utf-8").strip()

                if response == "":
                    self.responseCount += 1
                    if self.responseCount >= 10:
                        self.setError("No response from printer")
                        raise Exception("No response from printer")
                elif "error" in response.lower():
                    self.setError(response)
                    break
                else:
                    self.responseCount = 0
                
                if "ok" in response:
                    break
                print(f"Command: {message}, Received: {response}")
        except Exception as e:
            self.setError(e)
            return "error"

    def parseGcode(self, path, job):
        try:
            with open(path, "r") as g:
                # Read the file and store the lines in a list
                if(self.terminated==1): 
                    return 
                
                lines = g.readlines()

                #  Time handling
                comment_lines = [line for line in lines if line.strip() and line.startswith(";")]

                for i in reversed(range(len(comment_lines))):
                    # Check if the line contains ";LAYER_CHANGE"
                    if ";LAYER_CHANGE" in comment_lines[i]:
                        # Check if the next line exists
                        if i < len(comment_lines) - 1:
                            # Save the next line
                            line = comment_lines[i + 1]
                            # Use regex to find the numerical value after ";Z:"
                            match = re.search(r";Z:(\d+\.?\d*)", line)
                            if match:
                                max_layer_height = float(match.group(1))
                                break

                job.setMaxLayerHeight(max_layer_height)
                

                total_time = job.getTimeFromFile(comment_lines)
                job.setTime(total_time, 0)
                # job.setTime(total_time, 0)

                # Only send the lines that are not empty and don't start with ";"
                # so we can correctly get the progress
                command_lines = [
                    line for line in lines if line.strip() and not line.startswith(";")
                ]
                # store the total to find the percentage later on
                total_lines = len(command_lines)
                # set the sent lines to 0
                sent_lines = 0
                # previous line to check for layer height
                prev_line = ""
                # Replace file with the path to the file. "r" means read mode. 
                # now instead of reading from 'g', we are reading line by line
                for line in lines:
                    if(self.terminated==1): 
                        return 
                    
                    if("layer" in line.lower() and self.status=='colorchange' and job.getFilePause()==0 and self.colorbuff==0):
                        self.setColorChangeBuffer(1)

                    # if line contains ";LAYER_CHANGE", do job.currentLayerHeight(the next line)
                    if prev_line and ";LAYER_CHANGE" in prev_line:
                        match = re.search(r";Z:(\d+\.?\d*)", line)
                        if match:
                            current_layer_height = float(match.group(1))
                            job.setCurrentLayerHeight(current_layer_height)
                    prev_line = line

                    # remove whitespace
                    line = line.strip()
                    # Don't send empty lines and comments. ";" is a comment in gcode.
                    if ";" in line:  # Remove inline comments
                        line = line.split(";")[
                            0
                        ].strip()  # Remove comments starting with ";"

                    if len(line) == 0 or line.startswith(";"):
                        continue

                    if("M569" in line) and job.getTimeStarted()==0:
                        job.setTimeStarted(1)
                        job.setTime(job.calculateEta(), 1)
                        job.setTime(datetime.now(), 2)
                 
                    res = self.sendGcode(line)
                    
                    if(job.getFilePause() == 1):
                        # self.setStatus("printing")
                        job.setTime(job.colorEta(), 1)
                        job.setTime(job.calculateColorChangeTotal(), 0)
                        job.setTime(datetime.min, 3)
                        job.setFilePause(0)
                        if(self.getStatus()=="complete"):
                            return "cancelled"
                        self.setStatus("printing")
                    
                    if("M600" in line):
                        job.setTime(datetime.now(), 3)
                        # job.setTime(job.calculateTotalTime(), 0)
                        # job.setTime(job.updateEta(), 1)
                        self.setStatus("colorchange")
                        # self.setColorChangeBuffer(3)
                        # self.setColorChangeBuffer(1)
                        job.setFilePause(1)

                    if("M569" in line) and (job.getExtruded()==0):
                        job.setExtruded(1)
                    
                    if self.prevMes == "M602":
                        self.prevMes=""
                             
                #  software pausing        
                    if (self.getStatus()=="paused"):
                        # self.prevMes = "M601"
                        self.sendGcode("M601") # pause command for prusa
                        job.setTime(datetime.now(), 3)
                        while(True):
                            time.sleep(1)
                            stat = self.getStatus()
                            if(stat=="printing"):
                                self.prevMes = "M602"

                                self.sendGcode("M602") # resume command for prusa

                                time.sleep(2)
                                job.setTime(job.colorEta(), 1)
                                job.setTime(job.calculateColorChangeTotal(), 0)
                                job.setTime(datetime.min, 3)
                                break
                    
                    # software color change
                    if (self.getStatus()=="colorchange" and job.getFilePause()==0 and self.colorbuff==1):
                        job.setTime(datetime.now(), 3)
                        # job.setTime(job.calculateTotalTime(), 0)
                        # job.setTime(job.updateEta(), 1)
                        self.sendGcode("M600") # color change command
                        job.setTime(job.colorEta(), 1)
                        job.setTime(job.calculateColorChangeTotal(), 0)
                        job.setTime(datetime.min, 3)
                        job.setFilePause(1)
                        self.setColorChangeBuffer(0)
                        # self.setStatus("printing")

                    # Increment the sent lines
                    sent_lines += 1
                    job.setSentLines(sent_lines)
                    # Calculate the progress
                    progress = (sent_lines / total_lines) * 100

                    # Call the setProgress method
                    job.setProgress(progress)
                
                    
                    # if self.getStatus() == "complete" and job.extruded != 0:
                    if self.getStatus() == "complete":
                        return "cancelled"

                    if self.getStatus() == "error":
                        return "error"

            return "complete"
        except Exception as e:
            # self.setStatus("error")
            self.setError(e)
            return "error"

    # Function to send "ending" gcode commands
    def endingSequence(self, job=None):
        try:
            # *** Prusa MK4 ending sequence ***
            # self.gcodeEnding("{if layer_z < max_print_height}G1 Z{z_offset+min(layer_z+1, max_print_height)} F720 ; Move print head up{endif}")
            self.gcodeEnding("M104 S0")# ; turn off temperature
            self.gcodeEnding("M140 S0")# ; turn off heatbed
            self.gcodeEnding("M107")# ; turn off fan

            if(job and job.getExtruded()==1):
                self.gcodeEnding("G1 X241 Y170 F3600")# ; park
            # self.gcodeEnding("{if layer_z < max_print_height}G1 Z{z_offset+min(layer_z+23, max_print_height)} F300")# ; Move print head up{endif}
                self.gcodeEnding("G4")# ; wait

            self.gcodeEnding("M900 K0")# ; reset LA
            self.gcodeEnding("M142 S36")# ; reset heatbreak target temp
            self.gcodeEnding("M84 X Y E")# ; disable motors   

        except Exception as e:
            self.setError(e)
            return "error"

    def printNextInQueue(self):
        # self.connect()
        job = self.getQueue().getNext()  # get next job
        try:
            self.setStatus("printing")  # set printer status to printing
            self.sendStatusToJob(job, job.id, "printing")

            begin = self.beginPrint(job)
            
            if begin==True: 
                Printer.repairPorts() 
                self.connect()
                if self.getSer():
                    self.responseCount = 0
                    job.saveToFolder()
                    path = job.generatePath()
                    verdict = self.parseGcode(path, job)  # passes file to code. returns "complete" if successful, "error" if not.
                    self.handleVerdict(verdict, job)
                    job.removeFileFromPath(path)  # remove file from folder after job complete
                else:
                    self.getQueue().deleteJob(job.id, self.id)
                    # self.setStatus("error")
                    self.setError("Printer not connected")
                    self.sendStatusToJob(job, job.id, "error")
            else: 
                self.handleVerdict("misprint", job)    
            return
        except Exception as e:
            self.setErrorMessage(e)
            self.getQueue().deleteJob(job.id, self.id)
            self.setStatus("error")
            self.sendStatusToJob(job, job.id, "error")
            return 
            # self.handleVerdict("error", job)

    def setErrorMessage(self, error):
        self.error = str(error)
        self.setStatus("error")
        current_app.socketio.emit(
            "error_update", {"printerid": self.id, "error": self.error}
        )
            
    def beginPrint(self, job): 
        while True: 
            time.sleep(1)
            if job.getReleased()==1: 
                return True 
            if self.getStatus() == "complete": 
                return False 
            
    def handleVerdict(self, verdict, job):
        # self.disconnect()
        if verdict == "complete":
            self.disconnect()
            self.setStatus("complete")
            self.sendStatusToJob(job, job.id, "complete")
            
        elif verdict == "error":
            self.disconnect()
            self.getQueue().deleteJob(job.id, self.id)
            self.setStatus("error")
            self.sendStatusToJob(job, job.id, "error")
            # self.setError("Error")
        elif verdict == "cancelled":
            self.endingSequence(job)
            self.sendStatusToJob(job, job.id, "cancelled")
            self.disconnect()
        elif verdict== "misprint": 
            self.sendStatusToJob(job, job.id, "cancelled")            
        return 
    
    def fileExistsInPath(self, path):
        if os.path.exists(path):
            return True

    # printer-specific classes
    def getDevice(self):
        return self.device

    def getQueue(self):
        return self.queue

    def getHwid(self):
        return self.hwid
    
    def setQueue(self, queue): 
        self.queue = queue

    # def removeJobFromQueue(self, job_id):
    #     self.queue.removeJob(job_id)

    #     current_app.socketio.emit('job_removed', {'printer_id': self.id, 'job_id': job_id})

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

    def setDevice(self, device): 
        self.device = device 

    #  now when we set the status, we can emit the status to the frontend

    def setStatus(self, newStatus):
        try:
            if(self.status == "error" and newStatus!="error"): 
                Printer.hardReset(self.id)
            
            self.status = newStatus
            current_app.socketio.emit(
                "status_update", {"printer_id": self.id, "status": newStatus}
            )
        except Exception as e:
            print("Error setting status:", e)

    def setStopPrint(self, stopPrint):
        self.stopPrint = stopPrint

    def setError(self, error):
        self.disconnect()
        self.error = str(error)
        self.setStatus("error")
        current_app.socketio.emit(
            "error_update", {"printerid": self.id, "error": self.error}
        )

    def sendStatusToJob(self, job, job_id, status):
        try:
            job.setStatus(status)
            data = {
                "printerid": self.id,
                "jobid": job_id,
                "status": status,  # Assuming status is accessible here
            }
            
            base_url = os.getenv('BASE_URL')
            response = requests.post(f"{base_url}/updatejobstatus", json=data)
            if response.status_code == 200:
                print("Status sent successfully")
            else:
                print("Failed to send status:", response.text)
        except requests.exceptions.RequestException as e:
            print(f"Failed to send status to job: {e}")

    @classmethod 
    def repairPorts(cls):
        try:
            base_url = os.getenv('BASE_URL')
            response = requests.post(f"{base_url}/repairports")

        except requests.exceptions.RequestException as e:
            print(f"Failed to repair ports: {e}")
            
    @classmethod 
    def hardReset(cls, printerid):
        try:
            base_url = os.getenv('BASE_URL')
            response = requests.post(f"{base_url}/hardreset", json={'printerid': printerid, 'restore': 1})

        except requests.exceptions.RequestException as e:
            print(f"Failed to repair ports: {e}")   

    def setTemps(self, extruder_temp, bed_temp):
        self.extruder_temp = extruder_temp
        self.bed_temp = bed_temp
        current_app.socketio.emit(
            'temp_update', {'printerid': self.id, 'extruder_temp': self.extruder_temp, 'bed_temp': self.bed_temp})


    def setCanPause(self, canPause):
        try:
            self.canPause = canPause
            current_app.socketio.emit('can_pause', {'printerid': self.id, 'canPause': canPause})
        except Exception as e:
            print('Error setting canPause:', e)

    def setColorChangeBuffer(self, buff): 
        self.colorbuff = buff
        current_app.socketio.emit('color_buff', {'printerid': self.id, 'colorChangeBuffer': buff})


            
            