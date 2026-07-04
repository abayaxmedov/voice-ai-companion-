const API_BASE = "http://127.0.0.1:8765";

const runtimePill = document.querySelector("#runtime-pill");
const runtimeText = document.querySelector("#runtime-text");
const providersEl = document.querySelector("#providers");
const sendButton = document.querySelector("#send-turn");
const micButton = document.querySelector("#mic-button");
const refreshButton = document.querySelector("#refresh-button");
const utteranceEl = document.querySelector("#utterance");
const spokenResponseEl = document.querySelector("#spoken-response");
const turnMetaEl = document.querySelector("#turn-meta");
const assistantAudioEl = document.querySelector("#assistant-audio");
const avatarIdEl = document.querySelector("#avatar-id");
const avatarMoodEl = document.querySelector("#avatar-mood");
const avatarAudioEl = document.querySelector("#avatar-audio");
const avatarVisemesEl = document.querySelector("#avatar-visemes");
const bridgeStatusEl = document.querySelector("#bridge-status");
const bridgeStreamEl = document.querySelector("#bridge-stream");
const bridgeQueueEl = document.querySelector("#bridge-queue");
const bridgeEventEl = document.querySelector("#bridge-event");
const speakingRing = document.querySelector("#speaking-ring");
const pixelStream = document.querySelector("#pixel-stream");
const streamPlaceholder = document.querySelector("#stream-placeholder");
const canvas = document.querySelector("#avatar-canvas");
const ctx = canvas.getContext("2d");

let avatarMood = "idle";
let tick = 0;
let mediaRecorder = null;
let recordingChunks = [];
let isRecording = false;
let voiceMode = "pipeline";
let humeEviReady = false;
let humeSocket = null;
let humeAudioStream = null;
let humeMuted = false;
let humeSessionActive = false;
let humeTurnTimeout = null;
let humeInputFinished = false;
let humeUserSpeechSeen = false;
let humeFinalUserMessageSeen = false;
let humeAssistantResponseStarted = false;
let humeResponseAudioSeen = false;
let eviAudioQueue = [];
let eviAudioPlaying = false;
let currentEviAudio = null;

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message || payload.error || "API error");
  }
  return payload;
}

async function refreshHealth() {
  try {
    const [health, catalog] = await Promise.all([
      api("/health"),
      api("/providers/catalog").catch(() => null),
    ]);
    runtimePill.classList.toggle("ready", health.ready);
    runtimePill.classList.toggle("error", !health.ready);
    voiceMode = catalog?.voice_mode || health.voice_mode || "pipeline";
    humeEviReady = Boolean(catalog?.hume_evi?.ready || health.hume_evi?.ready);
    runtimeText.textContent = health.ready ? `Ready · ${health.state} · ${voiceMode}` : "Backend error";
    renderProviders(catalog?.providers || health.providers, catalog?.selected || health.selected_providers || {});
    renderBridge(health.avatar_bridge);
  } catch (error) {
    runtimePill.classList.remove("ready");
    runtimePill.classList.add("error");
    runtimeText.textContent = "Backend topilmadi";
    providersEl.innerHTML = "";
    spokenResponseEl.textContent = "Backend server ishlamayapti yoki port boshqa.";
    turnMetaEl.textContent = error.message;
  }
}

function renderProviders(providers, selectedProviders = {}) {
  providersEl.innerHTML = "";
  for (const provider of providers) {
    const isSelected = selectedProviders[provider.kind] === provider.provider_id;
    const item = document.createElement("div");
    item.className = `provider${isSelected ? " selected" : ""}`;
    if (provider.message) {
      item.title = provider.message;
    }
    item.innerHTML = `
      <div>
        <strong>${provider.provider_id}</strong>
        <span>${provider.kind} · ${provider.status}${isSelected ? " · selected" : ""}</span>
      </div>
      <div class="badge${provider.ready ? "" : " off"}">${provider.ready ? "READY" : "OFF"}</div>
    `;
    providersEl.appendChild(item);
  }
}

