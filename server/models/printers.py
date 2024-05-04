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
                if(self.terminated==1): # Exit target function if "hard reset" in registered view 
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

                if ("T:" in response) and ("B:" in response): # We sent a GCode command to get the temperature of the extruder and bed in the response. This code parses it to display frontend 
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


    """
        Command that sends ending commands to printer. I think originally there was a reason we used a separate function to 
        send the ending commands (instead of just using sendGcode) but I think they're the same now. Maybe we can get rid of this in the future.
    """
    def gcodeEnding(self, message):
        try: 
            self.ser.write(f"{message}\n".encode("utf-8"))
            while True:
                if(self.terminated==1): 
                    return 
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

    """
        The point of this function is to open the file and send gcode commands (sendGcode function) one by one to the printer. 
        This also handles logic for pausing, colorchange, timer, etc. 
    """
    def parseGcode(self, path, job):
        try:
            with open(path, "r") as g:
                if(self.terminated==1): 
                    return 
                
                lines = g.readlines() 
                
                comment_lines = [line for line in lines if line.strip() and line.startswith(";")] # Retrieves all lines in file that are not empty and start with ";"

                # Get the max layer height from the comments to display on frontebd 
                for i in reversed(range(len(comment_lines))):
                    if ";LAYER_CHANGE" in comment_lines[i]:
                        if i < len(comment_lines) - 1:
                            line = comment_lines[i + 1]
                            match = re.search(r";Z:(\d+\.?\d*)", line)
                            if match:
                                max_layer_height = float(match.group(1))
                                break
                job.setMaxLayerHeight(max_layer_height)
                
                # Get the total time from the comments to display on frontend
                total_time = job.getTimeFromFile(comment_lines)
                job.setTime(total_time, 0)
                
                command_lines = [
                    line for line in lines if line.strip() and not line.startswith(";")
                ]
                
                # Store total # of lines. Progress bar is calculated based on (sent_lines / total_lines)*100. 
                total_lines = len(command_lines)
                sent_lines = 0
                prev_line = ""

                # Now begin looping through every non-commented line in the file and send them to the printer. 
                for line in lines:
                    if(self.terminated==1): 
                        return 
                    
                    if("layer" in line.lower() and self.status=='colorchange' and job.getFilePause()==0 and self.colorbuff==0): # If the user clicked the "colorchange" button, status is now colorchange. If the printer isn't already paused (job.getFilePause()), and the color buffer is 0, meaning the color change sequence has not yet been initiated, and a new layer is detected in the line, set the "colorbuff" to 1. This is a "gate" that allows it to enter the colorchange sequence below. 
                        self.setColorChangeBuffer(1)

                    # if line contains ";LAYER_CHANGE", do job.currentLayerHeight(the next line)
                    if prev_line and ";LAYER_CHANGE" in prev_line:
                        match = re.search(r";Z:(\d+\.?\d*)", line)
                        if match:
                            current_layer_height = float(match.group(1))
                            job.setCurrentLayerHeight(current_layer_height)
                    prev_line = line

                    # Strip out all lines that begin with ; and are empty. 
                    # Sending comments to printers "breaks" the sendGcode function. 
                    line = line.strip()
                    if ";" in line:
                        line = line.split(";")[
                            0
                        ].strip() 
                    if len(line) == 0 or line.startswith(";"):
                        continue

                    # We are using the "M569" command to detect the start of the print. 
                    # This is hardcoded for prusa so we may need a better solution going forward, as idk 
                    # if this is a universal command.
                    if("M569" in line) and job.getTimeStarted()==0:
                        job.setTimeStarted(1) 
                        job.setTime(job.calculateEta(), 1)
                        job.setTime(datetime.now(), 2)
                 
                    # Send the line to the printer
                    res = self.sendGcode(line)
                    
                    # If the job was paused and now needs to be marked as resumed, do so. However, if the user 
                    # cancelled the print (which sets the status to complete), return "cancelled" to break out of the loop.
                    if(job.getFilePause() == 1):
                        job.setTime(job.colorEta(), 1)
                        job.setTime(job.calculateColorChangeTotal(), 0)
                        job.setTime(datetime.min, 3)
                        job.setFilePause(0)
                        if(self.getStatus()=="complete"):
                            return "cancelled"
                        self.setStatus("printing") # Set status back to printing instead of paused. 

                    # If color change is detected in-line, set the status and indicate that the file is paused. 
                    if("M600" in line):
                        job.setTime(datetime.now(), 3)
                        self.setStatus("colorchange")
                        job.setFilePause(1)

                    # If M569 is in line, thats command for first extrude. 
                    if("M569" in line) and (job.getExtruded()==0):
                        job.setExtruded(1)
                    
                    if self.prevMes == "M602":
                        self.prevMes=""
                                
                    # If the user set the status to "paused," send the pause command. Stay in the while True loop until the 
                    # user sets the status back to "printing."
                    if (self.getStatus()=="paused"):
                        self.sendGcode("M601") 
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
                    
                    # If the user set the status to colorchange and the layer is complete (color buffer is 1), and 
                    # it isn't already "paused" (file pause == 0), send m600 command to initiate color change sequence.
                    if (self.getStatus()=="colorchange" and job.getFilePause()==0 and self.colorbuff==1):
                        job.setTime(datetime.now(), 3)
                        self.sendGcode("M600") # "Stuck" here until user changes filament on LCD screen 
                        job.setTime(job.colorEta(), 1)
                        job.setTime(job.calculateColorChangeTotal(), 0)
                        job.setTime(datetime.min, 3)
                        job.setFilePause(1)
                        self.setColorChangeBuffer(0)

                    # Calculate progress for progress bar 
                    sent_lines += 1
                    job.setSentLines(sent_lines)
                    progress = (sent_lines / total_lines) * 100
                    job.setProgress(progress)
                
                    # If the user cancelled the print, status is set to "complete" so return cancelled. 
                    if self.getStatus() == "complete":
                        return "cancelled"

                    # If an above function reached an exception, it sets the status to error. Return "error" and break 
                    # out of the loop if this is the case. 
                    if self.getStatus() == "error":
                        return "error"
                    
            return "complete"  # Return complete after all of the lines have been sent to the printer. 
        except Exception as e:
            self.setError(e)
            return "error"

    """
        Every printer has a different "ending" sequence. We found this somewhere in the prusa github in a big JSON file 
        with a bunch of different printer's "ending" sequences to home printer, turn off fans, etc. 
    """
    def endingSequence(self, job=None):
        try:
            # *** Prusa MK4 ending sequence ***
            self.gcodeEnding("M104 S0")# ; turn off temperature
            self.gcodeEnding("M140 S0")# ; turn off heatbed
            self.gcodeEnding("M107")# ; turn off fan

            # If the printer started printing (extruded first line), also "park" the nozzle to the corner. 
            # Otherwise, just do the other commands to turn off temps. We were having issues with making the printer 
            # "park" and move if it hasn't extruded yet.
            if(job and job.getExtruded()==1):
                self.gcodeEnding("G1 X241 Y170 F3600")# ; park
                self.gcodeEnding("G4")# ; wait

            self.gcodeEnding("M900 K0")# ; reset LA
            self.gcodeEnding("M142 S36")# ; reset heatbreak target temp
            self.gcodeEnding("M84 X Y E")# ; disable motors   
        except Exception as e:
            self.setError(e)
            return "error"

    """
        When the printer's status gets set to "ready," the target function of each thread in PrinterStatusService 
        will call this function to print the next job in the queue.
        
        First, it gets the next job in the queue. Then, it sets the printer status to "printing" and sends the status. It stays in the 
        while loop in self.beginPrint until the user clicks "start print" on the frontend. The system checks if the 
        printer's port it was registered under is the same it is now connected to, and re-registeres the port if not. 
        
        The code connecs to the serial port, saves the job's file to the uploads folder, and enters the parseGcode function 
        to loop through the entire file and send each line to the printer. After the file is done, it returns cancelled, complete, or error 
        to "verdict" and the verdict is "handled" by self.handleVerdict. 
    """
    def printNextInQueue(self):
        job = self.getQueue().getNext()
        try:
            self.setStatus("printing")
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

    """
        Sends the error message to the frontend to display to the user. 
    """
    def setErrorMessage(self, error):
        self.error = str(error)
        self.setStatus("error")
        current_app.socketio.emit(
            "error_update", {"printerid": self.id, "error": self.error}
        )
  
    """
        The thread is "stuck" here until the user clicks "Start Print" on the frontend. When the user clicks start, the 
        job's "released" flag is set to 1 and the thread can continue. If the user cancels the print, the status is set to
        "cancelled" and the file is never sent to the printer. 
    """          
    def beginPrint(self, job): 
        while True: 
            time.sleep(1)
            if job.getReleased()==1: 
                return True 
            if self.getStatus() == "complete": 
                return False 
    
    """
        After the printer is finished printing, depending on what was returned by parseGcode, the verdict is handled here.
        If the entire file was sent to the printer, verdict is "complete" so status of job/printer is complete. 
        
        If an exception was reached or printer errored, verdict is "error" so status of job/printer is error.
        
        If the printer's status was set to "complete" mid-print, the loop stops and returns "cancelled." Status of 
        job is set to cancelled and status of printer is complete. 
        
        If the user clicked "stop" and never clicked "start print," verdict is "misprint" and the status of the job is cancelled.
    """        
    def handleVerdict(self, verdict, job):
        if verdict == "complete":
            self.disconnect()
            self.setStatus("complete")
            self.sendStatusToJob(job, job.id, "complete")
        elif verdict == "error":
            self.disconnect()
            self.getQueue().deleteJob(job.id, self.id)
            self.setStatus("error")
            self.sendStatusToJob(job, job.id, "error")
        elif verdict == "cancelled":
            self.endingSequence(job)
            self.sendStatusToJob(job, job.id, "cancelled")
            self.disconnect()
        elif verdict== "misprint": 
            self.sendStatusToJob(job, job.id, "cancelled")            
        return 
    
    """
        Check if file was saved to the uploads folder 
    """
    def fileExistsInPath(self, path):
        if os.path.exists(path):
            return True

    """
        To avoid circular imports/application out of context errors, we can only "reach" functions located inside the 
        job model through the controller/routes. This is how we set status of job in the database. The in-memory job status 
        can be set without sending it through the controller. 
    """
    def sendStatusToJob(self, job, job_id, status):
        try:
            job.setStatus(status) # Setting status in-memory 
            data = {
                "printerid": self.id,
                "jobid": job_id,
                "status": status,
            }
            base_url = os.getenv('BASE_URL')
            response = requests.post(f"{base_url}/updatejobstatus", json=data) # Setting status of job in the database
            if response.status_code == 200:
                print("Status sent successfully")
            else:
                print("Failed to send status:", response.text)
        except requests.exceptions.RequestException as e:
            print(f"Failed to send status to job: {e}")

    """
       This function is located inside of the controller/routes. Explanation in the function itself. Basically 
       checks what port the registered printer is currently attached to. 
    """
    @classmethod 
    def repairPorts(cls):
        try:
            base_url = os.getenv('BASE_URL')
            response = requests.post(f"{base_url}/repairports")
        except requests.exceptions.RequestException as e:
            print(f"Failed to repair ports: {e}")
  
    """
       This function is located inside of the controller/routes. Explanation in the function itself. Basically 
       deletes / restores a printer thread and returns it to the target function. 
    """          
    @classmethod 
    def hardReset(cls, printerid):
        try:
            base_url = os.getenv('BASE_URL')
            response = requests.post(f"{base_url}/hardreset", json={'printerid': printerid, 'restore': 1})

        except requests.exceptions.RequestException as e:
            print(f"Failed to repair ports: {e}")   
            
            
    """
        Getters 
    """
    def getDevice(self):
        return self.device

    def getQueue(self):
        return self.queue

    def getHwid(self):
        return self.hwid
    
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
    
    """
        Setters 
    """
    """
        Perform hard reset on printer if the status was error and the user sets printer to ready. 
        Otherwise, just update the status and also update it on the frontend. 
    """
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


    """
        Disconnect from port on error. Set error message and send to frontend. 
    """
    def setError(self, error):
        self.disconnect()
        self.error = str(error)
        self.setStatus("error")
        current_app.socketio.emit(
            "error_update", {"printerid": self.id, "error": self.error}
        )

    """
        Send bed/nozzle temperature to frontend.
    """
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
        
    def setQueue(self, queue): 
        self.queue = queue

    def setSer(self, port):
        self.ser = port

    def setDevice(self, device): 
        self.device = device 

    def setStopPrint(self, stopPrint):
        self.stopPrint = stopPrint