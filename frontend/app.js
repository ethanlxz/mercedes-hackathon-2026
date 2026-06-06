// -------------------------------------------------------------
// MBUX Mobility Assistant - Frontend JS Logic
// -------------------------------------------------------------

const BACKEND_URL = "http://127.0.0.1:8000";

// Simulation State Variables
let speedVal = 110;
let batteryVal = 100;
let fatigueStr = "Low";
let fatigueVal = 10; // 0 to 100 scale internally
let cabinTemp = 22.5;
let walletBalance = 150.0;
let routeActive = false;
let isDriving = false;
let currentCoordinateIndex = 0;
let simSpeedMultiplier = 10;
let simulationInterval = null;

// Map & Markers
let map = null;
let carMarker = null;
let routePolyline = null;
let mapTiles = null;
let markersGroup = null;

// Waypoints (KL -> Penang Segment Details)
const WAYPOINTS = {
  KL: { name: "Kuala Lumpur", coords: [3.1390, 101.6869], color: "#00ffcc" },
  Rawang: { name: "Rawang", coords: [3.3224, 101.5739] },
  TanjungMalim: { name: "Tanjung Malim", coords: [3.6826, 101.5204] },
  Tapah: { name: "Shell Recharge Tapah (Charging Stop)", coords: [4.2008, 101.2618], isCharger: true },
  Ipoh: { name: "Starbucks Ipoh (Rest Stop)", coords: [4.5975, 101.0901], isRestStop: true },
  Taiping: { name: "Taiping", coords: [4.8513, 100.7410] },
  Penang: { name: "Penang (Destination)", coords: [5.4141, 100.3288], color: "#bf5af2" }
};

// Compile full smooth driving path by interpolating segment coordinates
let routeCoordinates = [];

function initRouteCoordinates() {
  const segments = [
    [WAYPOINTS.KL.coords, WAYPOINTS.Rawang.coords, 25],
    [WAYPOINTS.Rawang.coords, WAYPOINTS.TanjungMalim.coords, 30],
    [WAYPOINTS.TanjungMalim.coords, WAYPOINTS.Tapah.coords, 40],
    [WAYPOINTS.Tapah.coords, WAYPOINTS.Ipoh.coords, 35],
    [WAYPOINTS.Ipoh.coords, WAYPOINTS.Taiping.coords, 30],
    [WAYPOINTS.Taiping.coords, WAYPOINTS.Penang.coords, 40]
  ];

  routeCoordinates = [];
  segments.forEach(segment => {
    const [start, end, steps] = segment;
    for (let i = 0; i < steps; i++) {
      const lat = start[0] + (end[0] - start[0]) * (i / steps);
      const lng = start[1] + (end[1] - start[1]) * (i / steps);
      routeCoordinates.push([lat, lng]);
    }
  });
  // Add the absolute destination point
  routeCoordinates.push(WAYPOINTS.Penang.coords);
}

// -------------------------------------------------------------
// Initialization & Map Rendering
// -------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initRouteCoordinates();
  initMap();
  initClock();
  syncWalletBalance();
  
  // Set up speed slider input event
  document.getElementById("speed-slider").addEventListener("input", (e) => {
    speedVal = parseInt(e.target.value);
    document.getElementById("speed-val").innerText = speedVal;
    updateSpeedRadialGauge();
  });
  
  // Set up battery slider input event
  document.getElementById("battery-slider").addEventListener("input", (e) => {
    batteryVal = parseInt(e.target.value);
    updateUI();
  });
  
  document.getElementById("battery-slider").addEventListener("change", (e) => {
    syncWithBackend();
    // Intentionally not calling `queryAgent()` here to avoid extra API usage
  });

  // Load favorite memory stops
  loadMemoryStops();

  // Quick initial API sync and agent check
  // Only sync state on load; do not query the agent until simulation start
  syncWithBackend();
});

