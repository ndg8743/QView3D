import base64
from io import BytesIO
import io
import shutil
import tempfile
from flask import Blueprint, Response, jsonify, request, make_response, send_file
from models.jobs import Job
from models.printers import Printer
from app import printer_status_service
import json 
from werkzeug.utils import secure_filename
import os 
import gzip
from flask import current_app
import serial
import serial.tools.list_ports

# get data for jobs 
jobs_bp = Blueprint("jobs", __name__)

"""
    Get all jobs from database with specified filters 
"""  
@jobs_bp.route('/getjobs', methods=["GET"])
def getJobs():
    page = request.args.get('page', default=1, type=int)
    pageSize = request.args.get('pageSize', default=10, type=int)
    printerIds = request.args.get('printerIds', type=json.loads)
    
    oldestFirst = request.args.get('oldestFirst', default='false')
    oldestFirst = oldestFirst.lower() in ['true', '1']

    searchJob = request.args.get('searchJob', default='', type=str)
    searchCriteria = request.args.get('searchCriteria', default='', type=str)
    
    searchTicketId = request.args.get('searchTicketId', default='', type=str)

    favoriteOnly = request.args.get('favoriteOnly', default='false')
    favoriteOnly = favoriteOnly.lower() in ['true', '1']
    
    issueIds = request.args.get('issueIds', type=json.loads)
    
    startdate = request.args.get('startdate', default='', type=str)
    enddate = request.args.get('enddate', default='', type=str)
    
    fromError = request.args.get('fromError', default=0, type=int)
    
    countOnly = request.args.get('countOnly', default=0, type=int)

    try:
        res = Job.get_job_history(page, pageSize, printerIds, oldestFirst, searchJob, searchCriteria, searchTicketId, favoriteOnly, issueIds, startdate, enddate, fromError, countOnly)
        return jsonify(res)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500


