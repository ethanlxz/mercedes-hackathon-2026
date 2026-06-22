const video = document.getElementById("webcam");
const overlay = document.getElementById("overlay");
const ctx = overlay.getContext("2d");
const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const connectionStatus = document.getElementById("connectionStatus");
const statusDot = document.getElementById("statusDot");
const faceStatus = document.getElementById("faceStatus");
const emptyState = document.getElementById("emptyState");
const fatigueLevel = document.getElementById("fatigueLevel");
const fatigueScore = document.getElementById("fatigueScore");
const scoreFill = document.getElementById("scoreFill");
const symptomsList = document.getElementById("symptomsList");
const alertBackdrop = document.getElementById("alertBackdrop");
const alertOkButton = document.getElementById("alertOkButton");
const eyeClosureCount = document.getElementById("eyeClosureCount");
const blinkCount = document.getElementById("blinkCount");
const yawnCount = document.getElementById("yawnCount");
const headNodCount = document.getElementById("headNodCount");

const captureCanvas = document.createElement("canvas");
const captureCtx = captureCanvas.getContext("2d");

let stream = null;
let socket = null;
let frameTimer = null;
let awaitingResponse = false;
let alertLocked = false;
let userStoppedDetection = false;

const colors = {
  leftEye: "#2563eb",
  rightEye: "#0891b2",
  nose: "#f59e0b",
  leftEar: "#7c3aed",
  rightEar: "#dc2626",
};

startButton.addEventListener("click", startDetecting);
stopButton.addEventListener("click", stopDetecting);
alertOkButton.addEventListener("click", restartAfterAlert);
window.addEventListener("resize", syncCanvasSize);

async function startDetecting() {
  userStoppedDetection = false;
  startButton.disabled = true;
  stopButton.disabled = true;
  setStatus("Requesting camera access", "warning");

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
      audio: false,
    });

    video.srcObject = stream;
    await video.play();
    emptyState.classList.add("is-hidden");
    stopButton.disabled = false;
    syncCanvasSize();
    connectWebSocket();
  } catch (error) {
    setStatus("Camera access failed", "error");
    faceStatus.textContent = "Unable to access camera";
    startButton.disabled = false;
    stopButton.disabled = true;
  }
}

function stopDetecting() {
  userStoppedDetection = true;
  alertLocked = false;
  awaitingResponse = false;
  stopFrameLoop();

  if (socket) {
    socket.close();
    socket = null;
  }

  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }

  video.srcObject = null;
  alertBackdrop.classList.remove("is-visible");
  emptyState.classList.remove("is-hidden");
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  updateScore("Unknown", 0);
  updateCounters({});
  updateSymptoms([]);
  faceStatus.textContent = "No camera stream";
  setStatus("Detection stopped", "ready");
  startButton.disabled = false;
  stopButton.disabled = true;
}

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.host || "127.0.0.1:8000";

  socket = new WebSocket(`${protocol}://${host}/ws/detect`);

  socket.addEventListener("open", () => {
    setStatus("Detection active", "connected");
    faceStatus.textContent = "Looking for face";
    stopButton.disabled = false;
    startFrameLoop();
  });

  socket.addEventListener("message", (event) => {
    awaitingResponse = false;
    const result = JSON.parse(event.data);
    updateDashboard(result);
  });

  socket.addEventListener("close", () => {
    stopFrameLoop();
    awaitingResponse = false;
    if (userStoppedDetection) {
      return;
    }

    if (!alertLocked) {
      setStatus("Connection closed", "error");
      startButton.disabled = false;
      stopButton.disabled = !stream;
    }
  });

  socket.addEventListener("error", () => {
    setStatus("Backend connection failed", "error");
    startButton.disabled = false;
    stopButton.disabled = !stream;
  });
}

function startFrameLoop() {
  stopFrameLoop();
  frameTimer = window.setInterval(sendCurrentFrame, 140);
}

function stopFrameLoop() {
  if (frameTimer) {
    window.clearInterval(frameTimer);
    frameTimer = null;
  }
}

