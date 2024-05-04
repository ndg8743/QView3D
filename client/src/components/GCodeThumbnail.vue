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
const canvas = ref<HTMLCanvasElement | undefined>(undefined);
let preview: GCodePreview.WebGLPreview | null = null;

// ref for the thumbnail source
const thumbnailSrc = ref<string | null>(null);

// when the component is mounted
// if there is no modal, log an error
// initialize the preview to have the canvas, but thats all we need
// get the file
// if the file is available, convert it to a string
// try to extract the thumbnail from the metadata
// if the thumbnail is available, set the thumbnail source
// when the modal is hidden, clean up the preview
// this is for failsafe
onMounted(async () => {
    if (!modal) {
        console.error('Modal element is not available');
        return;
    }

    preview = GCodePreview.init({
        canvas: canvas.value,
    });

    const fileValue = await file();
    if (fileValue) {
        const gcode = await fileToString(fileValue);
        try {
            // Extract the thumbnail from the metadata
            const { metadata } = preview.parser.parseGCode(gcode);
            if (metadata.thumbnails && metadata.thumbnails['640x480']) {
                const thumbnailData = metadata.thumbnails['640x480'];
                thumbnailSrc.value = thumbnailData.src;
            }
        } catch (error) {
            console.error('Failed to process GCode:', error);
        }
    }

    modal.addEventListener('hidden.bs.modal', () => {
        // Clean up when the modal is hidden
        preview?.processGCode('');
        preview?.clear();
        preview = null;
        thumbnailSrc.value = null;
    });
});

// this is for failsafe again, just when the component is unmounted
onUnmounted(() => {
    preview?.processGCode('');
    preview?.clear();
    preview = null;
    thumbnailSrc.value = null;
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
        now we need to have a canvas in order to have a preview
        but we don't want to show it because this is for the thumbnail

        if the thumbnail source is available, show the thumbnail
        otherwise, show a message
     -->
    <canvas v-show="false" style="display: hidden" ref="canvas"></canvas>
    <img v-if="thumbnailSrc" :src="thumbnailSrc" alt="GCode Thumbnail" />
    <div v-else>This file doesn't have a thumbnail attached, you can check the viewer instead!</div>
</template>

<style scoped>
/*
thought these widths and heights would be a good size
but they can be changed
*/
img {
    max-width: 500px;
    max-height: 500px;
    display: block;
    margin: auto;
}
</style>