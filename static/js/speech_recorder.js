/* Speech Analysis View - Recording and Analysis */

var speechRecorder = {
    mediaRecorder: null,
    audioChunks: [],
    recordingStartTime: null,
    timerInterval: null,
    visualizerInterval: null,
    audioContext: null,
    analyser: null,
    webSpeechRecognition: null,
    transcribedText: '',
    currentInterim: '',
    transcribedWords: [],
    lastSessionAudioUrl: null
};

function initSpeechAnalysis() {
    var container = document.getElementById('view-speech-analysis');
    if (!container) {
        console.error('Speech analysis container not found');
        return;
    }
    
    // Check if Web Speech API is available
    var hasSpeechRecognition = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
    
    var html = '';
    html += '<div class="card" style="max-width: 800px; margin: 0 auto; text-align: center;">';
    html += '  <div id="recording-state">';
    html += '    <h2 style="margin-bottom: 16px;">Speech Analysis</h2>';
    html += '    <p class="text-secondary" style="margin-bottom: 24px;">Record your speech and get AI-powered analysis with personalized feedback</p>';
    
    if (!hasSpeechRecognition) {
        html += '    <div style="background: #FED7D7; color: #C53030; padding: 12px; border-radius: 8px; margin-bottom: 16px;">';
        html += '      <p>Your browser does not support speech recognition. Please use Chrome or Edge for best results.</p>';
        html += '    </div>';
    }
    
    html += '    <div id="waveform-container" style="height: 120px; background: rgba(79, 209, 197, 0.05); border-radius: 12px; margin-bottom: 24px; display: flex; align-items: center; justify-content: center; overflow: hidden; position: relative;">';
    html += '      <div id="visualizer-bars" style="display: flex; gap: 4px; align-items: center; height: 100%;"></div>';
    html += '      <div id="timer" style="position: absolute; top: 10px; right: 20px; font-weight: bold; color: #718096;">00:00</div>';
    html += '    </div>';
    html += '    <div id="live-transcript" style="display: none; text-align: left; padding: 16px; background: #F7FAFC; border-radius: 8px; margin-bottom: 16px; min-height: 60px; font-size: 1.1rem; color: #4A5568;"></div>';
    html += '    <div class="controls" style="display: flex; justify-content: center; gap: 16px; flex-wrap: wrap;">';
    html += '      <button id="btn-start" class="btn btn-primary btn-lg" style="display: inline-flex; align-items: center; gap: 8px;">';
    html += '        <i data-lucide="mic"></i> Start Recording';
    html += '      </button>';
    html += '      <button id="btn-upload" class="btn btn-outline btn-lg" style="display: inline-flex; align-items: center; gap: 8px;">';
    html += '        <i data-lucide="upload"></i> Upload Audio';
    html += '      </button>';
    html += '      <input type="file" id="audio-file-input" accept="audio/*" style="display: none;">';
    html += '      <button id="btn-stop" class="btn btn-lg" style="display: none; background-color: #E53E3E; color: white; align-items: center; gap: 8px;">';
    html += '        <i data-lucide="square"></i> Stop & Analyze';
    html += '      </button>';
    html += '      <button id="btn-cancel" class="btn btn-outline btn-lg" style="display: none;">Cancel</button>';
    html += '    </div>';
    html += '    <p id="status-msg" class="text-secondary" style="margin-top: 16px;">Click start and speak clearly into your microphone.</p>';
    html += '  </div>';
    html += '  <div id="processing-state" style="display: none;">';
    html += '    <div style="width: 60px; height: 60px; border: 5px solid #E2E8F0; border-top-color: #4FD1C5; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 24px;"></div>';
    html += '    <h2 id="processing-title">Analyzing Your Speech...</h2>';
    html += '    <p id="processing-subtitle" class="text-secondary">Our AI is processing your fluency metrics.</p>';
    html += '    <div style="max-width: 400px; margin: 24px auto 0;">';
    html += '      <div style="width: 100%; height: 8px; background: #E2E8F0; border-radius: 4px; overflow: hidden;">';
    html += '        <div id="progress-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #4FD1C5, #4299E1); transition: width 0.3s ease;"></div>';
    html += '      </div>';
    html += '    </div>';
    html += '  </div>';
    html += '  <div id="error-state" style="display: none;">';
    html += '    <div style="background: #FED7D7; color: #C53030; padding: 24px; border-radius: 12px; margin-bottom: 24px;">';
    html += '      <h3 style="margin-bottom: 8px;">Analysis Failed</h3>';
    html += '      <p id="error-message">Something went wrong. Please try again.</p>';
    html += '    </div>';
    html += '    <button class="btn btn-primary" onclick="initSpeechAnalysis()">Try Again</button>';
    html += '  </div>';
    html += '</div>';
    
    container.innerHTML = html;
    
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    setupSpeechRecordingHandlers();
}