function renderBridge(bridge) {
  if (!bridge) {
    bridgeStatusEl.textContent = "-";
    bridgeStreamEl.textContent = "-";
    bridgeQueueEl.textContent = "-";
    bridgeEventEl.textContent = "-";
    return;
  }
  bridgeStatusEl.textContent = bridge.ready ? `connected · ${bridge.avatar_id || "unknown"}` : bridge.status;
  const streamUrl = bridge.player_url || bridge.url;
  bridgeStreamEl.textContent = bridge.stream_ready ? streamUrl : "Unreal stream not ready";
  bridgeQueueEl.textContent = bridge.queued_events ?? "-";
  bridgeEventEl.textContent = bridge.message || "avatar.play queue orqali yuboriladi";

  const shouldShowStream = Boolean(bridge.ready && bridge.stream_ready && streamUrl);
  pixelStream.hidden = !shouldShowStream;
  canvas.hidden = shouldShowStream;
  streamPlaceholder.hidden = shouldShowStream;
  if (shouldShowStream && pixelStream.src !== streamUrl) {
    pixelStream.src = streamUrl;
  }
}

async function sendTurn(audioRef = null) {
  const transcript = utteranceEl.value.trim();
  if (!transcript && !audioRef) return;
  const transcriptOverride = audioRef ? null : transcript || null;

  setBusy(true);
  resetAssistantAudio();
  avatarMood = "thinking";
  spokenResponseEl.textContent = "O'ylayapman...";
  turnMetaEl.textContent = audioRef ? "Audio voice turn yuborildi" : "Voice turn yuborildi";

  try {
    const body = {
      session_id: "front-session",
      agent_id: "default",
      audio_ref: audioRef,
      transcript_override: transcriptOverride,
    };
    const result = await api("/voice/turn", {
      method: "POST",
      body: JSON.stringify(body),
    });

    avatarMood = result.avatar_job.mood || "thoughtful";
    utteranceEl.value = result.transcript.text || transcript;
    spokenResponseEl.textContent = result.llm_response.response;
    const emotion = result.analysis.emotion ? ` · ${result.analysis.emotion}` : "";
    turnMetaEl.textContent = `${result.analysis.provider_id}${emotion} · ${result.tts.provider_id} · ${result.tts.duration_ms}ms`;
    avatarIdEl.textContent = result.avatar_job.avatar_id;
    avatarMoodEl.textContent = result.avatar_job.mood;
    avatarAudioEl.textContent = result.avatar_job.audio_ref;
    avatarVisemesEl.textContent = String(result.avatar_job.visemes.length);
    playAssistantAudio(result.avatar_job.audio_ref || result.tts.audio_ref);
    speakingRing.classList.add("active");
    window.setTimeout(() => speakingRing.classList.remove("active"), 2400);
  } catch (error) {
    avatarMood = "error";
    spokenResponseEl.textContent = "Voice turn bajarilmadi.";
    turnMetaEl.textContent = error.message;
  } finally {
    setBusy(false);
    refreshHealth();
  }
}

function resetAssistantAudio() {
  assistantAudioEl.pause();
  assistantAudioEl.removeAttribute("src");
  assistantAudioEl.load();
  assistantAudioEl.hidden = true;
}

async function playAssistantAudio(audioRef) {
  const audioUrl = resolveAudioUrl(audioRef);
  if (!audioUrl) {
    return;
  }
  assistantAudioEl.src = audioUrl;
  assistantAudioEl.hidden = false;
  try {
    await assistantAudioEl.play();
  } catch (error) {
    turnMetaEl.textContent = `${turnMetaEl.textContent} · audio ready`;
  }
}

function resolveAudioUrl(audioRef) {
  if (!audioRef || audioRef.startsWith("mock://")) {
    return "";
  }
  if (audioRef.startsWith("http://") || audioRef.startsWith("https://")) {
    return audioRef;
  }
  if (audioRef.startsWith("/")) {
    return `${API_BASE}${audioRef}`;
  }
  if (audioRef.startsWith("file://")) {
    const filename = audioRef.split("/").pop();
    return filename ? `${API_BASE}/audio/cache/${encodeURIComponent(filename)}` : "";
  }
  return "";
}