function initMap() {
  // Center map around Malaysia route coordinates
  map = L.map('map', {
    zoomControl: true,
    attributionControl: false
  }).setView([3.8, 101.2], 8);

  // Premium CARTO Dark Matter Tiles
  mapTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
  }).addTo(map);

  markersGroup = L.layerGroup().addTo(map);

  // Add icons and markers for landmarks
  // Origin (KL)
  L.circleMarker(WAYPOINTS.KL.coords, {
    radius: 7,
    color: '#00ffd2',
    fillColor: '#00ffd2',
    fillOpacity: 1,
    weight: 2
  }).addTo(markersGroup).bindPopup("<b>Origin:</b> Kuala Lumpur");

  // Destination (Penang)
  L.circleMarker(WAYPOINTS.Penang.coords, {
    radius: 7,
    color: '#bf5af2',
    fillColor: '#bf5af2',
    fillOpacity: 1,
    weight: 2
  }).addTo(markersGroup).bindPopup("<b>Destination:</b> Penang");

  // Charge Stop (Tapah)
  L.circleMarker(WAYPOINTS.Tapah.coords, {
    radius: 6,
    color: '#0a84ff',
    fillColor: '#0a84ff',
    fillOpacity: 0.6,
    weight: 1
  }).addTo(markersGroup).bindPopup("<b>EV Fast Charger:</b> Shell Recharge Tapah");

  // Rest Stop (Ipoh)
  L.circleMarker(WAYPOINTS.Ipoh.coords, {
    radius: 6,
    color: '#ff9f0a',
    fillColor: '#ff9f0a',
    fillOpacity: 0.6,
    weight: 1
  }).addTo(markersGroup).bindPopup("<b>Rest Area:</b> Starbucks Ipoh");

  // Polyline for full route
  routePolyline = L.polyline(routeCoordinates, {
    color: 'rgba(255, 255, 255, 0.15)',
    weight: 4,
    dashArray: '5, 8'
  }).addTo(map);

  // Vehicle Active Indicator Marker
  carMarker = L.circleMarker(WAYPOINTS.KL.coords, {
    radius: 9,
    color: '#00ffd2',
    fillColor: '#0b0d12',
    fillOpacity: 1,
    weight: 3,
    className: 'glow-vehicle'
  }).addTo(map);
  
  carMarker.bindPopup("<b>Mercedes EV Active</b>").openPopup();
}

function initClock() {
  const updateClock = () => {
    const now = new Date();
    let hours = now.getHours().toString().padStart(2, '0');
    let minutes = now.getMinutes().toString().padStart(2, '0');
    document.getElementById("clock-display").innerText = `${hours}:${minutes}`;
  };
  setInterval(updateClock, 1000);
  updateClock();
}

// -------------------------------------------------------------
// Core Drive Simulator Loop
// -------------------------------------------------------------
function toggleSimulation() {
  const btn = document.getElementById("btn-toggle-sim");
  
  if (isDriving) {
    // Pause driving
    isDriving = false;
    btn.innerHTML = `<i class="fa-solid fa-play"></i> Resume Trip Simulation`;
    btn.classList.remove("active");
    clearInterval(simulationInterval);
    addTransactionLog("System", "Trip simulation paused by driver.");
  } else {
    // Start driving
    isDriving = true;
    routeActive = true;
    btn.innerHTML = `<i class="fa-solid fa-pause"></i> Pause Trip Simulation`;
    btn.classList.add("active");
    document.getElementById("route-info-panel").style.display = "flex";
    
    // Highlight route line
    routePolyline.setStyle({
      color: 'var(--accent-cyan)',
      weight: 5,
      dashArray: null
    });
    
    addTransactionLog("System", "Drive simulation started. Route: KL to Penang.");
    
    // Call agent query once at start of simulation to get initial assessment
    queryAgent();

    simulationInterval = setInterval(simulationTick, 1000);
  }
}