function setupSpeechRecordingHandlers() {
    var btnStart = document.getElementById('btn-start');
    var btnStop = document.getElementById('btn-stop');
    var btnCancel = document.getElementById('btn-cancel');
    var visualizer = document.getElementById('visualizer-bars');
    var timerDisplay = document.getElementById('timer');
    var statusMsg = document.getElementById('status-msg');
    var liveTranscript = document.getElementById('live-transcript');
    
    if (!btnStart) {
        console.error('Start button not found');
        return;
    }
    
    // Initialize Web Speech Recognition
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        speechRecorder.webSpeechRecognition = new SpeechRecognition();
        speechRecorder.webSpeechRecognition.continuous = true;
        speechRecorder.webSpeechRecognition.interimResults = true;
        speechRecorder.webSpeechRecognition.lang = 'en-US';
        
        speechRecorder.webSpeechRecognition.onresult = function(event) {
            var finalTranscript = '';
            var interimTranscript = '';
            
            for (var i = event.resultIndex; i < event.results.length; i++) {
                var transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript + ' ';
                } else {
                    interimTranscript += transcript;
                }
            }
            
            if (finalTranscript) {
                speechRecorder.transcribedText += finalTranscript;
            }
            
            // Store interim text to be used if recording stops
            speechRecorder.currentInterim = interimTranscript;
            
            // Show live transcript
            if (liveTranscript) {
                liveTranscript.innerHTML = speechRecorder.transcribedText + 
                    '<span style="color: #A0AEC0;">' + interimTranscript + '</span>';
                // Auto scroll
                liveTranscript.scrollTop = liveTranscript.scrollHeight;
            }
        };
        
        speechRecorder.webSpeechRecognition.onerror = function(event) {
            console.error('Speech recognition error:', event.error);
        };
    }
    
    // Start recording button
    btnStart.addEventListener('click', function() {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function(stream) {
                // Reset transcription
                speechRecorder.transcribedText = '';
                speechRecorder.currentInterim = '';
                speechRecorder.transcribedWords = [];
                
                // Show live transcript area
                if (liveTranscript) {
                    liveTranscript.style.display = 'block';
                    liveTranscript.innerHTML = '<span style="color: #A0AEC0;">Listening...</span>';
                }
                
                // Start Web Speech Recognition
                if (speechRecorder.webSpeechRecognition) {
                    try {
                        speechRecorder.webSpeechRecognition.start();
                        console.log('Web Speech Recognition started');
                    } catch (e) {
                        console.error('Could not start speech recognition:', e);
                    }
                }
                
                // Setup audio visualization
                speechRecorder.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                speechRecorder.analyser = speechRecorder.audioContext.createAnalyser();
                var source = speechRecorder.audioContext.createMediaStreamSource(stream);
                source.connect(speechRecorder.analyser);
                speechRecorder.analyser.fftSize = 128;
                
                // Create visualizer bars
                visualizer.innerHTML = '';
                for (var i = 0; i < 40; i++) {
                    var bar = document.createElement('div');
                    bar.className = 'v-bar';
                    bar.style.cssText = 'width: 6px; height: 10px; background-color: #4FD1C5; border-radius: 3px; transition: height 0.05s ease;';
                    visualizer.appendChild(bar);
                }
                
                // Animate visualization
                var dataArray = new Uint8Array(speechRecorder.analyser.frequencyBinCount);
                speechRecorder.visualizerInterval = setInterval(function() {
                    speechRecorder.analyser.getByteFrequencyData(dataArray);
                    var bars = document.querySelectorAll('.v-bar');
                    bars.forEach(function(bar, i) {
                        var value = dataArray[i] || 0;
                        var height = Math.max(10, (value / 255) * 100);
                        bar.style.height = height + '%';
                    });
                }, 50);
                
                // Setup MediaRecorder - try different formats for better compatibility
                var mimeType = 'audio/webm';
                var fileExt = 'webm';
                
                // Prefer formats that convert better to MP3
                if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
                    mimeType = 'audio/webm;codecs=opus';
                    fileExt = 'webm';
                } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
                    mimeType = 'audio/ogg;codecs=opus';
                    fileExt = 'ogg';
                } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    mimeType = 'audio/mp4';
                    fileExt = 'mp4';
                } else if (MediaRecorder.isTypeSupported('audio/webm')) {
                    mimeType = 'audio/webm';
                    fileExt = 'webm';
                }
                
                console.log('Using recording format:', mimeType);
                speechRecorder.recordingMimeType = mimeType;
                speechRecorder.recordingExt = fileExt;
                
                speechRecorder.mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });
                speechRecorder.audioChunks = [];
                
                speechRecorder.mediaRecorder.ondataavailable = function(e) {
                    if (e.data.size > 0) {
                        speechRecorder.audioChunks.push(e.data);
                    }
                };
                
                speechRecorder.mediaRecorder.onstop = function() {
                    stream.getTracks().forEach(function(track) { track.stop(); });
                    if (speechRecorder.timerInterval) clearInterval(speechRecorder.timerInterval);
                    if (speechRecorder.visualizerInterval) clearInterval(speechRecorder.visualizerInterval);
                    if (speechRecorder.audioContext) speechRecorder.audioContext.close();
                    
                    if (speechRecorder.audioChunks.length > 0) {
                        var audioBlob = new Blob(speechRecorder.audioChunks, { type: speechRecorder.recordingMimeType || 'audio/webm' });
                        console.log('Recording complete:', audioBlob.size, 'bytes,', audioBlob.type);
                        processSpeechRecording(audioBlob, speechRecorder.recordingExt || 'webm');
                    }
                };
                
                // Start recording
                speechRecorder.mediaRecorder.start(1000);
                speechRecorder.recordingStartTime = Date.now();
                
                // Update UI
                btnStart.style.display = 'none';
                if (document.getElementById('btn-upload')) {
                    document.getElementById('btn-upload').style.display = 'none';
                }
                btnStop.style.display = 'inline-flex';
                btnCancel.style.display = 'inline-flex';
                statusMsg.innerHTML = '<span style="color: #E53E3E;">● Recording...</span> Speak clearly into your microphone';
                
                // Start timer
                speechRecorder.timerInterval = setInterval(function() {
                    var elapsed = Math.floor((Date.now() - speechRecorder.recordingStartTime) / 1000);
                    var m = Math.floor(elapsed / 60).toString().padStart(2, '0');
                    var s = (elapsed % 60).toString().padStart(2, '0');
                    timerDisplay.textContent = m + ':' + s;
                }, 1000);
            })
            .catch(function(err) {
                console.error('Microphone access error:', err);
                statusMsg.innerHTML = '<span style="color: #E53E3E;">Microphone access denied. Please allow microphone access and try again.</span>';
            });
    });
    
    // Stop recording button
    btnStop.addEventListener('click', function() {
        // Stop Web Speech API recognition
        if (speechRecorder.webSpeechRecognition) {
            try {
                speechRecorder.webSpeechRecognition.stop();
            } catch (e) {
                console.log('Recognition already stopped');
            }
        }
        
        if (speechRecorder.mediaRecorder && speechRecorder.mediaRecorder.state === 'recording') {
            speechRecorder.mediaRecorder.stop();
        }
    });
    
    // Cancel recording button
    btnCancel.addEventListener('click', function() {
        // Stop Web Speech API recognition
        if (speechRecorder.webSpeechRecognition) {
            try {
                speechRecorder.webSpeechRecognition.stop();
            } catch (e) {
                console.log('Recognition already stopped');
            }
        }
        speechRecorder.transcribedText = ''; // Clear any transcription
        
        if (speechRecorder.mediaRecorder && speechRecorder.mediaRecorder.state === 'recording') {
            speechRecorder.audioChunks = [];
            speechRecorder.mediaRecorder.stop();
        }
        if (speechRecorder.timerInterval) clearInterval(speechRecorder.timerInterval);
        if (speechRecorder.visualizerInterval) clearInterval(speechRecorder.visualizerInterval);
        initSpeechAnalysis();
    });
    
    // Upload audio button
    var btnUpload = document.getElementById('btn-upload');
    var audioFileInput = document.getElementById('audio-file-input');
    
    if (btnUpload && audioFileInput) {
        btnUpload.addEventListener('click', function() {
            audioFileInput.click();
        });
        
        audioFileInput.addEventListener('change', function(e) {
            var file = e.target.files[0];
            if (file) {
                console.log('Audio file selected:', file.name, file.type, file.size);
                statusMsg.innerHTML = '<span style="color: #4299E1;">Processing uploaded file: ' + file.name + '</span>';
                processSpeechRecording(file);
            }
        });
    }
}

