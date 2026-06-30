function setFatigueStatus(message, status = "") {
  if (elements.fatigueConnectionStatus) {
    elements.fatigueConnectionStatus.textContent = message;
  }
  if (elements.fatigueStatusDot) {
    elements.fatigueStatusDot.className = `fatigue-status-dot ${status}`;
  }
}

function setFatigueButtonLoading(button, isLoading, label) {
  button.disabled = isLoading;
  button.textContent = isLoading ? "..." : label;
}

function openFatigueMonitor() {
  elements.fatigueMonitor.classList.remove("hidden");
  elements.fatigueMonitor.setAttribute("aria-hidden", "false");
  setActiveSidebarAction(elements.fatigueButton);
  closeSidebar();
  syncFatigueCanvasSize();
}

function closeFatigueMonitor() {
  stopFatigueDetection();
  elements.fatigueMonitor.classList.add("hidden");
  elements.fatigueMonitor.setAttribute("aria-hidden", "true");
  syncActiveSidebarAction();
}

async function startFatigueDetection() {
  state.fatigue.userStoppedDetection = false;
  setFatigueButtonLoading(elements.fatigueStartButton, true, "Start");
  elements.fatigueStopButton.disabled = true;
  setFatigueStatus("Requesting camera access", "warning");

  try {
    state.fatigue.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: "user",
      },
      audio: false,
    });

    elements.fatigueWebcam.srcObject = state.fatigue.stream;
    await elements.fatigueWebcam.play();
    elements.fatigueEmptyState.classList.add("hidden");
    elements.fatigueStopButton.disabled = false;
    syncFatigueCanvasSize();
    connectFatigueWebSocket();
  } catch (error) {
    setFatigueStatus("Camera access failed", "error");
    elements.fatigueFaceStatus.textContent = "Unable to access camera";
    setFatigueButtonLoading(elements.fatigueStartButton, false, "Start");
    elements.fatigueStopButton.disabled = true;
  }
}

function stopFatigueDetection() {
  state.fatigue.userStoppedDetection = true;
  state.fatigue.alertLocked = false;
  state.fatigue.awaitingResponse = false;
  stopFatigueFrameLoop();

  if (state.fatigue.socket) {
    state.fatigue.socket.close();
    state.fatigue.socket = null;
  }

  if (state.fatigue.stream) {
    state.fatigue.stream.getTracks().forEach((track) => track.stop());
    state.fatigue.stream = null;
  }

  elements.fatigueWebcam.srcObject = null;
  elements.fatigueAlertModal.classList.add("hidden");
  elements.fatigueAlertModal.setAttribute("aria-hidden", "true");
  elements.fatigueEmptyState.classList.remove("hidden");
  fatigueOverlayCtx.clearRect(0, 0, elements.fatigueOverlay.width, elements.fatigueOverlay.height);
  updateFatigueScore("Unknown", 0);
  updateFatigueCounters({});
  updateFatigueSymptoms([]);
  elements.fatigueFaceStatus.textContent = "No camera stream";
  setFatigueStatus("Detection stopped", "ready");
  setFatigueButtonLoading(elements.fatigueStartButton, false, "Start");
  elements.fatigueStopButton.disabled = true;
}

function connectFatigueWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.host || "127.0.0.1:8000";
  state.fatigue.socket = new WebSocket(`${protocol}://${host}/ws/fatigue/detect`);

  state.fatigue.socket.addEventListener("open", () => {
    setFatigueStatus("Detection active", "connected");
    elements.fatigueFaceStatus.textContent = "Looking for face";
    setFatigueButtonLoading(elements.fatigueStartButton, false, "Start");
    elements.fatigueStartButton.disabled = true;
    elements.fatigueStopButton.disabled = false;
    startFatigueFrameLoop();
  });

  state.fatigue.socket.addEventListener("message", (event) => {
    state.fatigue.awaitingResponse = false;
    updateFatigueDashboard(JSON.parse(event.data));
  });

  state.fatigue.socket.addEventListener("close", () => {
    stopFatigueFrameLoop();
    state.fatigue.awaitingResponse = false;
    if (state.fatigue.userStoppedDetection) {
      return;
    }

    if (!state.fatigue.alertLocked) {
      setFatigueStatus("Connection closed", "error");
      elements.fatigueStartButton.disabled = false;
      elements.fatigueStopButton.disabled = !state.fatigue.stream;
    }
  });

  state.fatigue.socket.addEventListener("error", () => {
    setFatigueStatus("Backend connection failed", "error");
    elements.fatigueStartButton.disabled = false;
    elements.fatigueStopButton.disabled = !state.fatigue.stream;
  });
}

