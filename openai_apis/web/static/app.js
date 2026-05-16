/**
 * OpenAI Voice Agent - Frontend Application
 */

// Constants
const SAMPLE_RATE = 24000;
const API_BASE = '';

// State
let audioContext = null;
let mediaRecorder = null;
let recordedChunks = [];
let isRecording = false;
let realtimeWs = null;
let realtimeAudioContext = null;
let pttActive = false;
let pttMediaRecorder = null;
let pttAudioChunks = [];
let ttsAudioBuffer = null;

// DOM Elements
const elements = {};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initElements();
    initTabs();
    initRealtime();
    initTranscription();
    initTTS();
    initSettings();
    checkHealth();
});

/**
 * Initialize DOM element references
 */
function initElements() {
    // Tabs
    elements.tabBtns = document.querySelectorAll('.tab-btn');
    elements.tabPanels = document.querySelectorAll('.tab-panel');

    // Realtime
    elements.wsStatus = document.getElementById('ws-status');
    elements.wsStatusText = document.getElementById('ws-status-text');
    elements.connectBtn = document.getElementById('connect-btn');
    elements.disconnectBtn = document.getElementById('disconnect-btn');
    elements.pttBtn = document.getElementById('ptt-btn');
    elements.recordingIndicator = document.getElementById('recording-indicator');
    elements.conversationLog = document.getElementById('conversation-log');
    elements.rtVoice = document.getElementById('rt-voice');
    elements.rtLanguage = document.getElementById('rt-language');
    elements.rtInstructions = document.getElementById('rt-instructions');

    // Transcription
    elements.recordTranscribeBtn = document.getElementById('record-transcribe-btn');
    elements.audioFileInput = document.getElementById('audio-file-input');
    elements.transcriptionRecordingStatus = document.getElementById('transcription-recording-status');
    elements.sttModel = document.getElementById('stt-model');
    elements.sttLanguage = document.getElementById('stt-language');
    elements.sttPrompt = document.getElementById('stt-prompt');
    elements.transcriptionResult = document.getElementById('transcription-result');
    elements.copyTranscriptionBtn = document.getElementById('copy-transcription-btn');

    // TTS
    elements.ttsText = document.getElementById('tts-text');
    elements.ttsCharCount = document.getElementById('tts-char-count');
    elements.ttsVoice = document.getElementById('tts-voice');
    elements.ttsModel = document.getElementById('tts-model');
    elements.ttsSpeed = document.getElementById('tts-speed');
    elements.ttsSpeedValue = document.getElementById('tts-speed-value');
    elements.generateTtsBtn = document.getElementById('generate-tts-btn');
    elements.downloadTtsBtn = document.getElementById('download-tts-btn');
    elements.ttsAudioContainer = document.getElementById('tts-audio-container');
    elements.ttsInfo = document.getElementById('tts-info');
    elements.ttsDuration = document.getElementById('tts-duration');

    // Settings
    elements.defaultLanguage = document.getElementById('default-language');
    elements.defaultVoice = document.getElementById('default-voice');
    elements.defaultTemperature = document.getElementById('default-temperature');
    elements.defaultTempValue = document.getElementById('default-temp-value');
    elements.defaultInstructions = document.getElementById('default-instructions');
    elements.saveSettingsBtn = document.getElementById('save-settings-btn');
    elements.resetSettingsBtn = document.getElementById('reset-settings-btn');
    elements.apiStatus = document.getElementById('api-status');
    elements.apiKeyStatus = document.getElementById('api-key-status');

    // Toast
    elements.toastContainer = document.getElementById('toast-container');
}

/**
 * Initialize tab navigation
 */
function initTabs() {
    elements.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;

            // Update buttons
            elements.tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update panels
            elements.tabPanels.forEach(p => p.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// ============ REALTIME ============

function initRealtime() {
    elements.connectBtn.addEventListener('click', connectRealtime);
    elements.disconnectBtn.addEventListener('click', disconnectRealtime);

    // Push-to-talk with mouse events
    elements.pttBtn.addEventListener('mousedown', startPTT);
    elements.pttBtn.addEventListener('mouseup', stopPTT);
    elements.pttBtn.addEventListener('mouseleave', stopPTT);

    // Touch support
    elements.pttBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startPTT();
    });
    elements.pttBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopPTT();
    });

    // Load saved settings
    loadSettings();
}