function processSpeechRecording(audioBlob, fileExt) {
    fileExt = fileExt || 'webm';
    var recordingState = document.getElementById('recording-state');
    var processingState = document.getElementById('processing-state');
    var errorState = document.getElementById('error-state');
    var progressBar = document.getElementById('progress-bar');
    var processingTitle = document.getElementById('processing-title');
    var processingSubtitle = document.getElementById('processing-subtitle');
    
    // Show processing state
    recordingState.style.display = 'none';
    processingState.style.display = 'block';
    
    // Check for browser transcription (stored in transcribedText)
    // Combine finalized text with any remaining interim text
    var fullTranscription = speechRecorder.transcribedText || '';
    if (speechRecorder.currentInterim) {
        fullTranscription += (fullTranscription ? ' ' : '') + speechRecorder.currentInterim;
    }
    
    var browserTranscription = fullTranscription.trim();
    var hasBrowserTranscription = browserTranscription.length > 0;
    
    console.log('Browser transcription available:', hasBrowserTranscription, browserTranscription);
    
    var titles = hasBrowserTranscription ? 
        ['Processing...', 'Analyzing Patterns...', 'Generating Report...', 'Complete!'] :
        ['Uploading Audio...', 'Transcribing Speech...', 'Analyzing Patterns...', 'Generating Report...'];
    var subtitles = hasBrowserTranscription ?
        [
            'Using browser transcription...',
            'AI is detecting stuttering patterns...',
            'Preparing your personalized feedback...',
            'Analysis ready!'
        ] :
        [
            'Sending your recording to our servers...',
            'Converting your speech to text with ElevenLabs...',
            'AI is detecting stuttering patterns...',
            'Preparing your personalized feedback...'
        ];
    
    function updateStep(stepIndex) {
        if (stepIndex >= titles.length) return;
        processingTitle.textContent = titles[stepIndex];
        processingSubtitle.textContent = subtitles[stepIndex];
        progressBar.style.width = ((stepIndex + 1) * 25) + '%';
    }
    
    updateStep(0);
    
    // Create form data
    var formData = new FormData();

    // Keep a local URL for session replay in result screen
    if (speechRecorder.lastSessionAudioUrl) {
        try { URL.revokeObjectURL(speechRecorder.lastSessionAudioUrl); } catch (e) {}
        speechRecorder.lastSessionAudioUrl = null;
    }
    try {
        speechRecorder.lastSessionAudioUrl = URL.createObjectURL(audioBlob);
    } catch (e) {
        console.warn('Could not create session audio URL:', e);
    }
    
    // Handle both Blob (recorded) and File (uploaded) objects
    if (audioBlob instanceof File) {
        formData.append('audio_file', audioBlob, audioBlob.name);
    } else {
        var filename = 'recording.' + fileExt;
        console.log('Uploading recorded audio as:', filename, 'size:', audioBlob.size);
        formData.append('audio_file', audioBlob, filename);
    }
    
    // Include browser transcription if available
    if (hasBrowserTranscription) {
        formData.append('browser_transcription', browserTranscription);
        console.log('Sending browser transcription:', browserTranscription);
    }
    
    // Clear transcription for next recording
    speechRecorder.transcribedText = '';
    
    // Get CSRF token
    var csrfToken = '';
    var csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput) {
        csrfToken = csrfInput.value;
    } else {
        var cookies = document.cookie.split('; ');
        for (var i = 0; i < cookies.length; i++) {
            if (cookies[i].startsWith('csrftoken=')) {
                csrfToken = cookies[i].split('=')[1];
                break;
            }
        }
    }
    
    updateStep(1);
    
    // Send to API
    fetch('/api/transcribe/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        },
        body: formData
    })
    .then(function(response) {
        updateStep(2);
        if (!response.ok) {
            throw new Error('Server error: ' + response.status);
        }
        return response.json();
    })
    .then(function(result) {
        if (!result.success) {
            throw new Error(result.error || 'Analysis failed');
        }
        updateStep(3);
        setTimeout(function() {
            showSpeechResults(result, {
                audioUrl: speechRecorder.lastSessionAudioUrl
            });
        }, 500);
    })
    .catch(function(error) {
        console.error('Processing error:', error);
        processingState.style.display = 'none';
        errorState.style.display = 'block';
        document.getElementById('error-message').textContent = error.message || 'Failed to analyze speech. Please try again.';
    });
}

