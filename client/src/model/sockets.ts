import { socket } from './myFetch'
import type { Device } from './ports'
import { jobTime } from './jobs'

/*
    This file contains functions that set up the socket connection and event listeners for the client side.
    The functions are used to update the status of the printers and jobs in real-time.
*/

// *** PORTS ***

// Update temperature data of printer 
export function setupTempSocket(printers: any) {
  socket.on('temp_update', (data: any) => {
    const printer = printers.value.find((p: Device) => p.id === data.printerid)
    if (printer) {
      printer.extruder_temp = data.extruder_temp
      printer.bed_temp = data.bed_temp
    }
  })
}

// Get status of printer
export function setupStatusSocket(printers: any) {
  socket.on('status_update', (data: any) => {
    if (printers) {
      const printer = printers.value.find((p: Device) => p.id === data.printer_id)
      if (printer) {
        printer.status = data.status
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Get updates for when backend queue changes 
export function setupQueueSocket(printers: any) {
  socket.on('queue_update', (data: any) => {
    if (printers) {
      const printer = printers.value.find((p: Device) => p.id === data.printerid)
      if (printer) {
        printer.queue = data.queue
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Printer error updates 
export function setupErrorSocket(printers: any) {
  socket.on('error_update', (data: any) => {
    if (printers) {
      const printer = printers.value.find((p: Device) => p.id === data.printerid)
      if (printer) {
        printer.error = data.error
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Printer paused updates 
export function setupCanPauseSocket(printers: any) {
  socket.on('can_pause', (data: any) => {
    if (printers) {
      const printer = printers.value.find((p: Device) => p.id === data.printerid)
      if (printer) {
        printer.canPause = data.canPause
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// *** JOBS ***

// Lets frontend know if the job is paused
export function setupPauseFeedbackSocket(printers: any) {
  socket.on('file_pause_update', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (job) {
        job.file_pause = data.file_pause
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Update when time started for job
export function setupTimeStartedSocket(printers: any) {
  socket.on('set_time_started', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (job) {
        job.time_started = data.time_started
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Constantly update progress bar of job 
export function setupProgressSocket(printers: any) {
  socket.on('progress_update', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (job) {
        job.progress = data.progress
        // job.elapsed_time = data.elapsed_time
        // Update the display value only if progress is defined
        if (data.progress !== undefined) {
          job.progress = data.progress
        }
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Socket to release job (remove from queue when done printing )
export function setupReleaseSocket(printers: any) {
  socket.on('release_job', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)
      if (job) {
        job.released = data.released
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Job status updates from backend 
export function setupJobStatusSocket(printers: any) {
  socket.on('job_status_update', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (job) {
        job.status = data.status
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Ports on registeredview automatically updated when ports are updated before printer starts printing 
export function setupPortRepairSocket(printers: any) {
  socket.on('port_repair', (data: any) => {
    if (printers) {
      const printer = printers.value.find((p: Device) => p.id === data.printer_id)
      printer.device = data.device
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// 
export function setupGCodeViewerSocket(printers: any) {
  socket.on('gcode_viewer', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (job) {
        job.gcode_num = data.gcode_num
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Update when job has had first extrusion. Then, the color change and pause buttons are no longer disabled. 
export function setupExtrusionSocket(printers: any) {
  socket.on('extruded_update', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (job) {
        job.extruded = data.extruded
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

// Update when layer finishes and the user can change the color of the filament.
export function setupColorChangeBuffer(printers: any) {
  socket.on('color_buff', (data: any) => {
    if (printers) {
      const printer = printers.value.find((p: Device) => p.id === data.printerid)
      if (printer) {
        printer.colorbuff = data.colorbuff
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}


export function setupMaxLayerHeightSocket(printers: any) {
  socket.on('max_layer_height', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (job) {
        job.max_layer_height = data.max_layer_height
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}

export function setupCurrentLayerHeightSocket(printers: any) {
  socket.on('current_layer_height', (data: any) => {
    if (printers) {
      const job = printers.value
        .flatMap((printer: { queue: any }) => printer.queue)
        .find((job: { id: any }) => job?.id === data.job_id)

      if (job) {
        job.current_layer_height = data.current_layer_height
      }
    } else {
      console.error('printers or printers.value is undefined')
    }
  })
}