import { useRouter } from 'vue-router'
import { ref, computed, onUnmounted } from 'vue'
import * as myFetch from './myFetch'
import { toast } from './toast'
import { type Job } from './jobs'
import { socket } from './myFetch'

export function api(action: string, body?: unknown, method?: string, headers?: any) {
  headers = headers ?? {}
  return myFetch.api(`${action}`, body, method, headers).catch((err) => console.log(err))
}

export interface Device {
  device: string
  description: string
  hwid: string
  name?: string
  status?: string
  date?: Date
  id?: number
  error?: string
  canPause?: number
  queue?: Job[] //  Store job array to store queue for each printer.
  isQueueExpanded?: boolean
  isInfoExpanded?: boolean
  extruder_temp?: number
  bed_temp?: number
  colorChangeBuffer?: number
}

/*
  Global variable to store the list of printers and printer queues based on in-memory thread data from backend 
*/
export let printers = ref<Device[]>([])

/*
  Get all connected serial ports. Only return ports that are connected to 3D printers. 
*/
export function useGetPorts() {
  return {
    async ports() {
      try {
        const response = await api('getports')
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Register printer based on data collected from useGetPorts 
*/
export function useRegisterPrinter() {
  return {
    async register(printer: Device) {
      try {
        const response = await api('register', { printer })
        if (response) {
          if (response.success === false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to register printer. Unexpected response')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to register printer. Unexpected response')
        }
      } catch (error) {
        console.error(error)
        toast.error('An error occurred while registering the printer')
      }
    }
  }
}

/*
  Gets all registered printers from the database to display on Registered View 
*/
export function useRetrievePrinters() {
  return {
    async retrieve() {
      try {
        const response = await api('getprinters')
        return response.printers
      } catch (error) {
        console.error(error)
      }
    }
  }
}


/*
  Main function to retrieve thread data from backend and store it in the printers variable.
*/
export function useRetrievePrintersInfo() {
  return {
    async retrieveInfo() {
      try {
        const response = await api('getprinterinfo')
        return response // return the response directly
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Set status of printer 
*/
export function useSetStatus() {
  return {
    async setStatus(printerid: number | undefined, status: string) {
      try {
        const response = await api('setstatus', { printerid, status })
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Delete and recreate thread data for printer
*/
export function useHardReset() {
  return {
    async hardReset(printerid: number | undefined) {
      try {
        const response = await api('hardreset', { printerid })
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
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  If a printer is deregistered, set all FKs of jobs connected to that printer to null
*/
export function useNullifyJobs() {
  return {
    async nullifyJobs(printerid: number | undefined) {
      try {
        const response = await api('nullifyjobs', { printerid })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to nullify jobs. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to nullify jobs. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Delete printer from database
*/
export function useDeletePrinter() {
  return {
    async deletePrinter(printerid: number | undefined) {
      try {
        const response = await api('deleteprinter', { printerid })
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Delete in-memory thread data for printer
*/
export function useRemoveThread() {
  return {
    async removeThread(printerid: number | undefined) {
      try {
        const response = await api('removethread', { printerid })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to remove thread. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to remove thread. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Edit name of printer in database 
*/
export function useEditName() {
  return {
    async editName(printerid: number | undefined, name: string) {
      try {
        const response = await api('editname', { printerid, name })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to edit name. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to edit name. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Edit name of printer in thread data
*/
export function useEditThread() {
  return {
    async editThread(printerid: number | undefined, newname: string) {
      try {
        const response = await api('editNameInThread', { printerid, newname })
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Tells user if printer is connected to a serial port or not and if the port it is registered under 
  is the port that the printer is currently connected to.
*/
export function useDiagnosePrinter() {
  return {
    async diagnose(device: string) {
      try {
        const response = await api('diagnose', { device })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to diagnose printer. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to diagnose printer. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
    Lists all of the ports currently connected to the machine. If the port the printer is registered under does not match the  
    port the printer is currently connected to, update the port in the database. We check this by comparing the hwid 
    returned by the connected port and the hwid stored in the database. 
*/
export function useRepair() {
  return {
    async repair() {
      try {
        const response = await api('repairports')
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to repair ports. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to repair ports. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
    Route to send the "printer home" gcode command while the printer is registering a printer, so the user can tell 
    which printer they have selected. 
*/
export function useMoveHead() {
  return {
    async move(port: string) {
      try {
        const response = await api('movehead', { port })
        if (response) {
          if (response.success == false) {
            toast.error(response.message)
          } else if (response.success === true) {
            toast.success(response.message)
          } else {
            console.error('Unexpected response:', response)
            toast.error('Failed to move head. Unexpected response.')
          }
        } else {
          console.error('Response is undefined or null')
          toast.error('Failed to move head. Unexpected response')
        }
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}

/*
  Method to change the order of printer threads so the user can rearrange the order of printers on the UI (Main view)
*/
export function useMovePrinterList() {
  return {
    async movePrinterList(printers: Device[]) {
      try {
        // make new array of printer id's in the order they are in the printers array
        const printersIds = printers.map((printer) => printer.id)
        const response = await api('moveprinterlist', { printersIds })
        return response
      } catch (error) {
        console.error(error)
      }
    }
  }
}