function changeSimSpeed(val) {
  simSpeedMultiplier = parseInt(val);
  addTransactionLog("System", `Simulation speed adjusted to ${val}x.`);
  
  // Re-start interval if driving to adopt new multiplier speed immediately
  if (isDriving) {
    clearInterval(simulationInterval);
    simulationInterval = setInterval(simulationTick, 1000);
  }
}

function simulationTick() {
  if (!isDriving) return;

  // Move vehicle along route coordinates
  // Step size is determined by speed and multiplier
  // Moving 1 waypoint per tick represents a speed of ~100km/h at 10x multiplier
  let stepIncrement = Math.max(1, Math.round((speedVal / 110) * (simSpeedMultiplier / 10)));
  currentCoordinateIndex += stepIncrement;

  // Check if reached destination
  if (currentCoordinateIndex >= routeCoordinates.length - 1) {
    currentCoordinateIndex = routeCoordinates.length - 1;
    isDriving = false;
    clearInterval(simulationInterval);
    
    document.getElementById("btn-toggle-sim").innerHTML = `<i class="fa-solid fa-flag-checkered"></i> Destination Reached`;
    document.getElementById("btn-toggle-sim").disabled = true;
    document.getElementById("btn-toggle-sim").classList.remove("active");
    
    batteryVal = Math.max(5, batteryVal - 2); // Final discharge
    speedVal = 0;
    document.getElementById("speed-slider").value = 0;
    document.getElementById("speed-val").innerText = 0;
    updateSpeedRadialGauge();
    
    addTransactionLog("System", "Arrived at Penang. Ride summary: 350 km driven successfully.");
    appendChatBubble("MBUX Assistant", "We have arrived at your destination: Penang. I hope you enjoyed your drive! Wallet payments and trip parameters finalized.");
    syncWithBackend();
    return;
  }

  // Update position
  const currentPos = routeCoordinates[currentCoordinateIndex];
  carMarker.setLatLng(currentPos);
  
  // Dynamic map panning
  if (currentCoordinateIndex % 5 === 0) {
    map.panTo(currentPos);
  }

  // Energy consumption (roughly 0.12% per coordinate segment * speed factor)
  let energyDrain = 0.15 * (speedVal / 110) * stepIncrement;
  batteryVal = Math.max(0, batteryVal - energyDrain);
  
  // Fatigue progression (increases roughly 0.15% per tick * fatigue multiplier)
  if (document.getElementById("auto-fatigue").checked) {
    fatigueVal = Math.min(100, fatigueVal + (0.12 * stepIncrement));
    updateFatigueCategoryFromVal();
  }

  // Sync state to UI and backend
  updateUI();
  syncWithBackend();
}

function updateFatigueCategoryFromVal() {
  if (fatigueVal < 40) {
    fatigueStr = "Low";
  } else if (fatigueVal < 75) {
    fatigueStr = "Medium";
  } else {
    fatigueStr = "High";
  }
}

function onFatigueChange(val) {
  fatigueStr = val;
  if (val === "Low") fatigueVal = 15;
  else if (val === "Medium") fatigueVal = 55;
  else fatigueVal = 85;
  
  updateUI();
  syncWithBackend();
  // Do not call agent on manual fatigue changes to avoid extra API usage
  addTransactionLog("System", `Fatigue state manually simulated as: ${val}.`);
}

function adjustClimate(diff) {
  cabinTemp = parseFloat((cabinTemp + diff).toFixed(1));
  document.getElementById("climate-temp").innerText = `${cabinTemp.toFixed(1)}°C`;
  syncWithBackend();
  // Do not call agent when adjusting climate from UI
}