async function toggleRecording() {
  if (voiceMode === "hume_evi" && humeEviReady) {
    await toggleHumeEviTurn();
    return;
  }
  if (isRecording && mediaRecorder) {
    mediaRecorder.stop();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    spokenResponseEl.textContent = "Bu browser mic recordingni qo'llamayapti.";
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordingChunks = [];
    const mimeType = preferredMimeType();
    mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) {
        recordingChunks.push(event.data);
      }
    });
    mediaRecorder.addEventListener("stop", async () => {
      isRecording = false;
      micButton.classList.remove("recording");
      micButton.title = "Voice yozishni boshlash";
      stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(recordingChunks, { type: mediaRecorder.mimeType || "audio/webm" });
      mediaRecorder = null;
      if (!blob.size) {
        turnMetaEl.textContent = "Audio yozilmadi";
        return;
      }
      await uploadAndSendAudio(blob);
    });
    mediaRecorder.start();
    isRecording = true;
    micButton.classList.add("recording");
    micButton.title = "Voice yozishni to'xtatish";
    spokenResponseEl.textContent = "Tinglayapman...";
    turnMetaEl.textContent = "Recording";
  } catch (error) {
    isRecording = false;
    micButton.classList.remove("recording");
    spokenResponseEl.textContent = "Mic permission yoki recording xatosi.";
    turnMetaEl.textContent = error.message;
  }
}

async function toggleHumeEviTurn() {
  if (humeSessionActive) {
    if (!humeMuted) {
      humeMuted = true;
      humeInputFinished = true;
      isRecording = false;
      micButton.classList.remove("recording");
      micButton.title = "Hume javobini kutish";
      spokenResponseEl.textContent = "Hume EVI javobini kutyapman...";
      turnMetaEl.textContent = "Speech-to-speech processing";
      resetHumeTurnTimeout("Hume EVI javobi kutilgan vaqtdan oshdi.", 45000);
    }
    return;
  }

  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    spokenResponseEl.textContent = "Bu browser mic recordingni qo'llamayapti.";
    return;
  }

  resetAssistantAudio();
  stopEviAudioQueue();
  setBusy(true);
  micButton.disabled = false;
  avatarMood = "listening";
  spokenResponseEl.textContent = "Hume EVI tinglayapti...";
  turnMetaEl.textContent = "Speech-to-speech ulanyapti";

  const socketUrl = `${API_BASE.replace(/^http/, "ws")}/voice/hume-evi/ws`;
  humeSocket = new WebSocket(socketUrl);
  humeSessionActive = true;
  humeMuted = false;
  humeInputFinished = false;
  humeUserSpeechSeen = false;
  humeFinalUserMessageSeen = false;
  humeAssistantResponseStarted = false;
  humeResponseAudioSeen = false;

  humeSocket.addEventListener("open", startHumeAudioCapture);
  humeSocket.addEventListener("message", handleHumeMessage);
  humeSocket.addEventListener("error", () => {
    finishHumeTurn("Hume EVI socket xatosi.", true);
  });
  humeSocket.addEventListener("close", () => {
    if (humeSessionActive) {
      finishHumeTurn("Hume EVI ulanishi yopildi.", true);
    }
  });
}

async function startHumeAudioCapture() {
  try {
    humeAudioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const mimeType = preferredMimeType();
    mediaRecorder = mimeType ? new MediaRecorder(humeAudioStream, { mimeType }) : new MediaRecorder(humeAudioStream);
    const activeRecorder = mediaRecorder;
    activeRecorder.addEventListener("dataavailable", async (event) => {
      if (!event.data.size || !humeSocket || humeSocket.readyState !== WebSocket.OPEN) {
        return;
      }
      const chunk = humeMuted ? new Blob([new Uint8Array(event.data.size)], { type: activeRecorder.mimeType }) : event.data;
      const data = await blobToBase64(chunk);
      humeSocket.send(JSON.stringify({ type: "audio_input", data }));
    });
    activeRecorder.start(100);
    isRecording = true;
    micButton.classList.add("recording");
    micButton.title = "Gapirishni yakunlash";
    turnMetaEl.textContent = "Hume EVI connected · gapiring";
    resetHumeTurnTimeout("Hume EVI javobi kutilgan vaqtdan oshdi.", 60000);
  } catch (error) {
    finishHumeTurn(`Mic permission yoki recording xatosi: ${error.message}`, true);
  }
}

