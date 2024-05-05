from threading import Thread
from models.printers import Printer
import serial
import serial.tools.list_ports
import time
import requests
from Classes.Queue import Queue
from flask import jsonify 

class PrinterThread(Thread):
    def __init__(self, printer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.printer = printer

class PrinterStatusService:
    
    """
        Store printer threads in a list 
    """
    def __init__(self, app):
        self.app = app
        self.printer_threads = []

    """
        Start a printer thread and assign its "target function" to the update_thread class. 
        Thread daemon kills thread when main program exits. 
    """
    def start_printer_thread(self, printer):
        thread = PrinterThread(printer, target=self.update_thread, args=(printer, self.app)) 
        thread.daemon = True 
        thread.start()
        return thread


    """
        For all printers in the printers_data list, create a printer object and start a printer thread. 
        This function is called on server start by app.py. 
        Also appends the thread to the thread array. 
    """
    def create_printer_threads(self, printers_data):
        for printer_info in printers_data:
            printer = Printer(
                id=printer_info["id"],
                device=printer_info["device"],
                description=printer_info["description"],
                hwid=printer_info["hwid"],
                name=printer_info["name"],
                status='configuring',
            )
            printer_thread = self.start_printer_thread(
                printer
            ) 
            self.printer_threads.append(printer_thread)


    """
        This is the thread's target function. It stays here and listens for printer status updates the whole time 
        the server is running. 
                
        For error handling, we have "response count" to keep track of the number of times the printer HAS NOT responded (response = "") and set an error after 10 times. 
        We reset this variable when a new job is sent to printer. 
        
        When the printer status is "ready" and there is a job in the queue, the printer will 
        print the next job in the queue. This functionality is in models/printers.py.
    """
    def update_thread(self, printer, app):
        with app.app_context(): # Flask needs "app context" in order to recognize the database
            while True:
                time.sleep(2) # slight buffer 
                status = printer.getStatus()  
                queueSize = printer.getQueue().getSize() 
                printer.responseCount = 0 
                if (status == "ready" and queueSize > 0):
                    time.sleep(2)
                    if status != "offline": 
                        printer.printNextInQueue()

    """
        This function is called by the UI to reset a printer thread. Passes a printer_id, deletes the thread, and 
        creates it again based on printer data. 
        
        Sets a variable called "terminated" to 1. If the thread is "stuck" in its target function, it detects this 
        terminated flag and returns. 
    """
    def resetThread(self, printer_id):
        try: 
            for thread in self.printer_threads:
                if thread.printer.id == printer_id:    
                    printer = thread.printer
                    printer.terminated = 1 
                    thread_data = {
                        "id": printer.id, 
                        "device": printer.device,
                        "description": printer.description,
                        "hwid": printer.hwid,
                        "name": printer.name, 
                    }
                    self.printer_threads.remove(thread)
                    self.create_printer_threads([thread_data])
                    break
            return jsonify({"success": True, "message": "Printer thread reset successfully"})
        except Exception as e:
            print(f"Unexpected error: {e}")
            return jsonify({"success": False, "error": "Unexpected error occurred"}), 500
  
    """
        Loops through threads and deletes thread associated with printer_id parameter. 
    """      
    def deleteThread(self, printer_id):
        try: 
            for thread in self.printer_threads:
                if thread.printer.id == printer_id:    
                    printer = thread.printer
                    thread_data = {
                        "id": printer.id, 
                        "device": printer.device,
                        "description": printer.description,
                        "hwid": printer.hwid,
                        "name": printer.name
                    }
                    self.printer_threads.remove(thread)
                    break
            return jsonify({"success": True, "message": "Printer thread reset successfully"})
        except Exception as e:
            print(f"Unexpected error: {e}")
            return jsonify({"success": False, "error": "Unexpected error occurred"}), 500
     
    """
        Edits name of printer in-memory because the printer object exists both in the database and in-memory. 
    """   
    def editName(self, printer_id, name):
        try: 
            for thread in self.printer_threads:
                if thread.printer.id == printer_id:    
                    printer = thread.printer
                    printer.name = name
                    break
            return jsonify({"success": True, "message": "Printer name updated successfully"})
        except Exception as e:
            print(f"Unexpected error: {e}")
            return jsonify({"success": False, "error": "Unexpected error occurred"}), 500
        

    """
        This function is called by the UI to retrieve printer info and queues to display in a JSON format. 
    """
    def retrieve_printer_info(self):
        printer_info_list = []
        for thread in self.printer_threads:
            printer = (
                thread.printer
            )  # get the printer object associated with the thread
            printer_info = {
                "device": printer.device,
                "description": printer.description,
                "hwid": printer.hwid,
                "name": printer.name,
                "status": printer.status,
                "id": printer.id,
                "error": printer.error, 
                "canPause": printer.canPause,
                "queue": [], # empty queue to store job objects 
                "colorChangeBuffer": printer.colorbuff
                # "colorChangeBuffer": printer.colorChangeBuffer
            }
            queue = printer.getQueue()
            
            for job in queue: 
                job_info = {
                    "id": job.id,
                    "name": job.name,
                    "status": job.status,
                    "date": job.date.strftime('%a, %d %b %Y %H:%M:%S'),
                    "printerid": job.printer_id, 
                    "errorid": job.error_id,
                    "file_name_original": job.file_name_original, 
                    "progress": job.progress,
                    "favorite": job.favorite,
                    "released": job.released,
                    "file_pause": job.filePause, 
                    "comments": job.comments, 
                    "extruded": job.extruded,
                    "td_id": job.td_id,
                    "time_started": job.time_started,
                    "printer_name": job.printer_name,
                    "max_layer_height": job.max_layer_height,
                    "current_layer_height": job.current_layer_height,
                    "filament": job.filament,
                }
                printer_info['queue'].append(job_info)
            
            printer_info_list.append(printer_info)
            
        return printer_info_list

    """
        Get method for thread array 
    """
    def getThreadArray(self):
        return self.printer_threads
    
    """
        When the user changes the order of the printers on Main View in the UI, the order of the backend 
        array is changed as well. 
    """
    def movePrinterList(self, printer_ids):
        new_thread_list = []
        for id in printer_ids:
            for thread in self.printer_threads:
                if thread.printer.id == id:
                    new_thread_list.append(thread)
                    break
        self.printer_threads = new_thread_list
        return jsonify({"success": True, "message": "Printer list reordered successfully"})

