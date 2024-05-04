import { api } from './ports'
import { toast } from './toast'
import { type Device } from '@/model/ports'
import { socket } from './myFetch'
import { saveAs } from 'file-saver'
import { ref } from 'vue'

export let pageSize = ref(10)
export let isLoading = ref(false)

/*
  Form data pre-filled when the user reruns a job 
*/
export const selectedPrinters = ref<Array<Device>>([])
export const file = ref<File>()
export const fileName = ref<string>('')
export const quantity = ref<number>(1)
export const priority = ref<number>(0)
export const favorite = ref<boolean>(false)
export const name = ref<string>('')
export const tdid = ref<number>(0)
export const filament = ref<string>('')
const API_ROOT = import.meta.env.VITE_API_ROOT as string

export interface Job {
  id: number
  name: string
  file: File
  download_link?: string
  file_name_original: string
  date?: Date
  status?: string
  progress?: number //store progress of job
  gcode_num?: number //store gcode of job
  printer: string //store printer name
  printerid: number

  td_id: number //store td_id of job
  max_layer_height?: number //store max layer height of job
  current_layer_height?: number //store current layer height of job
  errorid?: number
  error?: string // store issue name

  comment?: string // store comments

  extruded?: number
  filament?: string

  file_pause: number
  priority?: string
  favorite?: boolean
  released?: number
  job_server?: [number, Date | string, Date | string, Date | string] // this saves all of the data from the backend.Only changed if there is a pause involved.

  job_client?: {
    // this is frontend data CALCULATED based on the backend data
    total_time: number
    eta: number
    elapsed_time: number
    extra_time: number
    remaining_time: number
  }
  timer?: NodeJS.Timeout
  time_started?: number
  colorbuff?: number 
  printer_name?: string
  queue_selected?: boolean
}

/*
  This function is called whenever the user opens the printer's time information and also whenever the job_time array in the backend 
  is updated. 

  The job_server array stores all of the static time data from the backend (ETA, total time, time started, pause time).

  The job_client object uses the static job_server data to calculate the dynamic time data (elapsed time, extra time, remaining time).
*/
export async function jobTime(job: Job, printers: any) {
  if (printers) {

    // Instantiate job_client 
    if (!job.job_client) {
      job.job_client = {
        total_time: 0,
        eta: 0,
        elapsed_time: 0,
        extra_time: 0,
        remaining_time: NaN
      }
    }

    // Instantiate job_server
    if (!job.job_server) {
      job.job_server = [0, '00:00:00', '00:00:00', '00:00:00']

      // Fetch static time data from backend and update job_server. This is necessary because when the user reloads the page, 
      // the in-memory job_server data is lost. This repopulates the job_server data so job_client can calculate the dynamic time data.
      for (const printer of printers.value) {
        if (printer.queue && printer.queue.length != 0 && printer.queue[0].status != 'inqueue') {
          let timejson = await refetchtime(printer.id!, printer.queue[0].id)
          if (printer.queue[0].job_server) {
            printer.queue[0].job_server![0] = timejson.total
            if (job.time_started == 1) {
              printer.queue[0].job_server![1] = Date.parse(timejson.eta)
              printer.queue[0].job_server![2] = Date.parse(timejson.timestart)
              printer.queue[0].job_server![3] = Date.parse(timejson.pause)
            }
          }
        }
      }
    }

    const printerid = job.printerid
    const printer = printers.value.find((printer: { id: number }) => printer.id === printerid)

    // Every second, update job time 
    const updateJobTime = () => {
      if (printer.status !== 'printing') {
        clearInterval(job.timer)
        delete job.timer
        return
      }

      // total time = total time of job in seconds from backend * 1000 (convert to milliseconds, formatted in Main View JavaScript)
      let totalTime = job.job_server![0]
      job.job_client!.total_time = totalTime * 1000

      // ETA = ETA of job in milliseconds from backend
      let eta =
        job.job_server![1] instanceof Date ? job.job_server![1].getTime() : job.job_server![1]

      // @ts-ignore
      job.job_client!.eta = eta

      if (
        printer.status === 'printing' ||
        printer.status === 'colorchange' ||
        printer.status === 'paused'
      ) {
        const now = Date.now()
        const elapsedTime = now - new Date(job.job_server![2]).getTime() // Elapsed time = now - time started 
        job.job_client!.elapsed_time = Math.round(elapsedTime / 1000) * 1000
        if (!isNaN(job.job_client!.elapsed_time)) {
          if (job.job_client!.elapsed_time <= job.job_client!.total_time) {
            job.job_client!.remaining_time = // Remaining time = total time - elapsed time 
              job.job_client!.total_time - job.job_client!.elapsed_time
          }
        }
      }

      if (job.job_client!.elapsed_time > job.job_client!.total_time) {
        //@ts-ignore
        job.job_client!.extra_time = Date.now() - eta // Extra time = now - eta 
      }

      // Update elapsed_time after the first second
      if (job.job_client!.elapsed_time === 0) {
        job.job_client!.elapsed_time = 1
      }
    }

    // Call updateJobTime immediately when jobTime is called
    updateJobTime()

    // Continue to call updateJobTime at regular intervals
    job.timer = setInterval(updateJobTime, 1000)
  } else {
    console.error('printers is undefined')
  }
}