async function connectRealtime() {
    const voice = elements.rtVoice.value;
    const language = elements.rtLanguage.value;
    const instructions = elements.rtInstructions.value;

    updateWsStatus('connecting', 'Connecting...');

    try {
        // Request microphone permission first
        await navigator.mediaDevices.getUserMedia({ audio: true });

        // Build WebSocket URL with query params
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/realtime?voice=${voice}&language=${language}&instructions=${encodeURIComponent(instructions)}`;

        realtimeWs = new WebSocket(wsUrl);

        realtimeWs.onopen = () => {
            console.log('WebSocket connected');
        };

        realtimeWs.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleRealtimeMessage(data);
        };

        realtimeWs.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateWsStatus('error', 'Connection error');
            showToast('Connection error', 'error');
        };

        realtimeWs.onclose = () => {
            console.log('WebSocket closed');
            updateWsStatus('disconnected', 'Disconnected');
            elements.connectBtn.disabled = false;
            elements.disconnectBtn.disabled = true;
            elements.pttBtn.disabled = true;
        };

    } catch (error) {
        console.error('Failed to connect:', error);
        updateWsStatus('error', 'Failed to connect');
        showToast('Failed to connect: ' + error.message, 'error');
    }
}

function disconnectRealtime() {
    if (realtimeWs) {
        realtimeWs.close();
        realtimeWs = null;
    }
}

function handleRealtimeMessage(data) {
    switch (data.type) {
        case 'session_ready':
            updateWsStatus('connected', 'Connected');
            elements.connectBtn.disabled = true;
            elements.disconnectBtn.disabled = false;
            elements.pttBtn.disabled = false;
            showToast('Session ready', 'success');
            break;

        case 'transcription':
            addConversationItem('user', data.text);
            break;

        case 'response_text':
            addConversationItem('assistant', data.text);
            break;

        case 'response_audio':
            playRealtimeAudio(data.data);
            break;

        case 'response_done':
            console.log('Response complete');
            break;

        case 'error':
            showToast('Error: ' + data.message, 'error');
            break;
    }
}

function updateWsStatus(status, text) {
    elements.wsStatus.className = 'status-indicator ' + status;
    elements.wsStatusText.textContent = text;
}

async function startPTT() {
    if (!realtimeWs || realtimeWs.readyState !== WebSocket.OPEN || pttActive) return;

    pttActive = true;
    elements.pttBtn.classList.add('recording');
    elements.recordingIndicator.classList.add('active');
    pttAudioChunks = [];

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: SAMPLE_RATE,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
            }
        });

        // Create AudioContext for raw PCM capture
        realtimeAudioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
        const source = realtimeAudioContext.createMediaStreamSource(stream);

        // Create ScriptProcessor for PCM capture (deprecated but works)
        const processor = realtimeAudioContext.createScriptProcessor(4096, 1, 1);

        processor.onaudioprocess = (e) => {
            if (!pttActive) return;

            const inputData = e.inputBuffer.getChannelData(0);
            // Convert float32 to int16
            const int16Data = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                int16Data[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
            }

            // Send as base64
            const base64 = arrayBufferToBase64(int16Data.buffer);
            if (realtimeWs && realtimeWs.readyState === WebSocket.OPEN) {
                realtimeWs.send(JSON.stringify({ type: 'audio', data: base64 }));
            }
        };

        source.connect(processor);
        processor.connect(realtimeAudioContext.destination);

        // Store for cleanup
        pttMediaRecorder = { stream, source, processor };

    } catch (error) {
        console.error('PTT start error:', error);
        showToast('Microphone error: ' + error.message, 'error');
        stopPTT();
    }
}

function stopPTT() {
    if (!pttActive) return;

    pttActive = false;
    elements.pttBtn.classList.remove('recording');
    elements.recordingIndicator.classList.remove('active');

    // Cleanup audio resources
    if (pttMediaRecorder) {
        if (pttMediaRecorder.processor) {
            pttMediaRecorder.processor.disconnect();
        }
        if (pttMediaRecorder.source) {
            pttMediaRecorder.source.disconnect();
        }
        if (pttMediaRecorder.stream) {
            pttMediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
        pttMediaRecorder = null;
    }

    if (realtimeAudioContext) {
        realtimeAudioContext.close();
        realtimeAudioContext = null;
    }

    // Commit audio and request response
    if (realtimeWs && realtimeWs.readyState === WebSocket.OPEN) {
        realtimeWs.send(JSON.stringify({ type: 'commit' }));
    }
}

function playRealtimeAudio(base64Audio) {
    if (!audioContext) {
        audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
    }

    // Decode base64 to ArrayBuffer
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }

    // Convert int16 to float32 for Web Audio
    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768;
    }

    // Create and play buffer
    const buffer = audioContext.createBuffer(1, float32.length, SAMPLE_RATE);
    buffer.copyToChannel(float32, 0);

    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.destination);
    source.start();
}

function addConversationItem(role, text) {
    const item = document.createElement('div');
    item.className = `conversation-item ${role}`;
    item.innerHTML = `<div class="role">${role === 'user' ? 'You' : 'Assistant'}</div><div class="content">${escapeHtml(text)}</div>`;
    elements.conversationLog.appendChild(item);
    elements.conversationLog.scrollTop = elements.conversationLog.scrollHeight;
}

// ============ TRANSCRIPTION ============

function initTranscription() {
    elements.recordTranscribeBtn.addEventListener('click', toggleTranscriptionRecording);
    elements.audioFileInput.addEventListener('change', handleFileUpload);
    elements.copyTranscriptionBtn.addEventListener('click', copyTranscription);
}

async function toggleTranscriptionRecording() {
    if (isRecording) {
        stopTranscriptionRecording();
    } else {
        startTranscriptionRecording();
    }
}

async function startTranscriptionRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: SAMPLE_RATE,
                channelCount: 1,
            }
        });

        recordedChunks = [];
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4'
        });

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                recordedChunks.push(e.data);
            }
        };

        mediaRecorder.onstop = async () => {
            stream.getTracks().forEach(track => track.stop());
            const blob = new Blob(recordedChunks, { type: mediaRecorder.mimeType });
            await transcribeAudio(blob);
        };

        mediaRecorder.start();
        isRecording = true;
        elements.transcriptionRecordingStatus.classList.remove('hidden');
        elements.recordTranscribeBtn.innerHTML = '<span class="btn-icon">⏹</span> Stop Recording';

    } catch (error) {
        console.error('Recording error:', error);
        showToast('Microphone error: ' + error.message, 'error');
    }
}

function stopTranscriptionRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    isRecording = false;
    elements.transcriptionRecordingStatus.classList.add('hidden');
    elements.recordTranscribeBtn.innerHTML = '<span class="btn-icon">🎤</span> Record & Transcribe';
}

async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    await transcribeAudio(file);
    e.target.value = ''; // Reset input
}

async function transcribeAudio(audioBlob) {
    elements.transcriptionResult.innerHTML = '<span class="placeholder">Transcribing...</span>';
    elements.copyTranscriptionBtn.disabled = true;

    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');
    formData.append('model', elements.sttModel.value);
    formData.append('language', elements.sttLanguage.value);
    if (elements.sttPrompt.value) {
        formData.append('prompt', elements.sttPrompt.value);
    }

    try {
        const response = await fetch(`${API_BASE}/api/transcribe`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Transcription failed');
        }

        const result = await response.json();
        elements.transcriptionResult.textContent = result.text;
        elements.copyTranscriptionBtn.disabled = false;
        showToast('Transcription complete', 'success');

    } catch (error) {
        console.error('Transcription error:', error);
        elements.transcriptionResult.innerHTML = `<span class="placeholder" style="color: var(--error-color)">Error: ${error.message}</span>`;
        showToast('Transcription failed: ' + error.message, 'error');
    }
}

function copyTranscription() {
    const text = elements.transcriptionResult.textContent;
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard', 'success');
    });
}

// ============ TTS ============

function initTTS() {
    elements.ttsText.addEventListener('input', updateCharCount);
    elements.ttsSpeed.addEventListener('input', updateSpeedValue);
    elements.generateTtsBtn.addEventListener('click', generateTTS);
    elements.downloadTtsBtn.addEventListener('click', downloadTTS);
}

function updateCharCount() {
    const count = elements.ttsText.value.length;
    elements.ttsCharCount.textContent = count;
}

function updateSpeedValue() {
    elements.ttsSpeedValue.textContent = elements.ttsSpeed.value;
}

async function generateTTS() {
    const text = elements.ttsText.value.trim();
    if (!text) {
        showToast('Please enter text to synthesize', 'warning');
        return;
    }

    elements.generateTtsBtn.disabled = true;
    elements.generateTtsBtn.innerHTML = '<span class="btn-icon">⏳</span> Generating...';
    elements.ttsAudioContainer.innerHTML = '<span class="placeholder">Generating audio...</span>';

    try {
        const response = await fetch(`${API_BASE}/api/synthesize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                voice: elements.ttsVoice.value,
                model: elements.ttsModel.value,
                speed: parseFloat(elements.ttsSpeed.value),
                output_format: 'base64',
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'TTS failed');
        }

        const result = await response.json();

        // Decode base64 and create audio
        const binaryString = atob(result.audio);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        // Store for download
        ttsAudioBuffer = bytes.buffer;

        // Create WAV blob for playback
        const wavBlob = createWavBlob(bytes.buffer, SAMPLE_RATE);
        const audioUrl = URL.createObjectURL(wavBlob);

        elements.ttsAudioContainer.innerHTML = `<audio controls src="${audioUrl}"></audio>`;
        elements.ttsDuration.textContent = result.audio_duration_seconds.toFixed(2);
        elements.ttsInfo.classList.remove('hidden');
        elements.downloadTtsBtn.disabled = false;

        showToast('Audio generated', 'success');

    } catch (error) {
        console.error('TTS error:', error);
        elements.ttsAudioContainer.innerHTML = `<span class="placeholder" style="color: var(--error-color)">Error: ${error.message}</span>`;
        showToast('TTS failed: ' + error.message, 'error');

    } finally {
        elements.generateTtsBtn.disabled = false;
        elements.generateTtsBtn.innerHTML = '<span class="btn-icon">🔊</span> Generate Speech';
    }
}