function handleHumeMessage(event) {
  let message;
  try {
    message = JSON.parse(event.data);
  } catch (error) {
    return;
  }

  switch (message.type) {
    case "proxy_status":
      turnMetaEl.textContent = "Hume EVI connected";
      break;
    case "user_message":
      {
        const userText = message.message?.content || "";
        if (userText) {
          humeUserSpeechSeen = true;
          if (!message.interim) {
            humeFinalUserMessageSeen = true;
            turnMetaEl.textContent = `Siz: ${userText}`;
          } else {
            turnMetaEl.textContent = `Eshitildi: ${userText}`;
          }
        }
      }
      break;
    case "assistant_message": {
      const assistantText = message.message?.content || "";
      if (isHumeUserResponseReady()) {
        humeAssistantResponseStarted = true;
        if (assistantText) {
          spokenResponseEl.textContent = assistantText;
        }
        avatarMood = "thoughtful";
      } else if (assistantText) {
        turnMetaEl.textContent = "Hume EVI tayyor · gapiring";
      }
      break;
    }
    case "audio_output":
      if (message.data && (isHumeUserResponseReady() || humeAssistantResponseStarted)) {
        humeResponseAudioSeen = true;
        queueEviAudio(message.data);
        speakingRing.classList.add("active");
      }
      break;
    case "assistant_end":
      if (humeAssistantResponseStarted || humeResponseAudioSeen) {
        avatarMood = "warm";
        window.setTimeout(() => speakingRing.classList.remove("active"), 2400);
        finishHumeTurn("Hume EVI javobi tayyor.", false);
      } else if (!humeInputFinished) {
        turnMetaEl.textContent = "Hume EVI tayyor · gapiring";
      }
      break;
    case "error":
      finishHumeTurn(message.message || "Hume EVI xatosi.", true);
      break;
    default:
      break;
  }
}

function isHumeUserResponseReady() {
  return humeFinalUserMessageSeen || (humeInputFinished && humeUserSpeechSeen);
}

function resetHumeTurnTimeout(message, delayMs) {
  if (humeTurnTimeout) {
    window.clearTimeout(humeTurnTimeout);
  }
  humeTurnTimeout = window.setTimeout(() => {
    finishHumeTurn(message, true);
  }, delayMs);
}

function queueEviAudio(base64Audio) {
  const blob = base64ToBlob(base64Audio, "audio/wav");
  eviAudioQueue.push(blob);
  assistantAudioEl.hidden = false;
  if (!assistantAudioEl.src) {
    assistantAudioEl.src = URL.createObjectURL(blob);
  }
  playNextEviAudio();
}

function playNextEviAudio() {
  if (eviAudioPlaying || !eviAudioQueue.length) return;
  eviAudioPlaying = true;
  const blob = eviAudioQueue.shift();
  const audioUrl = URL.createObjectURL(blob);
  currentEviAudio = new Audio(audioUrl);
  currentEviAudio.addEventListener("ended", () => {
    URL.revokeObjectURL(audioUrl);
    eviAudioPlaying = false;
    currentEviAudio = null;
    playNextEviAudio();
  });
  currentEviAudio.play().catch(() => {
    eviAudioPlaying = false;
    currentEviAudio = null;
  });
}

function stopEviAudioQueue() {
  currentEviAudio?.pause();
  currentEviAudio = null;
  eviAudioPlaying = false;
  eviAudioQueue = [];
}

function finishHumeTurn(message, isError) {
  if (humeTurnTimeout) {
    window.clearTimeout(humeTurnTimeout);
    humeTurnTimeout = null;
  }
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  humeAudioStream?.getTracks().forEach((track) => track.stop());
  humeAudioStream = null;
  mediaRecorder = null;
  if (humeSocket && humeSocket.readyState === WebSocket.OPEN) {
    humeSocket.close();
  }
  humeSocket = null;
  humeSessionActive = false;
  humeMuted = false;
  isRecording = false;
  micButton.classList.remove("recording");
  micButton.title = "Voice yozishni boshlash";
  if (isError) {
    avatarMood = "error";
    spokenResponseEl.textContent = "Speech-to-speech bajarilmadi.";
  }
  turnMetaEl.textContent = message;
  setBusy(false);
  refreshHealth();
}

function base64ToBlob(base64, mimeType) {
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index);
  }
  return new Blob([bytes], { type: mimeType });
}

