import asyncio
import base64
from operator import or_
import os
import re
from models.db import db
from models.printers import Printer 
from models.issues import Issue  # assuming the Issue model is defined in the issue.py file in the models directory
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, LargeBinary, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from flask import jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from tzlocal import get_localzone
from io import BytesIO
from werkzeug.datastructures import FileStorage
import time
import gzip
import csv
from flask import send_file

from app import printer_status_service
# model for job history table


class Job(db.Model):
    
    id = db.Column(db.Integer, primary_key=True)
    file = db.Column(db.LargeBinary(16777215), nullable=True)
    name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=lambda: datetime.now(
        timezone.utc).astimezone(), nullable=False)
    printer_id = db.Column(db.Integer, db.ForeignKey('printer.id'), nullable=True) # Storing printer ID, foreign key to printer
    printer = db.relationship('Printer', backref='Job')
    printer_name = db.Column(db.String(50), nullable=True)
    td_id = db.Column(db.Integer, nullable=True) # Storing ticket ID (set by user)
    error_id = db.Column(db.Integer, db.ForeignKey('issue.id'), nullable=True) # Storing "issue", foreign key to issue 
    error = db.relationship('Issue', backref='Issue')
    comments = db.Column(db.String(500), nullable=True)
    file_name_original = db.Column(db.String(50), nullable=False)
    favorite = db.Column(db.Boolean, nullable=False)
    file_name_pk = None # Store the file name with the primary key identifier for easy access when saved in uploads folder
    max_layer_height = 0.0
    current_layer_height = 0.0
    filament = '' # Stores the filament type for the job (PLA, ABS, etc...)
    released = 0 # 0 if not released, 1 if released by user (Start Print button)
    filePause = 0 # Indicates if paused by user 
    progress = 0.0
    time_started = 0
    extruded = 0
    
    #Stores job time: total time, eta, timestart, time paused 
    job_time = [0, datetime.min, datetime.min, datetime.min]


    
    def __init__(self, file, name, printer_id, status, file_name_original, favorite, td_id, printer_name):
        self.file = file 
        self.name = name 
        self.printer_id = printer_id 
        self.status = status 
        self.file_name_original = file_name_original # original file name without PK identifier 
        self.td_id = td_id
        self.file_name_pk = None
        self.favorite = favorite
        self.released = 0 
        self.filePause = 0
        self.progress = 0.0
        self.time_started = 0
        self.extruded = 0
        self.job_time = [0, datetime.min, datetime.min, datetime.min]
        self.error_id = 0
        self.printer_name = printer_name
        self.max_layer_height = 0.0
        self.current_layer_height = 0.0
        self.filament = ''

    """
        toString method 
    """
    def __repr__(self):
        return f"Job(id={self.id}, name={self.name}, printer_id={self.printer_id}, status={self.status})"


    """
        Gets job history from database. Applies user filters. 

    """
    @classmethod
    def get_job_history(
        cls,
        page,
        pageSize,
        printerIds=None,
        oldestFirst=False,
        searchJob="",
        searchCriteria="",
        searchTicketId=None,
        favoriteOnly=False, 
        issueIds = None, 
        startDate=None,
        endDate=None,
        fromError = None, 
        countOnly = None 
    ):
        try:
            query = cls.query
            
            if(fromError==1):
                query = cls.query.filter_by(status="error")
            
            if printerIds:
                query = query.filter(cls.printer_id.in_(printerIds))

            if issueIds:
                query = query.filter(cls.error_id.in_(issueIds))
                
            if searchJob:
                searchJob = f"%{searchJob}%"
                query = query.filter(
                    or_(
                        cls.name.ilike(searchJob),
                        cls.file_name_original.ilike(searchJob),
                    )
                )

            if "searchByJobName" in searchCriteria:
                searchByJobName = f"%{searchJob}%"
                query = query.filter(cls.name.ilike(searchByJobName))
            elif "searchByFileName" in searchCriteria:
                searchByFileName = f"%{searchJob}%"
                query = query.filter(cls.file_name_original.ilike(searchByFileName))
                
            if searchTicketId:
                searchTicketId = int(searchTicketId)
                query = query.filter(cls.td_id == searchTicketId)

            if favoriteOnly:
                query = query.filter(cls.favorite == True)

            if oldestFirst:
                query = query.order_by(cls.date.asc())
            else:
                query = query.order_by(cls.date.desc())  # Change this line

            
            if startDate!='' or endDate!='':
                if(endDate==''):
                    cls.date.between(
                        datetime.fromisoformat(startDate),
                        datetime.fromisoformat(startDate),
                    )
                    
                query = query.filter(
                    cls.date.between(
                        datetime.fromisoformat(startDate),
                        datetime.fromisoformat(endDate),
                    )
                )

            pagination = query.paginate(page=page, per_page=pageSize, error_out=False)
            jobs = pagination.items

            jobs_data = [ # return results as JSON array 
                {
                    "id": job.id,
                    "name": job.name,
                    "status": job.status,
                    "date": job.date.strftime("%a, %d %b %Y %H:%M:%S"),
                    "printerid": job.printer_id,
                    "errorid": job.error_id,
                    "file_name_original": job.file_name_original,
                    "comments": job.comments,
                    "td_id": job.td_id,
                    "printer": job.printer.name if job.printer else "None",
                    "error": job.error.issue if job.error else 'None', 
                    "printer_name": job.printer_name
                }
                for job in jobs
            ]
            if(countOnly == 0): 
                return jobs_data, pagination.total
            else: 
                return pagination.total
            
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return jsonify({"error": "Failed to retrieve jobs. Database error"}), 500

    """
        Insert jobs into database 
    """
    @classmethod
    def jobHistoryInsert(cls, name, printer_id, status, file, file_name_original, favorite, td_id): 
        try:
            if isinstance(file, bytes):
                file_data = file
            else:
                file.seek(0)
                file_data = file.read()

            try: # "double check" if compressed already. Only store compressed file in database. 
                gzip.decompress(file_data)
                # If it decompresses successfully, it's already compressed
                compressed_data = file_data
            except OSError:
                compressed_data = gzip.compress(file_data)

            printer = Printer.query.get(printer_id)

            job = cls(
                file=compressed_data,
                name=name,
                printer_id=printer_id,
                status=status,
                file_name_original = file_name_original,
                favorite = favorite, 
                td_id = td_id, 
                printer_name = printer.name 
            )

            db.session.add(job)
            db.session.commit()

            return {"success": True, "message": "Job added to collection.", "id": job.id}
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"error": "Failed to add job. Database error"}),
                500,
            )


    """
        Update job status in database and also update on frontend array via websocket
    """
    @classmethod
    def update_job_status(cls, job_id, new_status):
        try:
            job = cls.query.get(job_id)
            if job:
                job.status = new_status
                db.session.commit()
                current_app.socketio.emit('job_status_update', {'job_id': job_id, 'status': new_status})
                return {"success": True, "message": f"Job {job_id} status updated successfully."}
            else:
                return {"success": False, "message": f"Job {job_id} not found."}, 404
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return (
                jsonify({"error": "Failed to update job status. Database error"}),
                500,
            )

    """
        Delete job from database. 
    """
    @classmethod
    def delete_job(cls, job_id):
        try:
            job = cls.query.get(job_id)
            if job:
                db.session.delete(job)
                db.session.commit()
                return {"success": True, "message": f"Job with ID {job_id} deleted from the database."}
            else:
                return {"error": f"Job with ID {job_id} not found in the database."}
        except Exception as e:
            print(f"Unexpected error: {e}")
            # When an error occurs or an exception is raised during a database operation (such as adding,
            # updating, or deleting records), it may leave the database in an inconsistent state. To handle such
            # situations, a rollback is performed to revert any changes made within the current session to maintain the integrity of the database.
            db.session.rollback()
            return {"error": "Unexpected error occurred during job deletion."}

    """
        Find job in database by PK 
    """
    @classmethod
    def findJob(cls, job_id):
        try:
            job = cls.query.filter_by(id=job_id).first()
            return job
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return jsonify({"error": "Failed to retrieve job. Database error"}), 500

    """
        Find job in in-memory queue by PK
    """
    @classmethod
    def findPrinterObject(self, printer_id):
        threads = printer_status_service.getThreadArray()
        return list(filter(lambda thread: thread.printer.id == printer_id, threads))[0].printer

    """
        Remove file from uploads folder 
    """
    @classmethod
    def removeFileFromPath(cls, file_path):
        if os.path.exists(file_path):    
            os.remove(file_path)       

    """
        Edit status of job in database 
    """
    @classmethod
    def setDBstatus(cls, jobid, status):
        cls.update_job_status(jobid, status)

    """
        Generate file path to delete from the uploads folder after the file is done printing 
    """
    @classmethod
    def getPathForDelete(cls, file_name):
        return os.path.join('../uploads', file_name)

    """
        When the user deregisters a printer, this function sets the FK of the printer associated with this job to None. 
    """
    @classmethod
    def nullifyPrinterId(cls, printer_id):
        try:
            jobs = cls.query.filter_by(printer_id=printer_id).all()
            for job in jobs:
                job.printer_id = 0
            db.session.commit()
            return {"success": True, "message": "Printer ID nullified successfully."}
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return jsonify({"error": "Failed to nullify printer ID. Database error"}), 500

    """
        Removes files from the database that have existed for >6 months. The job itself remains in the database, 
        but the associated file is deleted. 
    """
    @classmethod
    def clearSpace(cls):
        try:
            six_months_ago = datetime.now() - timedelta(days=182)  # 6 months ago
            old_jobs = Job.query.filter(Job.date < six_months_ago).all()

            # thirty_seconds_ago = datetime.now() - timedelta(seconds=30)  # 30 seconds ago
            # old_jobs = Job.query.filter(Job.date < thirty_seconds_ago).all()

            for job in old_jobs:
                if(job.favorite==0):
                    job.file = None  # Set file to None
                    if "Removed after 6 months" not in job.file_name_original:
                        job.file_name_original = f"{job.file_name_original}: Removed after 6 months"
            db.session.commit()  # Commit the changes
            return {"success": True, "message": "Space cleared successfully."}
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return jsonify({"error": "Failed to clear space. Database error"}), 500
   
    """
        Retrieve all jobs from the database that are "favorited" by the user. 
    """
    @classmethod
    def getFavoriteJobs(cls):
        try:
            jobs = cls.query.filter_by(favorite=True).all()

            jobs_data = [{
                "id": job.id,
                "name": job.name,
                "status": job.status,
                "date": f"{job.date.strftime('%a, %d %b %Y %H:%M:%S')} {get_localzone().tzname(job.date)}",
                "printer": job.printer.name if job.printer else 'None',
                "file_name_original": job.file_name_original,
                "favorite": job.favorite
            } for job in jobs]

            return jobs_data
        except SQLAlchemyError as e:
            print(f"Database error: {e}")
            return jsonify({"error": "Failed to retrieve favorite jobs. Database error"}), 500
       
    """
        Assign an issue to a job. issue id is stored as "error_id" in this class. 
    """ 
    @classmethod
    def setIssue(cls, job_id, issue_id):
        job = cls.query.get(job_id)

        if job is None:
            return None

        job.error_id = issue_id
        try:
            db.session.commit()
            return {"success": True, "message": "Issue assigned successfully."}
        except Exception as e:
            db.session.rollback()
            print(f"Error setting issue: {e}")
            return None
    
    """
        Unassigns an issue from a job. 
    """    
    @classmethod
    def unsetIssue(cls, job_id):
        job = cls.query.get(job_id)

        if job is None:
            return None

        job.error_id = None

        try:
            db.session.commit()
            return {"success": True, "message": "Issue removed successfully."}
        except Exception as e:
            db.session.rollback()
            print(f"Error unsetting issue: {e}")
            return None
      
    """
        Assign comments to a job and commit to database. 
    """  
    @classmethod
    def setComment(cls, job_id, comments):
        job = cls.query.get(job_id)

        if job is None:
            return None
        job.comments = comments

        try:
            db.session.commit()
            return {"success": True, "message": "Comments added successfully."}
        except Exception as e:
            db.session.rollback()
            print(f"Error setting comments: {e}")
            return None
    
    """
        Based on the user filter, download a CSV file based on job history data, 
    """    
    @classmethod
    def downloadCSV(cls, alljobs, jobids=None):
        try: 
            if(jobids!=None): 
                # Join Job and Issue on error_id and filter by jobids
                jobs = db.session.query(cls, Issue).outerjoin(Issue, cls.error_id == Issue.id).filter(cls.id.in_(jobids)).all()
            else: 
                # Join Job and Issue on error_id
                jobs = db.session.query(cls, Issue).outerjoin(Issue, cls.error_id == Issue.id).all()

            # Specify the columns you want to include
            column_names = ['td_id', 'printer', 'name','file_name_original', 'status', 'date', 'issue', 'comments']

            date_string = datetime.now().strftime("%m%d%Y")        
                
            csv_file_name = f'../tempcsv/jobs_{date_string}.csv'
            
            # Write to CSV
            with open(csv_file_name, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(column_names)  # write headers
                for job, issue in jobs:
                    row = [getattr(job, 'td_id', ''), getattr(job, 'printer_name', ''), getattr(job, 'name', ''), getattr(job, 'file_name_original', ''), getattr(job, 'status', ''), getattr(job, 'date', ''), getattr(issue, 'issue', '') if issue else '', getattr(job, 'comments', '')]
                    writer.writerow(row)  # write data rows
            
            csv_file_path = f'./{csv_file_name}'
        
            return send_file(csv_file_path, as_attachment=True)
        
        except Exception as e:
            print(f"Error downloading CSV: {e}")
            return {"status": "error", "message": f"Error downloading CSV: {e}"}
      
    """
        Save file to the uploads folder while printing for temporary storage. 
    """         
    def saveToFolder(self):
        file_data = self.getFile()
        decompressed_data = gzip.decompress(file_data)
        with open(self.generatePath(), 'wb') as f:
            f.write(decompressed_data)

    """
        Generate temporary path to uploads folder and temporarily append the job's PK to the file name 
    """
    def generatePath(self):
        return os.path.join('../uploads', self.getFileNamePk())

    """
        TIME-RELATED CODE BELOW 
    """
    
    """
        Enter .gcode file and locate the model's time estimate. This will be the basis of the clocks and ETA on the frontend. 
    """
    def getTimeFromFile(self, comment_lines):
        # job_line can look two ways:
        # 1. ;TIME:seconds
        # 2. ; estimated printing time (normal mode) = minutes seconds
        # if first line contains "FLAVOR", then the second line contains the time estimate in the format of ";TIME:seconds"
        if "FLAVOR" in comment_lines[0]:
            time_line = comment_lines[1]
            time_seconds = int(time_line.split(":")[1])
        else:
            # search for the line that contains "printing time", then the time estimate is in the format of "; estimated printing time (normal mode) = minutes seconds"
            time_line = next(line for line in comment_lines if "time" in line)
            time_values = re.findall(r'\d+', time_line)

            # Initialize all time units to 0
            time_days = time_hours = time_minutes = time_seconds = 0

            # Assign values from right to left (seconds, minutes, hours, days)
            time_values = time_values[::-1]
            if len(time_values) > 0:
                time_seconds = int(time_values[0])
            if len(time_values) > 1:
                time_minutes = int(time_values[1])
            if len(time_values) > 2:
                time_hours = int(time_values[2])
            if len(time_values) > 3:
                time_days = int(time_values[3])

            # Calculate total time in seconds
            time_seconds = time_days * 24 * 60 * 60 + time_hours * 60 * 60 + time_minutes * 60 + time_seconds
        # date = datetime.fromtimestamp(time_seconds)
        return time_seconds
    
    """
        Calculate ETA based on now + total time of print. Total time located in getTimeFromFile function and stored in
        self.job_time array position 0. 
    """
    def calculateEta(self):
        now = datetime.now()
        eta = timedelta(seconds=self.job_time[0]) + now
        return eta

    """
        Update ETA is utilized when the print is paused. 
    """
    def updateEta(self):
        now = datetime.now()
        pause_time = self.getJobTime()[3]

        duration = now - pause_time

        new_eta = self.getJobTime()[1] + timedelta(seconds=1)
        return new_eta

    """
        ColorETA is utilized when the print is paused. 
    """   
    def colorEta(self):
        now = datetime.now()
        pause_time = self.getJobTime()[3]
        duration = now - pause_time
        eta = self.getJobTime()[1] + duration
        return eta 

    """
       Total time of print increases when print is paused or in color change sequence. 
    """
    def calculateTotalTime(self):
        total_time = self.getJobTime()[0]
        total_time+=1
        return total_time
    
    """
       Calulates total amount of time spent in a color change sequence. Used to update the ETA and the total time. 
    """
    def calculateColorChangeTotal(self):
        now = datetime.now()
        pause_time = self.getJobTime()[3]
        duration = now - pause_time
        duration_in_seconds = duration.total_seconds()
        total_time = self.getJobTime()[0] + duration_in_seconds
        return total_time
    
    """
        Getters 
    """
    def getName(self):
        return self.name

    def getFilePath(self):
        return self.path

    def getFile(self):
        return self.file

    def getStatus(self):
        return self.status

    def getFileNamePk(self):
        return self.file_name_pk

    def getFileNameOriginal(self):
        return self.file_name_original
    
    def getFileFavorite(self):
        return self.favorite

    def getPrinterId(self): 
        return self.printer_id

    def getJobId(self):
        return self.id

    def getFilePause(self):
        return self.filePause
    
    def getExtruded(self):
        return self.extruded
    
    def getProgress(self):
        return self.progress

    def getTimeStarted(self):
        return self.time_started
    
    def getJobTime(self):
        return self.job_time
    
    def getReleased(self): 
        return self.released
    
    def getTdId(self): 
        return self.td_id
    
    def getPrinterId(self):
        return self.printer_id
    
    """
        Setters 
    """
    def setFileFavorite(self, favorite):
        self.favorite = favorite
        db.session.commit()
        return {"success": True, "message": "Favorite status updated successfully."}
    
    def setFilePause(self, pause):
        self.filePause = pause
        current_app.socketio.emit('file_pause_update', {
                                  'job_id': self.id, 'file_pause': self.filePause})
    
    def setExtruded(self, extruded):
        self.extruded = extruded
        current_app.socketio.emit('extruded_update', {
                                    'job_id': self.id, 'extruded': self.extruded}) 
    def setStatus(self, status):
        self.status = status

    def setProgress(self, progress):
        if self.status == 'printing':
            self.progress = progress
            # Emit a 'progress_update' event with the new progress
            current_app.socketio.emit(
                'progress_update', {'job_id': self.id, 'progress': self.progress})
    
    def setMaxLayerHeight(self, max_layer_height):
        self.max_layer_height = max_layer_height
        current_app.socketio.emit('max_layer_height', {'job_id': self.id, 'max_layer_height': self.max_layer_height})

    def setCurrentLayerHeight(self, current_layer_height):
        self.current_layer_height = current_layer_height
        current_app.socketio.emit('current_layer_height', {'job_id': self.id, 'current_layer_height': self.current_layer_height})

    def setFilament(self, filament):
        self.filament = filament
    
    def setPath(self, path): 
        self.path = path 

    def setFileName(self, filename):
        self.file_name_pk = filename

    def setFile(self, file):
        self.file = file

    def setReleased(self, released):
        self.released = released
        current_app.socketio.emit('release_job', {'job_id': self.id, 'released': released}) 

    def setTimeStarted(self, time_started):
            self.time_started = time_started
            current_app.socketio.emit('set_time_started', {'job_id': self.id, 'started': time_started}) 

    def setTime(self, timeData, index):
        self.job_time[index] = timeData
        if index==0: 
            current_app.socketio.emit('set_time', {'job_id': self.id, 'new_time': timeData, 'index': index}) 
        else: 
            current_app.socketio.emit('set_time', {'job_id': self.id, 'new_time': timeData.isoformat(), 'index': index}) 