function showSpeechResults(data, sessionMeta) {
    var container = document.getElementById('view-speech-analysis');

    ensureReplayStyles();

    var parsedAnalysis = normalizeAnalysisPayload(data.analysis);
    var transcriptText = (data.transcript || '').trim();
    var replayWords = buildReplayWords(data, transcriptText);
    var flaggedWords = mergeFlaggedWords(data.flagged_words || [], replayWords);

    var fluencyScore = parsedAnalysis.fluencyScore;
    var stutteringType = parsedAnalysis.fluencyRating;
    var tips = parsedAnalysis.tips;
    var summary = parsedAnalysis.summary;
    var dysfluencies = parsedAnalysis.dysfluencies;
    
    var transcriptHtml = '';
    if (replayWords.length > 0) {
        transcriptHtml = replayWords.map(function(w, i) {
            var word = w.word || '';
            var isFlagged = flaggedWords.some(function(fw) { return fw.index === i || fw.word === word; });
            if (isFlagged) {
                return '<span style="background-color: #FED7D7; border-bottom: 2px solid #E53E3E; padding: 2px 4px; border-radius: 4px;">' + word + '</span>';
            }
            return '<span>' + word + '</span>';
        }).join(' ');
    } else {
        transcriptHtml = transcriptText || 'No transcription available';
    }
    
    var tipsHtml = '';
    if (tips.length > 0) {
        tips.forEach(function(tip) {
            tipsHtml += '<div style="display: flex; gap: 12px; align-items: flex-start; padding: 12px; background: #F0FFF4; border-radius: 8px; margin-bottom: 8px;">';
            tipsHtml += '<i data-lucide="lightbulb" style="color: #38A169; width: 20px; flex-shrink: 0;"></i>';
            tipsHtml += '<p style="margin: 0; font-size: 0.95rem;">' + tip + '</p>';
            tipsHtml += '</div>';
        });
    }
    
    var scoreColor = fluencyScore >= 80 ? '#38A169' : (fluencyScore >= 60 ? '#D69E2E' : '#E53E3E');
    var typeBg = stutteringType === 'Mild' ? '#C6F6D5' : (stutteringType === 'Moderate' ? '#FEFCBF' : '#FED7D7');
    var typeColor = stutteringType === 'Mild' ? '#22543D' : (stutteringType === 'Moderate' ? '#744210' : '#C53030');
    
    var html = '';
    html += '<div style="display: grid; grid-template-columns: 1fr 2fr; gap: 24px;">';
    
    // Left column
    html += '<div style="display: flex; flex-direction: column; gap: 24px;">';
    
    // Fluency Score card
    html += '<div class="card" style="text-align: center;">';
    html += '<h3>Fluency Score</h3>';
    html += '<div style="position: relative; width: 150px; height: 150px; margin: 16px auto;">';
    html += '<svg viewBox="0 0 36 36" style="transform: rotate(-90deg); width: 100%; height: 100%;">';
    html += '<path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#E2E8F0" stroke-width="3" />';
    html += '<path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="' + scoreColor + '" stroke-width="3" stroke-dasharray="' + fluencyScore + ', 100" />';
    html += '</svg>';
    html += '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 2rem; font-weight: 800; color: #2C5282;">' + fluencyScore + '%</div>';
    html += '</div>';
    html += '<p class="text-secondary">' + (summary || 'Analysis complete!') + '</p>';
    html += '</div>';
    
    // Stuttering Type card
    html += '<div class="card">';
    html += '<h3>Stuttering Type</h3>';
    html += '<div style="text-align: center; padding: 16px 0;">';
    html += '<span style="font-size: 1.1rem; padding: 10px 20px; background: ' + typeBg + '; color: ' + typeColor + '; border-radius: 20px;">' + stutteringType + '</span>';
    html += '</div></div>';
    
    // Dysfluency Breakdown card
    html += '<div class="card">';
    html += '<h3>Dysfluency Breakdown</h3>';
    html += '<div style="margin-top: 16px;">';
    html += '<div style="display: flex; justify-content: space-between; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #E2E8F0;"><span>Blocks</span><span style="font-weight: 700; color: #2C5282;">' + (dysfluencies.blocks || 0) + '</span></div>';
    html += '<div style="display: flex; justify-content: space-between; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #E2E8F0;"><span>Prolongations</span><span style="font-weight: 700; color: #2C5282;">' + (dysfluencies.prolongations || 0) + '</span></div>';
    html += '<div style="display: flex; justify-content: space-between; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #E2E8F0;"><span>Repetitions</span><span style="font-weight: 700; color: #2C5282;">' + (dysfluencies.repetitions || 0) + '</span></div>';
    html += '<div style="display: flex; justify-content: space-between;"><span>Interjections</span><span style="font-weight: 700; color: #2C5282;">' + (dysfluencies.interjections || 0) + '</span></div>';
    html += '</div></div>';
    
    // New Recording button
    html += '<button class="btn btn-primary" onclick="initSpeechAnalysis()" style="width: 100%;"><i data-lucide="mic"></i> New Recording</button>';
    html += '</div>';
    
    // Right column
    html += '<div style="display: flex; flex-direction: column; gap: 24px;">';
    
    // Transcript card
    html += '<div class="card">';
    html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">';
    html += '<h3>Transcript</h3>';
    var wordCount = replayWords.length || (transcriptText ? transcriptText.split(/\s+/).filter(Boolean).length : 0);
    html += '<span class="badge badge-easy">' + wordCount + ' words</span>';
    html += '</div>';
    html += '<div style="font-size: 1.15rem; line-height: 2; color: #4A5568; max-height: 300px; overflow-y: auto; padding: 16px; background: #F7FAFC; border-radius: 8px;">' + transcriptHtml + '</div>';
    html += '<p style="margin-top: 16px; font-size: 0.85rem; color: #A0AEC0;"><i data-lucide="info" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle;"></i> Highlighted words indicate potential dysfluencies</p>';
    html += '</div>';

    // Session replay card with synced transcript
    html += '<div class="card">';
    html += '<h3 style="margin-bottom: 12px;">Session Replay & Word Highlighting</h3>';
    html += '<audio id="session-replay-audio" controls style="width: 100%; margin-bottom: 12px;"></audio>';
    html += '<div id="session-replay-timeline" style="font-size: 1rem; line-height: 2; max-height: 220px; overflow-y: auto; padding: 12px; background: #F7FAFC; border-radius: 8px; border: 1px solid #E2E8F0;"></div>';
    html += '<p style="margin-top: 10px; font-size: 0.85rem; color: #718096;">Click any word to jump to that part. Red tags = potential stutter events.</p>';
    html += '</div>';

    // AI suggestion card (Groq)
    html += '<div class="card">';
    html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">';
    html += '<h3 style="margin-bottom: 0;">AI Suggestion</h3>';
    html += '<span class="badge" style="background: #E6FFFA; color: #22543D;">Powered by Groq</span>';
    html += '</div>';
    html += '<div id="ai-suggestion-content" style="padding: 12px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; color: #4A5568;">Generating personalized guidance...</div>';
    html += '</div>';
    
    // Tips card
    html += '<div class="card">';
    html += '<h3 style="margin-bottom: 16px;">Personalized Tips</h3>';
    html += tipsHtml || '<p class="text-secondary">No specific tips for this session.</p>';
    html += '</div>';
    
    html += '</div></div>';
    
    container.innerHTML = html;
    
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    setupSessionReplay((sessionMeta && sessionMeta.audioUrl) || '', replayWords, flaggedWords);
    requestAiSuggestion(transcriptText, parsedAnalysis);
}