function startFatigueFrameLoop() {
  stopFatigueFrameLoop();
  state.fatigue.frameTimer = window.setInterval(sendFatigueFrame, 140);
}

function stopFatigueFrameLoop() {
  if (state.fatigue.frameTimer) {
    window.clearInterval(state.fatigue.frameTimer);
    state.fatigue.frameTimer = null;
  }
}

function sendFatigueFrame() {
  if (
    state.fatigue.alertLocked ||
    state.fatigue.awaitingResponse ||
    !state.fatigue.socket ||
    state.fatigue.socket.readyState !== WebSocket.OPEN ||
    elements.fatigueWebcam.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
  ) {
    return;
  }

  const width = elements.fatigueWebcam.videoWidth;
  const height = elements.fatigueWebcam.videoHeight;
  if (!width || !height) {
    return;
  }

  fatigueCaptureCanvas.width = 640;
  fatigueCaptureCanvas.height = Math.round((height / width) * fatigueCaptureCanvas.width);
  fatigueCaptureCtx.drawImage(
    elements.fatigueWebcam,
    0,
    0,
    fatigueCaptureCanvas.width,
    fatigueCaptureCanvas.height,
  );

  state.fatigue.awaitingResponse = true;
  state.fatigue.socket.send(
    JSON.stringify({
      frame: fatigueCaptureCanvas.toDataURL("image/jpeg", 0.72),
    }),
  );
}

function fatigueSeverityLabel(severity) {
  if (severity === "critical") {
    return "Critical Fatigue Alert";
  }
  if (severity === "high") {
    return "High Fatigue Alert";
  }
  return "Fatigue Alert";
}

function formatNotificationEta(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) {
    return "";
  }
  const minutes = Math.max(1, Math.round(value / 60));
  return `${minutes} min away`;
}

function formatNotificationDistance(distanceMeters) {
  const value = Number(distanceMeters);
  if (!Number.isFinite(value) || value <= 0) {
    return "";
  }
  if (value < 1000) {
    return `${Math.round(value)} m`;
  }
  return `${(value / 1000).toFixed(1)} km`;
}

function showFatigueNotification(notification) {
  state.centralAgent.pendingNotification = notification;
  state.fatigue.alertLocked = true;
  stopFatigueFrameLoop();
  setFatigueStatus("Fatigue rest recommendation", notification.severity === "warning" ? "warning" : "error");
  elements.fatigueAlertDialog.dataset.severity = notification.severity || "warning";

  elements.fatigueAlertEyebrow.textContent = fatigueSeverityLabel(notification.severity);
  elements.fatigueAlertTitle.textContent = notification.title || "Fatigue risk detected";
  elements.fatigueAlertMessage.textContent = notification.message || "Please consider taking a rest stop.";
  elements.fatigueAlertMessage.classList.remove("error");

  const eta = formatNotificationEta(notification.estimatedDriveSeconds);
  const distance = formatNotificationDistance(notification.distanceMeters);
  elements.fatigueRestMeta.textContent = [eta, distance].filter(Boolean).join(" / ") || "Recommended rest stop";
  elements.fatigueRestName.textContent = notification.place?.name || "Rest stop";
  elements.fatigueRestAddress.textContent = notification.place?.address || "Address unavailable";
  elements.fatigueRestCard.classList.remove("hidden");
  elements.fatigueRestAcceptButton.textContent = notification.primaryAction?.label || "Rest there";
  elements.fatigueAlertDismissButton.textContent = notification.secondaryAction?.label || "Not now";
  elements.fatigueRestAcceptButton.classList.remove("hidden");

  elements.fatigueAlertModal.classList.remove("hidden");
  elements.fatigueAlertModal.setAttribute("aria-hidden", "false");

  if (notification.severity === "high" || notification.severity === "critical") {
    clearActiveSymptomPill();
  }
}

