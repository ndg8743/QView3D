<script setup lang="ts">
import { onMounted, ref, toRef, watchEffect, onUnmounted } from 'vue';
import { useGetFile, type Job } from '@/model/jobs';
import * as GCodePreview from 'gcode-preview';

// method to be used in the component
const { getFile } = useGetFile();

// prop, just a job
const props = defineProps({
    job: Object as () => Job
})

// assing the job passed to a ref
const job = toRef(props, 'job');

// ref for the modal from the page it was opened from
const modal = document.getElementById('gcodeLiveViewModal');

// create a ref for the canvas, a variable for the preview and an array for the layers
const canvas = ref<HTMLCanvasElement | null>(null);
let preview: GCodePreview.WebGLPreview | null = null;
let layers: string[][] = [];

// when the component is mounted
// if there is no modal, log an error
// get the file from the job
// convert the file to a string
// split the string into lines
// create an array of layers
// watch to see if the next layer should be drawn
// when the modal is shown, initialize the preview and draw the gcode
// when the modal is hidden, clean up the preview
// this is for failsafe
onMounted(async () => {
    if (!modal) {
        console.error('Modal element is not available');
        return;
    }

    const gcodeFile = await getFile(props.job!);
    if (!gcodeFile) {
        console.error('Failed to get the file');
        return;
    }

    const fileString = await fileToString(gcodeFile);
    const lines = fileString.split('\n');
    layers = lines.reduce((layers, line) => {
        if (line.startsWith(";LAYER_CHANGE")) {
            layers.push([]);
        }
        if (layers.length > 0) {
            layers[layers.length - 1].push(line as never);
        }
        return layers;
    }, [[]]);

    watchEffect(() => {
        if (job.value?.current_layer_height && preview) {
            try {
                // process gcode of layers up to current_layer_height
                const currentLayerIndex = layers.findIndex(layer => layer.includes(`;Z:${job.value!.current_layer_height}`));
                if (currentLayerIndex !== -1) {
                    preview.clear();
                    preview.processGCode(layers.slice(0, currentLayerIndex + 1).flat());
                }
            } catch (error) {
                console.error('Failed to process GCode:', error);
            }
        }
    });

    modal.addEventListener('shown.bs.modal', async () => {
        // Initialize the GCodePreview and show the GCode when the modal is shown
        if (canvas.value) {
            preview = GCodePreview.init({
                canvas: canvas.value,
                extrusionColor: getComputedStyle(document.documentElement).getPropertyValue('--bs-primary-color').trim() || '#7561A9',
                backgroundColor: 'black',
                buildVolume: { x: 250, y: 210, z: 220, r: 0, i: 0, j: 0 },
            });

            preview.camera.position.set(0, 475, 0);
            preview.camera.lookAt(0, 0, 0);

            if (job.value?.current_layer_height && preview) {
                try {
                    // process gcode of layers up to current_layer_height
                    const currentLayerIndex = layers.findIndex(layer => layer.includes(`;Z:${job.value!.current_layer_height}`));
                    if (currentLayerIndex !== -1) {
                        preview.clear();
                        const gcode = layers.slice(0, currentLayerIndex + 1).flat();
                        preview.processGCode(gcode);
                    }
                } catch (error) {
                    console.error('Failed to process GCode:', error);
                }
            }
        }
    });

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