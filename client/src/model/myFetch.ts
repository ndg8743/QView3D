import io from 'socket.io-client';

/*
    This function is used to make fetch requests to server and specifies headers and body of the request.
*/

export const socket = io(import.meta.env.VITE_API_ROOT, {
    transports: ['websocket']
})
const API_ROOT = import.meta.env.VITE_API_ROOT as string;

export function rest(url: string, body?: unknown, method?: string, headers?: HeadersInit){
    
    // Specify different headers if FormData is used.
    const isFormData = body instanceof FormData;
    const options: RequestInit = {
        method: method ?? (body ? "POST" : "GET"),
        headers: {
            ...headers
        },
        body: isFormData ? body : JSON.stringify(body)
    };

    if (!isFormData) {
        options.headers = options.headers || {};
        (options.headers as Record<string, string>)['Content-Type'] = 'application/json';
    }

    return fetch(url, options)
        .then(response => response.ok 
            ? response.json()
            : response.json().then(err => Promise.reject(err))    )
}

export function api(action: string, body?: unknown, method?: string, headers?: HeadersInit){
    return rest(`${API_ROOT}/${action}`, body, method, headers);
}