function showGenericFatigueAlert() {
  state.centralAgent.pendingNotification = null;
  state.fatigue.alertLocked = true;
  stopFatigueFrameLoop();
  setFatigueStatus("Fatigue alert active", "error");
  elements.fatigueAlertDialog.dataset.severity = "high";

  elements.fatigueAlertEyebrow.textContent = "Fatigue Alert";
  elements.fatigueAlertTitle.textContent = "High fatigue risk detected";
  elements.fatigueAlertMessage.textContent = "The monitor is seeing signs of tiredness. Please pause and continue only when you feel alert.";
  elements.fatigueAlertMessage.classList.remove("error");
  elements.fatigueRestCard.classList.add("hidden");
  elements.fatigueRestAcceptButton.classList.add("hidden");
  elements.fatigueAlertDismissButton.textContent = "OK";

  elements.fatigueAlertModal.classList.remove("hidden");
  elements.fatigueAlertModal.setAttribute("aria-hidden", "false");
  clearActiveSymptomPill();
}

async function maybeRequestRestStopRecommendation(result) {
  const score = Number(result.fatigueScore) || 0;
  if (
    score < 50 ||
    !state.centralAgent.activeRouteId ||
    state.centralAgent.requestInFlight ||
    state.fatigue.alertLocked ||
    Date.now() < state.centralAgent.cooldownUntil
  ) {
    return false;
  }

  state.centralAgent.requestInFlight = true;
  try {
    const payload = await requestFatigueRecommendation(result);
    if (payload.notification) {
      showFatigueNotification(payload.notification);
      return true;
    }
  } catch (error) {
    console.warn("Central agent recommendation failed", error);
  } finally {
    state.centralAgent.requestInFlight = false;
  }

  return false;
}

function updateFatigueDashboard(result) {
  elements.fatigueFaceStatus.textContent = result.faceDetected ? "Face detected" : "No face detected";
  updateFatigueScore(result.fatigueLevel, result.fatigueScore);
  updateFatigueCounters(result.symptomCounts);
  updateFatigueSymptoms(result.symptoms, result.symptomCounts);
  drawFatigueLandmarks(result.landmarks || {});

  maybeRequestRestStopRecommendation(result).then((shownRecommendation) => {
    if (
      result.alert &&
      !shownRecommendation &&
      !state.fatigue.alertLocked &&
      !state.centralAgent.requestInFlight &&
      Date.now() >= state.centralAgent.cooldownUntil
    ) {
      showGenericFatigueAlert();
    }
  });
}

function hideFatigueAlertAndResume({ cooldown = true } = {}) {
  state.fatigue.alertLocked = false;
  state.centralAgent.pendingNotification = null;
  if (cooldown) {
    state.centralAgent.cooldownUntil = Date.now() + 5 * 60 * 1000;
  }
  elements.fatigueAlertModal.classList.add("hidden");
  elements.fatigueAlertModal.setAttribute("aria-hidden", "true");
  updateFatigueScore("Normal", 0);
  updateFatigueCounters({});
  updateFatigueSymptoms([]);
  fatigueOverlayCtx.clearRect(0, 0, elements.fatigueOverlay.width, elements.fatigueOverlay.height);
  setFatigueStatus("Detection active", "connected");

  if (state.fatigue.socket?.readyState === WebSocket.OPEN) {
    state.fatigue.socket.send(JSON.stringify({ action: "reset" }));
  }

  startFatigueFrameLoop();
}

function updateFatigueScore(level, score) {
  const safeScore = Number.isFinite(score) ? score : 0;
  elements.fatigueLevel.textContent = level || "Unknown";
  elements.fatigueScore.textContent = `${safeScore}%`;
  elements.fatigueScoreFill.style.width = `${Math.min(Math.max(safeScore, 0), 100)}%`;

  let color = "#22c55e";
  if (safeScore >= 75) {
    color = "#ef4444";
  } else if (safeScore >= 50) {
    color = "#f59e0b";
  } else if (safeScore >= 25) {
    color = "#1685ff";
  }
  elements.fatigueScoreFill.style.background = color;
}

function updateFatigueCounters(counts = {}) {
  elements.fatigueEyeCount.textContent = counts.eyeClosures || 0;
  elements.fatigueBlinkCount.textContent = counts.blinks || 0;
  elements.fatigueYawnCount.textContent = counts.yawns || 0;
  elements.fatigueNodCount.textContent = counts.headNods || 0;
}