/*
  Time socket. Retrieves job_server data from backend and listens for updates. 
*/
export function setupTimeSocket(printers: any) {
  socket.on('set_time', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (!job.job_client || !job.job_server) {
        job.job_client = {
          total_time: 0,
          eta: 0,
          elapsed_time: 0,
          extra_time: 0,
          remaining_time: NaN
        }
        job.job_server = [0, '00:00:00', '00:00:00', '00:00:00']
      }

      if (typeof data.new_time === 'number') {
        job.job_server[data.index] = data.new_time
      } else {
        job.job_server[data.index] = Date.parse(data.new_time)
      }

      jobTime(job, printers)
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

/*
  Refetches job_server data from backend. Called by jobTime function.
*/
async function refetchtime(printerid: number, jobid: number) {
  try {
    const response = await api('refetchtimedata', { printerid, jobid })
    return response
  } catch (error) {
    console.error(error)
    toast.error('An error occurred while updating the job status')
  }
}

/*

*/
export function download(
  action: string,
  body?: unknown,
  method: string = 'POST',
  headers: HeadersInit = { 'Content-Type': 'application/json' }
) {
  return fetch(`${API_ROOT}/${action}`, {
    method,
    headers,
    body: JSON.stringify(body)
  })
}

/*
  Retrieve all jobs to display in Job History based on filter data 
*/
export function useGetJobs() {
  return {
    async jobhistory(
      page: number,
      pageSize: number,
      printerIds?: number[],
      fromError?: number,
      oldestFirst?: boolean,
      searchJob: string = '',
      searchCriteria: string = '',
      searchTicketId: string = '',
      favoriteOnly?: boolean,
      issues?: number[],
      startdate: string = '',
      enddate: string = '',
      countOnly?: number
    ) {
      try {
        const response = await api(
          `getjobs?page=${page}&pageSize=${pageSize}&printerIds=${JSON.stringify(printerIds)}&oldestFirst=${oldestFirst}&searchJob=${encodeURIComponent(searchJob)}&searchCriteria=${encodeURIComponent(searchCriteria)}&searchTicketId=${encodeURIComponent(searchTicketId)}&favoriteOnly=${favoriteOnly}&issueIds=${JSON.stringify(issues)}&startdate=${startdate}&enddate=${enddate}&fromError=${fromError}&countOnly=${countOnly}`
        )
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while retrieving the jobs')
      }
    },
    async getFavoriteJobs() {
      try {
        const response = await api('getfavoritejobs')
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while retrieving the jobs')
      }
    }
  }
}

/*  
  Update job status / assign status to error 
*/
export function useUpdateJobStatus() {
  return {
    async updateJobStatus(jobid: number, status: string) {
      try {
        const response = await api('assigntoerror', { jobid, status })
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while updating the job status')
      }
    }
  }
}

/*
  Add job to queue 
*/
export function useAddJobToQueue() {
  return {
    async addJobToQueue(job: FormData) {
      try {
        const response = await api('addjobtoqueue', job)
        if (response) {
          return response
        } else {
          console.error('Response is undefined or null')
          return { success: false, message: 'Response is undefined or null.' }
        }
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while adding the job to the queue')
      }
    }
  }
}

/*
  Auto-queue job (send to printer with smallest queue)
*/
export function useAutoQueue() {
  return {
    async auto(job: FormData) {
      try {
        const response = await api('autoqueue', job)
        if (response) {
          return response
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to queue job. Unexpected response')
        }
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while adding the job to the queue')
      }
    }
  }
}

/*
  Pass the job PK you'd like to rerun. This is located in the database & duplicated to the specified printer. 
*/
export function useRerunJob() {
  return {
    async rerunJob(job: Job | undefined, printer: Device) {
      try {
        let printerpk = printer.id
        let jobpk = job?.id

        const response = await api('rerunjob', { jobpk, printerpk }) 
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to rerun job. Unexpected response')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to rerun job. Unexpected response')
        }
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while rerunning the job')
      }
    }
  }
}

/*
  Cancels the job in the queue.
*/
export function useRemoveJob() {
  return {
    async removeJob(jobarr: number[]) {
      try {
        const response = await api('cancelfromqueue', { jobarr })
        if (response) {
          return response
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to remove job. Unexpected response')
        }
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while removing the job')
      }
    }
  }
}

/*
  Not sure if we use this anymore, used to change position of jobs in queue 
*/
export function bumpJobs() {
  return {
    async bumpjob(job: Job, printer: Device, choice: number) {
      try {
        let printerid = printer.id
        let jobid = job.id
        const response = await api('bumpjob', { printerid, jobid, choice })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to bump job. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to bump job. Unexpected response')
        }
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while bumping the job')
      }
    }
  }
}