// -------------------------------------------------------------
// UI Render Updates
// -------------------------------------------------------------
function updateUI() {
  // Battery level
  const batteryPctText = `${Math.round(batteryVal)}%`;
  document.getElementById("battery-pct").innerText = batteryPctText;
  const batFill = document.getElementById("battery-bar-fill");
  batFill.style.width = batteryPctText;
  
  const rangeVal = Math.round(batteryVal * 4); // 400km base range
  document.getElementById("range-val").innerText = `${rangeVal} km`;
  
  // Sync the battery slider value back to the UI
  const batterySlider = document.getElementById("battery-slider");
  if (batterySlider) {
    batterySlider.value = Math.round(batteryVal);
  }

  const batContainer = document.getElementById("battery-status-container");
  const batWarning = document.getElementById("battery-warning");
  if (batteryVal < 25) {
    batContainer.classList.add("low-battery");
    batWarning.style.display = "inline";
  } else {
    batContainer.classList.remove("low-battery");
    batWarning.style.display = "none";
  }

  // Fatigue
  document.getElementById("fatigue-label").innerText = `${fatigueStr} Fatigue`;
  document.getElementById("fatigue-bar-fill").style.width = `${fatigueVal}%`;
  
  const fatContainer = document.getElementById("fatigue-container");
  const sysStatusText = document.getElementById("system-status-text");
  const sysStatusBox = document.querySelector(".system-status");
  
  document.getElementById("fatigue-selector").value = fatigueStr;

  if (fatigueStr === "High") {
    fatContainer.className = "telemetry-card fatigue-card danger-level glow-alert-red";
    sysStatusText.innerText = "ATTENTION ALERT: DRIVER TIRED";
    sysStatusBox.className = "system-status danger";
  } else if (fatigueStr === "Medium") {
    fatContainer.className = "telemetry-card fatigue-card warning-level";
    sysStatusText.innerText = "DRIVE CAUTIOUSLY";
    sysStatusBox.className = "system-status warning";
  } else {
    fatContainer.className = "telemetry-card fatigue-card";
    sysStatusText.innerText = "SYSTEM ACTIVE";
    sysStatusBox.className = "system-status";
  }

  // Route progress
  const progress = Math.round((currentCoordinateIndex / (routeCoordinates.length - 1)) * 100);
  document.getElementById("route-progress-txt").innerText = `Progress: ${progress}% | ETA: ${Math.round((100 - progress) * 2.5)} mins`;
  
  updateSpeedRadialGauge();
}

function updateSpeedRadialGauge() {
  const maxStroke = 314; // dasharray of circle
  // Speed gauge represents 0 to 180 km/h. At speed 0, offset = maxStroke. At speed 180, offset = 0.
  const speedRatio = Math.min(speedVal, 150) / 150;
  const strokeOffset = maxStroke - (speedRatio * 187); // Cap at 3/4 circle for aesthetic
  document.getElementById("speed-gauge-fill").style.strokeDashoffset = strokeOffset;
}

// -------------------------------------------------------------
// API / Backend Integration
// -------------------------------------------------------------
function compileCurrentState() {
  const progress = (currentCoordinateIndex / (routeCoordinates.length - 1)) * 100;
  const currentPos = routeCoordinates[currentCoordinateIndex] || WAYPOINTS.KL.coords;
  
  return {
    speed_kmh: speedVal,
    battery_soc: batteryVal,
    fatigue_level: fatigueStr,
    cabin_temp_c: cabinTemp,
    origin: routeActive ? "Kuala Lumpur" : "",
    destination: routeActive ? "Penang" : "",
    current_lat: currentPos[0],
    current_lng: currentPos[1],
    route_active: routeActive,
    progress_percentage: progress
  };
}