function normalizeAnalysisPayload(rawAnalysis) {
    var parsed = rawAnalysis;
    if (typeof parsed === 'string') {
        try {
            parsed = JSON.parse(parsed);
        } catch (e) {
            parsed = {};
        }
    }
    parsed = parsed || {};

    var fluencyScore = Number(parsed.overall_score || parsed.fluency_score || 75);
    if (isNaN(fluencyScore)) fluencyScore = 75;
    fluencyScore = Math.max(0, Math.min(100, Math.round(fluencyScore)));

    var fluencyRating = parsed.fluency_rating || parsed.stuttering_type || 'Mild';
    var tips = parsed.recommendations || parsed.tips || [];
    if (!Array.isArray(tips)) tips = [];
    var summary = parsed.detailed_analysis || parsed.summary || '';

    var dys = {
        blocks: 0,
        prolongations: 0,
        repetitions: 0,
        interjections: 0
    };

    if (Array.isArray(parsed.stuttering_types)) {
        parsed.stuttering_types.forEach(function (t) {
            var name = String((t && t.name) || '').toLowerCase();
            var count = Number((t && t.count) || 0);
            if (isNaN(count)) count = 0;
            if (name.indexOf('block') !== -1) dys.blocks = count;
            else if (name.indexOf('prolong') !== -1) dys.prolongations = count;
            else if (name.indexOf('repetition') !== -1 || name.indexOf('repeat') !== -1) dys.repetitions = count;
            else if (name.indexOf('interjection') !== -1 || name.indexOf('filler') !== -1) dys.interjections = count;
        });
    } else if (parsed.dysfluencies && typeof parsed.dysfluencies === 'object') {
        dys.blocks = Number(parsed.dysfluencies.blocks || 0) || 0;
        dys.prolongations = Number(parsed.dysfluencies.prolongations || 0) || 0;
        dys.repetitions = Number(parsed.dysfluencies.repetitions || 0) || 0;
        dys.interjections = Number(parsed.dysfluencies.interjections || 0) || 0;
    }

    return {
        fluencyScore: fluencyScore,
        fluencyRating: fluencyRating,
        tips: tips,
        summary: summary,
        dysfluencies: dys
    };
}