async function uploadAndSendAudio(blob) {
  setBusy(true);
  try {
    const audioBase64 = await blobToBase64(blob);
    const upload = await api("/audio/upload", {
      method: "POST",
      body: JSON.stringify({
        session_id: "front-session",
        mime_type: blob.type || "audio/webm",
        audio_base64: audioBase64,
      }),
    });
    await sendTurn(upload.audio_ref);
  } catch (error) {
    avatarMood = "error";
    spokenResponseEl.textContent = "Audio yuborilmadi.";
    turnMetaEl.textContent = error.message;
  } finally {
    setBusy(false);
  }
}

function preferredMimeType() {
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return options.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",", 2)[1] : result);
    };
    reader.onerror = () => reject(reader.error || new Error("Audio read failed"));
    reader.readAsDataURL(blob);
  });
}

function setBusy(isBusy) {
  sendButton.disabled = isBusy;
  micButton.disabled = isBusy && !isRecording;
}

function drawAvatar() {
  tick += 0.018;
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2 + 18;
  const breathe = Math.sin(tick) * 5;
  const moodColor = avatarMood === "error" ? "#ff5b6e" : avatarMood === "thoughtful" ? "#8f7cff" : "#48d6c7";

  ctx.save();
  ctx.translate(cx, cy + breathe);

  const body = ctx.createLinearGradient(-150, 150, 150, 390);
  body.addColorStop(0, "#2a3036");
  body.addColorStop(1, "#111417");
  ctx.fillStyle = body;
  roundRect(ctx, -168, 92, 336, 360, 150);
  ctx.fill();

  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 2;
  ctx.stroke();

  const neck = ctx.createLinearGradient(0, -20, 0, 110);
  neck.addColorStop(0, "#c79b80");
  neck.addColorStop(1, "#7f5a4b");
  ctx.fillStyle = neck;
  roundRect(ctx, -42, 46, 84, 120, 34);
  ctx.fill();

  const face = ctx.createRadialGradient(-45, -80, 80, 0, -74, 208);
  face.addColorStop(0, "#e7b99c");
  face.addColorStop(0.62, "#ba846e");
  face.addColorStop(1, "#6d4b42");
  ctx.fillStyle = face;
  roundRect(ctx, -132, -236, 264, 316, 118);
  ctx.fill();

  ctx.fillStyle = "#161719";
  roundRect(ctx, -126, -248, 252, 94, 72);
  ctx.fill();
  roundRect(ctx, -142, -206, 58, 142, 30);
  ctx.fill();
  roundRect(ctx, 84, -206, 58, 142, 30);
  ctx.fill();

  ctx.fillStyle = "#101113";
  drawEye(-50, -78, moodColor);
  drawEye(50, -78, moodColor);

  ctx.strokeStyle = "rgba(20,20,22,0.72)";
  ctx.lineWidth = 8;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(-42, 14);
  const mouthOpen = speakingRing.classList.contains("active") ? 14 + Math.sin(tick * 12) * 5 : 4;
  ctx.quadraticCurveTo(0, 18 + mouthOpen, 42, 14);
  ctx.stroke();

  ctx.strokeStyle = moodColor;
  ctx.globalAlpha = 0.85;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.arc(0, -72, 194 + Math.sin(tick * 2) * 4, -0.3, Math.PI + 0.3, true);
  ctx.stroke();
  ctx.globalAlpha = 1;

  ctx.restore();
  requestAnimationFrame(drawAvatar);
}

function drawEye(x, y, glow) {
  ctx.fillStyle = "#101113";
  ctx.beginPath();
  ctx.ellipse(x, y, 25, 14, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(x + Math.sin(tick * 1.4) * 3, y, 6, 0, Math.PI * 2);
  ctx.fill();
}

function roundRect(context, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  context.beginPath();
  context.moveTo(x + r, y);
  context.arcTo(x + width, y, x + width, y + height, r);
  context.arcTo(x + width, y + height, x, y + height, r);
  context.arcTo(x, y + height, x, y, r);
  context.arcTo(x, y, x + width, y, r);
  context.closePath();
}

sendButton.addEventListener("click", () => sendTurn());
micButton.addEventListener("click", toggleRecording);
refreshButton.addEventListener("click", refreshHealth);

refreshHealth();
drawAvatar();
window.setInterval(refreshHealth, 6000);
