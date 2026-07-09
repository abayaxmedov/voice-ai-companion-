// Ovozli Hamroh — asosiy oqim (TZ 6/8, Unclaw-uslub tajriba):
// doimiy tinglash (VAD) yoki push-to-talk -> upload -> /voice/turn -> avatar javobi.
// Matn kiritish ham bor (Unclaw kabi), lekin asosiy rejim — ovoz.

(function () {
  // Web rejimda API shu sahifa kelgan server; Electron'da preload beradi.
  const API =
    (window.companion && window.companion.orchestratorUrl) ||
    (location.protocol.startsWith("http") ? location.origin : "http://127.0.0.1:8765");
  const SESSION_ID = "desktop-" + Math.random().toString(36).slice(2, 10);

  // Ochiq serverda API token: ?token=... bilan ochilsa saqlanadi va har
  // so'rovga X-Companion-Token sarlavhasi qo'shiladi.
  const API_TOKEN = (() => {
    try {
      const fromUrl = new URLSearchParams(location.search).get("token");
      if (fromUrl) localStorage.setItem("companion_token", fromUrl);
      return fromUrl || localStorage.getItem("companion_token") || "";
    } catch {
      return "";
    }
  })();
  const AUTH_HEADERS = API_TOKEN ? { "X-Companion-Token": API_TOKEN } : {};

  const statusPill = document.getElementById("status-pill");
  const providerDot = document.getElementById("provider-dot");
  const toolStatus = document.getElementById("tool-status");
  const bottomInner = document.getElementById("bottombar-inner");
  const textInput = document.getElementById("text-input");
  const pttBtn = document.getElementById("ptt-btn");
  const voiceToggle = document.getElementById("voice-toggle");

  const diagnostics = document.getElementById("diagnostics");
  const conversation = document.getElementById("conversation");
  const settingsOverlay = document.getElementById("settings-overlay");

  const STATE_LABELS = {
    booting: "Yuklanmoqda…",
    idle: "Tayyor",
    listening: "Tinglayapman…",
    transcribing: "Yozib olyapman…",
    thinking: "O'ylayapman…",
    synthesizing: "Ovoz tayyorlanyapti…",
    speaking: "Gapiryapman",
    interrupted: "To'xtatildi",
    error: "Xatolik",
  };

  const AVATAR_STATES = {
    booting: "idle",
    idle: "idle",
    listening: "listening",
    transcribing: "thinking",
    thinking: "thinking",
    synthesizing: "thinking",
    speaking: "speaking",
    interrupted: "listening",
    error: "error",
  };

  let uiState = "booting";
  let mediaStream = null;
  let mediaRecorder = null;
  let recordedChunks = [];
  let recording = false;
  let busy = false;
  let profile = null;

  let audioCtx = null;
  let currentAudio = null;
  let analyserRAF = null;
  let activeStream = null; // streaming TTS sessiyasi (WebAudio)

  // iOS/Safari: audio faqat foydalanuvchi harakati ichida ochiladi.
  // Har bir gesture'da (PTT, Enter, tugma) chaqiramiz — arzon va xavfsiz.
  function unlockAudio() {
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
    } catch {
      // audio qurilmasi yo'q muhit
    }
  }

  function avatar() {
    return window.Avatar3D && window.Avatar3D.ready ? window.Avatar3D : window.Avatar;
  }

  function setUiState(state) {
    uiState = state;
    statusPill.dataset.state =
      ["listening", "thinking", "speaking", "error", "idle"].find((s) =>
        state === s || (s === "thinking" && ["transcribing", "thinking", "synthesizing"].includes(state))
      ) || "idle";
    statusPill.textContent = STATE_LABELS[state] || state;
    avatar().setState(AVATAR_STATES[state] || "idle");
  }

  // ---------- Backend ----------
  async function api(path, options) {
    const response = await fetch(API + path, {
      ...options,
      headers: { "Content-Type": "application/json", ...AUTH_HEADERS, ...(options && options.headers) },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    }
    return payload;
  }

  // ---------- Unreal Pixel Streaming avto-almashinuv (AD-002) ----------
  // Bridge orqali UE oqimi tayyor bo'lsa Three.js o'rnida WebRTC player
  // ochiladi; oqim yo'qolsa avtomatik Three.js'ga qaytadi.
  let ueFrame = null;
  let bridgeUrl = null;

  // UE lab-sinxron soatini haqiqiy audio pozitsiyasiga tuzatish: UE oqimi
  // aktiv bo'lsa har ~500ms bridge'ga pozitsiya yuboriladi (avatar.sync).
  function postAvatarSync(positionMs) {
    if (!bridgeUrl || !ueFrame || !Number.isFinite(positionMs)) return;
    fetch(bridgeUrl + "/avatar/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ position_ms: Math.round(positionMs) }),
    }).catch(() => { /* bridge vaqtincha yo'q — jim */ });
  }

  function updateAvatarStream(bridge) {
    if (bridge && bridge.bridge_url) bridgeUrl = bridge.bridge_url;
    const ready = !!(bridge && bridge.stream_ready && bridge.player_url);
    const three = document.getElementById("avatar3d-container");
    const twoD = document.getElementById("avatar-canvas");
    if (ready && !ueFrame) {
      ueFrame = document.createElement("iframe");
      ueFrame.id = "ue-stream-frame";
      ueFrame.src = bridge.player_url;
      ueFrame.allow = "autoplay";
      ueFrame.style.cssText =
        "position:absolute;inset:0;width:100%;height:100%;border:0;z-index:1;background:#060304;";
      document.getElementById("stage").prepend(ueFrame);
      if (three) three.style.display = "none";
      if (twoD) twoD.style.display = "none";
      console.info("[avatar] Unreal Pixel Streaming ulandi:", bridge.player_url);
    } else if (!ready && ueFrame) {
      ueFrame.remove();
      ueFrame = null;
      if (three) three.style.display = "";
      if (twoD) twoD.style.display = "";
      console.info("[avatar] UE oqimi uzildi — Three.js avatarga qaytdik.");
    }
  }

  async function refreshHealth() {
    try {
      const health = await api("/health");
      updateAvatarStream(health.avatar_bridge);
      const providers = health.providers || [];
      const allReady = providers.every((p) => p.ready);
      providerDot.className = "dot " + (allReady ? "ok" : "degraded");
      providerDot.title = providers
        .map((p) => `${p.provider_id}: ${p.ready ? "tayyor" : p.status}`)
        .join("\n");
      const diag = {
        stt: providers.find((p) => p.kind === "stt"),
        llm: providers.find((p) => p.kind === "llm"),
        tts: providers.find((p) => p.kind === "tts"),
      };
      setDiag("diag-stt", diag.stt && `${diag.stt.provider_id} (${diag.stt.status})`);
      setDiag("diag-llm", diag.llm && `${diag.llm.provider_id} (${diag.llm.status})`);
      setDiag("diag-tts", diag.tts && `${diag.tts.provider_id} (${diag.tts.status})`);
      if (uiState === "booting") setUiState("idle");
      return health;
    } catch {
      providerDot.className = "dot error";
      providerDot.title = "Backend bilan aloqa yo'q";
      if (uiState === "booting") statusPill.textContent = "Backend kutilmoqda…";
      return null;
    }
  }

  function setDiag(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value || "—";
  }

  // ---------- Soat, salomlashuv, iqtiboslar ----------
  const WEEKDAYS = ["Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"];
  const MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];

  function updateClock() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    document.getElementById("clock").textContent =
      `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    document.getElementById("date-line").textContent =
      `${WEEKDAYS[now.getDay()]}, ${now.getDate()}-${MONTHS[now.getMonth()]}`;
  }

  function updateGreeting() {
    const h = new Date().getHours();
    let text = "Xayrli tun";
    if (h >= 5 && h < 11) text = "Xayrli tong";
    else if (h >= 11 && h < 18) text = "Xayrli kun";
    else if (h >= 18 && h < 23) text = "Xayrli oqshom";
    const name = (profile && profile.user_name) || "";
    document.getElementById("greeting").innerHTML =
      name ? `${text}, <em>${escapeHtml(name)}</em>.` : `${text}.`;
  }

  const QUOTES = [
    { t: "Yetarlicha rivojlangan texnologiya sehrdan farq qilmaydi.", a: "Artur Klark" },
    { t: "Soddalik — yetuklikning eng yuqori darajasi.", a: "Leonardo da Vinchi" },
    { t: "Kelajak allaqachon shu yerda, faqat tekis taqsimlanmagan.", a: "Uilyam Gibson" },
    { t: "Ilm olish — har bir inson uchun farzdir.", a: "Hadis" },
    { t: "Avval ishlashini ta'minla, keyin to'g'rila, keyin tezlashtir.", a: "Kent Bek" },
    { t: "Bilimdan qudratliroq kuch yo'q.", a: "Abu Rayhon Beruniy" },
    { t: "Tavakkal qilmagan — g'alaba qilmaydi.", a: "Xalq maqoli" },
    { t: "Har bir mushkulning osoni bor.", a: "Xalq maqoli" },
    { t: "Kamtarlik — ulug'lik belgisi.", a: "Alisher Navoiy" },
    { t: "Xato qilmagan odam hech narsa qilmagan odamdir.", a: "Teodor Ruzvelt" },
  ];
  let quoteIndex = Math.floor(Math.random() * QUOTES.length);
  function rotateQuote() {
    const q = QUOTES[quoteIndex % QUOTES.length];
    quoteIndex += 1;
    document.getElementById("quote-text").textContent = `“${q.t}”`;
    document.getElementById("quote-author").textContent = q.a;
  }

  // ---------- Typewriter takliflar ----------
  const SUGGESTIONS = [
    "Menga ayting…",
    "Bugun kayfiyatingiz qanday?",
    "Ertaga nima rejalaringiz bor?",
    "Menga bir qiziq fakt ayting",
    "Toshkentda ob-havo qanday?",
    "Menga motivatsiya kerak",
  ];
  let sugIndex = 0;
  let sugChar = 0;
  let sugTimer = null;
  function typewriterTick() {
    if (document.activeElement === textInput || textInput.value) {
      sugTimer = setTimeout(typewriterTick, 900);
      return;
    }
    const target = SUGGESTIONS[sugIndex % SUGGESTIONS.length];
    if (sugChar <= target.length) {
      textInput.placeholder = target.slice(0, sugChar);
      sugChar += 1;
      sugTimer = setTimeout(typewriterTick, 55);
    } else {
      sugIndex += 1;
      sugChar = 0;
      sugTimer = setTimeout(typewriterTick, 2600);
    }
  }

  // ---------- Suhbat tarixi ----------
  const convMessages = document.getElementById("conv-messages");

  function addMessage(role, text, timeIso) {
    if (!text) return;
    const div = document.createElement("div");
    div.className = "msg " + (role === "assistant" ? "assistant" : "user");
    const body = document.createElement("span");
    body.textContent = text;
    div.appendChild(body);
    const time = document.createElement("span");
    time.className = "msg-time";
    const d = timeIso ? new Date(timeIso) : new Date();
    time.textContent = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    div.appendChild(time);
    convMessages.appendChild(div);
    convMessages.scrollTop = convMessages.scrollHeight;
  }

  async function loadConversation() {
    try {
      const data = await api("/conversation");
      convMessages.innerHTML = "";
      for (const m of data.messages || []) {
        addMessage(m.role, m.text, m.created_at);
      }
    } catch {
      // backend hali tayyor emas
    }
  }

  document.getElementById("conv-clear").addEventListener("click", async () => {
    try {
      await api("/conversation/clear", { method: "POST" });
      convMessages.innerHTML = "";
    } catch (err) {
      showToolStatus("Tozalab bo'lmadi: " + err.message);
    }
  });

  // ---------- Yozib olish ----------
  async function ensureMic() {
    if (mediaStream) return mediaStream;
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    return mediaStream;
  }

  function pickMimeType() {
    // audio/mp4 (m4a) birinchi: Aisha STT webm qabul qilmaydi (mp3/wav/ogg/m4a),
    // ElevenLabs va OpenAI uchun ham m4a bemalol ishlaydi.
    const candidates = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm"];
    return candidates.find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || "";
  }

  let captureStartedAt = 0;

  async function startRecording(sourceKind) {
    if (recording || busy) return;
    unlockAudio();
    stopPlayback("barge_in"); // TZ 6.1: barge-in.
    try {
      const stream = await ensureMic();
      recordedChunks = [];
      const mimeType = pickMimeType();
      mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) recordedChunks.push(e.data);
      };
      mediaRecorder.onstop = onRecordingStopped;
      mediaRecorder.start();
      recording = true;
      captureStartedAt = performance.now();
      if (sourceKind === "ptt") pttBtn.classList.add("recording");
      bottomInner.classList.add("voice-capturing");
      setUiState("listening");
    } catch (err) {
      showError("Mikrofonga ruxsat kerak: " + err.message);
    }
  }

  function stopRecording() {
    if (!recording || !mediaRecorder) return;
    recording = false;
    pttBtn.classList.remove("recording");
    bottomInner.classList.remove("voice-capturing");
    try {
      mediaRecorder.stop();
    } catch {
      // already stopped
    }
  }

  async function onRecordingStopped() {
    const blob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
    recordedChunks = [];
    const durationMs = performance.now() - captureStartedAt;
    if (blob.size < 1200 || durationMs < 450) {
      setUiState("idle");
      return;
    }
    busy = true;
    try {
      setUiState("transcribing");
      const base64 = await blobToBase64(blob);
      const upload = await api("/audio/upload", {
        method: "POST",
        body: JSON.stringify({
          audio_base64: base64,
          mime_type: blob.type || "audio/webm",
          session_id: SESSION_ID,
        }),
      });

      setUiState("thinking");
      await runTurn({
        session_id: SESSION_ID,
        agent_id: "default",
        audio_ref: upload.audio_ref,
        user_locale: "uz-Latn",
      });
    } catch (err) {
      showError(err.message);
    } finally {
      busy = false;
    }
  }

  async function sendText(text) {
    const clean = text.trim();
    if (!clean || busy) return;
    busy = true;
    unlockAudio();
    stopPlayback("new_turn");
    try {
      setUiState("thinking");
      await runTurn({
        session_id: SESSION_ID,
        agent_id: "default",
        transcript_override: clean,
        user_locale: "uz-Latn",
      });
    } catch (err) {
      showError(err.message);
    } finally {
      busy = false;
    }
  }

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  // ---------- Doimiy tinglash (VAD) ----------
  let voiceMode = false;
  let vadCtx = null;
  let vadAnalyser = null;
  let vadTimer = null;
  let vadSpeechFrames = 0;
  let vadSilenceFrames = 0;

  const VAD_START_RMS = 0.045;
  const VAD_BARGE_RMS = 0.10;   // gapirayotganda kuchliroq signal kerak (echo himoyasi)
  const VAD_STOP_RMS = 0.02;
  const VAD_START_FRAMES = 3;   // ~180ms
  const VAD_STOP_FRAMES = 15;   // ~900ms sukut

  async function enableVoiceMode() {
    try {
      const stream = await ensureMic();
      if (!vadCtx) {
        vadCtx = new (window.AudioContext || window.webkitAudioContext)();
        const source = vadCtx.createMediaStreamSource(stream);
        vadAnalyser = vadCtx.createAnalyser();
        vadAnalyser.fftSize = 512;
        source.connect(vadAnalyser);
      }
      if (vadCtx.state === "suspended") await vadCtx.resume();
      voiceMode = true;
      voiceToggle.classList.add("active");
      bottomInner.classList.add("voice-live");
      vadSpeechFrames = 0;
      vadSilenceFrames = 0;
      vadTimer = setInterval(vadTick, 60);
      showToolStatus("Doimiy tinglash yoqildi — shunchaki gapiring.");
    } catch (err) {
      showError("Mikrofonga ruxsat kerak: " + err.message);
    }
  }

  function disableVoiceMode() {
    voiceMode = false;
    voiceToggle.classList.remove("active");
    bottomInner.classList.remove("voice-live");
    clearInterval(vadTimer);
    if (recording) stopRecording();
  }

  function vadRms() {
    const data = new Uint8Array(vadAnalyser.frequencyBinCount);
    vadAnalyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    return Math.sqrt(sum / data.length);
  }

  function vadTick() {
    if (!voiceMode || !vadAnalyser) return;
    const rms = vadRms();

    if (!recording) {
      if (busy) return; // navbatdagi javob tayyorlanmoqda
      const playing = currentAudio || (activeStream && activeStream.gotAudio);
      const threshold = playing ? VAD_BARGE_RMS : VAD_START_RMS;
      if (rms > threshold) {
        vadSpeechFrames += 1;
        if (vadSpeechFrames >= VAD_START_FRAMES) {
          vadSpeechFrames = 0;
          startRecording("vad");
        }
      } else {
        vadSpeechFrames = 0;
      }
      return;
    }

    // Yozib olinyapti: sukutni kutamiz.
    if (rms < VAD_STOP_RMS) {
      vadSilenceFrames += 1;
      if (vadSilenceFrames >= VAD_STOP_FRAMES) {
        vadSilenceFrames = 0;
        stopRecording();
      }
    } else {
      vadSilenceFrames = 0;
    }
  }

  voiceToggle.addEventListener("click", () => {
    unlockAudio();
    if (voiceMode) disableVoiceMode();
    else enableVoiceMode();
  });

  // ---------- Streaming turn (past kechikish) ----------
  // Backend /voice/turn/stream NDJSON qaytaradi: meta -> audio* -> end.
  // Audio chunk'lar WebAudio navbatida ijro etiladi, avatar viseme/curves'ni
  // kelishi bilan oladi. Har qanday erta xatoda klassik yo'lga qaytamiz.
  async function runTurn(body) {
    try {
      const handled = await streamTurn(body);
      if (handled) return;
    } catch (err) {
      console.warn("[stream] klassik yo'lga qaytish:", err?.message || err);
    }
    const result = await api("/voice/turn", {
      method: "POST",
      body: JSON.stringify(body),
    });
    handleTurnResult(result);
  }

  function handleStreamMeta(ev) {
    const userText = ev.transcript?.text || "";
    const botText = ev.llm_response?.response || "";
    setDiag("diag-transcript", "Siz: " + (userText || "—"));
    setDiag("diag-response", "Hamroh: " + (botText || "—"));
    setDiag("diag-error", ev.llm_response?.debug_reason || "");
    avatar().setMood(ev.mood || ev.llm_response?.mood);
    if (userText) addMessage("user", userText);
    if (botText) addMessage("assistant", botText);
  }

  async function streamTurn(body) {
    const controller = new AbortController();
    const response = await fetch(API + "/voice/turn/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...AUTH_HEADERS },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok || !response.body) return false;

    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") await audioCtx.resume();

    const st = {
      controller,
      sources: new Set(),
      t0: null,
      nextTime: 0,
      clock: null,
      curves: { fps: 50, energy: [], jaw: [], close: [], spread: [], round: [], pitch: [] },
      visemes: [],
      gotAudio: false,
      stopped: false,
      finishTimer: null,
      mouthTimer: null,
      syncTimer: null,
    };
    st.stop = () => {
      if (st.stopped) return;
      st.stopped = true;
      try { controller.abort(); } catch { /* allaqachon tugagan */ }
      for (const src of st.sources) { try { src.stop(); } catch { /* ok */ } }
      st.sources.clear();
      clearTimeout(st.finishTimer);
      clearInterval(st.mouthTimer);
      clearInterval(st.syncTimer);
      if (activeStream === st) activeStream = null;
    };
    stopPlayback("new_turn");
    activeStream = st;

    const finish = () => {
      if (st.stopped) return;
      st.stop();
      const av = avatar();
      if (av.stopSpeaking) av.stopSpeaking();
      av.setMouthLevel(0);
      setUiState("idle");
    };

    const handleEvent = (ev) => {
      if (ev.type === "meta") {
        handleStreamMeta(ev);
        return null;
      }
      if (ev.type === "audio") {
        const raw = atob(ev.pcm_b64 || "");
        if (!raw.length) return null;
        const bytes = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
        const pcm = new Int16Array(bytes.buffer, 0, Math.floor(bytes.length / 2));
        const sr = ev.sample_rate || 24000;
        const buffer = audioCtx.createBuffer(1, pcm.length, sr);
        const channel = buffer.getChannelData(0);
        for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 32768;

        if (st.t0 === null) {
          st.t0 = audioCtx.currentTime + 0.1; // kichik jitter-bufer
          st.nextTime = st.t0;
          st.clock = {
            get currentTime() { return Math.max(0, audioCtx.currentTime - st.t0); },
          };
          setUiState("speaking");
        }
        const src = audioCtx.createBufferSource();
        src.buffer = buffer;
        src.connect(audioCtx.destination);
        src.onended = () => st.sources.delete(src);
        st.nextTime = Math.max(st.nextTime, audioCtx.currentTime + 0.02);
        src.start(st.nextTime);
        st.nextTime += pcm.length / sr;
        st.sources.add(src);

        if (ev.curves) {
          for (const key of ["energy", "jaw", "close", "spread", "round", "pitch"]) {
            if (ev.curves[key]) st.curves[key].push(...ev.curves[key]);
          }
        }
        if (Array.isArray(ev.visemes) && ev.visemes.length) st.visemes = ev.visemes;

        const av = avatar();
        if (!st.gotAudio) {
          st.gotAudio = true;
          if (av.speak) {
            av.speak(
              st.visemes.length ? st.visemes : [{ time_ms: 0, name: "aa", weight: 0.8 }],
              st.clock,
              st.curves
            );
          }
          // 2D fallback og'zi + 3D energiya zaxirasi uchun.
          st.mouthTimer = setInterval(() => {
            const tMs = st.clock ? st.clock.currentTime * 1000 : 0;
            const idx = Math.min(
              st.curves.energy.length - 1,
              Math.floor((tMs / 1000) * st.curves.fps)
            );
            avatar().setMouthLevel(idx >= 0 ? st.curves.energy[idx] : 0);
          }, 50);
          // UE lab-sinxron soati uchun haqiqiy pozitsiya (avatar.sync).
          st.syncTimer = setInterval(() => {
            if (st.clock) postAvatarSync(st.clock.currentTime * 1000);
          }, 500);
        } else if (av.updateTimeline) {
          av.updateTimeline(st.visemes, st.curves);
        }
        return null;
      }
      if (ev.type === "end") {
        const lat = ev.latency_ms || {};
        setDiag(
          "diag-latency",
          Object.entries(lat).map(([k, v]) => `${k}=${v}`).join(" ") || "—"
        );
        const remainMs = st.t0 === null
          ? 0
          : Math.max(0, (st.nextTime - audioCtx.currentTime) * 1000) + 150;
        st.finishTimer = setTimeout(finish, remainMs);
        return null;
      }
      if (ev.type === "error") {
        if (!st.gotAudio) return "fallback";
        finish();
        showError(ev.message || "Streaming xatosi.");
        return null;
      }
      return null;
    };

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          let ev;
          try { ev = JSON.parse(line); } catch { continue; }
          const action = handleEvent(ev);
          if (action === "fallback") {
            st.stop();
            return false;
          }
        }
      }
    } catch (err) {
      if (!st.gotAudio) { st.stop(); throw err; }
      // Audio boshlangan bo'lsa — borini ijro etib tugatamiz.
      if (!st.finishTimer) st.finishTimer = setTimeout(finish, 500);
    }
    if (!st.gotAudio) { st.stop(); return false; }
    if (!st.finishTimer && !st.stopped) st.finishTimer = setTimeout(finish, 300);
    return true;
  }

  // ---------- Javob va ijro ----------
  function handleTurnResult(result) {
    const userText = result.transcript?.text || "";
    const botText = result.llm_response?.response || "";
    setDiag("diag-transcript", "Siz: " + (userText || "—"));
    setDiag("diag-response", "Hamroh: " + (botText || "—"));
    const lat = result.latency_ms || {};
    setDiag(
      "diag-latency",
      Object.entries(lat).map(([k, v]) => `${k}=${v}`).join(" ") || "—"
    );
    setDiag("diag-error", result.llm_response?.debug_reason || "");
    avatar().setMood(result.llm_response?.mood);

    if (userText && result.transcript?.provider_id !== "transcript_override") {
      addMessage("user", userText);
    } else if (result.transcript?.provider_id === "transcript_override") {
      addMessage("user", userText);
    }
    if (botText) addMessage("assistant", botText);

    const audioRef = result.tts?.audio_ref || "";
    if (audioRef.startsWith("http")) {
      playResponse(
        audioRef,
        result.avatar_job?.visemes || [],
        result.avatar_job?.mouth_curves || null
      );
    } else {
      setUiState("idle");
      showToolStatus("Ovoz fayli yo'q (mock TTS). Sozlamalardan TTS provider tanlang.");
    }
  }

  function playResponse(url, visemes, curves) {
    stopPlayback("new_turn");
    setUiState("speaking");

    const audio = new Audio();
    audio.crossOrigin = "anonymous";
    audio.src = url;
    currentAudio = audio;

    // Fonema-aniq lab-sinxron: viseme timeline + audio-tahlil egri chiziqlari
    // (mouth_curves) 3D avatarga uzatiladi. Analyser RMS fallback bo'lib qoladi.
    const av = avatar();
    if (av.speak && Array.isArray(visemes) && visemes.length) {
      av.speak(visemes, audio, curves);
    }

    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaElementSource(audio);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      analyser.connect(audioCtx.destination);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        if (currentAudio !== audio) return;
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / data.length);
        avatar().setMouthLevel(Math.min(1, rms * 6));
        analyserRAF = requestAnimationFrame(tick);
      };
      analyserRAF = requestAnimationFrame(tick);
    } catch {
      const fake = setInterval(() => {
        if (currentAudio !== audio) return clearInterval(fake);
        avatar().setMouthLevel(0.3 + Math.random() * 0.5);
      }, 90);
    }

    const syncTimer = setInterval(() => {
      if (currentAudio !== audio) return clearInterval(syncTimer);
      postAvatarSync(audio.currentTime * 1000);
    }, 500);

    audio.onended = () => {
      clearInterval(syncTimer);
      if (currentAudio === audio) finishPlayback();
    };
    audio.onerror = () => {
      clearInterval(syncTimer);
      if (currentAudio === audio) {
        finishPlayback();
        showError("Audio o'ynatishda xatolik.");
      }
    };
    audio.play().catch((err) => showError("Audio boshlanmadi: " + err.message));
  }

  function finishPlayback() {
    currentAudio = null;
    if (analyserRAF) cancelAnimationFrame(analyserRAF);
    const av = avatar();
    if (av.stopSpeaking) av.stopSpeaking();
    av.setMouthLevel(0);
    setUiState("idle");
  }

  function stopPlayback(reason) {
    // Streaming sessiyani ham to'xtatamiz (barge-in / yangi turn).
    if (activeStream && reason !== "new_turn_self") {
      const st = activeStream;
      activeStream = null;
      st.stop();
      const avs = avatar();
      if (avs.stopSpeaking) avs.stopSpeaking();
      avs.setMouthLevel(0);
      if (reason === "barge_in") setUiState("interrupted");
    }
    if (!currentAudio) return;
    const audio = currentAudio;
    currentAudio = null;
    if (analyserRAF) cancelAnimationFrame(analyserRAF);
    try {
      audio.pause();
      audio.src = "";
    } catch {
      // ignored
    }
    const av = avatar();
    if (av.stopSpeaking) av.stopSpeaking();
    av.setMouthLevel(0);
    if (reason === "barge_in") setUiState("interrupted");
  }

  function showError(message) {
    setUiState("error");
    setDiag("diag-error", message);
    showToolStatus(message);
    setTimeout(() => {
      if (uiState === "error") setUiState("idle");
    }, 4000);
  }

  let toolStatusTimer = null;
  function showToolStatus(message) {
    toolStatus.textContent = message;
    toolStatus.classList.remove("hidden");
    clearTimeout(toolStatusTimer);
    toolStatusTimer = setTimeout(() => toolStatus.classList.add("hidden"), 5000);
  }

  // ---------- Matn yuborish ----------
  textInput.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const value = textInput.value;
    textInput.value = "";
    sendText(value);
  });

  // ---------- Push-to-talk ----------
  pttBtn.addEventListener("mousedown", () => startRecording("ptt"));
  pttBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording("ptt"); });
  window.addEventListener("mouseup", () => { if (!voiceMode) stopRecording(); });
  pttBtn.addEventListener("touchend", () => { if (!voiceMode) stopRecording(); });

  window.addEventListener("keydown", (e) => {
    if (e.code !== "Space" || e.repeat) return;
    const tag = document.activeElement && document.activeElement.tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    e.preventDefault();
    startRecording("ptt");
  });
  window.addEventListener("keyup", (e) => {
    if (e.code !== "Space") return;
    const tag = document.activeElement && document.activeElement.tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    if (!voiceMode) stopRecording();
    else stopRecording();
  });

  // ---------- Chap panel vidjetlari ----------
  const sideCard = document.getElementById("side-card");
  let sideCardOpen = null;

  function openSideCard(kind, title, bodyHtml) {
    if (sideCardOpen === kind) {
      sideCard.classList.add("hidden");
      sideCardOpen = null;
      return;
    }
    sideCardOpen = kind;
    document.getElementById("side-card-title").textContent = title;
    document.getElementById("side-card-body").innerHTML = bodyHtml;
    sideCard.classList.remove("hidden");
  }

  document.getElementById("side-bell").addEventListener("click", async () => {
    let body = "Hozircha bildirishnoma yo'q.";
    try {
      const rs = await api("/runtime/state");
      const events = (rs.events || []).slice(-6).reverse();
      if (events.length) {
        body = events
          .map((ev) => `<div class="rowline"><span>${escapeHtml(ev.state)}</span><span>${escapeHtml(String(ev.message).slice(0, 40))}</span></div>`)
          .join("");
      }
    } catch {
      body = "Backend bilan aloqa yo'q.";
    }
    openSideCard("bell", "Bildirishnomalar", body);
  });

  const WEATHER_CODES = {
    0: "ochiq", 1: "asosan ochiq", 2: "qisman bulutli", 3: "bulutli",
    45: "tuman", 48: "qirovli tuman",
    51: "yengil sevalama", 53: "sevalama", 55: "kuchli sevalama",
    61: "yengil yomg'ir", 63: "yomg'ir", 65: "kuchli yomg'ir",
    71: "yengil qor", 73: "qor", 75: "kuchli qor",
    80: "yomg'irli jala", 81: "jala", 82: "kuchli jala",
    95: "momaqaldiroq", 96: "do'lli momaqaldiroq", 99: "kuchli do'l",
  };
  let weatherCache = { at: 0, html: "" };

  document.getElementById("side-weather").addEventListener("click", async () => {
    const city = (profile && profile.city) || "Tashkent";
    if (Date.now() - weatherCache.at < 15 * 60 * 1000 && weatherCache.html) {
      openSideCard("weather", `Ob-havo — ${city}`, weatherCache.html);
      return;
    }
    openSideCard("weather", `Ob-havo — ${city}`, "Yuklanmoqda…");
    try {
      const geo = await fetch(
        `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=en`
      ).then((r) => r.json());
      const place = geo.results && geo.results[0];
      if (!place) throw new Error("shahar topilmadi");
      const wx = await fetch(
        `https://api.open-meteo.com/v1/forecast?latitude=${place.latitude}&longitude=${place.longitude}` +
        `&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1`
      ).then((r) => r.json());
      const t = Math.round(wx.current?.temperature_2m ?? 0);
      const code = WEATHER_CODES[wx.current?.weather_code] || "";
      const tmax = Math.round(wx.daily?.temperature_2m_max?.[0] ?? 0);
      const tmin = Math.round(wx.daily?.temperature_2m_min?.[0] ?? 0);
      const html =
        `<div class="big">${t}°C</div>` +
        `<div>${escapeHtml(code)}</div>` +
        `<div class="rowline"><span>Maksimal</span><span>${tmax}°C</span></div>` +
        `<div class="rowline"><span>Minimal</span><span>${tmin}°C</span></div>`;
      weatherCache = { at: Date.now(), html };
      if (sideCardOpen === "weather") {
        document.getElementById("side-card-body").innerHTML = html;
      }
    } catch (err) {
      if (sideCardOpen === "weather") {
        document.getElementById("side-card-body").textContent =
          "Ob-havoni olib bo'lmadi: " + err.message;
      }
    }
  });

  document.getElementById("side-diag").addEventListener("click", () => {
    conversation.classList.add("hidden");
    diagnostics.classList.toggle("hidden");
  });

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
  }

  // ---------- Drawerlar ----------
  document.getElementById("chat-toggle-btn").addEventListener("click", () => {
    diagnostics.classList.add("hidden");
    conversation.classList.toggle("hidden");
  });
  document.getElementById("conv-close").addEventListener("click", () =>
    conversation.classList.add("hidden"));
  document.getElementById("diag-close").addEventListener("click", () =>
    diagnostics.classList.add("hidden"));

  // ---------- Sozlamalar modali ----------
  document.getElementById("settings-btn").addEventListener("click", async () => {
    settingsOverlay.classList.remove("hidden");
    await Promise.all([loadSettings(), loadProfileForm()]);
  });
  document.getElementById("settings-close").addEventListener("click", () =>
    settingsOverlay.classList.add("hidden"));
  settingsOverlay.addEventListener("click", (e) => {
    if (e.target === settingsOverlay) settingsOverlay.classList.add("hidden");
  });

  for (const tab of document.querySelectorAll("#settings-tabs .tab")) {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#settings-tabs .tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.querySelector(`.tab-pane[data-pane="${tab.dataset.tab}"]`).classList.add("active");
    });
  }

  const SLIDER_WORDS = {
    formality: ["ERKIN", "SAMIMIY", "RASMIY"],
    humor: ["JIDDIY", "O'RTACHA", "QUVNOQ"],
    directness: ["YUMSHOQ", "HALOL", "DADIL"],
    verbosity: ["QISQA", "O'RTACHA", "BATAFSIL"],
  };
  function sliderWord(kind, value) {
    const words = SLIDER_WORDS[kind];
    return value < 34 ? words[0] : value < 67 ? words[1] : words[2];
  }
  for (const kind of ["formality", "humor", "directness", "verbosity"]) {
    const input = document.getElementById("p-" + kind);
    input.addEventListener("input", () => {
      document.getElementById("v-" + kind).textContent = sliderWord(kind, Number(input.value));
    });
  }

  async function loadProfileForm() {
    try {
      profile = await api("/profile");
    } catch {
      return;
    }
    applyProfileToUi();
    document.getElementById("p-user-name").value = profile.user_name || "";
    document.getElementById("p-agent-name").value = profile.display_name || "";
    document.getElementById("p-city").value = profile.city || "";
    document.getElementById("p-timezone").value = profile.timezone || "";
    document.getElementById("p-hobbies").value = (profile.hobbies || []).join(", ");
    for (const kind of ["formality", "humor", "directness", "verbosity"]) {
      const value = Math.round((profile["vibe_" + kind] ?? 0.5) * 100);
      document.getElementById("p-" + kind).value = value;
      document.getElementById("v-" + kind).textContent = sliderWord(kind, value);
    }
    document.getElementById("profile-hello").textContent =
      profile.user_name ? `Salom, ${profile.user_name}.` : "Salom.";
  }

  function applyProfileToUi() {
    if (!profile) return;
    const agentName = profile.display_name || "Hamroh";
    document.getElementById("agent-name").textContent = agentName;
    document.getElementById("conv-agent-name").textContent = agentName;
    updateGreeting();
  }

  async function loadSettings() {
    try {
      const [catalog, current] = await Promise.all([
        api("/providers/catalog"),
        api("/settings"),
      ]);
      const providers = catalog.providers || [];
      fillSelect("set-stt", providers.filter((p) => p.kind === "stt"), current.selected_providers.stt);
      fillSelect("set-llm", providers.filter((p) => p.kind === "llm"), current.selected_providers.llm);
      fillSelect("set-tts", providers.filter((p) => p.kind === "tts"), current.selected_providers.tts);
      document.getElementById("set-elevenlabs-voice").value = current.elevenlabs?.voice_id || "";
      document.getElementById("set-openai-model").value = current.openai?.model || "";
      document.getElementById("set-openai-key").placeholder = current.openai?.api_key_configured
        ? "•••••• (saqlangan)"
        : "sk-…";
      document.getElementById("set-elevenlabs-key").placeholder = current.elevenlabs?.api_key_configured
        ? "•••••• (saqlangan)"
        : "sk_…";
      document.getElementById("set-aisha-key").placeholder = current.aisha?.api_key_configured
        ? "•••••• (saqlangan)"
        : "Aisha Space → API kalitlari";
      document.getElementById("set-aisha-mood").value = current.aisha?.mood || "Neutral";
      document.getElementById("set-aisha-voice").value = current.aisha?.voice_id || "";
      document.getElementById("set-avatar-url").value =
        localStorage.getItem("avatar_glb_url") || "";
    } catch (err) {
      settingsStatus("Sozlamalarni yuklab bo'lmadi: " + err.message);
    }
  }

  function fillSelect(id, providers, selected) {
    const select = document.getElementById(id);
    select.innerHTML = "";
    for (const p of providers) {
      const option = document.createElement("option");
      option.value = p.provider_id;
      option.textContent = `${p.provider_id}${p.ready ? "" : " (kalit kerak)"}`;
      if (p.provider_id === selected) option.selected = true;
      select.appendChild(option);
    }
  }

  function settingsStatus(message) {
    document.getElementById("settings-status").textContent = message;
  }

  document.getElementById("save-settings").addEventListener("click", async () => {
    const settingsPayload = {
      stt_provider: document.getElementById("set-stt").value,
      llm_provider: document.getElementById("set-llm").value,
      tts_provider: document.getElementById("set-tts").value,
    };
    const openaiKey = document.getElementById("set-openai-key").value.trim();
    const openaiModel = document.getElementById("set-openai-model").value.trim();
    const elKey = document.getElementById("set-elevenlabs-key").value.trim();
    const voiceId = document.getElementById("set-elevenlabs-voice").value.trim();
    const aishaKey = document.getElementById("set-aisha-key").value.trim();
    const aishaMood = document.getElementById("set-aisha-mood").value;
    const aishaVoice = document.getElementById("set-aisha-voice").value.trim();
    if (openaiKey) settingsPayload.openai_api_key = openaiKey;
    if (openaiModel) settingsPayload.openai_model = openaiModel;
    if (elKey) settingsPayload.elevenlabs_api_key = elKey;
    if (voiceId) settingsPayload.elevenlabs_voice_id = voiceId;
    if (aishaKey) settingsPayload.aisha_api_key = aishaKey;
    if (aishaMood) settingsPayload.aisha_tts_mood = aishaMood;
    settingsPayload.aisha_voice_id = aishaVoice;

    const profilePayload = {
      user_name: document.getElementById("p-user-name").value,
      display_name: document.getElementById("p-agent-name").value,
      city: document.getElementById("p-city").value,
      timezone: document.getElementById("p-timezone").value,
      hobbies: document.getElementById("p-hobbies").value,
      vibe_formality: Number(document.getElementById("p-formality").value) / 100,
      vibe_humor: Number(document.getElementById("p-humor").value) / 100,
      vibe_directness: Number(document.getElementById("p-directness").value) / 100,
      vibe_verbosity: Number(document.getElementById("p-verbosity").value) / 100,
    };

    const avatarUrl = document.getElementById("set-avatar-url").value.trim();
    if (avatarUrl) localStorage.setItem("avatar_glb_url", avatarUrl);
    else localStorage.removeItem("avatar_glb_url");

    try {
      settingsStatus("Saqlanmoqda…");
      profile = await api("/profile", { method: "PATCH", body: JSON.stringify(profilePayload) });
      await api("/settings", { method: "PATCH", body: JSON.stringify(settingsPayload) });
      document.getElementById("set-openai-key").value = "";
      document.getElementById("set-elevenlabs-key").value = "";
      document.getElementById("set-aisha-key").value = "";
      applyProfileToUi();
      settingsStatus("Saqlandi. Providerlar qayta yuklandi.");
      await refreshHealth();
      await loadSettings();
    } catch (err) {
      settingsStatus("Xatolik: " + err.message);
    }
  });

  document.getElementById("test-voice").addEventListener("click", async () => {
    try {
      settingsStatus("Ovoz testi yuborilmoqda…");
      setUiState("thinking");
      await runTurn({
        session_id: SESSION_ID,
        agent_id: "default",
        transcript_override: "Salom! Ovoz testini o'tkazyapmiz, meni eshityapsizmi?",
        user_locale: "uz-Latn",
      });
      settingsStatus("Test javobi keldi.");
    } catch (err) {
      settingsStatus("Test xatosi: " + err.message);
      setUiState("idle");
    }
  });

  // ---------- Boot ----------
  (async function boot() {
    setUiState("booting");
    updateClock();
    setInterval(updateClock, 1000);
    rotateQuote();
    setInterval(rotateQuote, 30000);
    updateGreeting();
    setInterval(updateGreeting, 60000);
    typewriterTick();

    if (window.companion && window.companion.ensureBackend) {
      try {
        await window.companion.ensureBackend();
      } catch {
        // health polling davom etadi
      }
    }
    await refreshHealth();
    try {
      profile = await api("/profile");
      applyProfileToUi();
    } catch {
      // profil hali mavjud emas
    }
    await loadConversation();
    setInterval(refreshHealth, 5000);
    setInterval(async () => {
      try {
        const rs = await api("/runtime/state");
        setDiag("diag-state", rs.state);
      } catch {
        setDiag("diag-state", "aloqa yo'q");
      }
    }, 3000);
    // FPS (qabul mezoni: 55+). 3D avatar tayyor bo'lsa ko'rsatiladi.
    setInterval(() => {
      const av = window.Avatar3D;
      setDiag("diag-fps", av && av.getFps ? av.getFps() + " fps" : "2D rejim");
    }, 1000);
  })();
})();
