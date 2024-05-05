<script setup lang="ts">
import { onUnmounted, ref, computed, watchEffect, onMounted, watch } from 'vue'
import { printers, type Device } from '../model/ports'
import { useRerunJob, useRemoveJob, type Job, useMoveJob, useGetFile, useGetJobFile, isLoading } from '../model/jobs'
import draggable from 'vuedraggable'
import { toast } from '@/model/toast'
import GCode3DImageViewer from '@/components/GCode3DImageViewer.vue'
import GCodeThumbnail from '@/components/GCodeThumbnail.vue';

// methods from the models to be used in the view
const { removeJob } = useRemoveJob()
const { rerunJob } = useRerunJob()
const { moveJob } = useMoveJob()
const { getFile } = useGetFile()
const { getFileDownload } = useGetJobFile()

// used for checkboxes for deleting jobs
const selectedJobs = ref<Array<Job>>([])

// used for the modal
let currentJob = ref<Job | null>(null)
let isGcodeImageVisible = ref(false)
const isImageVisible = ref(true)

// colors for the status of the printer
const primaryColor = ref('');
const primaryColorActive = ref('');
const successColorActive = ref('');

// observer for the colors
// needed this if the user is on this page while changing the colors
let observer: MutationObserver;

// when the page is loaded we use the observer to get the colors
// we also get the modal and add an event listener to it
// so when the modal is closed we change the visibility of the visible values
onMounted(() => {
  isLoading.value = true
  observer = new MutationObserver(() => {
    primaryColor.value = window.getComputedStyle(document.documentElement).getPropertyValue('--bs-primary-color').trim() || '#7561A9';
    primaryColorActive.value = window.getComputedStyle(document.documentElement).getPropertyValue('--bs-primary-color-active').trim() || '#51457C';
    successColorActive.value = window.getComputedStyle(document.documentElement).getPropertyValue('--bs-success-color-active').trim() || '#3e7776';
  });

  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['style'] });

  const modal = document.getElementById('gcodeImageModal')

  modal?.addEventListener('hidden.bs.modal', () => {
    isGcodeImageVisible.value = false
    isImageVisible.value = true
  });
  isLoading.value = false
});

// when unmounted we set each printers isQueueExpanded to false
// and disconnect the observer
onUnmounted(() => {
  for (const printer of printers.value) {
    printer.isQueueExpanded = false
  }
  observer.disconnect();
})

// observer for the colors
watchEffect(() => {
  primaryColor.value = window.getComputedStyle(document.documentElement).getPropertyValue('--bs-primary-color').trim() || '#7561A9';
  primaryColorActive.value = window.getComputedStyle(document.documentElement).getPropertyValue('--bs-primary-color-active').trim() || '#51457C';
  successColorActive.value = window.getComputedStyle(document.documentElement).getPropertyValue('--bs-success-color-active').trim() || '#3e7776';
});

// if the user selects to rerun a job
const handleRerun = async (job: Job, printer: Device) => {
  await rerunJob(job, printer)
}

// if the user selects to delete a job from the queue
// we get the selected jobs and remove them from the queue
const deleteSelectedJobs = async () => {
  isLoading.value = true
  let response = null
  const selectedJobIds = computed(() => selectedJobs.value.map(job => job.id));
  response = await removeJob(selectedJobIds.value);
  if (response.success == false) {
    toast.error(response.message)
  } else if (response.success === true) {
    toast.success(response.message)
  } else {
    console.error('Unexpected response:', response)
    toast.error('Failed to remove job. Unexpected response.')
  }

  for (const printer of printers.value) {
    printer.queue?.forEach((job) => job.queue_selected = false)
  }

  isLoading.value = false
}

// this is for the select all jobs checkbox for each printer
// when you click it, all the jobs in queue for that printer will be selected
// and when you click the checkbox for all the jobs in queue, the selectAllJobs checkbox will be selected as well
const selectAllJobs = (printer: Device) => computed({
  get: () => {
    if (printer.queue?.length === 0) {
      return false;
    }
    return printer.queue?.every((job: Job) => job.queue_selected);
  },
  set: (value) => {
    printer.queue?.forEach((job: Job) => job.queue_selected = value);
  }
});

// when the printers change, we update the selected jobs accordingly
watch(printers, (printers) => {
  selectedJobs.value = printers.flatMap((printer) => printer.queue?.filter((job) => job.queue_selected) || [])
}, { deep: true })

