<script setup lang="ts">
import { printers } from '../model/ports'
import { selectedPrinters, file, fileName, quantity, priority, favorite, name, tdid, filament, useAddJobToQueue, useGetFile, useAutoQueue, isLoading } from '../model/jobs'
import { ref, onMounted, watchEffect, computed, watch } from 'vue'
import { RouterLink, routerKey, useRoute } from 'vue-router';
import { toast } from '@/model/toast';
import GCode3DImageViewer from '@/components/GCode3DImageViewer.vue';
import GCodeThumbnail from '@/components/GCodeThumbnail.vue';
import router from '@/router';
import { time } from 'console';

// methods from the models to be used in the view
const { addJobToQueue } = useAddJobToQueue()
const { auto } = useAutoQueue()
const { getFile } = useGetFile();

// route to get the job and printer from the previous page
const route = useRoute();

// variables from the route if they exist
const job = route.params.job ? JSON.parse(route.params.job as string) : null;
const printer = route.params.printer ? JSON.parse(route.params.printer as string) : null;
const isAsteriksVisible = ref(true)

// variables to be used in the view
const form = ref<HTMLFormElement | null>(null);
let isSubmitDisabled = false;

const isGcodeImageVisible = ref(false)
const isImageVisible = ref(true)

const filamentTypes = ['PLA', 'PETG', 'ABS', 'ASA', 'FLEX', 'HIPS', 'EDGE', 'NGEN', 'PA', 'PVA', 'PCTG', 'PP', 'PC', 'CPE', 'PEBA', 'PVB', 'PLA TOUGH', 'METAL', 'PET']

// fills printers array with printers that have threads from the database
onMounted(async () => {
    try {
        isLoading.value = true
        if (printer && !selectedPrinters.value.some(selectedPrinter => selectedPrinter.id === printer.id)) {
            selectedPrinters.value.push(printer)
        }

        if (job) {
            file.value = await getFile(job)
            fileName.value = file.value?.name || ''
            name.value = job.name
            if (file.value) {
                getFilament(file.value).then(filamentType => {
                    filament.value = filamentType ? filamentType.toString() : '';
                }).catch(() => {
                    filament.value = '';
                });
            } else {
                filament.value = '';
            }
        }
        isLoading.value = false

        const modal = document.getElementById('gcodeImageModal');

        modal?.addEventListener('hidden.bs.modal', () => {
            isGcodeImageVisible.value = false;
            isImageVisible.value = true;
            isAsteriksVisible.value = true;
        });

        const filamentDropdown = document.getElementById('filamentDropdown');

        filamentDropdown?.addEventListener('shown.bs.dropdown', () => {
            isAsteriksVisible.value = false;
        });

        filamentDropdown?.addEventListener('hidden.bs.dropdown', () => {
            isAsteriksVisible.value = true;
        });
    } catch (error) {
        console.error('There has been a problem with your fetch operation:', error)
    }
})

// watches the selected printers and the quantity
// so if the user selects three printers while the quantity is 1,
// the quantity will be set to 3
watch(selectedPrinters, () => {
    if (quantity.value < selectedPrinters.value.length) {
        quantity.value = selectedPrinters.value.length;
    }
});

// watches the quantity and makes it so the quantity cannot be greater than 1000
// if the user tries to input a number greater than 1000, it will set the quantity
// to 1000 really fast and show a toast message
// and also disables the submit button if the form is not valid
watchEffect(() => {
    if (quantity.value > 1000) {
        quantity.value = 1000;
        toast.error('Quantity cannot be greater than 1000');
    }
    isSubmitDisabled = !(file.value !== undefined && name.value.trim() !== '' && quantity.value > 0 && (quantity.value >= selectedPrinters.value.length || selectedPrinters.value.length == 0) && filament.value !== '');
});

// file upload handler
// checks if the file name is longer than 50 characters, which is the limit
// sets the file, file name, and name variables
const handleFileUpload = (event: Event) => {
    isLoading.value = true
    const target = event.target as HTMLInputElement;
    const uploadedFile = target.files ? target.files[0] : undefined;
    if (uploadedFile && uploadedFile.name.length > 50) {
        toast.error('The file name should not be longer than 50 characters');
        target.value = ''
        file.value = undefined
        fileName.value = ''
    } else {
        file.value = uploadedFile
        fileName.value = uploadedFile?.name || ''
        name.value = fileName.value.replace('.gcode', '') || ''

        if (file.value) {
            getFilament(file.value).then(filamentType => {
                filament.value = filamentType ? filamentType.toString() : '';
            }).catch(() => {
                filament.value = '';
            });
        } else {
            filament.value = '';
        }
    }
    isLoading.value = false
}