function formatFatigueSymptom(symptom, counts = {}) {
  const countBySymptom = {
    "Eyes closed too long": counts.eyeClosures,
    Yawning: counts.yawns,
    "Head nodding": counts.headNods,
  };
  const count = countBySymptom[symptom];
  return count ? `${symptom} x${count}` : symptom;
}

const fatigueSymptomOrder = ["Eyes closed too long", "Yawning", "Head nodding"];

function ensureFatigueSymptomState() {
  if (
    !state.fatigue.detectedSymptoms ||
    Array.isArray(state.fatigue.detectedSymptoms)
  ) {
    const previousSymptoms = Array.isArray(state.fatigue.detectedSymptoms)
      ? state.fatigue.detectedSymptoms
      : [];
    state.fatigue.detectedSymptoms = {
      "Eyes closed too long": previousSymptoms.includes("Eyes closed too long"),
      Yawning: previousSymptoms.includes("Yawning"),
      "Head nodding": previousSymptoms.includes("Head nodding"),
    };
  }
}

function fatigueSymptomsFromCounts(counts = {}) {
  const symptoms = [];
  if ((counts.eyeClosures || 0) > 0) {
    symptoms.push("Eyes closed too long");
  }
  if ((counts.yawns || 0) > 0) {
    symptoms.push("Yawning");
  }
  if ((counts.headNods || 0) > 0) {
    symptoms.push("Head nodding");
  }
  return symptoms;
}

function areFatigueSymptomCountsReset(counts = {}) {
  return (
    (counts.eyeClosures || 0) === 0 &&
    (counts.yawns || 0) === 0 &&
    (counts.headNods || 0) === 0
  );
}

function resetFatigueSymptoms() {
  ensureFatigueSymptomState();
  fatigueSymptomOrder.forEach((symptom) => {
    state.fatigue.detectedSymptoms[symptom] = false;
  });
}

function clearActiveSymptomPill() {
  resetFatigueSymptoms();
  updateFatigueSymptoms([]);
}

function updateFatigueSymptoms(symptoms, counts = {}) {
  ensureFatigueSymptomState();
  const nextSymptoms = [
    ...(Array.isArray(symptoms) ? symptoms : []),
    ...fatigueSymptomsFromCounts(counts),
  ];

  if (nextSymptoms.length === 0 && areFatigueSymptomCountsReset(counts)) {
    resetFatigueSymptoms();
  }

  nextSymptoms.forEach((symptom) => {
    if (symptom in state.fatigue.detectedSymptoms) {
      state.fatigue.detectedSymptoms[symptom] = true;
    }
  });

  elements.fatigueSymptomsList.innerHTML = "";
  const latchedSymptoms = fatigueSymptomOrder.filter((symptom) => state.fatigue.detectedSymptoms[symptom]);

  if (latchedSymptoms.length === 0) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = "No symptoms detected";
    elements.fatigueSymptomsList.appendChild(emptyItem);
    return;
  }

  latchedSymptoms.forEach((symptom) => {
    const item = document.createElement("li");
    item.className = "active";
    item.textContent = formatFatigueSymptom(symptom, counts);
    elements.fatigueSymptomsList.appendChild(item);
  });
}

function drawFatigueLandmarks(landmarks) {
  syncFatigueCanvasSize();
  fatigueOverlayCtx.clearRect(0, 0, elements.fatigueOverlay.width, elements.fatigueOverlay.height);

  drawFatigueFeature(landmarks.leftEye, fatigueLandmarkColors.leftEye, true);
  drawFatigueFeature(landmarks.rightEye, fatigueLandmarkColors.rightEye, true);
  drawFatigueFeature(landmarks.nose, fatigueLandmarkColors.nose, true);
  drawFatigueFeature(landmarks.leftEar, fatigueLandmarkColors.leftEar, false);
  drawFatigueFeature(landmarks.rightEar, fatigueLandmarkColors.rightEar, false);
}