"""
    Add job to in-memory queue and insert into the database. Add to front/back of queue depending on priority. 
"""  
@jobs_bp.route('/addjobtoqueue', methods=["POST"])
def add_job_to_queue():
    try:
        file = request.files['file'] 
        file_name_original = file.filename
        name = request.form['name'] 
        printer_id = int(request.form['printerid'])
        favorite = request.form['favorite']
        td_id = int(request.form['td_id'])
        filament = request.form['filament']
        favoriteOne = False 
        priority = request.form['priority']
        if(favorite == 'true' and not favoriteOne):
            favorite = 1
            favoriteOne = True
        else: 
            favorite = 0
        status = 'inqueue'
        
        res = Job.jobHistoryInsert(name, printer_id, status, file, file_name_original, favorite, td_id) 
        id = res['id']
        job = Job.query.get(id)
        
        base_name, extension = os.path.splitext(file_name_original)
        file_name_pk = f"{base_name}_{id}{extension}"
        job.setFileName(file_name_pk) 
        job.setFilament(filament) 

        if priority == 'true':
            findPrinterObject(printer_id).getQueue().addToFront(job, printer_id)
        else:
            findPrinterObject(printer_id).getQueue().addToBack(job, printer_id)
                        
        return jsonify({"success": True, "message": "Job added to printer queue."}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Basically the same exact function as above, but this time, the printer ID is not passed in and the job is 
    sent to the printer that has the smallest queue. 
"""
@jobs_bp.route('/autoqueue', methods=["POST"])
def auto_queue(): 
    try: 
        file = request.files['file'] 
        file_name_original = file.filename
        name = request.form['name'] 
        favorite = request.form['favorite']
        td_id = request.form['td_id']
        filament = request.form['filament']
        favoriteOne = False 
        status = 'inqueue' 
        priority = request.form['priority']
        
        if(favorite == 'true' and not favoriteOne):
            favorite = 1
            favoriteOne = True
        else: 
            favorite = 0

        printer_id = getSmallestQueue()
        res = Job.jobHistoryInsert(name, printer_id, status, file, file_name_original, favorite, td_id) # insert into DB 
        
        id = res['id']
        job = Job.query.get(id)
        base_name, extension = os.path.splitext(file_name_original)
        file_name_pk = f"{base_name}_{id}{extension}"
        job.setFileName(file_name_pk) 
        job.setFilament(filament) 

        if priority == 'true':
            print("front")
            findPrinterObject(printer_id).getQueue().addToFront(job, printer_id)
        else:
            print("back")
            findPrinterObject(printer_id).getQueue().addToBack(job, printer_id)
        
        return jsonify({"success": True, "message": "Job added to printer queue."}), 200
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    Route to duplicate an old job from the database into the in-memory queue. 
"""
@jobs_bp.route('/rerunjob', methods=["POST"])
def rerun_job():
    try:
        data = request.get_json()
        printerpk = data['printerpk'] 
        jobpk = data['jobpk']
        rerunjob(printerpk, jobpk, "back")
        return jsonify({"success": True, "message": "Job added to printer queue."}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    I'm pretty sure we don't use this anymore 
"""
@jobs_bp.route('/jobdbinsert', methods=["POST"])
def job_db_insert():
    try:
        jobdata = request.form.get('jobdata')
        jobdata = json.loads(jobdata)  
        name = jobdata.get('name')
        printer_id = jobdata.get('printer_id')
        status = jobdata.get('status')
        file_path=jobdata.get("file_path")
        res = Job.jobHistoryInsert(name, printer_id, status, file_path)
        return "success"
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
 I don't think we use this anymore
"""
@jobs_bp.route('/canceljob', methods=["POST"]) 
def remove_job():
    try:
        data = request.get_json()
        jobpk = data['jobpk']
        job = Job.findJob(jobpk) 
        printerid = job.getPrinterId() 
        jobstatus = job.getStatus()
        
        printerobject = findPrinterObject(printerid)
        queue = printerobject.getQueue()
        inmemjob = queue.getJob(job)
        
        if jobstatus == 'printing': 
            printerobject.setStatus("complete")
        else: 
            queue.deleteJob(jobpk, printerid) 
            
        inmemjob.setStatus("cancelled")
        Job.update_job_status(jobpk, "cancelled")

        return jsonify({"success": True, "message": "Job removed from printer queue."}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Route to cancel job(s). If the job is currently printing, then ONLY set the printer's status to "complete." This will 
    make the printer break out of the parseGcode loop and set the job status to "cancelled."

    If the job is not currently printing, simply remove the job from the queue and set the job status to "cancelled."

    Also update the job status in the database. 
"""
@jobs_bp.route('/cancelfromqueue', methods=["POST"]) 
def remove_job_from_queue():
    try:
        data = request.get_json()
        jobarr = data['jobarr']
        
        for jobpk in jobarr:
            job = Job.findJob(jobpk) 
            printerid = job.getPrinterId() 

            jobstatus = job.getStatus()
            printerobject = findPrinterObject(printerid)
            queue = printerobject.getQueue()
            inmemjob = queue.getJob(job)
            
            if jobstatus == 'printing':
                printerobject.setStatus("complete")
            else: 
                queue.deleteJob(jobpk, printerid) 
                
            inmemjob.setStatus("cancelled")
            Job.update_job_status(jobpk, "cancelled")

        return jsonify({"success": True, "message": "Job removed from printer queue."}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    This route is called when the user clicks one of the three buttons after a print is done: clear, clear & rerun, or fail. 
    
    The job is located and so is the printer that corresponds with the printerid saved by the job. The job is 
    removed from the queue. 
    
    If the key == 3, the user clicked fail. The job status is set to "error" and the printer status is set to "error." The error 
    message is set to whatever the user commented on the job in the comments field. If they left no comments, its empty. 
    
    If the key == 2, the user clicked clear & rerun. The job is rerun and added to the front of the queue. The printer status is set to "ready" unless 
    the user shut the printer offline. 
    
    If the key == 1, the user clicked clear. The printer status is set to "ready" unless the user shut the printer offline.
"""   
@jobs_bp.route('/releasejob', methods=["POST"])
def releasejob(): 
    try: 
        data = request.get_json()
        jobpk = data['jobpk']
        key = data['key']
        
        job = Job.findJob(jobpk) 
        printerid = job.getPrinterId() 
        printerobject = findPrinterObject(printerid)
        printerobject.error = ""
        queue = printerobject.getQueue()

        queue.deleteJob(jobpk, printerid)
        printerid = data['printerid']
        
        currentStatus = printerobject.getStatus()

        if key == 3: 
            Job.update_job_status(jobpk, "error")
            printerobject.setError(job.comments)
            printerobject.setStatus("error") 
        elif key == 2: 
            rerunjob(printerid, jobpk, "front")
            if currentStatus!="offline":
                printerobject.setStatus("ready") 
        elif key == 1: 
            if currentStatus!="offline":
                printerobject.setStatus("ready") 

        return jsonify({"success": True, "message": "Job released successfully."}), 200
    except Exception as e: 
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500  
    
"""
    I don't think we use this anymore
"""
@jobs_bp.route('/bumpjob', methods=["POST"])
def bumpjob():
    try:
        data = request.get_json()
        printer_id = data['printerid']
        job_id = data['jobid']
        choice = data['choice']
        
        printerobject = findPrinterObject(printer_id)
        
        if choice == 1: 
            printerobject.queue.bump(True, job_id)
        elif choice == 2: 
            printerobject.queue.bump(False, job_id)
        elif choice == 3: 
            printerobject.queue.bumpExtreme(True, job_id, printer_id)
        elif choice == 4: 
            printerobject.queue.bumpExtreme(False, job_id, printer_id)
        else: 
            return jsonify({"error": "Unexpected error occurred"}), 500
        
        return jsonify({"success": True, "message": "Job bumped up in printer queue."}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    Code to move items around in the queue on QueueView. 
"""
@jobs_bp.route('/movejob', methods=["POST"])
def moveJob():
    try:
        data = request.get_json()
        printer_id = data['printerid']
        arr = data['arr']
        
        printerobject = findPrinterObject(printer_id)
        printerobject.queue.reorder(arr)
        return jsonify({"success": True, "message": "Queue updated successfully."}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500   
  
"""
    Code to update the status of the job in memory and in the database. The job is NOT removed from the queue.
"""  
@jobs_bp.route('/updatejobstatus', methods=["POST"])
def updateJobStatus():
    try:
        data = request.get_json()
        job_id = data['jobid']
        newstatus = data['status']
        
        res = Job.update_job_status(job_id, newstatus)
        
        job = Job.findJob(job_id) 
        printerid = job.getPrinterId() 
        printerobject = findPrinterObject(printerid)
        # queue = printerobject.getQueue()
        return jsonify(res), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
  
"""
    Code to update the status of the job in memory and in the database to error. 
    The job is also removed from the queue. Used when user clicks "fail" on a print. 
"""  
@jobs_bp.route('/assigntoerror', methods=["POST"])
def assignToError():
    try:
        data = request.get_json()
        job_id = data['jobid']
        newstatus = data['status']
        
        res = Job.update_job_status(job_id, newstatus)
        
        job = Job.findJob(job_id) 
        printerid = job.getPrinterId() 
        printerobject = findPrinterObject(printerid)
        queue = printerobject.getQueue()
        
        queue.deleteJob(job_id, printerid)
        
        return jsonify(res), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
  
"""
    Used to delete a job from the database and from the in-memory queue if it is still there. 
"""  
@jobs_bp.route('/deletejob', methods=["POST"])
def delete_job():
    try:
        data = request.get_json()
        job_id = data['jobid']
        job = Job.findJob(job_id) 
        printer_id = job.getPrinterId()
        
        if printer_id != 0:
            printer_object = findPrinterObject(printer_id)
            queue = printer_object.getQueue()
            queue.deleteJob(job_id, printer_id) 
            
        Job.delete_job(job_id)
        return jsonify({"success": True, "message": f"Job with ID {job_id} deleted successfully."}), 200

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    Set status of a printer object from frontend 
"""
@jobs_bp.route("/setstatus", methods=["POST"])
def setStatus():
    try:
        data = request.get_json() # get json data 
        printer_id = data['printerid']
        newstatus = data['status']
 
        printerobject = findPrinterObject(printer_id)
        printerobject.setStatus(newstatus)
        
        return jsonify({"success": True, "message": "Status updated successfully."}), 200

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    Retrieve file from database and return it to the frontend if the user wants to download a past file 
"""
@jobs_bp.route('/getfile', methods=["GET"])
def getFile():
    try:
        job_id = request.args.get('jobid', default=-1, type=int)        
        job = Job.findJob(job_id) 
        file_blob = job.getFile()  # Assuming this returns the file blob
        decompressed_file = gzip.decompress(file_blob).decode('utf-8')
        
        return jsonify({"file": decompressed_file, "file_name": job.getFileNameOriginal()}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Used when the user deregisters a printer. All FK's in the job table in the database that reference that printer 
    are set to 0. 
"""
@jobs_bp.route('/nullifyjobs', methods=["POST"])
def nullifyJobs():
    try: 
        data = request.get_json()
        printerid = data['printerid']
        res = Job.nullifyPrinterId(printerid)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
""" 
    Route that removes all files stored in the database that are >6 months old. The other job data is still saved 
    in the database.
"""
@jobs_bp.route('/clearspace', methods=["GET"])
def clearSpace(): 
    try: 
        res = Job.clearSpace()
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Return all favorited jobs
"""
@jobs_bp.route('/getfavoritejobs', methods=["GET"])
def getFavoriteJobs():
    try:
        res = Job.getFavoriteJobs()
        return jsonify(res)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
""" 
    Mark a job as "favorited" or not.
"""
@jobs_bp.route('/favoritejob', methods=["POST"])
def favoriteJob():
    try: 
        data = request.get_json()
        jobid = data['jobid']
        favorite = data['favorite']
        job = Job.findJob(jobid)
        res = job.setFileFavorite(favorite)
        return res
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Assign an issue to a specific job.
"""
@jobs_bp.route('/assignissue', methods=["POST"])
def assignIssue():
    try: 
        data = request.get_json()
        jobid = data['jobid']
        issueid = data['issueid']
        job = Job.findJob(jobid)
        jobid = job.getJobId()
        res = job.setIssue(jobid, issueid)
        return res
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Unassign an issue from a specific job.
"""
@jobs_bp.route('/removeissue', methods=["POST"])
def removeIssue():
    try: 
        data = request.get_json()
        jobid = data['jobid']
        job = Job.findJob(jobid)
        jobid = job.getJobId()
        res = job.unsetIssue(jobid)
        return res
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    "Release" a print. Called when the user clicks Start Print. 
"""
@jobs_bp.route('/startprint', methods=["POST"])
def startPrint(): 
    try: 
        data = request.get_json()
        printerid = data['printerid']
        jobid = data['jobid']
        printerobject = findPrinterObject(printerid)
        queue = printerobject.getQueue()
        inmemjob = queue.getJobById(jobid)
        inmemjob.setReleased(1)
        
        return jsonify({"success": True, "message": "Job started successfully."}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected ersetupPortRepairSocketror occurred"}), 500
    
"""
    Assign a comment to a job 
"""
@jobs_bp.route('/savecomment', methods=["POST"])
def saveComment(): 
    try: 
        data = request.get_json()
        jobid = data['jobid']
        comment = data['comment']
        res = Job.setComment(jobid, comment)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    Download a CSV file of jobs in the database specified by an array of JobIDs specified in the frontend by the user. 
"""
@jobs_bp.route('/downloadcsv', methods=["GET", "POST"])
def downloadCSV():
    try:
        data = request.get_json()
        alljobsselected = data.get('allJobs')
        jobids = data.get('jobIds')

        if alljobsselected == 1:
            res = Job.downloadCSV(1)
        else:
            res = Job.downloadCSV(0, jobids)
        return res 
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
    
"""
    This function is called by the system once the user downloads the CSV file. The file is temporarily stored in the 
    tempcsv file, sent to the frontend, and then removed. 
"""
@jobs_bp.route('/removeCSV', methods=["GET", "POST"])
def removeCSV():
    try:
        csv_folder = os.path.join('../tempcsv')
        if os.path.exists(csv_folder):
            shutil.rmtree(csv_folder)
            os.makedirs(csv_folder)
        else:
            os.makedirs(csv_folder)
        return jsonify({"success": True, "message": "CSV file removed successfully."}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500

"""
    Lists all of the ports currently connected to the machine. If the port the printer is registered under does not match the  
    port the printer is currently connected to, update the port in the database. We check this by comparing the hwid 
    returned by the connected port and the hwid stored in the database. 
"""
@jobs_bp.route("/repairports", methods=["POST", "GET"])
def repair_ports(): 
    try:
        ports = serial.tools.list_ports.comports()    
        for port in ports: 
            hwid = port.hwid
            hwid_without_location = hwid.split(' LOCATION=')[0]
            printer = Printer.getPrinterByHwid(hwid_without_location)
            if printer is not None: 
                if(printer.getDevice()!=port.device):
                    printer.editPort(printer.getId(), port.device)
                    printerthread = findPrinterObject(printer.getId())
                    printerthread.setDevice(port.device)
        return {"success": True, "message": "Printer port(s) successfully updated."}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500
   
"""
    Retreieves the time array stored in the backend of a job. Stores ETA, total time in print, time started, and time paused.
"""
@jobs_bp.route("/refetchtimedata", methods=['POST', 'GET']) 
def refetch_time(): 
    try: 
        data = request.get_json()
        jobid = data['jobid']
        printerid = data['printerid']

        printer = findPrinterObject(printerid)
        job = printer.getQueue().getNext()
        timearray = job.job_time 
        timejson = {
            'total': timearray[0], 
            'eta': timearray[1].isoformat(), 
            'timestart': timearray[2].isoformat(), 
            'pause': timearray[3].isoformat()
        }
        return jsonify(timejson) 

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Unexpected error occurred"}), 500    
    
"""
    Locates the thread object that corresponds with the printer. 
"""
def findPrinterObject(printer_id): 
    threads = printer_status_service.getThreadArray()
    return list(filter(lambda thread: thread.printer.id == printer_id, threads))[0].printer  

"""
    Loops through all of the printer threads and return the printer with the smallest queue. 
"""
def getSmallestQueue():
    threads = printer_status_service.getThreadArray()
    smallest_queue_thread = min(threads, key=lambda thread: thread.printer.queue.getSize())
    return smallest_queue_thread.printer.id
    
"""
    Rerun a job by duplicating it from the database and adding it to the in-memory queue.
"""
def rerunjob(printerpk, jobpk, position):
    job = Job.findJob(jobpk) 
    status = 'inqueue'
    file_name_original = job.getFileNameOriginal()
    favorite = job.getFileFavorite() 
    td_id = job.getTdId()
    res = Job.jobHistoryInsert(name=job.getName(), printer_id=printerpk, status=status, file=job.getFile(), file_name_original=file_name_original, favorite=favorite, td_id=td_id) # insert into DB 
    
    id = res['id']
    file_name_pk = file_name_original + f"_{id}" # append id to file name to make it unique
    
    rjob = Job.query.get(id)
    base_name, extension = os.path.splitext(file_name_original)

    # Append the ID to the base name
    file_name_pk = f"{base_name}_{id}{extension}"
    
    rjob.setFileName(file_name_pk) # set unique file name 
    
    if position == "back":
        findPrinterObject(printerpk).getQueue().addToBack(rjob, rjob.printer_id)
    else: 
        findPrinterObject(printerpk).getQueue().addToFront(rjob, rjob.printer_id)
        