// validates the quantity
// checks if the quantity is less than the number of selected printers,
// if it is, it sets the quantity to the number of selected printers
const validateQuantity = () => {
    if (quantity.value < 1 && selectedPrinters.value.length > 0) {
        quantity.value = selectedPrinters.value.length
    }
    if (quantity.value < selectedPrinters.value.length) {
        toast.error('Quantity must be greater than or equal to the number of selected printers')
        return false;
    }
    return true;
}

// only allows numbers to be inputted
// checks if the key code is not a number or backspace
const onlyNumber = ($event: KeyboardEvent) => {
    let keyCode = $event.keyCode;
    if ((keyCode < 48 || keyCode > 57) && (keyCode < 96 || keyCode > 105) && keyCode !== 8) { // 48-57 are the keycodes for 0-9, 96-105 are for the numpad 0-9, 8 is for backspace
        $event.preventDefault();
    }
}

/*
    Used when the user is submitting a job. If no printer is selected (selectedPrinters.value.length == 0), use the auto 
    function. Else, evenly split jobs amongst all selected printers. 
*/
const handleSubmit = async () => {
    isLoading.value = true
    let isFavoriteSet = false;
    let res = null
    if (selectedPrinters.value.length == 0) {
        let numPrints = quantity.value
        for (let i = 0; i < numPrints; i++) {
            const formData = new FormData() 
            formData.append('file', file.value as File) 
            formData.append('name', name.value as string)
            formData.append('priority', priority.value.toString())
            formData.append('td_id', tdid.value.toString())
            formData.append('filament', filament.value as string)
            // If favorite is true and it's not set yet, set it for the first job only
            if (favorite.value && !isFavoriteSet) {
                formData.append('favorite', 'true')
                isFavoriteSet = true;
            } else {
                formData.append('favorite', 'false')
            }
            try {
                res = await auto(formData)
            } catch (error) {
                console.error('There has been a problem with your fetch operation:', error)
            }
        }
        resetValues()

    } else {
        let sub = validateQuantity()
        if (sub == true) {
            let printsPerPrinter = Math.floor(quantity.value / selectedPrinters.value.length) // number of even prints per printer
            let remainder = quantity.value % selectedPrinters.value.length; //remainder to be evenly distributed 
            for (const printer of selectedPrinters.value) {
                let numPrints = printsPerPrinter
                if (remainder > 0) {
                    numPrints += 1
                    remainder -= 1
                }
                for (let i = 0; i < numPrints; i++) {
                    const formData = new FormData() // create FormData object
                    formData.append('file', file.value as File) // append form data
                    formData.append('name', name.value as string)
                    formData.append('printerid', printer?.id?.toString() || '');
                    formData.append('priority', priority.value.toString())
                    formData.append('quantity', numPrints.toString())
                    formData.append('td_id', tdid.value.toString())
                    formData.append('filament', filament.value as string)

                    // If favorite is true and it's not set yet, set it for the first job only
                    if (favorite.value && !isFavoriteSet) {
                        formData.append('favorite', 'true')
                        isFavoriteSet = true;
                    } else {
                        formData.append('favorite', 'false')
                    }

                    try {
                        res = await addJobToQueue(formData)
                    } catch (error) {
                        console.error('There has been a problem with your fetch operation:', error)
                    }
                }
            }
            resetValues()
        }
    }
    if (res.success == true) {
        toast.success('Job added to queue')
    } else if (res.success == false) {
        toast.error('Job failed to add to queue')
    } else {
        toast.error('Failed to add job to queue. Unexpected response.')
    }
    setTimeout(() => {
        router.go(0)}, 500);

    isLoading.value = false
    isAsteriksVisible.value = true
}

// resets the values of the form
// makes quantity 1 if there are no selected printers
function resetValues() {
    selectedPrinters.value = [];
    // quantity.value = selectedPrinters.value.length;
    if (selectedPrinters.value.length > 0) {
        quantity.value = selectedPrinters.value.length;
    } else {
        quantity.value = 1
    }
    priority.value = 0;
    favorite.value = false;
    name.value = "";
    fileName.value = '';
    file.value = undefined;
    tdid.value = 0;
    filament.value = '';
}