// capitalize the first letter of the printers status
// to be displayed on the accordion, solely for aesthetics
function capitalizeFirstLetter(string: string | undefined) {
  return string ? string.charAt(0).toUpperCase() + string.slice(1) : ''
}

// colors for the status of the printer
// displayed on the accordion, with different colors for different statuses
function statusColor(status: string | undefined) {
  switch (status) {
    case 'ready':
      return successColorActive.value;
    case 'error':
      return '#ad6060';
    case 'offline':
      return 'black';
    case 'printing':
      return primaryColorActive.value;
    case 'complete':
      return primaryColor.value;
    default:
      return 'black';
  }
}

// jobs are draggable, this function is called when a job is placed after dragging
// it updates the position of the job in the queue in the backend by calling the moveJob function
const handleDragEnd = async (evt: any) => {
  const printerId = Number(evt.item.dataset.printerId)
  const arr = Array.from(evt.to.children).map((child: any) => Number(child.dataset.jobId))
  await moveJob(printerId, arr)
}

// checks if the job is in the queue
const isInqueue = (evt: any) => {
  return evt.relatedContext.element.status === 'inqueue'
}

// opens the modal for the gcode image
// setting the current job and printer
const openModal = async (job: Job, printerName: string) => {
  currentJob.value = job
  currentJob.value.printer = printerName
  isGcodeImageVisible.value = true
  if (currentJob.value) {
    const file = await getFile(currentJob.value)
    if (file) {
      currentJob.value.file = file
    }
  }
}
</script>

