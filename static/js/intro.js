/* Intro JKVAL: progreso real, skip, teclado, movimiento reducido y audio sintetizado. */
(function () {
  "use strict";

  var overlay = document.getElementById("jkval-intro");
  if (!overlay) return;

  var STORAGE_KEY = "jkval:intro-seen:v2";
  var reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  var skipButton = overlay.querySelector("[data-intro-skip]");
  var soundButton = overlay.querySelector("[data-intro-sound]");
  var replayButton = overlay.querySelector("[data-intro-replay]");
  var video = overlay.querySelector("[data-intro-video]");
  var progress = document.getElementById("intro-progress");
  var main = document.getElementById("contenido");
  var rafId = 0;
  var startedAt = 0;
  var finished = false;
  var soundOn = false;
  var audioContext = null;
  var masterGain = null;
  var soundTimers = [];
  var previousFocus = document.activeElement;

  function duration() {
    return reducedQuery.matches ? 1400 : 5200;
  }

  function finish(skipped) {
    if (finished) return;
    finished = true;
    if (rafId) window.cancelAnimationFrame(rafId);
    soundTimers.forEach(function (id) { window.clearTimeout(id); });
    soundTimers = [];
    if (video) {
      try { video.pause(); } catch (error) { /* noop */ }
    }
    if (progress) progress.value = 100;
    overlay.classList.add("intro--done");
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("intro-lock");
    try {
      window.sessionStorage.setItem(STORAGE_KEY, "1");
    } catch (error) {
      /* almacenamiento no disponible: la intro se repetirá en la próxima página */
    }
    window.setTimeout(function () {
      overlay.hidden = true;
      var target = main || previousFocus;
      if (target && typeof target.focus === "function") {
        target.focus({ preventScroll: true });
      }
    }, 600);
    if (skipped) {
      overlay.dataset.skipped = "true";
    }
  }

  function tick(now) {
    if (finished) return;
    var elapsed = now - startedAt;
    var total = duration();
    if (progress) progress.value = Math.max(0, Math.min(100, (elapsed / total) * 100));
    if (elapsed >= total) {
      finish(false);
      return;
    }
    rafId = window.requestAnimationFrame(tick);
  }

  function startProgress() {
    startedAt = window.performance.now();
    if (progress) progress.value = 0;
    rafId = window.requestAnimationFrame(tick);
  }

  function ensureAudio() {
    if (audioContext) return true;
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return false;
    try {
      audioContext = new Ctx();
      masterGain = audioContext.createGain();
      masterGain.gain.value = 0.32;
      masterGain.connect(audioContext.destination);
      return true;
    } catch (error) {
      audioContext = null;
      return false;
    }
  }

  function noiseSource(seconds) {
    var length = Math.max(1, Math.floor(audioContext.sampleRate * seconds));
    var buffer = audioContext.createBuffer(1, length, audioContext.sampleRate);
    var data = buffer.getChannelData(0);
    for (var i = 0; i < length; i += 1) {
      data[i] = Math.random() * 2 - 1;
    }
    var source = audioContext.createBufferSource();
    source.buffer = buffer;
    return source;
  }

  function envelopeGain(peak, attack, decay) {
    var gain = audioContext.createGain();
    var now = audioContext.currentTime;
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak), now + attack);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + attack + decay);
    return gain;
  }

  function playWhoosh() {
    if (!ensureAudio()) return;
    var now = audioContext.currentTime;
    var source = noiseSource(1.1);
    var filter = audioContext.createBiquadFilter();
    filter.type = "bandpass";
    filter.Q.value = 1.1;
    filter.frequency.setValueAtTime(420, now);
    filter.frequency.exponentialRampToValueAtTime(2600, now + 0.75);
    var gain = envelopeGain(0.18, 0.08, 0.85);
    source.connect(filter);
    filter.connect(gain);
    gain.connect(masterGain);
    source.start(now);
    source.stop(now + 1.15);
  }

  function playSlash() {
    if (!ensureAudio()) return;
    var now = audioContext.currentTime;
    var source = noiseSource(0.24);
    var filter = audioContext.createBiquadFilter();
    filter.type = "highpass";
    filter.frequency.value = 1600;
    var gain = envelopeGain(0.24, 0.005, 0.2);
    source.connect(filter);
    filter.connect(gain);
    gain.connect(masterGain);
    source.start(now);
    source.stop(now + 0.26);

    var osc = audioContext.createOscillator();
    var oscGain = envelopeGain(0.12, 0.005, 0.22);
    osc.type = "sine";
    osc.frequency.setValueAtTime(1900, now);
    osc.frequency.exponentialRampToValueAtTime(240, now + 0.2);
    osc.connect(oscGain);
    oscGain.connect(masterGain);
    osc.start(now);
    osc.stop(now + 0.24);
  }

  function playChime() {
    if (!ensureAudio()) return;
    var now = audioContext.currentTime;
    [660, 990].forEach(function (freq, index) {
      var osc = audioContext.createOscillator();
      var gain = audioContext.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(0.075 - index * 0.02, now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.1);
      osc.connect(gain);
      gain.connect(masterGain);
      osc.start(now);
      osc.stop(now + 1.15);
    });
  }

  function clearSoundTimers() {
    soundTimers.forEach(function (id) { window.clearTimeout(id); });
    soundTimers = [];
  }

  function scheduleSequence(fromElapsed) {
    clearSoundTimers();
    if (!soundOn) return;
    var cues = [
      { at: 120, fn: playWhoosh },
      { at: overlay.classList.contains("intro--video") ? 1850 : 2350, fn: playSlash },
      { at: 4050, fn: playChime }
    ];
    var played = false;
    cues.forEach(function (cue) {
      if (cue.at >= fromElapsed) {
        played = true;
        soundTimers.push(window.setTimeout(cue.fn, Math.max(0, cue.at - fromElapsed)));
      }
    });
    if (!played) {
      soundTimers.push(window.setTimeout(playChime, 60));
    }
  }

  function setSoundLabel() {
    if (!soundButton) return;
    soundButton.setAttribute("aria-pressed", soundOn ? "true" : "false");
    soundButton.textContent = soundOn ? "Silenciar sonido" : "Activar sonido";
    if (replayButton) replayButton.hidden = !soundOn;
  }

  function toggleSound() {
    if (!ensureAudio()) {
      if (soundButton) {
        soundButton.disabled = true;
        soundButton.textContent = "Audio no disponible";
        soundButton.title = "Este navegador no permite Web Audio.";
      }
      return;
    }
    soundOn = !soundOn;
    setSoundLabel();
    if (soundOn) {
      if (audioContext.state === "suspended") audioContext.resume();
      var elapsed = finished ? 0 : Math.max(0, window.performance.now() - startedAt);
      if (elapsed < duration()) {
        scheduleSequence(elapsed);
        if (elapsed < 150) {
          /* el whoosh ya está programado por scheduleSequence */
        }
      } else {
        playChime();
      }
    } else {
      clearSoundTimers();
    }
  }

  function replaySound() {
    if (!ensureAudio()) return;
    if (!soundOn) {
      soundOn = true;
      setSoundLabel();
    }
    if (audioContext.state === "suspended") audioContext.resume();
    scheduleSequence(0);
  }

  function onKeydown(event) {
    if (finished) return;
    if (event.key === "Escape") {
      event.preventDefault();
      finish(true);
      return;
    }
    if ((event.key === "Enter" || event.key === " " || event.key === "Spacebar") && document.activeElement === overlay) {
      event.preventDefault();
      finish(true);
      return;
    }
    if (event.key === "Tab") {
      var focusables = overlay.querySelectorAll("button:not([disabled]):not([hidden]), a[href]");
      if (!focusables.length) return;
      var first = focusables[0];
      var last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  function prepareVideo() {
    if (!video || reducedQuery.matches) return;
    video.muted = true;
    video.addEventListener("canplay", function () {
      overlay.classList.add("intro--video");
      var playing = video.play();
      if (playing && typeof playing.catch === "function") {
        playing.catch(function () {
          /* autoplay bloqueado: se conserva la animación de respaldo */
          overlay.classList.remove("intro--video");
        });
      }
    }, { once: true });
    video.addEventListener("error", function () {
      overlay.classList.remove("intro--video");
    }, { once: true });
    video.load();
  }

  function init() {
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("intro-lock");
    overlay.classList.add("is-active");
    if (reducedQuery.matches) overlay.classList.add("intro--reduced");
    prepareVideo();
    setSoundLabel();
    if (skipButton) skipButton.focus({ preventScroll: true });
    startProgress();
    if (skipButton) skipButton.addEventListener("click", function () { finish(true); });
    if (soundButton) soundButton.addEventListener("click", toggleSound);
    if (replayButton) replayButton.addEventListener("click", replaySound);
    document.addEventListener("keydown", onKeydown);
    reducedQuery.addEventListener("change", function () {
      overlay.classList.toggle("intro--reduced", reducedQuery.matches);
      if (reducedQuery.matches) {
        overlay.classList.remove("intro--video");
        if (video) {
          try { video.pause(); } catch (error) { /* noop */ }
        }
      }
    });
    window.addEventListener("pagehide", function () {
      if (!finished) {
        try { window.sessionStorage.setItem(STORAGE_KEY, "1"); } catch (error) { /* noop */ }
      }
    });
  }

  var alreadySeen = false;
  try {
    alreadySeen = window.sessionStorage.getItem(STORAGE_KEY) === "1";
  } catch (error) {
    alreadySeen = false;
  }
  if (alreadySeen) {
    overlay.hidden = true;
    return;
  }

  try {
    init();
  } catch (error) {
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("intro-lock");
  }
})();