// computed property to check if all printers are selected
// in the form, there is a select all checkbox to select all printers to print to
// this computed property checks if all printers are selected or not
// and also sets all printers to be selected if the user selects the select all checkbox
const allSelected = computed({
    get: () => selectedPrinters.value.length > 0 && selectedPrinters.value.length === printers.value.length,
    set: (value) => {
        if (value) {
            selectedPrinters.value = printers.value.slice();
            if (quantity.value < selectedPrinters.value.length) {
                quantity.value = selectedPrinters.value.length;
            }
        } else {
            selectedPrinters.value = [];
        }
    }
});

// when the user clicks the browse button, it triggers the file input
const triggerFileInput = () => {
    const fileInput = document.getElementById('file') as HTMLInputElement;
    fileInput.click();
}

// sets the filament type
const selectFilament = (type: string) => {
    filament.value = type
}

// gets the filament type from the gcode file
// reads the file backwards and looks for the filament type
// works for prusa slicer gcode files
const getFilament = (file: File) => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = function (event) {
            const lines = (event.target?.result as string).split('\n').reverse();
            for (let line of lines) {
                if (line.startsWith('; filament_type = ')) {
                    resolve(line.split('= ')[1]);
                    return;
                }
            }
            resolve(null);
        };
        reader.onerror = function () {
            reject(new Error("Failed to read file"));
        };
        reader.readAsText(file);
    });
};