/*
  The "key" parameter indicates if the user clicked clear, clear & rerun, or fail. This removes the job from the queue 
  after its done printing. 
*/
export function useReleaseJob() {
  return {
    async releaseJob(job: Job | undefined, key: number, printerid: number | undefined) {
      try {
        let jobpk = job?.id
        const response = await api('releasejob', { jobpk, key, printerid })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to release job. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to release job. Unexpected response')
        }
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while releasing the job')
      }
    }
  }
}

/*

*/
export function useGetGcode() {
  return {
    async getgcode(job: Job) {
      try {
        const response = await api('getgcode', job)
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while retrieving the gcode')
      }
    }
  }
}

/*

*/
export function useGetJobFile() {
  return {
    async getFileDownload(jobid: number) {
      try {
        const response = await api(`getfile?jobid=${jobid}`)
        const file = new Blob([response.file], { type: 'text/plain' })
        const file_name = response.file_name
        saveAs(file, file_name)
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while retrieving the file')
      }
    }
  }
}

export function useGetFile() {
  return {
    async getFile(job: Job): Promise<File | undefined> {
      try {
        const jobid = job.id
        const response = await api(`getfile?jobid=${jobid}`)
        const file = new File([response.file], response.file_name, { type: 'text/plain' })
        return file
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while retrieving the file')
        return undefined
      }
    }
  }
}

/*
  Removes files from database >6 months old 
*/
export function useClearSpace() {
  return {
    async clearSpace() {
      try {
        const response = await api('clearspace')
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to clear space. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to clear space. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Makes job's "favorites" flag 1 
*/
export function useFavoriteJob() {
  return {
    async favorite(job: Job, favorite: boolean) {
      let jobid = job?.id
      try {
        const response = await api(`favoritejob`, { jobid, favorite })
        if (response.success) {
          job.favorite = favorite ? true : false
        }
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while favoriting the job')
      }
    }
  }
}

/*
  Moves position of jobs in queue 
*/
export function useMoveJob() {
  return {
    async moveJob(printerid: number | undefined, arr: number[] | undefined) {
      try {
        const response = await api('movejob', { printerid, arr })
        if (response) {
          return response
        } else {
          console.error('Response is undefined or null')
          return { success: false, message: 'Response is undefined or null.' }
        }
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while adding the job to the queue')
      }
    }
  }
}

/*
  Deletes job from database
*/
export function useDeleteJob() {
  return {
    async deleteJob(job: Job) {
      let jobid = job?.id
      try {
        const response = await api(`deletejob`, { jobid })
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while deleting the job')
      }
    }
  }
}

/*
  When the user clicks "start print," this function is called. Allows the printer to begin recieving gcode commands. 
*/
export function useStartJob() {
  return {
    async start(jobid: number, printerid: number) {
      try {
        const response = await api(`startprint`, { jobid, printerid })
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while starting the job')
      }
    }
  }
}

/*
  Assigns a comment to a job 
*/
export function useAssignComment() {
  return {
    async assignComment(job: Job, comment: string) {
      let jobid = job?.id
      try {
        const response = await api(`savecomment`, { jobid, comment })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to write comment. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to write comment. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while assigning the comment')
      }
    }
  }
}

/*
  Removes issues from job 
*/
export function useRemoveIssue() {
  return {
    async removeIssue(job: Job) {
      let jobid = job?.id
      try {
        const response = await api(`removeissue`, { jobid })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to remove issue. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to remove issue. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while removing the issue')
      }
    }
  }
}

/*
  Downloads CSV file of all jobs in the jobIds array (filled when user applies filter to job history). If not specified, 
  all jobs in database are downloaded. 
*/
export function useDownloadCsv() {
  return {
    async csv(allJobs: number, jobIds?: number[]): Promise<void> {
      try {
        const response = await download(`downloadcsv`, { allJobs, jobIds })

        if (!response.ok) {
          throw new Error('HTTP error ' + response.status)
        }

        const blob = await response.blob() // Convert the response to a blob
        const date = new Date()
        const dateString = ('0' + (date.getMonth() + 1)).slice(-2) + ('0' + date.getDate()).slice(-2) + date.getFullYear();
        const filename = `jobs_${dateString}.csv`

        saveAs(blob, filename) // saves file 

        await deleteCSVFromServer() // Calls backend to remove the CSV file from the server b/c it successfully downloaded to downloads folder 
      } catch (error) {
        console.error('An error occurred while downloading the CSV:', error)
        toast.error('An error occurred while downloading the CSV')
      }
    }
  }
}

// Calls backend to remove the CSV file from the server b/c it successfully downloaded to downloads folder. 
// Called by useDownloadCSV. 
export async function deleteCSVFromServer() {
  try {
    const response = await api(`removeCSV`)
    return response
  } catch (error) {
    console.error(error)
    toast.error('An error occurred while removing the issue')
  }
}