<template>
  <!-- 
    this modal is used to show the gcode image
    it has two views, the image view and the viewer view
    if the file has an image, it will show the image view
    but no matter what, it will show the viewer view

    both components gets the job as a prop
   -->
  <div class="modal fade" id="gcodeImageModal" tabindex="-1" aria-labelledby="gcodeImageModalLabel" aria-hidden="true">
    <div :class="['modal-dialog', isImageVisible ? '' : 'modal-xl', 'modal-dialog-centered']">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="gcodeImageModalLabel">
            <b>{{ currentJob?.printer }}:</b> {{ currentJob?.name }}
            <div class="form-check form-switch">
              <label class="form-check-label" for="switchView">{{ isImageVisible ? 'Image' : 'Viewer'
                }}</label>
              <input class="form-check-input" type="checkbox" id="switchView" v-model="isImageVisible">
            </div>
          </h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <div class="row">
            <GCode3DImageViewer v-if="isGcodeImageVisible && !isImageVisible" :job="currentJob!" />
            <GCodeThumbnail v-else-if="isGcodeImageVisible && isImageVisible" :job="currentJob!" />
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 
    this modal is used to show the confirmation of removing jobs
    it will show the amount of jobs that will be removed
    and ask the user if they are sure they want to remove them
   -->
  <div class="modal fade" id="exampleModal" tabindex="-1" aria-labelledby="exampleModalLabel" aria-hidden="true"
    data-bs-backdrop="static">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="exampleModalLabel">
            Removing {{ selectedJobs.length }} job(s) from queue!
          </h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <p>
            Are you sure you want to remove these job(s) from queue? Job will be saved to history
            with a final status of <i>cancelled</i>.
          </p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
          <button type="button" class="btn btn-danger" data-bs-dismiss="modal" @click="deleteSelectedJobs">
            Remove
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 
    on the top of the view, there is a button to all jobs that are selected

    below that, every printer has an accordion, displaying its name, status and the amount of jobs in the queue
    when opened, it will display the jobs in the queue in a table
    each job has:
      - ticket id
      - a split dropdown
        - button to rerun the job to the same printer
        - dropdown with options to rerun the job to another printer
      - the position in the queue
      - the job title
      - the file name
      - the date added
      - the job status
      - a dropdown with options to:
        - show the gcode image
        - download the file
      - a checkbox to select the job to be removed
      - a handle to drag the job in the queue

    the table is draggable, so the user can change the order of the jobs in the queue
    when the user changes the order, the handleDragEnd function is called
    which updates the position of the job in the queue in the backend

    at the top of the printers queues table, in the header, there is a checkbox
    that selects all jobs in the queue or deselects all jobs in the queue

    and for when there are no printers available, it will display a message to the user to register a printer
   -->
  <div class="container">
    <div class="row w-100" style="margin-bottom: 0.5rem">
      <div class="col-2 text-start" style="padding-left: 0">

      </div>
      <div class="col-8"></div>
      <div class="col-2 text-end" style="padding-right: 0">
        <button class="btn btn-danger" data-bs-toggle="modal" data-bs-target="#exampleModal"
          :disabled="selectedJobs.length === 0">
          Remove
        </button>
      </div>
    </div>

    <div v-if="printers.length === 0">
      No printers available. Either register a printer
      <RouterLink class="routerLink" to="/registration"> here </RouterLink>, or restart the server.
    </div>

    <div v-else class="accordion" id="accordionPanelsStayOpenExample">
      <div class="accordion-item" v-for="(printer, index) in printers" :key="printer.id">
        <h2 class="accordion-header" :id="'panelsStayOpen-heading' + index">
          <button class="accordion-button" type="button" data-bs-toggle="collapse"
            :data-bs-target="'#panelsStayOpen-collapse' + index" :aria-expanded="printer.isQueueExpanded"
            :aria-controls="'panelsStayOpen-collapse' + index" :class="{ collapsed: !printer.isQueueExpanded }">
            <b>{{ printer.name }}:&nbsp;
              <span v-if="printer.status === 'printing' && printer.queue?.[0]?.released === 0">
                Pending Release
              </span>
              <span v-else>
                <span class="status-text" :style="{ color: statusColor(printer.status) }">
                  {{ capitalizeFirstLetter(printer.status) }}
                </span>
              </span>
              <span v-if="printer.queue?.length != 1" style="position: absolute; right: 50px;">{{ printer.queue?.length
      || 0 }} jobs in queue</span>
              <span v-if="printer.queue?.length == 1" style="position: absolute; right: 50px;">{{ printer.queue?.length
      || 0 }} job in queue</span>
            </b>
          </button>
        </h2>
        <div :id="'panelsStayOpen-collapse' + index" class="accordion-collapse collapse"
          :class="{ show: printer.isQueueExpanded }" :aria-labelledby="'panelsStayOpen-heading' + index"
          @show.bs.collapse="printer.isQueueExpanded = !printer.isQueueExpanded">
          <div class="accordion-body">
            <div :class="{ 'scrollable': printer.queue!.length > 3 }">
              <table class="table-striped">
                <thead>
                  <tr style="position: sticky; top: 0; z-index: 100; background-color: white;">
                    <th style="width: 102px;">Ticket ID</th>
                    <th style="width: 143px;">Rerun Job</th>
                    <th style="width: 76px;">Position</th>
                    <th style="width: 215px;">Job Title</th>
                    <th style="width: 215px;">File</th>
                    <th style="width: 220px;">Date Added</th>
                    <th style="width: 96px;">Job Status</th>
                    <th style="width: 75px;">Actions</th>
                    <th style="width: 48px;">
                      <div class="checkbox-container">
                        <input class="form-check-input" type="checkbox" :disabled="printer.queue!.length === 0"
                          v-model="selectAllJobs(printer).value" />
                      </div>

                    </th>
                    <th style="width: 58px">Move</th>
                  </tr>
                </thead>
                <draggable v-model="printer.queue" tag="tbody" :animation="300" itemKey="job.id" handle=".handle"
                  dragClass="hidden-ghost" :onEnd="handleDragEnd" v-if="printer.queue && printer.queue.length"
                  :move="isInqueue">
                  <template #item="{ element: job }">
                    <tr :id="job.id.toString()" :data-printer-id="printer.id" :data-job-id="job.id"
                      :data-job-status="job.status" :key="job.id" :class="{ 'printing': job.status === 'printing' }">
                      <td class="truncate" :title="job.td_id">{{ job.td_id }}</td>
                      <td class="text-center">
                        <div class="btn-group w-100">
                          <div class="btn btn-primary" @click="handleRerun(job, printer)">
                            Rerun Job
                          </div>
                          <div class="btn btn-primary dropdown-toggle dropdown-toggle-split" data-bs-toggle="dropdown"
                            aria-expanded="false"></div>
                          <div class="dropdown-menu">
                            <div class="dropdown-item" v-for="printer in printers" :key="printer.id"
                              @click="handleRerun(job, printer)">
                              {{ printer.name }}
                            </div>
                          </div>
                        </div>
                      </td>

                      <td class="text-center">
                        <b>
                          {{ printer.queue ? printer.queue.findIndex((j) => j === job) + 1 : '' }}
                        </b>
                      </td>
                      <td class="truncate" :title="job.name">
                        <b>{{ job.name }}</b>
                      </td>
                      <td class="truncate" :title="job.file_name_original">{{ job.file_name_original }}</td>
                      <td class="truncate" :title="job.date">{{ job.date }}</td>
                      <td class="truncate" :title="job.status"
                        v-if="printer.queue && printer.status == 'printing' && printer.queue?.[0].released == 0 && job.status == 'printing'">
                        pending release</td>
                      <td v-else>{{ job.status }}</td>

                      <td style="width:">
                        <div class="dropdown">
                          <div style="
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100%;
                          ">
                            <button type="button" id="settingsDropdown" data-bs-toggle="dropdown" aria-expanded="false"
                              style="background: none; border: none">
                              <i class="fa-solid fa-bars"></i>
                            </button>
                            <ul class="dropdown-menu" aria-labelledby="settingsDropdown">
                              <li>
                                <a class="dropdown-item d-flex align-items-center" data-bs-toggle="modal"
                                  data-bs-target="#gcodeImageModal" v-if="printer.queue && printer.queue.length > 0"
                                  @click="printer.name && openModal(job, printer.name)">
                                  <i class="fa-solid fa-image"></i>
                                  <span class="ms-2">GCode Image</span>
                                </a>
                              </li>
                              <li>
                                <a class="dropdown-item d-flex align-items-center" @click="getFileDownload(job.id)"
                                  :disabled="job.file_name_original.includes('.gcode:')">
                                  <i class="fas fa-download"></i>
                                  <span class="ms-2">Download</span>
                                </a>
                              </li>
                            </ul>
                          </div>
                        </div>
                      </td>

                      <td class="text-center">
                        <input class="form-check-input" type="checkbox" v-model="job.queue_selected" :value="job"
                          :disabled="job.status !== 'inqueue'" />
                      </td>

                      <td class="text-center handle" :class="{ 'not-draggable': job.status !== 'inqueue' }">
                        <i class="fas fa-grip-vertical" :class="{ 'icon-disabled': job.status !== 'inqueue' }"></i>
                      </td>
                    </tr>
                  </template>
                </draggable>

                <tr v-if="printer.queue && printer.queue.length === 0">
                  <td colspan="10" class="text-center">No jobs in queue</td>
                </tr>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scrollable {
  max-height: 230px;
  overflow-y: auto;
}