async function syncWithBackend() {
  const currentState = compileCurrentState();
  
  try {
    // 1. Sync simulation state in backend (telemetry upload)
    await fetch(`${BACKEND_URL}/simulation/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentState)
    });
  } catch (error) {
    console.warn("Backend server not responding during telemetry sync.", error);
  }
}

async function queryAgent(command = null) {
  const currentState = compileCurrentState();
  const payload = { state: currentState };
  if (command) {
    payload.command = command;
  }
  
  try {
    const response = await fetch(`${BACKEND_URL}/agent/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    if (response.ok) {
      const data = await response.json();
      renderRecommendations(data.recommendations);
      renderJsonPayload(data);
      if (command) {
        appendChatBubble("MBUX Assistant", data.chat_response);
        handleAPICommandEffects(command, data);
      } else {
        // If proactive check found alerts, post to chat so driver is warned
        if (data.chat_response && data.chat_response.trim()) {
          appendChatBubble("MBUX Assistant", data.chat_response);
        }
      }
    }
  } catch (error) {
    console.warn("Backend agent not responding. Falling back to offline engine.", error);
    if (command) {
      handleOfflineCommandFallback(command, currentState);
    } else {
      generateMockOfflineRecommendations(currentState);
    }
  }
}

async function syncWalletBalance() {
  try {
    const res = await fetch(`${BACKEND_URL}/wallet/balance`);
    if (res.ok) {
      const data = await res.json();
      walletBalance = data.balance;
      document.getElementById("wallet-balance-display").innerText = `RM ${walletBalance.toFixed(2)}`;
    }
  } catch (err) {
    // Local memory sync if backend offline
    document.getElementById("wallet-balance-display").innerText = `RM ${walletBalance.toFixed(2)}`;
  }
}

async function topUpWallet(amount) {
  try {
    const response = await fetch(`${BACKEND_URL}/wallet/topup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: parseFloat(amount) })
    });
    if (response.ok) {
      const data = await response.json();
      walletBalance = data.new_balance;
      addTransactionLog("Top Up", data.message);
      syncWalletBalance();
    }
  } catch (e) {
    // Offline fallback
    walletBalance += amount;
    addTransactionLog("Top Up", `Successfully topped up RM ${amount.toFixed(2)} offline.`);
    syncWalletBalance();
  }
}

async function chargeWallet(amount, reason) {
  try {
    const response = await fetch(`${BACKEND_URL}/wallet/charge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: parseFloat(amount), reason: reason })
    });
    if (response.ok) {
      const data = await response.json();
      walletBalance = data.new_balance;
      addTransactionLog("Charge", data.message);
      syncWalletBalance();
      return true;
    } else {
      const err = await response.json();
      alert(`Payment Error: ${err.detail}`);
      return false;
    }
  } catch (e) {
    // Offline fallback
    if (walletBalance < amount) {
      alert("Insufficient funds in offline wallet!");
      return false;
    }
    walletBalance -= amount;
    addTransactionLog("Charge", `Deducted RM ${amount.toFixed(2)} for: ${reason} (offline).`);
    syncWalletBalance();
    return true;
  }
}

// -------------------------------------------------------------
// Handle Route Planning
// -------------------------------------------------------------
async function handleRouteSubmit(event) {
  event.preventDefault();
  const fromSelect = document.getElementById("route-from");
  const toSelect = document.getElementById("route-to");
  
  const fromVal = fromSelect.value;
  const toVal = toSelect.value;
  
  const fromName = WAYPOINTS[fromVal]?.name || fromVal;
  const toName = WAYPOINTS[toVal]?.name || toVal;

  const command = `Plan my trip from ${fromName} to ${toName}`;

  // Add User bubble to layout
  appendChatBubble("User", `Plan my trip from ${fromName} to ${toName}`);

  // Do not call agent here to avoid extra API usage. Start simulation; the
  // agent will run once at simulation start via `toggleSimulation()`.
  if (!isDriving) toggleSimulation();
}


function handleAPICommandEffects(command, apiData) {
  const cmd = command.toLowerCase();
  
  if (cmd.includes("plan") && cmd.includes("penang")) {
    // If driving is not started, start it
    if (!isDriving) {
      toggleSimulation();
    }
  }
}