function drawFatigueFeature(points, color, connect) {
  if (!Array.isArray(points) || points.length === 0) {
    return;
  }

  const scaled = points.map((point) => ({
    x: point.x * elements.fatigueOverlay.width,
    y: point.y * elements.fatigueOverlay.height,
  }));

  fatigueOverlayCtx.save();
  fatigueOverlayCtx.strokeStyle = color;
  fatigueOverlayCtx.fillStyle = color;
  fatigueOverlayCtx.lineWidth = 3;
  fatigueOverlayCtx.shadowColor = "rgba(0, 0, 0, 0.38)";
  fatigueOverlayCtx.shadowBlur = 8;

  if (connect && scaled.length > 1) {
    fatigueOverlayCtx.beginPath();
    scaled.forEach((point, index) => {
      if (index === 0) {
        fatigueOverlayCtx.moveTo(point.x, point.y);
      } else {
        fatigueOverlayCtx.lineTo(point.x, point.y);
      }
    });
    fatigueOverlayCtx.closePath();
    fatigueOverlayCtx.stroke();
  }

  scaled.forEach((point) => {
    fatigueOverlayCtx.beginPath();
    fatigueOverlayCtx.arc(point.x, point.y, 4, 0, Math.PI * 2);
    fatigueOverlayCtx.fill();
  });

  fatigueOverlayCtx.restore();
}

async function acceptFatigueRestStop() {
  const notification = state.centralAgent.pendingNotification;
  if (!notification) {
    hideFatigueAlertAndResume({ cooldown: true });
    return;
  }

  setFatigueButtonLoading(elements.fatigueRestAcceptButton, true, "Rest there");
  elements.fatigueAlertDismissButton.disabled = true;
  try {
    const route = await acceptRestStopRecommendation(notification);
    await renderRoute(route);
    hideFatigueAlertAndResume({ cooldown: false });
    setStatus("Rest stop added to your route.");
  } catch (error) {
    elements.fatigueAlertMessage.textContent = error.message || "Could not add that rest stop. Please try again.";
    elements.fatigueAlertMessage.classList.add("error");
  } finally {
    setFatigueButtonLoading(elements.fatigueRestAcceptButton, false, "Rest there");
    elements.fatigueAlertDismissButton.disabled = false;
  }
}

function dismissFatigueAlert() {
  elements.fatigueAlertMessage.classList.remove("error");
  hideFatigueAlertAndResume({ cooldown: false });
}

function syncFatigueCanvasSize() {
  const rect = elements.fatigueWebcam.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));

  if (elements.fatigueOverlay.width !== width || elements.fatigueOverlay.height !== height) {
    elements.fatigueOverlay.width = width;
    elements.fatigueOverlay.height = height;
  }
}

function clampFatigueMonitorPosition(left, top) {
  const rect = elements.fatigueMonitor.getBoundingClientRect();
  const padding = 12;
  const maxLeft = Math.max(padding, window.innerWidth - rect.width - padding);
  const maxTop = Math.max(padding, window.innerHeight - rect.height - padding);
  return {
    left: Math.min(Math.max(padding, left), maxLeft),
    top: Math.min(Math.max(padding, top), maxTop),
  };
}

function moveFatigueMonitor(clientX, clientY) {
  const position = clampFatigueMonitorPosition(
    clientX - state.fatigue.dragOffsetX,
    clientY - state.fatigue.dragOffsetY,
  );
  elements.fatigueMonitor.style.left = `${position.left}px`;
  elements.fatigueMonitor.style.top = `${position.top}px`;
  elements.fatigueMonitor.style.right = "auto";
}

function startFatigueDrag(event) {
  if (event.target.closest("button")) {
    return;
  }
  const pointer = event.touches ? event.touches[0] : event;
  const rect = elements.fatigueMonitor.getBoundingClientRect();
  state.fatigue.isDragging = true;
  state.fatigue.dragOffsetX = pointer.clientX - rect.left;
  state.fatigue.dragOffsetY = pointer.clientY - rect.top;
  elements.fatigueMonitor.classList.add("is-dragging");
}

function dragFatigueMonitor(event) {
  if (!state.fatigue.isDragging) {
    return;
  }
  const pointer = event.touches ? event.touches[0] : event;
  if (!pointer) {
    return;
  }
  event.preventDefault();
  moveFatigueMonitor(pointer.clientX, pointer.clientY);
}

function stopFatigueDrag() {
  state.fatigue.isDragging = false;
  elements.fatigueMonitor.classList.remove("is-dragging");
}