</script>
<template>
    <!-- 
        this modal is used to show the gcode image
        it has two views, the image view and the viewer view
        if the file has an image, it will show the image view
        but no matter what, it will show the viewer view

        both components gets the file as a prop
     -->
    <div class="modal fade" id="gcodeImageModal" tabindex="-1" aria-labelledby="gcodeImageModalLabel"
        aria-hidden="true">
        <div :class="['modal-dialog', isImageVisible ? '' : 'modal-xl', 'modal-dialog-centered']">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="gcodeImageModalLabel">
                        <b>{{ fileName }}</b> <br>
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
                        <GCode3DImageViewer v-if="isGcodeImageVisible && !isImageVisible" :file="file" />
                        <GCodeThumbnail v-else-if="isGcodeImageVisible && isImageVisible" :file="file" />
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 
        this is the form to submit a job
        it has the following fields:
        - printer selection
        - file upload
        - filament selection
        - quantity
        - ticket id
        - priority
        - favorite
        - name

        the form has a submit button that will add the job(s) to the queue(s)
     -->
    <div class="container">
        <div class="card" style="border: 1px solid #484848; background: #d8d8d8;">
            <div class="card-body">
                <form @submit.prevent="handleSubmit" ref="form">

                    <div class="mb-3">
                        <label for="printer" class="form-label">Select Printer</label>
                        <div class="card"
                            style="max-height: 120px; overflow-y: auto; background-color: #f4f4f4 !important; border-color: #484848 !important;">
                            <ul class="list-unstyled card-body m-0" style="padding-top: .5rem; padding-bottom: .5rem;">
                                <li>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="select-all"
                                            v-model="allSelected">
                                        <label class="form-check-label" for="select-all">
                                            Select All
                                        </label>
                                    </div>
                                    <div class="border-top"
                                        style="border-width: 1px; margin-left: -16px; margin-right: -16px;"></div>
                                </li>
                                <li v-for="printer in printers" :key="printer.id">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" :value="printer"
                                            v-model="selectedPrinters" :id="'printer-' + printer.id">
                                        <label class="form-check-label" :for="'printer-' + printer.id">
                                            {{ printer.name }}
                                        </label>
                                    </div>
                                </li>
                            </ul>
                        </div>
                    </div>

                    <div class="mb-3">
                        <label class="form-label" v-if="selectedPrinters.length === 0">No printer selected, will <b>auto
                                queue</b></label>
                        <label class="form-label" v-else-if="selectedPrinters.length === 1">Selected printer:</label>
                        <label class="form-label" v-else>Selected printers:</label>
                        <ul class="list-group" style="max-height: 200px; overflow-y: auto;">
                            <li v-for="printer in selectedPrinters" class="list-group-item">
                                <b>{{ printer.name }}</b> status: {{ printer.status }}
                            </li>
                        </ul>
                    </div>

                    <div class="mb-3">
                        <label for="file" class="form-label">Upload your .gcode file</label>
                        <div class="tooltip">
                            <span v-if="isAsteriksVisible" class="text-danger">*</span>
                            <span class="tooltiptext">The file name should not be longer than 50 characters</span>
                        </div>
                        <input ref="fileInput" @change="handleFileUpload" style="display: none;" type="file" id="file"
                            name="file" accept=".gcode">
                        <div class="input-group">
                            <button type="button" @click="triggerFileInput" class="btn btn-primary">Browse</button>
                            <label class="form-control" style="width: 220px;">
                                <div v-if="fileName" class="ellipsis" style="width: 200px;">
                                    {{ fileName }}
                                </div>
                                <div v-else>No file selected.</div>
                            </label>
                            <button type="button" class="btn btn-primary" data-bs-toggle="modal"
                                data-bs-target="#gcodeImageModal"
                                @click="() => { isGcodeImageVisible = true; isAsteriksVisible = false }"
                                v-bind:disabled="!fileName">
                                <i class="fa-regular fa-image"></i>
                            </button>
                        </div>
                    </div>

                    <div class="mb-3">
                        <label for="filament" class="form-label">Filament</label>
                        <div class="tooltip">
                            <span v-if="isAsteriksVisible" class="text-danger">*</span>
                            <span class="tooltiptext">The filament needs to be selected if not prefilled.</span>
                        </div>
                        <div class="input-group">
                            <div class="dropdown w-100" id="filamentDropdown">


                                <button class="btn btn-primary dropdown-toggle w-100" type="button"
                                    id="dropdownMenuButton" data-bs-toggle="dropdown"
                                    :aria-expanded="filament ? 'false' : 'true'">
                                    {{ filament || 'Select Filament' }}
                                </button>

                                <ul class="dropdown-menu dropdown-menu-scrollable w-100"
                                    aria-labelledby="dropdownMenuButton">
                                    <li><a class="dropdown-item" v-for="type in filamentTypes" :key="type"
                                            @click="selectFilament(type)">{{ type }}</a></li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <div class="mb-3">
                        <label for="quantity" class="form-label">Quantity</label>
                        <div v-if="isAsteriksVisible" class="text-danger tooltip">*
                            <span class="tooltiptext">Quantity cannot be greater than 1000</span>
                        </div>
                        <input v-model="quantity" class="form-control" type="number" id="quantity" name="quantity"
                            min="1" @keydown="onlyNumber($event)">
                    </div>

                    <div class="mb-3">
                        <label for="quantity" class="form-label">Ticket ID</label>
                        <input v-model="tdid" class="form-control" type="number" id="tdid" name="tdid"
                            @keydown="onlyNumber($event)">
                    </div>

                    <div class="row mb-3">
                        <div class="col-2">
                            <div class="form-check">
                                <input v-model="priority" class="form-check-input" type="checkbox" id="priority"
                                    name="priority">
                                <label class="form-check-label" for="priority">Priority?</label>
                            </div>
                        </div>

                        <div class="col-6"></div>

                        <div class="col-2">
                            <div class="form-check">
                                <input v-model="favorite" class="form-check-input" type="checkbox" id="favorite"
                                    name="favorite">
                                <label class="form-check-label" for="favorite">Favorite?</label>
                            </div>
                        </div>
                    </div>

                    <div class="mb-3">
                        <label for="name" class="form-label">Name</label>
                        <div class="tooltip">
                            <span v-if="isAsteriksVisible" class="text-danger">*</span>
                            <span class="tooltiptext">Assign a name for the job.</span>
                        </div>
                        <input v-model="name" class="form-control" type="text" id="name" name="name">
                    </div>

                    <div>
                        <button v-if="selectedPrinters.length > 1" :disabled="isLoading || isSubmitDisabled"
                            class="btn btn-primary" type="submit">
                            Add to queues
                        </button>
                        <button v-else :disabled="isLoading || isSubmitDisabled" class="btn btn-primary" type="submit">
                            Add to queue
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</template>

<style scoped>
.dropdown-menu-scrollable {
    max-height: 200px;
    overflow-y: auto;
}

.form-control,
.list-group-item {
    background-color: #f4f4f4 !important;
    border-color: #484848 !important;
}

.form-container {
    border: 2px solid #333;
    padding: 20px;
    width: 300px;
}

.ellipsis {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.card {
    --bs-card-border-color: #484848;
}

.text-danger {
    cursor: help;
}
</style>