function sendCurrentFrame() {
  if (
    alertLocked ||
    awaitingResponse ||
    !socket ||
    socket.readyState !== WebSocket.OPEN ||
    video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
  ) {
    return;
  }

  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) {
    return;
  }

  captureCanvas.width = 640;
  captureCanvas.height = Math.round((height / width) * captureCanvas.width);
  captureCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);

  awaitingResponse = true;
  socket.send(
    JSON.stringify({
      frame: captureCanvas.toDataURL("image/jpeg", 0.72),
    })
  );
}

function updateDashboard(result) {
  faceStatus.textContent = result.faceDetected ? "Face detected" : "No face detected";

  updateScore(result.fatigueLevel, result.fatigueScore);
  updateCounters(result.symptomCounts);
  updateSymptoms(result.symptoms, result.symptomCounts);
  drawLandmarks(result.landmarks || {});

  if (result.alert && !alertLocked) {
    alertLocked = true;
    stopFrameLoop();
    setStatus("Fatigue alert active", "error");
    alertBackdrop.classList.add("is-visible");
  }
}

function updateScore(level, score) {
  const safeScore = Number.isFinite(score) ? score : 0;

  fatigueLevel.textContent = level || "Unknown";
  fatigueScore.textContent = `${safeScore}%`;
  scoreFill.style.width = `${Math.min(Math.max(safeScore, 0), 100)}%`;

  let color = "#16a34a";
  if (safeScore >= 75) color = "#dc2626";
  else if (safeScore >= 50) color = "#f59e0b";
  else if (safeScore >= 25) color = "#2563eb";

  scoreFill.style.background = color;
}

function updateSymptoms(symptoms, counts = {}) {
  symptomsList.innerHTML = "";

  if (!symptoms || symptoms.length === 0) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = "No symptoms detected";
    symptomsList.appendChild(emptyItem);
    return;
  }

  symptoms.forEach((symptom) => {
    const item = document.createElement("li");
    item.className = "active";
    item.textContent = formatSymptom(symptom, counts);
    symptomsList.appendChild(item);
  });
}

function updateCounters(counts = {}) {
  eyeClosureCount.textContent = counts.eyeClosures || 0;
  blinkCount.textContent = counts.blinks || 0;
  yawnCount.textContent = counts.yawns || 0;
  headNodCount.textContent = counts.headNods || 0;
}

function formatSymptom(symptom, counts = {}) {
  const countBySymptom = {
    "Eyes closed too long": counts.eyeClosures,
    "Frequent blinking": counts.blinks,
    Yawning: counts.yawns,
    "Head nodding": counts.headNods,
  };
  const count = countBySymptom[symptom];
  return count ? `${symptom} x${count}` : symptom;
}

function drawLandmarks(landmarks) {
  syncCanvasSize();
  ctx.clearRect(0, 0, overlay.width, overlay.height);

  drawFeature(landmarks.leftEye, colors.leftEye, true);
  drawFeature(landmarks.rightEye, colors.rightEye, true);
  drawFeature(landmarks.nose, colors.nose, true);
  drawFeature(landmarks.leftEar, colors.leftEar, false);
  drawFeature(landmarks.rightEar, colors.rightEar, false);
}

function drawFeature(points, color, connect) {
  if (!Array.isArray(points) || points.length === 0) {
    return;
  }

  const scaled = points.map((point) => ({
    x: point.x * overlay.width,
    y: point.y * overlay.height,
  }));

  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 3;
  ctx.shadowColor = "rgba(15, 23, 42, 0.25)";
  ctx.shadowBlur = 8;

  if (connect && scaled.length > 1) {
    ctx.beginPath();
    scaled.forEach((point, index) => {
      if (index === 0) ctx.moveTo(point.x, point.y);
      else ctx.lineTo(point.x, point.y);
    });
    ctx.closePath();
    ctx.stroke();
  }

  scaled.forEach((point) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.restore();
}

function restartAfterAlert() {
  alertLocked = false;
  alertBackdrop.classList.remove("is-visible");
  updateScore("Normal", 0);
  updateCounters({});
  updateSymptoms([]);
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  setStatus("Detection active", "connected");

  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ action: "reset" }));
  }

  startFrameLoop();
}

function syncCanvasSize() {
  const rect = video.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));

  if (overlay.width !== width || overlay.height !== height) {
    overlay.width = width;
    overlay.height = height;
  }
}

function setStatus(message, state) {
  connectionStatus.textContent = message;
  statusDot.className = `status-dot ${state || ""}`;
}