table {
  color: #1b1b1b;
  background-color: #d8d8d8;
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

td,
th {
  border-top: 0px solid #929292 !important;
}

.dropdown-item {
  display: flex;
  align-items: center;
  padding-left: 0.5rem;
}

.dropdown-item i {
  width: 20px;
}

.dropdown-item span {
  margin-left: 10px;
}

.btn-circle {
  width: 30px;
  height: 30px;
  padding: 0.375em 0;
  border-radius: 50%;
  font-size: 0.75em;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.sortable-chosen {
  opacity: 0.5;
  background-color: #f2f2f2;
}

.hidden-ghost {
  opacity: 0;
}

.handle {
  cursor: grab;
}

.handle:active {
  cursor: grabbing;
}

.checkbox-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.icon-disabled {
  color: #6e7073;
}

.not-draggable {
  pointer-events: none;
}

table {
  border-bottom: 0px !important;
  border-left: 0px !important;
  border-right: 0px !important;
  border-top: 0px !important;
}

table tr:last-child td {
  border-bottom: none !important;
}

.accordion-body {
  padding: 0;
}

/* HARDCODED */
.accordion-item {
  width: 1296px;
  overflow: hidden !important;
}

.accordion-button:not(.collapsed) {
  background-color: #9f9f9f;
}

.accordion-button {
  box-shadow: none;
}

.accordion-button {
  color: black;
  display: flex;
}

.accordion-button:not(.collapsed)::after {
  background-image: var(--bs-accordion-btn-icon);
}

.printerrerun {
  cursor: pointer;
  padding: 12px 16px;
}

.modal-backdrop {
  display: none;
}
</style>
