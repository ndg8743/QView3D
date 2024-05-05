from collections import deque
from flask import jsonify, current_app


class Queue:
    def __init__(self):
        self.__queue = deque()  # use Python double-ended queue

    def __iter__(self):  # iterate over queue
        return iter(self.__queue)

    """
        Add job to back of printer queue 
    """
    def addToBack(self, job, printerid):
        if self.__queue.count(job) > 0:
            raise Exception("Job ID already in queue.")
        self.__queue.append(
            job
        )  
        current_app.socketio.emit(
            "queue_update", {"queue": self.convertQueueToJson(), "printerid": printerid}
        )

    """
        Add job to front of printer queue or to second posiion if first job is printing
    """
    def addToFront(self, job, printerid):
        if self.__queue.count(job) > 0:
            raise Exception("Job ID already in queue.")
        if len(self.__queue) >= 1 and self.__queue[0].status == "printing":
            self.__queue.insert(1, job)
        else:
            self.__queue.appendleft(job)
        current_app.socketio.emit(
            "queue_update", {"queue": self.convertQueueToJson(), "printerid": printerid}
        )

    """
        Unsure if we use this function, used to change position of jobs in queue 
    """
    def bump(self, up, jobid): 
        index = next(
            (
                index
                for index, queued_job in enumerate(self.__queue)
                if queued_job.id == jobid
            ),
            -1,
        )
        if index == -1:
            print("Job not found in queue.")
            return
        job_to_move = self.__queue[index]
        self.__queue.remove(job_to_move)
        if up == True and index > 0:
            self.__queue.insert(index - 1, job_to_move)
        elif not up and index < len(self.__queue):
            self.__queue.insert(index + 1, job_to_move)
        
    """
        Used to reorder the queue based on the order of the jobids in the arr
    """
    def reorder(self, arr): 
        new_queue = deque()
        for jobid in arr: 
            for job in self.__queue: 
                if job.getJobId() == jobid: 
                    new_queue.append(job)
                    break
        self.__queue = new_queue
    
    """
        Delete job from queue
    """
    def deleteJob(self, jobid, printerid):
        deletedjob = None
        for job in self.__queue:
            if job.getJobId() == jobid:
                deletedjob = job
                self.__queue.remove(job)
                current_app.socketio.emit(
                    "queue_update",
                    {"queue": self.convertQueueToJson(), "printerid": printerid},
                )
                return deletedjob
        return "Job not found in queue."

    """
        Convery queue data to json format to send to frontend by other functions
    """
    def convertQueueToJson(self):
        queue = []
        for job in self.__queue:
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
            queue.append(job_info)
        return queue

    """
        Do we use this? front parameter is a boolean, sends job to absolute end of queue or absolute beginning 
    """
    def bumpExtreme(self, front, jobid, printerid): 
        index = next(
            (
                index
                for index, queued_job in enumerate(self.__queue)
                if queued_job.id == jobid
            ),
            -1,
        )
        if index == -1:
            print("Job not found in queue.")
            return
        job_to_move = self.__queue[index]
        self.__queue.remove(job_to_move)
        if front == True:
            if len(self.__queue) >= 1 and self.__queue[0].status == "printing":
                self.__queue.insert(1, job_to_move)
            else:
                self.__queue.insert(0, job_to_move)
        else:
            self.addToBack(job_to_move, printerid)

    """ 
        Find and return job in queue based on job PK 
    """
    def getJob(self, job_to_find):
        for job in self.__queue:
            if job.getJobId() == job_to_find.getJobId():
                return job
        return None  

    """
        Same as above? Not sure why we have two of these functions / which one we use 
    """
    def getJobById(self, job_to_find):
        for job in self.__queue:
            if job.getJobId() == job_to_find:
                return job
        return None  

    """
        Says if job exists in queue or not
    """
    def jobExists(self, jobid):
        for job in self.__queue:
            if job.id == jobid:
                return True
        return False

    """
        Removes last job in queue
    """
    def removeJob(self):
        self.__queue.pop()
        
    """
       Getters  
    """
    def getQueue(self):
        return self.__queue

    def getNext(self):
        return self.__queue[0]

    def getSize(self):
        return len(self.__queue)