function buildReplayWords(data, transcriptText) {
    var result = data.result || {};
    var words = [];

    function normalizeWordObject(w, idx) {
        if (typeof w === 'string') {
            return { index: idx, word: w, start: null, end: null };
        }
        var word = (w.word || w.text || '').toString().trim();
        var start = w.start || w.start_time || w.start_seconds || w.startTime || null;
        var end = w.end || w.end_time || w.end_seconds || w.endTime || null;
        return { index: idx, word: word, start: start, end: end };
    }

    if (Array.isArray(result.words)) {
        words = result.words.map(normalizeWordObject).filter(function (w) { return !!w.word; });
    }

    if (!words.length && result.resultObject && Array.isArray(result.resultObject.words)) {
        words = result.resultObject.words.map(normalizeWordObject).filter(function (w) { return !!w.word; });
    }

    if (!words.length && transcriptText) {
        var plainWords = transcriptText.split(/\s+/).filter(Boolean);
        words = plainWords.map(function (w, idx) {
            return { index: idx, word: w, start: null, end: null };
        });
    }

    return words;
}

function mergeFlaggedWords(serverFlags, words) {
    var flagged = Array.isArray(serverFlags) ? serverFlags.slice() : [];
    var heuristic = detectPotentialStutterWords(words);
    heuristic.forEach(function (h) {
        var exists = flagged.some(function (f) { return f.index === h.index || (f.word && f.word === h.word); });
        if (!exists) flagged.push(h);
    });
    return flagged;
}

