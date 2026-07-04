// Animatsion placeholder avatar (TZ AD-002: faqat erta plumbing bosqichi uchun;
// yakuniy MVP avatari Unreal/MetaHuman darajasida bo'ladi — bridge tayyor).
// Holatlar: idle | listening | thinking | speaking | error
// Lip-sync: setMouthLevel(0..1) — audio amplitudasidan keladi.

(function () {
  const canvas = document.getElementById("avatar-canvas");
  const ctx = canvas.getContext("2d");

  let state = "idle";
  let mood = "neutral";
  let mouthLevel = 0;
  let smoothMouth = 0;

  let blinkTimer = 0;
  let blinkPhase = 0; // 0 = open, 1 = closed
  let nextBlinkAt = 2 + Math.random() * 3;
  let clock = 0;

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  const MOOD_TINTS = {
    neutral: "#4f8cff",
    happy: "#35c26e",
    thoughtful: "#8f7bff",
    concerned: "#e8a13c",
    excited: "#ff7ba6",
    apologetic: "#5fb4c9",
    reassuring: "#5fb4c9",
  };

  function draw(dt) {
    clock += dt;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);

    // Scene background: soft radial glow behind the head.
    const tint = MOOD_TINTS[mood] || MOOD_TINTS.neutral;
    const bgGrad = ctx.createRadialGradient(w / 2, h * 0.42, 40, w / 2, h * 0.42, Math.max(w, h) * 0.7);
    bgGrad.addColorStop(0, "rgba(35, 45, 75, 0.9)");
    bgGrad.addColorStop(1, "rgba(11, 13, 20, 1)");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    const cx = w / 2;
    const cy = h * 0.44;
    const R = Math.min(w, h) * 0.21;

    // Idle breathing: the whole head gently floats (Unclaw "breathes between words" vibe).
    const breathe = Math.sin(clock * 1.4) * R * 0.015;
    const headY = cy + breathe;

    // Listening ring pulse.
    if (state === "listening") {
      const pulse = (clock % 1.2) / 1.2;
      ctx.beginPath();
      ctx.arc(cx, headY, R * (1.25 + pulse * 0.35), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(53, 194, 110, ${0.5 * (1 - pulse)})`;
      ctx.lineWidth = 3;
      ctx.stroke();
    }

    // Speaking aura.
    if (state === "speaking") {
      ctx.beginPath();
      ctx.arc(cx, headY, R * (1.18 + smoothMouth * 0.12), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(79, 140, 255, ${0.25 + smoothMouth * 0.4})`;
      ctx.lineWidth = 4;
      ctx.stroke();
    }

    // Head.
    const headGrad = ctx.createRadialGradient(cx - R * 0.3, headY - R * 0.4, R * 0.2, cx, headY, R * 1.15);
    headGrad.addColorStop(0, "#3a4258");
    headGrad.addColorStop(1, "#232a3c");
    ctx.beginPath();
    ctx.ellipse(cx, headY, R * 0.92, R, 0, 0, Math.PI * 2);
    ctx.fillStyle = headGrad;
    ctx.fill();
    ctx.strokeStyle = state === "error" ? "rgba(224, 82, 82, 0.8)" : "rgba(120, 140, 190, 0.35)";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Blink logic.
    blinkTimer += dt;
    if (blinkTimer > nextBlinkAt) {
      blinkPhase = Math.min(1, blinkPhase + dt * 14);
      if (blinkPhase >= 1) {
        blinkTimer = 0;
        nextBlinkAt = 2 + Math.random() * 3.5;
        blinkPhase = 0;
      }
    } else {
      blinkPhase = Math.max(0, blinkPhase - dt * 14);
    }
    const eyeOpen = state === "error" ? 0.55 : 1 - blinkPhase;

    // Gaze: thinking looks up-left; listening looks straight, subtle wander otherwise.
    let gx = Math.sin(clock * 0.5) * R * 0.02;
    let gy = Math.cos(clock * 0.7) * R * 0.015;
    if (state === "thinking") { gx = -R * 0.05; gy = -R * 0.07; }
    if (state === "listening") { gx = 0; gy = 0; }

    const eyeY = headY - R * 0.18;
    const eyeDX = R * 0.34;
    const eyeRX = R * 0.13;
    const eyeRY = R * 0.085 * Math.max(0.08, eyeOpen);

    for (const side of [-1, 1]) {
      const ex = cx + side * eyeDX;
      // Sclera.
      ctx.beginPath();
      ctx.ellipse(ex, eyeY, eyeRX, eyeRY, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#dfe6f2";
      ctx.fill();
      // Iris/pupil.
      if (eyeOpen > 0.25) {
        ctx.beginPath();
        ctx.ellipse(ex + gx, eyeY + gy, eyeRX * 0.42, eyeRY * 0.7, 0, 0, Math.PI * 2);
        ctx.fillStyle = tint;
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(ex + gx, eyeY + gy, eyeRX * 0.18, eyeRY * 0.32, 0, 0, Math.PI * 2);
        ctx.fillStyle = "#10131c";
        ctx.fill();
      }
      // Brow: thinking raises inner edge, concerned tilts down.
      const browLift = state === "thinking" ? -R * 0.045 : mood === "concerned" ? R * 0.02 : 0;
      ctx.beginPath();
      ctx.moveTo(ex - eyeRX, eyeY - R * 0.11 + (side === -1 ? browLift : 0));
      ctx.quadraticCurveTo(ex, eyeY - R * 0.16 + browLift, ex + eyeRX, eyeY - R * 0.11 + (side === 1 ? browLift : 0));
      ctx.strokeStyle = "rgba(200, 212, 235, 0.75)";
      ctx.lineWidth = Math.max(2, R * 0.025);
      ctx.lineCap = "round";
      ctx.stroke();
    }

    // Mouth: amplitude-driven when speaking; subtle smile otherwise.
    const target = state === "speaking" ? mouthLevel : 0;
    smoothMouth += (target - smoothMouth) * Math.min(1, dt * 18);
    const mouthY = headY + R * 0.42;
    const mouthW = R * 0.34 * (1 + smoothMouth * 0.25);
    const mouthH = Math.max(R * 0.015, smoothMouth * R * 0.22);

    ctx.beginPath();
    if (state === "speaking" && smoothMouth > 0.04) {
      ctx.ellipse(cx, mouthY, mouthW, mouthH, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#141824";
      ctx.fill();
      ctx.strokeStyle = "rgba(200, 212, 235, 0.6)";
      ctx.lineWidth = 2;
      ctx.stroke();
      // Upper teeth hint for wide open mouth.
      if (smoothMouth > 0.45) {
        ctx.beginPath();
        ctx.ellipse(cx, mouthY - mouthH * 0.55, mouthW * 0.7, mouthH * 0.28, 0, 0, Math.PI);
        ctx.fillStyle = "rgba(230, 236, 246, 0.85)";
        ctx.fill();
      }
    } else {
      const smile = mood === "happy" || mood === "excited" ? R * 0.07 : mood === "concerned" ? -R * 0.03 : R * 0.03;
      ctx.moveTo(cx - mouthW, mouthY);
      ctx.quadraticCurveTo(cx, mouthY + smile, cx + mouthW, mouthY);
      ctx.strokeStyle = "rgba(200, 212, 235, 0.7)";
      ctx.lineWidth = Math.max(2, R * 0.03);
      ctx.lineCap = "round";
      ctx.stroke();
    }

    // Thinking dots.
    if (state === "thinking") {
      const dotBase = clock * 2.2;
      for (let i = 0; i < 3; i++) {
        const alpha = 0.25 + 0.75 * Math.max(0, Math.sin(dotBase - i * 0.6));
        ctx.beginPath();
        ctx.arc(cx + R * 1.45 + i * R * 0.16, headY - R * 0.9, R * 0.045, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(232, 161, 60, ${alpha})`;
        ctx.fill();
      }
    }
  }

  let lastTime = performance.now();
  function loop(now) {
    const dt = Math.min(0.05, (now - lastTime) / 1000);
    lastTime = now;
    draw(dt);
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  window.Avatar = {
    setState(next) { state = next; },
    setMood(next) { mood = next || "neutral"; },
    setMouthLevel(level) { mouthLevel = Math.max(0, Math.min(1, level)); },
    // 3D aniq muvaffaqiyatsiz bo'lganda darhol ko'rsatish uchun.
    showFallback() { canvas.classList.add("visible"); },
  };

  // 2D yuz faqat zaxira: 6 soniyada 3D tayyor bo'lmasa (sekin tarmoq/oflayn)
  // silliq paydo bo'ladi. 3D kelsa u allaqachon display:none qilib qo'yadi.
  setTimeout(() => {
    if (!(window.Avatar3D && window.Avatar3D.ready)) {
      canvas.classList.add("visible");
    }
  }, 6000);
})();
