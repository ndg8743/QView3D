<script setup lang="ts">
import { onMounted, ref, toRef, onUnmounted } from 'vue';
import { useGetFile, type Job } from '@/model/jobs';
import * as GCodePreview from 'gcode-preview';

// method to be used in the component
const { getFile } = useGetFile();

// props
// could be job or file, not both
const props = defineProps({
    job: Object as () => Job,
    file: Object as () => File
})

// if file is provided, use the file
// if job is provided, get the file from the job
const file = () => {
    if (props.file) {
        return props.file
    } else if (props.job) {
        return getFile(props.job)
    } else {
        return null
    }
}

// ref for the modal from the page it was opened from
const modal = document.getElementById('gcodeImageModal');

// create a ref for the canvas and a variable for the preview
const canvas = ref<HTMLCanvasElement | null>(null);
let preview: GCodePreview.WebGLPreview | null = null;

// when the component is mounted
// if there is no modal, log an error
// if there is a canvas, initialize the preview
// set the preview camera to above the print bed
// look at the center of the bed
// get the file and convert it to a string
// draw the gcode on the preview
// when the modal is closed, clean up the preview
// this is for failsafe
onMounted(async () => {
    if (!modal) {
        console.error('Modal element is not available');
        return;
    }

    if (canvas.value) {
        preview = GCodePreview.init({
            canvas: canvas.value,
            extrusionColor: getComputedStyle(document.documentElement).getPropertyValue('--bs-primary-color').trim() || '#7561A9',
            backgroundColor: 'black',
            buildVolume: { x: 250, y: 210, z: 220, r: 0, i: 0, j: 0 },
        });

        preview.camera.position.set(0, 410, 365);
        preview.camera.lookAt(0, 0, 0);

        if (canvas.value) {
            // job.file to string
            const fileValue = await file();
            if (fileValue) {
                const gcode = await fileToString(fileValue);

                try {
                    preview?.processGCode(gcode); // MAIN LINE
                } catch (error) {
                    console.error('Failed to process GCode:', error);
                }
            }
        }
    }

    modal.addEventListener('hidden.bs.modal', () => {
        // Clean up when the modal is hidden
        preview?.processGCode('');
        preview?.clear();
        preview = null;
    });
});

// for fail safe again, just when the component is unmounted
onUnmounted(() => {
    preview?.processGCode('');
    preview?.clear();
    preview = null;
});

// convert the file to one long string
const fileToString = (file: File | undefined) => {
    if (!file) {
        console.error('File is not available');
        return '';
    }

    const reader = new FileReader();
    reader.readAsText(file);
    return new Promise<string>((resolve, reject) => {
        reader.onload = () => {
            resolve(reader.result as string);
        };
        reader.onerror = (error) => {
            reject(error);
        };
    });
};
</script>

<template>
    <!-- 
        the canvas where the gcode will be drawn
     -->
    <canvas ref="canvas"></canvas>
</template>

<style scoped>
canvas {
    width: 100%;
    height: 100%;
    display: block;
}
</style>