function downloadTTS() {
    if (!ttsAudioBuffer) return;

    const wavBlob = createWavBlob(ttsAudioBuffer, SAMPLE_RATE);
    const url = URL.createObjectURL(wavBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'speech.wav';
    a.click();
    URL.revokeObjectURL(url);
}

// ============ SETTINGS ============

function initSettings() {
    elements.defaultTemperature.addEventListener('input', () => {
        elements.defaultTempValue.textContent = elements.defaultTemperature.value;
    });

    elements.saveSettingsBtn.addEventListener('click', saveSettings);
    elements.resetSettingsBtn.addEventListener('click', resetSettings);

    loadSettings();
}

function saveSettings() {
    const settings = {
        language: elements.defaultLanguage.value,
        voice: elements.defaultVoice.value,
        temperature: elements.defaultTemperature.value,
        instructions: elements.defaultInstructions.value,
    };

    localStorage.setItem('voiceAgentSettings', JSON.stringify(settings));
    applySettings(settings);
    showToast('Settings saved', 'success');
}

function loadSettings() {
    const saved = localStorage.getItem('voiceAgentSettings');
    if (saved) {
        const settings = JSON.parse(saved);
        applySettings(settings);

        // Update settings form
        elements.defaultLanguage.value = settings.language || 'hu';
        elements.defaultVoice.value = settings.voice || 'ash';
        elements.defaultTemperature.value = settings.temperature || '0.8';
        elements.defaultTempValue.textContent = settings.temperature || '0.8';
        elements.defaultInstructions.value = settings.instructions || '';
    }
}

function applySettings(settings) {
    // Apply to realtime
    elements.rtLanguage.value = settings.language || 'hu';
    elements.rtVoice.value = settings.voice || 'ash';
    if (settings.instructions) {
        elements.rtInstructions.value = settings.instructions;
    }

    // Apply to transcription
    elements.sttLanguage.value = settings.language || 'hu';

    // Apply to TTS
    elements.ttsVoice.value = settings.voice || 'ash';
}

function resetSettings() {
    localStorage.removeItem('voiceAgentSettings');

    // Reset form to defaults
    elements.defaultLanguage.value = 'hu';
    elements.defaultVoice.value = 'ash';
    elements.defaultTemperature.value = '0.8';
    elements.defaultTempValue.textContent = '0.8';
    elements.defaultInstructions.value = 'You are a helpful assistant. Respond naturally and concisely in the user\'s language.';

    // Apply defaults
    applySettings({});

    showToast('Settings reset to defaults', 'success');
}

async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();

        elements.apiStatus.textContent = data.status === 'healthy' ? 'OK' : 'Error';
        elements.apiStatus.className = 'status-value ' + (data.status === 'healthy' ? 'ok' : 'error');

        elements.apiKeyStatus.textContent = data.api_key_configured ? 'Configured' : 'Not configured';
        elements.apiKeyStatus.className = 'status-value ' + (data.api_key_configured ? 'ok' : 'error');

    } catch (error) {
        elements.apiStatus.textContent = 'Unreachable';
        elements.apiStatus.className = 'status-value error';
        elements.apiKeyStatus.textContent = 'Unknown';
        elements.apiKeyStatus.className = 'status-value error';
    }
}

// ============ UTILITIES ============

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

function createWavBlob(pcmBuffer, sampleRate) {
    const numChannels = 1;
    const bytesPerSample = 2;
    const dataLength = pcmBuffer.byteLength;
    const headerLength = 44;
    const totalLength = headerLength + dataLength;

    const buffer = new ArrayBuffer(totalLength);
    const view = new DataView(buffer);

    // WAV header
    writeString(view, 0, 'RIFF');
    view.setUint32(4, totalLength - 8, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // fmt chunk size
    view.setUint16(20, 1, true); // audio format (PCM)
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numChannels * bytesPerSample, true); // byte rate
    view.setUint16(32, numChannels * bytesPerSample, true); // block align
    view.setUint16(34, bytesPerSample * 8, true); // bits per sample
    writeString(view, 36, 'data');
    view.setUint32(40, dataLength, true);

    // Copy PCM data
    const pcmView = new Uint8Array(pcmBuffer);
    const dataView = new Uint8Array(buffer, headerLength);
    dataView.set(pcmView);

    return new Blob([buffer], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}