function detectPotentialStutterWords(words) {
    var out = [];
    if (!Array.isArray(words) || !words.length) return out;

    var fillers = { 'um': true, 'uh': true, 'er': true, 'ah': true, 'like': true };
    for (var i = 0; i < words.length; i++) {
        var current = (words[i].word || '').toLowerCase().replace(/[^a-z']/g, '');
        var prev = i > 0 ? (words[i - 1].word || '').toLowerCase().replace(/[^a-z']/g, '') : '';

        if (!current) continue;
        if (fillers[current]) {
            out.push({ index: i, word: words[i].word });
            continue;
        }
        if (prev && current === prev) {
            out.push({ index: i, word: words[i].word });
            out.push({ index: i - 1, word: words[i - 1].word });
            continue;
        }
        if (/([a-z])\1\1/i.test(current)) {
            out.push({ index: i, word: words[i].word });
        }
    }
    return out;
}

function setupSessionReplay(audioUrl, words, flaggedWords) {
    var audioEl = document.getElementById('session-replay-audio');
    var timelineEl = document.getElementById('session-replay-timeline');
    if (!audioEl || !timelineEl) return;

    if (!audioUrl) {
        timelineEl.innerHTML = '<span style="color:#A0AEC0;">Replay unavailable for this session.</span>';
        return;
    }

    audioEl.src = audioUrl;

    var flaggedSet = {};
    (flaggedWords || []).forEach(function (f) {
        if (typeof f.index === 'number') flaggedSet[f.index] = true;
    });

    var wordHtml = words.map(function (w, idx) {
        var cls = 'replay-word';
        if (flaggedSet[idx]) cls += ' stutter';
        return '<span class="' + cls + '" data-word-idx="' + idx + '">' + escapeHtml(w.word || '') + '</span>';
    }).join(' ');
    timelineEl.innerHTML = wordHtml || '<span style="color:#A0AEC0;">No transcript timing available.</span>';

    var spans = timelineEl.querySelectorAll('.replay-word');
    if (!spans.length) return;

    function ensureEstimatedTimingIfMissing() {
        if (!words.length) return;
        var hasTiming = words.some(function (w) {
            return w.start != null && w.end != null && !isNaN(Number(w.start)) && !isNaN(Number(w.end));
        });
        if (hasTiming) return;

        var duration = isFinite(audioEl.duration) ? audioEl.duration : 0;
        if (!duration || duration <= 0) return;

        var perWord = duration / Math.max(words.length, 1);
        for (var i = 0; i < words.length; i++) {
            words[i].start = i * perWord;
            words[i].end = (i + 1) * perWord;
        }
    }

    function getActiveIndex(currentTime) {
        for (var i = 0; i < words.length; i++) {
            var start = Number(words[i].start);
            var end = Number(words[i].end);
            if (!isNaN(start) && !isNaN(end) && currentTime >= start && currentTime <= end) {
                return i;
            }
        }

        // fallback when precise timings missing
        if (isFinite(audioEl.duration) && audioEl.duration > 0 && words.length) {
            var idx = Math.floor((currentTime / audioEl.duration) * words.length);
            return Math.max(0, Math.min(words.length - 1, idx));
        }
        return -1;
    }

    function highlightAt(currentTime) {
        var idx = getActiveIndex(currentTime);
        spans.forEach(function (s, i) {
            if (i === idx) s.classList.add('active');
            else s.classList.remove('active');
        });

        if (idx >= 0 && spans[idx]) {
            spans[idx].scrollIntoView({ block: 'nearest', inline: 'nearest' });
        }
    }

    audioEl.addEventListener('loadedmetadata', ensureEstimatedTimingIfMissing);
    audioEl.addEventListener('timeupdate', function () {
        highlightAt(audioEl.currentTime || 0);
    });

    spans.forEach(function (span) {
        span.addEventListener('click', function () {
            var idx = Number(span.getAttribute('data-word-idx'));
            if (isNaN(idx) || idx < 0 || idx >= words.length) return;
            var seekTo = Number(words[idx].start);
            if (isNaN(seekTo)) return;
            audioEl.currentTime = Math.max(0, seekTo);
            audioEl.play();
        });
    });
}

function requestAiSuggestion(transcriptText, analysisObj) {
    var target = document.getElementById('ai-suggestion-content');
    if (!target) return;

    if (!transcriptText) {
        target.textContent = 'No transcript available to generate suggestions yet.';
        return;
    }

    var csrfToken = '';
    var csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfInput) {
        csrfToken = csrfInput.value;
    } else {
        var cookies = document.cookie.split('; ');
        for (var i = 0; i < cookies.length; i++) {
            if (cookies[i].startsWith('csrftoken=')) {
                csrfToken = cookies[i].split('=')[1];
                break;
            }
        }
    }

    var msg = 'Give practical speech-therapy suggestions for this session. ' +
        'Keep it short with 4 bullet points and 1 one-line daily routine. ' +
        'Fluency score: ' + analysisObj.fluencyScore + '. ' +
        'Fluency rating: ' + analysisObj.fluencyRating + '. ' +
        'Transcript: "' + transcriptText.slice(0, 1800) + '"';

    fetch('/api/ai-chat/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            message: msg,
            history: []
        })
    })
    .then(function (response) {
        if (!response.ok) {
            throw new Error('Server error: ' + response.status);
        }
        return response.json();
    })
    .then(function (res) {
        if (!res.success) {
            throw new Error(res.error || 'Could not generate suggestion.');
        }
        target.innerHTML = '<div style="white-space: pre-wrap; line-height: 1.6;">' + escapeHtml(res.reply || '') + '</div>';
    })
    .catch(function (err) {
        target.innerHTML = '<span style="color:#C53030;">Failed to generate AI suggestion: ' + escapeHtml(err.message || 'Unknown error') + '</span>';
    });
}

function ensureReplayStyles() {
    if (document.getElementById('replay-word-styles')) return;
    var style = document.createElement('style');
    style.id = 'replay-word-styles';
    style.textContent = '' +
        '.replay-word{padding:2px 5px;border-radius:6px;cursor:pointer;transition:all .15s ease;}' +
        '.replay-word:hover{background:#EBF8FF;}' +
        '.replay-word.active{background:#2C5282;color:#fff;}' +
        '.replay-word.stutter{background:#FFF5F5;border-bottom:2px solid #E53E3E;color:#742A2A;}';
    document.head.appendChild(style);
}

function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