function appendChatBubble(sender, text) {
  const container = document.getElementById("chat-output-container");
  const bubble = document.createElement("div");
  const isUser = sender === "User";
  
  bubble.className = `chat-bubble ${isUser ? "user" : "assistant"}`;
  bubble.innerHTML = `
    <div class="chat-sender">${sender}</div>
    <div class="chat-text">${text}</div>
  `;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

// -------------------------------------------------------------
// Render Recommendation Cards
// -------------------------------------------------------------
function renderRecommendations(recommendations) {
  const container = document.getElementById("recommendations-list");
  container.innerHTML = "";

  if (!recommendations || recommendations.length === 0) {
    container.innerHTML = `
      <div class="no-recs">
        <i class="fa-solid fa-shield-halved"></i>
        <p>MBUX is analyzing. No warnings or suggestions at this moment.</p>
      </div>
    `;
    return;
  }

  recommendations.forEach(rec => {
    const card = document.createElement("div");
    card.className = `rec-card ${rec.type}`;
    
    // Customize action button texts
    let actionBtnText = "Apply Action";
    let actionCallback = "";
    
    if (rec.type === "charging") {
      actionBtnText = "Charge EV (RM 45.00)";
      actionCallback = `executeEVCharging('${rec.location}')`;
    } else if (rec.type === "rest_stop") {
      actionBtnText = "Rest & Order Coffee (RM 15.00)";
      actionCallback = `executeRestStop('${rec.location}')`;
    } else if (rec.type === "climate") {
      actionBtnText = "Set Cabin to 21°C";
      actionCallback = `executeClimateAdjustment()`;
    } else if (rec.type === "digital_extra") {
      actionBtnText = "Purchase / Stream (RM 5.00)";
      actionCallback = `executeDigitalExtra('${rec.location}')`;
    }

    card.innerHTML = `
      <div class="rec-top">
        <span class="rec-badge">${rec.type.replace('_', ' ')}</span>
        <span class="rec-confidence">Conf: ${Math.round(rec.confidence * 100)}%</span>
      </div>
      <div class="rec-location">${rec.location || "System Action"}</div>
      <div class="rec-reason">${rec.reason}</div>
      <div class="rec-action-row">
        <button class="btn-rec-action" onclick="${actionCallback}">${actionBtnText}</button>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderJsonPayload(data) {
  document.getElementById("json-payload-display").innerText = JSON.stringify(data, null, 2);
}

function toggleJsonInspector() {
  const el = document.getElementById("json-content-container");
  const chevron = document.getElementById("json-chevron");
  if (el.style.display === "none") {
    el.style.display = "block";
    chevron.className = "fa-solid fa-chevron-up";
  } else {
    el.style.display = "none";
    chevron.className = "fa-solid fa-chevron-down";
  }
}

// -------------------------------------------------------------
// Proactive Recommendation Actions Execution
// -------------------------------------------------------------
async function executeEVCharging(location) {
  // Pause simulation while charging
  let driveStateBefore = isDriving;
  if (isDriving) toggleSimulation();
  
  addTransactionLog("System", `Routing to EV Charger: ${location}...`);
  
  // Deduct charging fee
  const success = await chargeWallet(45.00, `High speed EV charging at ${location}`);
  if (success) {
    appendChatBubble("MBUX Assistant", `Vehicle charging initiated at ${location}. Battery filled to 100%. Charged RM 45.00.`);
    batteryVal = 100;
    updateUI();
    syncWithBackend();
    
    // Resume driving if previously driving
    if (driveStateBefore) setTimeout(toggleSimulation, 1500);
  } else {
    if (driveStateBefore) toggleSimulation();
  }
}

async function executeRestStop(location) {
  let driveStateBefore = isDriving;
  if (isDriving) toggleSimulation();

  addTransactionLog("System", `Routing to Rest Stop: ${location}...`);

  // Order coffee & rest
  const success = await chargeWallet(15.00, `Rest stop purchase at ${location}`);
  if (success) {
    appendChatBubble("MBUX Assistant", `Rested at ${location}. Fatigue levels recovered. Drive safety rating: Perfect. Charged RM 15.00.`);
    fatigueVal = 5;
    fatigueStr = "Low";
    updateUI();
    syncWithBackend();

    if (driveStateBefore) setTimeout(toggleSimulation, 1500);
  } else {
    if (driveStateBefore) toggleSimulation();
  }
}

function executeClimateAdjustment() {
  cabinTemp = 21.0;
  document.getElementById("climate-temp").innerText = "21.0°C";
  appendChatBubble("MBUX Assistant", "Cabin climate adjusted to driver preference: 21.0°C. Maintaining alert driving environment.");
  updateUI();
  syncWithBackend();
}

async function executeDigitalExtra(name) {
  const success = await chargeWallet(5.00, `Mercedes Digital Extras: Stream ${name}`);
  if (success) {
    appendChatBubble("MBUX Assistant", `Now streaming premium audio '${name}' through Burmester 3D Surround Sound. Charged RM 5.00.`);
    syncWithBackend();
  }
}

// -------------------------------------------------------------
// Transaction Logs Feed
// -------------------------------------------------------------
function addTransactionLog(type, desc) {
  const list = document.getElementById("transaction-log-list");
  const entry = document.createElement("div");
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  
  let entryClass = "system";
  if (type === "Charge") entryClass = "charge";
  if (type === "Top Up") entryClass = "topup";
  
  entry.className = `log-entry ${entryClass}`;
  entry.innerHTML = `
    <span class="log-time">${time}</span>
    <span class="log-desc">${desc}</span>
  `;
  list.appendChild(entry);
  list.scrollTop = list.scrollHeight;
}

// -------------------------------------------------------------
// Offline Mock Fallbacks (Fallback rules when FastAPI is down)
// -------------------------------------------------------------
function generateMockOfflineRecommendations(state) {
  let recommendations = [];
  
  if (state.fatigue_level === "High") {
    recommendations.append({
      type: "rest_stop",
      location: "Starbucks Ipoh",
      reason: "Attention Assist Warning: High drowsiness detected. Recommend taking immediate rest.",
      confidence: 0.96
    });
  } else if (state.fatigue_level === "Medium") {
    recommendations.append({
      type: "rest_stop",
      location: "Starbucks Ipoh",
      reason: "Drive history indicates a stop at Starbucks Ipoh here is beneficial.",
      confidence: 0.82
    });
  }

  if (state.battery_soc < 25.0) {
    recommendations.append({
      type: "charging",
      location: "Shell Recharge Tapah",
      reason: `Battery at ${Math.round(state.battery_soc)}%. EV station is 12 km away.`,
      confidence: 0.95
    });
  }

  if (state.cabin_temp_c > 24) {
    recommendations.append({
      type: "climate",
      location: "Cabin A/C System",
      reason: "Interior climate warm. Reducing temperature helps sustain alert driving.",
      confidence: 0.72
    });
  }

  const payload = {
    chat_response: "MBUX offline assistant mode. Active analysis running locally.",
    recommendations: recommendations
  };
  
  renderRecommendations(recommendations);
  renderJsonPayload(payload);
}

function handleOfflineCommandFallback(command, state) {
  const cmd = command.toLowerCase();
  let chat_response = "";
  let recommendations = [];

  if (cmd.includes("plan") && cmd.includes("penang")) {
    chat_response = "Offline mode: Route planned from KL to Penang. Loaded Starbucks Ipoh stop from driver memory.";
    recommendations.push({
      type: "rest_stop",
      location: "Starbucks Ipoh",
      reason: "Frequent coffee stop on KL -> Penang route.",
      confidence: 0.95
    });
    recommendations.push({
      type: "charging",
      location: "Shell Recharge Tapah",
      reason: "Usual high-speed EV charging point.",
      confidence: 0.88
    });
    
    if (!isDriving) {
      setTimeout(toggleSimulation, 1000);
    }
  } else if (cmd.includes("stop") || cmd.includes("next")) {
    chat_response = "Analyzing next route node offline. Recommend Starbucks Ipoh for a break.";
    recommendations.push({
      type: "rest_stop",
      location: "Starbucks Ipoh",
      reason: "Coffee stop from long-term memory history.",
      confidence: 0.90
    });
  } else if (cmd.includes("battery") || cmd.includes("charge")) {
    chat_response = `Offline Check: Battery SoC is ${Math.round(state.battery_soc)}%. Estimated range: ${Math.round(state.battery_soc * 4)} km.`;
    if (state.battery_soc < 30) {
      recommendations.push({
        type: "charging",
        location: "Shell Recharge Tapah",
        reason: "Low battery warning trigger.",
        confidence: 0.94
      });
    }
  } else {
    chat_response = `Offline response to: "${command}". I can assist with route planning, battery checks, or adjusting climate settings.`;
    recommendations.push({
      type: "digital_extra",
      location: "MBUX Voice",
      reason: "Local speech node processing completed.",
      confidence: 0.50
    });
  }

  appendChatBubble("MBUX Assistant (Offline)", chat_response);
  renderRecommendations(recommendations);
  
  const payload = {
    chat_response: chat_response,
    recommendations: recommendations
  };
  renderJsonPayload(payload);
}

async function loadMemoryStops() {
  try {
    const res = await fetch(`${BACKEND_URL}/agent/memory`);
    if (res.ok) {
      const data = await res.json();
      const trips = data.frequent_trips || [];
      const listEl = document.getElementById("memory-stops-list");
      listEl.innerHTML = "";
      
      let totalStops = 0;
      trips.forEach(trip => {
        const origin = trip.origin;
        const destination = trip.destination;
        const stops = trip.stops || [];
        
        stops.forEach(stop => {
          totalStops++;
          const item = document.createElement("div");
          item.className = `memory-item ${stop.type}`;
          item.innerHTML = `
            <div class="memory-item-top">
              <span class="memory-item-name">${stop.location}</span>
              <span class="memory-item-route">${origin} → ${destination}</span>
            </div>
            <div class="memory-item-desc">${stop.reason} (${stop.type.replace('_', ' ')})</div>
          `;
          listEl.appendChild(item);
        });
      });
      
      if (totalStops === 0) {
        listEl.innerHTML = `
          <div class="no-recs" style="padding: 10px 0;">
            <p style="font-size: 11px; color: var(--text-secondary);">No favorite locations saved.</p>
          </div>
        `;
      }
    }
  } catch (err) {
    console.warn("Failed to load memory stops from backend.", err);
  }
}

function openAddMemoryModal() {
  document.getElementById("add-memory-modal").style.display = "flex";
}

function closeAddMemoryModal() {
  document.getElementById("add-memory-modal").style.display = "none";
}

async function handleAddMemorySubmit(event) {
  event.preventDefault();
  const origin = document.getElementById("mem-route-from").value;
  const destination = document.getElementById("mem-route-to").value;
  const location = document.getElementById("mem-location").value;
  const type = document.getElementById("mem-type").value;
  const reason = document.getElementById("mem-reason").value;
  
  try {
    const res = await fetch(`${BACKEND_URL}/agent/memory/frequent_stop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin, destination, location, type, reason })
    });
    
    if (res.ok) {
      const data = await res.json();
      addTransactionLog("System", `Remembered favorite location: ${location}`);
      appendChatBubble("MBUX Assistant", `I have saved '${location}' to your memory for trips between ${origin} and ${destination}. I will suggest it when planning routes.`);
      
      // Close modal and reset form
      closeAddMemoryModal();
      document.getElementById("add-memory-form").reset();
      
      // Reload lists
      await loadMemoryStops();
      
      // Do not request updated agent recommendations here to avoid extra API calls.
    } else {
      alert("Failed to save favorite location.");
    }
  } catch (err) {
    console.error("Error saving favorite location", err);
    alert("Error communicating with backend.");
  }
}

