const state = {
  map: null,
  geocoder: null,
  routePolyline: null,
  routeHighlight: null,
  hoverPosition: null,
  hoverWaypoint: null,
  markers: [],
  mode: "simple",
  tags: {
    home: "",
    work: "",
  },
  settings: {
    currentLocation: "",
  },
  fatigue: {
    stream: null,
    socket: null,
    frameTimer: null,
    awaitingResponse: false,
    alertLocked: false,
    userStoppedDetection: false,
    isDragging: false,
    dragOffsetX: 0,
    dragOffsetY: 0,
  },
  plannerThreadId: "",
  plannerAwaitingClarification: false,
  roadTripRecommendations: [],
};

const elements = {
  form: document.querySelector("#route-form"),
  sideRail: document.querySelector("#side-rail"),
  sidebarToggle: document.querySelector("#sidebar-toggle"),
  sidebarClose: document.querySelector("#sidebar-close"),
  sidebarScrim: document.querySelector("#sidebar-scrim"),
  sidebarActions: document.querySelector(".sidebar-actions"),
  gpsButton: document.querySelector("#gps-app-button"),
  plannerButton: document.querySelector("#planner-app-button"),
  roadTripAppButton: document.querySelector("#road-trip-app-button"),
  fatigueButton: document.querySelector("#fatigue-app-button"),
  editTagsButton: document.querySelector("#edit-tags-button"),
  settingsButton: document.querySelector("#settings-app-button"),
  simplePanel: document.querySelector("#simple-route-panel"),
  plannerPanel: document.querySelector("#planner-panel"),
  roadTripPanel: document.querySelector("#road-trip-panel"),
  tagsPanel: document.querySelector("#tags-panel"),
  settingsPanel: document.querySelector("#settings-panel"),
  origin: document.querySelector("#origin"),
  destination: document.querySelector("#destination"),
  routeButton: document.querySelector("#route-button"),
  status: document.querySelector("#status"),
  plannerStatus: document.querySelector("#planner-status"),
  roadTripOrigin: document.querySelector("#road-trip-origin"),
  roadTripDestination: document.querySelector("#road-trip-destination"),
  roadTripButton: document.querySelector("#road-trip-button"),
  roadTripStatus: document.querySelector("#road-trip-status"),
  roadTripResults: document.querySelector("#road-trip-results"),
  routeRecommendations: document.querySelector("#route-recommendations"),
  destinationRecommendations: document.querySelector("#destination-recommendations"),
  foodRecommendations: document.querySelector("#food-recommendations"),
  tagsStatus: document.querySelector("#tags-status"),
  settingsStatus: document.querySelector("#settings-status"),
  pinHoverCard: document.querySelector("#pin-hover-card"),
  tripInstruction: document.querySelector("#trip-instruction"),
  tripButton: document.querySelector("#trip-button"),
  homeAddress: document.querySelector("#home-address"),
  workAddress: document.querySelector("#work-address"),
  saveHomeButton: document.querySelector("#save-home-button"),
  saveWorkButton: document.querySelector("#save-work-button"),
  currentLocationInput: document.querySelector("#current-location-input"),
  saveCurrentLocationButton: document.querySelector("#save-current-location-button"),
  currentLocationDisplay: document.querySelector("#current-location-display"),
  duration: document.querySelector("#duration-text"),
  distance: document.querySelector("#distance-text"),
  arrival: document.querySelector("#arrival-time"),
  clock: document.querySelector("#clock"),
  fatigueMonitor: document.querySelector("#fatigue-monitor"),
  fatigueMonitorDrag: document.querySelector("#fatigue-monitor-drag"),
  fatigueWebcam: document.querySelector("#fatigue-webcam"),
  fatigueOverlay: document.querySelector("#fatigue-overlay"),
  fatigueStartButton: document.querySelector("#fatigue-start-button"),
  fatigueStopButton: document.querySelector("#fatigue-stop-button"),
  fatigueCloseButton: document.querySelector("#fatigue-close-button"),
  fatigueFaceStatus: document.querySelector("#fatigue-face-status"),
  fatigueEmptyState: document.querySelector("#fatigue-empty-state"),
  fatigueLevel: document.querySelector("#fatigue-level"),
  fatigueScore: document.querySelector("#fatigue-score"),
  fatigueScoreFill: document.querySelector("#fatigue-score-fill"),
  fatigueSymptomsList: document.querySelector("#fatigue-symptoms-list"),
  fatigueEyeCount: document.querySelector("#fatigue-eye-count"),
  fatigueBlinkCount: document.querySelector("#fatigue-blink-count"),
  fatigueYawnCount: document.querySelector("#fatigue-yawn-count"),
  fatigueNodCount: document.querySelector("#fatigue-nod-count"),
  fatigueStatusDot: document.querySelector("#fatigue-status-dot"),
  fatigueConnectionStatus: document.querySelector("#fatigue-connection-status"),
  fatigueAlertModal: document.querySelector("#fatigue-alert-modal"),
  fatigueAlertOkButton: document.querySelector("#fatigue-alert-ok-button"),
};

const fatigueCaptureCanvas = document.createElement("canvas");
const fatigueCaptureCtx = fatigueCaptureCanvas.getContext("2d");
const fatigueOverlayCtx = elements.fatigueOverlay.getContext("2d");
const fatigueLandmarkColors = {
  leftEye: "#60a5fa",
  rightEye: "#22d3ee",
  nose: "#fbbf24",
  leftEar: "#c084fc",
  rightEar: "#fb7185",
};

function activeStatusElement() {
  if (state.mode === "planner") {
    return elements.plannerStatus;
  }
  if (state.mode === "roadTrip") {
    return elements.roadTripStatus;
  }
  if (state.mode === "tags") {
    return elements.tagsStatus;
  }
  if (state.mode === "settings") {
    return elements.settingsStatus;
  }
  return elements.status;
}

function setStatus(message, isError = false) {
  const target = activeStatusElement();
  target.textContent = message;
  target.classList.toggle("error", isError);
}

function setButtonLoading(button, isLoading, label) {
  button.disabled = isLoading;
  button.textContent = isLoading ? "..." : label;
}

function openSidebar() {
  elements.sideRail.classList.add("open");
  elements.sideRail.setAttribute("aria-hidden", "false");
  elements.sidebarScrim.classList.remove("hidden");
  elements.sidebarToggle.classList.add("hidden");
  elements.sidebarToggle.setAttribute("aria-label", "Close sidebar");
}

function closeSidebar() {
  elements.sideRail.classList.remove("open");
  elements.sideRail.setAttribute("aria-hidden", "true");
  elements.sidebarScrim.classList.add("hidden");
  elements.sidebarToggle.classList.remove("hidden");
  elements.sidebarToggle.setAttribute("aria-label", "Open sidebar");
}

function toggleSidebar() {
  if (elements.sideRail.classList.contains("open")) {
    closeSidebar();
    return;
  }

  openSidebar();
}

function setActiveSidebarAction(activeButton) {
  [
    elements.gpsButton,
    elements.plannerButton,
    elements.roadTripAppButton,
    elements.fatigueButton,
    elements.editTagsButton,
    elements.settingsButton,
  ].forEach((button) => {
    button.classList.toggle("active", button === activeButton);
  });
}

function syncActiveSidebarAction() {
  if (state.mode === "planner") {
    setActiveSidebarAction(elements.plannerButton);
  } else if (state.mode === "roadTrip") {
    setActiveSidebarAction(elements.roadTripAppButton);
  } else if (state.mode === "tags") {
    setActiveSidebarAction(elements.editTagsButton);
  } else if (state.mode === "settings") {
    setActiveSidebarAction(elements.settingsButton);
  } else {
    setActiveSidebarAction(elements.gpsButton);
  }
}

function setRouteCardLayout(mode) {
  elements.form.classList.toggle("route-card-road-trip", mode === "roadTrip");
}

function resetRouteCardScroll() {
  elements.form.scrollTop = 0;
}

function switchSidebarMode(mode) {
  if (mode === "simple") {
    switchToSimpleMode();
  } else if (mode === "planner") {
    switchToPlannerMode();
  } else if (mode === "roadTrip") {
    switchToRoadTripMode();
  } else if (mode === "fatigue") {
    openFatigueMonitor();
  } else if (mode === "tags") {
    switchToTagsMode();
  } else if (mode === "settings") {
    switchToSettingsMode();
  }
}

function updateClock() {
  const now = new Date();
  elements.clock.textContent = now.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatArrival(duration) {
  const seconds = Number.parseInt(String(duration).replace("s", ""), 10);
  if (!Number.isFinite(seconds)) {
    return "--:--";
  }

  const arrival = new Date(Date.now() + seconds * 1000);
  return arrival.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function createGoogleMapsScript(browserKey) {
  window.__initCarplayMap = initMap;

  const script = document.createElement("script");
  script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(browserKey)}&libraries=geometry&v=weekly&callback=__initCarplayMap`;
  script.async = true;
  script.defer = true;
  script.onerror = () => setStatus("Google Maps could not load. Check the browser key and referrer restrictions.", true);
  document.head.appendChild(script);
}

async function loadMapConfig() {
  const response = await fetch("/api/maps/config");
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Map configuration is unavailable.");
  }

  if (!payload.browserKey) {
    throw new Error("GOOGLE_MAPS_BROWSER_KEY is missing from .env.");
  }

  createGoogleMapsScript(payload.browserKey);
}

function initMap() {
  const malaysiaCenter = { lat: 4.2105, lng: 101.9758 };

  state.map = new google.maps.Map(document.querySelector("#map"), {
    center: malaysiaCenter,
    zoom: 7,
    disableDefaultUI: true,
    gestureHandling: "greedy",
    keyboardShortcuts: false,
    mapTypeControl: false,
    fullscreenControl: false,
    streetViewControl: false,
    zoomControl: false,
    styles: [
      { elementType: "geometry", stylers: [{ color: "#223247" }] },
      { elementType: "labels.text.fill", stylers: [{ color: "#d7e8ff" }] },
      { elementType: "labels.text.stroke", stylers: [{ color: "#172231" }] },
      { featureType: "administrative", elementType: "geometry", stylers: [{ visibility: "off" }] },
      { featureType: "poi", stylers: [{ visibility: "off" }] },
      { featureType: "road", elementType: "geometry", stylers: [{ color: "#32405a" }] },
      { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#7282a0" }] },
      { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#243957" }] },
      { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#c18c2e" }] },
      { featureType: "road.highway", elementType: "labels", stylers: [{ visibility: "on" }] },
      { featureType: "transit", stylers: [{ visibility: "off" }] },
      { featureType: "water", elementType: "geometry", stylers: [{ color: "#075b66" }] },
      { featureType: "landscape", elementType: "geometry", stylers: [{ color: "#236354" }] },
    ],
  });
  state.geocoder = new google.maps.Geocoder();
  state.map.addListener("idle", repositionPinHoverCard);

  setStatus("Enter an origin and destination.");
}

function clearRoute() {
  if (state.routePolyline) {
    state.routePolyline.setMap(null);
  }
  if (state.routeHighlight) {
    state.routeHighlight.setMap(null);
  }
  state.markers.forEach((marker) => marker.setMap(null));
  state.markers = [];
  hidePinHoverCard();
}

function routeViewportPadding() {
  if (window.innerWidth <= 760) {
    return {
      top: 250,
      right: 35,
      bottom: 105,
      left: 95,
    };
  }

  return {
    top: 120,
    right: 120,
    bottom: 130,
    left: 520,
  };
}

function markerText(index, waypoint) {
  if (waypoint.role === "origin") {
    return "S";
  }
  if (waypoint.role === "destination") {
    return "D";
  }
  return String(index);
}

function markerColor(waypoint) {
  if (waypoint.role === "origin") {
    return "#22c55e";
  }
  if (waypoint.role === "destination") {
    return "#1685ff";
  }
  return "#f59e0b";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatRating(rating) {
  const value = Number(rating);
  if (!Number.isFinite(value)) {
    return "";
  }
  return value.toFixed(1).replace(/\.0$/, "");
}

function formatReviewCount(count) {
  const value = Number(count);
  if (!Number.isFinite(value) || value <= 0) {
    return "";
  }
  return `${value.toLocaleString()} reviews`;
}

function waypointCardContent(waypoint) {
  const rating = formatRating(waypoint.rating);
  const reviewCount = formatReviewCount(waypoint.userRatingCount);
  const category = waypoint.category
    ? `<div class="pin-hover-category">${escapeHtml(waypoint.category)}</div>`
    : "";
  const explanation = waypoint.explanation
    ? `<div class="pin-hover-explanation">${escapeHtml(waypoint.explanation)}</div>`
    : "";
  return `
    ${category}
    <div class="pin-hover-title">${escapeHtml(waypoint.label || "Location")}</div>
    <div class="pin-hover-address">${escapeHtml(waypoint.address || "")}</div>
    ${rating ? `<div class="pin-hover-rating">${escapeHtml(rating)} Google rating${reviewCount ? ` / ${escapeHtml(reviewCount)}` : ""}</div>` : ""}
    ${explanation}
  `;
}

function markerScreenPosition(position) {
  if (!state.map?.getProjection() || !state.map.getBounds()) {
    return null;
  }

  const projection = state.map.getProjection();
  const bounds = state.map.getBounds();
  const scale = 2 ** state.map.getZoom();
  const northWest = projection.fromLatLngToPoint(
    new google.maps.LatLng(
      bounds.getNorthEast().lat(),
      bounds.getSouthWest().lng(),
    ),
  );
  const point = projection.fromLatLngToPoint(position);

  return {
    x: (point.x - northWest.x) * scale,
    y: (point.y - northWest.y) * scale,
  };
}

function repositionPinHoverCard() {
  if (!state.hoverPosition || elements.pinHoverCard.classList.contains("hidden")) {
    return;
  }

  const point = markerScreenPosition(state.hoverPosition);
  if (!point) {
    return;
  }

  const cardRect = elements.pinHoverCard.getBoundingClientRect();
  const stageRect = document.querySelector(".map-stage").getBoundingClientRect();
  const maxLeft = Math.max(12, stageRect.width - cardRect.width - 12);
  const left = Math.min(Math.max(12, point.x - cardRect.width / 2), maxLeft);
  const top = Math.max(12, point.y - cardRect.height - 28);

  elements.pinHoverCard.style.left = `${left}px`;
  elements.pinHoverCard.style.top = `${top}px`;
}

function showPinHoverCard(position, waypoint) {
  state.hoverPosition = position;
  state.hoverWaypoint = waypoint;
  elements.pinHoverCard.innerHTML = waypointCardContent(waypoint);
  elements.pinHoverCard.classList.remove("hidden");
  elements.pinHoverCard.setAttribute("aria-hidden", "false");
  requestAnimationFrame(repositionPinHoverCard);
}

function hidePinHoverCard() {
  state.hoverPosition = null;
  state.hoverWaypoint = null;
  elements.pinHoverCard.classList.add("hidden");
  elements.pinHoverCard.setAttribute("aria-hidden", "true");
}

function createRouteMarker(position, waypoint, index) {
  const marker = new google.maps.Marker({
    position,
    map: state.map,
    label: {
      text: markerText(index, waypoint),
      color: "#ffffff",
      fontSize: "13px",
      fontWeight: "900",
    },
    icon: {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 13,
      fillColor: markerColor(waypoint),
      fillOpacity: 1,
      strokeColor: "#ffffff",
      strokeOpacity: 0.95,
      strokeWeight: 3,
    },
    title: `${waypoint.label}: ${waypoint.address}`,
    zIndex: 40,
  });

  marker.addListener("mouseover", () => {
    showPinHoverCard(marker.getPosition(), waypoint);
  });

  marker.addListener("mouseout", () => {
    hidePinHoverCard();
  });

  marker.addListener("click", () => {
    showPinHoverCard(marker.getPosition(), waypoint);
  });

  return marker;
}

function recommendationColor(section) {
  if (section === "destination") {
    return "#a855f7";
  }
  if (section === "food") {
    return "#ef4444";
  }
  return "#f59e0b";
}

function recommendationLabel(section) {
  if (section === "destination") {
    return "D";
  }
  if (section === "food") {
    return "F";
  }
  return "R";
}

function recommendationIcon(section) {
  if (section === "destination") {
    return "fa-mountain-sun";
  }
  if (section === "food") {
    return "fa-utensils";
  }
  return "fa-map-location-dot";
}

function createRecommendationMarker(recommendation) {
  const position = {
    lat: Number(recommendation.latitude),
    lng: Number(recommendation.longitude),
  };
  if (!Number.isFinite(position.lat) || !Number.isFinite(position.lng)) {
    return null;
  }

  const marker = new google.maps.Marker({
    position,
    map: state.map,
    label: {
      text: recommendationLabel(recommendation.section),
      color: "#ffffff",
      fontSize: "12px",
      fontWeight: "900",
    },
    icon: {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 11,
      fillColor: recommendationColor(recommendation.section),
      fillOpacity: 1,
      strokeColor: "#ffffff",
      strokeOpacity: 0.95,
      strokeWeight: 3,
    },
    title: `${recommendation.name}: ${recommendation.address}`,
    zIndex: 55,
  });

  const hoverWaypoint = {
    role: "recommendation",
    label: recommendation.name,
    address: recommendation.address,
    rating: recommendation.rating,
    userRatingCount: recommendation.userRatingCount,
    category: recommendation.category,
    explanation: recommendation.explanation,
  };

  marker.addListener("mouseover", () => {
    showPinHoverCard(marker.getPosition(), hoverWaypoint);
  });
  marker.addListener("mouseout", () => {
    hidePinHoverCard();
  });
  marker.addListener("click", () => {
    showPinHoverCard(marker.getPosition(), hoverWaypoint);
  });

  return marker;
}

async function geocodeAddress(address) {
  if (!state.geocoder) {
    return null;
  }

  try {
    const response = await state.geocoder.geocode({ address });
    return response.results[0]?.geometry?.location || null;
  } catch {
    return null;
  }
}

async function renderWaypointMarkers(waypoints, path) {
  if (!waypoints?.length) {
    const startMarker = createRouteMarker(
      path[0],
      { role: "origin", label: "Start", address: "Route start" },
      0,
    );
    const endMarker = createRouteMarker(
      path[path.length - 1],
      { role: "destination", label: "Destination", address: "Route destination" },
      1,
    );
    state.markers.push(startMarker, endMarker);
    return;
  }

  const geocodedMarkers = await Promise.all(
    waypoints.map(async (waypoint, index) => {
      let position = null;
      if (waypoint.role === "origin") {
        position = path[0];
      } else if (waypoint.role === "destination") {
        position = path[path.length - 1];
      } else {
        position = await geocodeAddress(waypoint.address);
      }

      if (!position) {
        return null;
      }

      return createRouteMarker(position, waypoint, index);
    }),
  );

  state.markers.push(...geocodedMarkers.filter(Boolean));
}

async function renderRoute(payload) {
  if (!state.map || !window.google?.maps?.geometry) {
    throw new Error("Google Maps is still loading. Try again in a moment.");
  }

  clearRoute();

  const path = google.maps.geometry.encoding.decodePath(payload.encodedPolyline);
  if (!path.length) {
    throw new Error("Google returned an empty route path.");
  }

  state.routePolyline = new google.maps.Polyline({
    path,
    map: state.map,
    strokeColor: "#0b79ff",
    strokeOpacity: 0.94,
    strokeWeight: 12,
    zIndex: 20,
  });

  state.routeHighlight = new google.maps.Polyline({
    path,
    map: state.map,
    strokeColor: "#69adff",
    strokeOpacity: 0.62,
    strokeWeight: 4,
    zIndex: 21,
  });

  const bounds = new google.maps.LatLngBounds();
  path.forEach((point) => bounds.extend(point));
  state.map.fitBounds(bounds, routeViewportPadding());

  await renderWaypointMarkers(payload.waypoints, path);

  elements.duration.textContent = payload.summary.durationText;
  elements.distance.textContent = payload.summary.distanceText;
  elements.arrival.textContent = formatArrival(payload.duration);
}

function recommendationCard(recommendation) {
  const rating = formatRating(recommendation.rating);
  const reviewCount = formatReviewCount(recommendation.userRatingCount);
  const ratingText = rating
    ? `${rating} Google rating${reviewCount ? ` / ${reviewCount}` : ""}`
    : "Google rating unavailable";
  const mapsLink = recommendation.googleMapsUri
    ? `<a href="${escapeHtml(recommendation.googleMapsUri)}" target="_blank" rel="noreferrer">Open in Maps</a>`
    : "";
  const section = ["destination", "food", "route"].includes(recommendation.section)
    ? recommendation.section
    : "route";

  return `
    <article class="recommendation-card recommendation-card-${escapeHtml(section)}">
      <div class="recommendation-card-icon" aria-hidden="true">
        <i class="fa-solid ${recommendationIcon(section)}"></i>
      </div>
      <div class="recommendation-card-body">
        <div class="recommendation-card-top">
          <span>${escapeHtml(recommendation.category)}</span>
          <em>${escapeHtml(ratingText)}</em>
        </div>
        <strong>${escapeHtml(recommendation.name)}</strong>
        <p>${escapeHtml(recommendation.explanation)}</p>
        <small>${escapeHtml(recommendation.address)}</small>
        ${mapsLink}
      </div>
    </article>
  `;
}

function renderRecommendationGroup(container, recommendations) {
  if (!recommendations.length) {
    container.innerHTML = `<p class="empty-recommendations">No recommendations found.</p>`;
    return;
  }

  container.innerHTML = recommendations.map(recommendationCard).join("");
}

function renderRoadTripResults(payload) {
  const routeRecommendations = payload.routeRecommendations || [];
  const destinationRecommendations = payload.destinationRecommendations || [];
  const foodRecommendations = payload.foodRecommendations || [];
  const allRecommendations = [
    ...routeRecommendations,
    ...destinationRecommendations,
    ...foodRecommendations,
  ];

  state.roadTripRecommendations = allRecommendations;
  elements.roadTripResults.classList.remove("hidden");
  renderRecommendationGroup(elements.routeRecommendations, routeRecommendations);
  renderRecommendationGroup(elements.destinationRecommendations, destinationRecommendations);
  renderRecommendationGroup(elements.foodRecommendations, foodRecommendations);

  allRecommendations.forEach((recommendation) => {
    const marker = createRecommendationMarker(recommendation);
    if (marker) {
      state.markers.push(marker);
    }
  });
}

async function requestRoute(origin, destination) {
  const response = await fetch("/api/routes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin, destination }),
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Route request failed.");
  }

  return payload;
}

async function requestRoadTrip(origin, destination) {
  const response = await fetch("/api/road-trip-planner", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin, destination }),
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Road trip planner request failed.");
  }

  return payload;
}

async function requestTripPlan(instruction) {
  const response = await fetch("/api/trip-planner", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Trip planner request failed.");
  }

  return payload;
}

async function resumeTripPlan(answer) {
  const response = await fetch("/api/trip-planner/resume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      threadId: state.plannerThreadId,
      answer,
    }),
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Trip planner resume failed.");
  }
  return payload;
}

async function requestSettings() {
  const response = await fetch("/api/settings");
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Could not load settings.");
  }

  return payload;
}

async function saveCurrentLocation() {
  const address = elements.currentLocationInput.value.trim();

  setButtonLoading(elements.saveCurrentLocationButton, true, "Submit");

  try {
    const response = await fetch("/api/settings/current-location", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not save current location.");
    }

    state.settings.currentLocation = payload.currentLocation || "";
    syncSettingsInputs();
    setStatus(
      state.settings.currentLocation
        ? "Current location saved."
        : "Current location cleared.",
    );
  } catch (error) {
    setStatus(error.message || "Could not save current location.", true);
  } finally {
    setButtonLoading(elements.saveCurrentLocationButton, false, "Submit");
  }
}

async function loadTags() {
  const response = await fetch("/api/location-tags");
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Could not load location tags.");
  }

  state.tags = {
    home: payload.home || "",
    work: payload.work || "",
  };
  syncTagInputs();
}

async function loadSettings() {
  const payload = await requestSettings();
  state.settings.currentLocation = payload.currentLocation || "";
  syncSettingsInputs();
}

async function saveTag(tag) {
  const addressInput = tag === "home" ? elements.homeAddress : elements.workAddress;
  const saveButton = tag === "home" ? elements.saveHomeButton : elements.saveWorkButton;
  const address = addressInput.value.trim();

  if (!address) {
    setStatus(`Enter a ${tag} address first.`, true);
    return;
  }

  setButtonLoading(saveButton, true, "Submit");

  try {
    const response = await fetch("/api/location-tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag, address }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not save tag.");
    }

    state.tags = {
      home: payload.home || "",
      work: payload.work || "",
    };
    syncTagInputs();
    setStatus(`${tag.charAt(0).toUpperCase()}${tag.slice(1)} tag saved.`);
  } catch (error) {
    setStatus(error.message || "Could not save tag.", true);
  } finally {
    setButtonLoading(saveButton, false, "Submit");
  }
}

function syncTagInputs() {
  elements.homeAddress.value = state.tags.home || "";
  elements.workAddress.value = state.tags.work || "";
}

function syncSettingsInputs() {
  elements.currentLocationInput.value = state.settings.currentLocation || "";
  elements.currentLocationDisplay.textContent = state.settings.currentLocation || "Not set";
}

function switchToSimpleMode() {
  state.mode = "simple";
  setRouteCardLayout(state.mode);
  resetRouteCardScroll();
  elements.simplePanel.classList.remove("hidden");
  elements.plannerPanel.classList.add("hidden");
  elements.roadTripPanel.classList.add("hidden");
  elements.tagsPanel.classList.add("hidden");
  elements.settingsPanel.classList.add("hidden");
  elements.status.classList.remove("error");
  elements.status.textContent = "Enter a destination. Origin can use Current Location or Home.";
  setActiveSidebarAction(elements.gpsButton);
  closeSidebar();
}

function switchToPlannerMode() {
  state.mode = "planner";
  setRouteCardLayout(state.mode);
  resetRouteCardScroll();
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.remove("hidden");
  elements.roadTripPanel.classList.add("hidden");
  elements.tagsPanel.classList.add("hidden");
  elements.settingsPanel.classList.add("hidden");
  elements.plannerStatus.classList.remove("error");
  elements.plannerStatus.textContent = "Describe your whole trip in one instruction.";
  setActiveSidebarAction(elements.plannerButton);
  closeSidebar();
}

function switchToRoadTripMode() {
  state.mode = "roadTrip";
  setRouteCardLayout(state.mode);
  resetRouteCardScroll();
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.add("hidden");
  elements.roadTripPanel.classList.remove("hidden");
  elements.tagsPanel.classList.add("hidden");
  elements.settingsPanel.classList.add("hidden");
  elements.roadTripStatus.classList.remove("error");
  elements.roadTripStatus.textContent = "Enter an origin and destination to find stops.";
  setActiveSidebarAction(elements.roadTripAppButton);
  closeSidebar();
}

async function switchToTagsMode() {
  state.mode = "tags";
  setRouteCardLayout(state.mode);
  resetRouteCardScroll();
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.add("hidden");
  elements.roadTripPanel.classList.add("hidden");
  elements.tagsPanel.classList.remove("hidden");
  elements.settingsPanel.classList.add("hidden");
  elements.tagsStatus.classList.remove("error");
  elements.tagsStatus.textContent = "Save Home or Work for trip planning context.";
  setActiveSidebarAction(elements.editTagsButton);
  closeSidebar();

  try {
    await loadTags();
  } catch (error) {
    setStatus(error.message || "Could not load saved tags.", true);
  }
}

async function switchToSettingsMode() {
  state.mode = "settings";
  setRouteCardLayout(state.mode);
  resetRouteCardScroll();
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.add("hidden");
  elements.roadTripPanel.classList.add("hidden");
  elements.tagsPanel.classList.add("hidden");
  elements.settingsPanel.classList.remove("hidden");
  elements.settingsStatus.classList.remove("error");
  elements.settingsStatus.textContent = "Set a default start point for routes.";
  setActiveSidebarAction(elements.settingsButton);
  closeSidebar();

  try {
    await loadSettings();
  } catch (error) {
    setStatus(error.message || "Could not load settings.", true);
  }
}

async function preloadTags() {
  try {
    await loadTags();
  } catch (error) {
    setStatus(error.message || "Could not load saved tags.", true);
  }
}

async function preloadSettings() {
  try {
    await loadSettings();
  } catch (error) {
    setStatus(error.message || "Could not load settings.", true);
  }
}

async function submitSimpleRoute() {
  const origin = elements.origin.value.trim();
  const destination = elements.destination.value.trim();

  if (!destination) {
    setStatus("Destination is required.", true);
    return;
  }

  setButtonLoading(elements.routeButton, true, "Go");
  setStatus("Calculating route...");

  try {
    const route = await requestRoute(origin, destination);
    await renderRoute(route);
    setStatus("Route ready.");
  } catch (error) {
    setStatus(error.message || "Something went wrong while loading the route.", true);
  } finally {
    setButtonLoading(elements.routeButton, false, "Go");
  }
}

async function submitTripPlan() {
  const instruction = elements.tripInstruction.value.trim();

  if (!instruction) {
    setStatus("Describe your trip first.", true);
    return;
  }

  setButtonLoading(elements.tripButton, true, "Plan");
  setStatus("Planning trip...");

  try {
    const plan = state.plannerAwaitingClarification && state.plannerThreadId
      ? await resumeTripPlan(instruction)
      : await requestTripPlan(instruction);
    await handleTripPlanResponse(plan);
  } catch (error) {
    setStatus(error.message || "Could not plan that trip.", true);
  } finally {
    setButtonLoading(elements.tripButton, false, "Plan");
  }
}

function setRoadTripStatus(message, isError = false) {
  elements.roadTripStatus.textContent = message;
  elements.roadTripStatus.classList.toggle("error", isError);
}

async function submitRoadTripPlan() {
  const origin = elements.roadTripOrigin.value.trim();
  const destination = elements.roadTripDestination.value.trim();

  if (!origin || !destination) {
    setRoadTripStatus("Enter both origin and destination.", true);
    return;
  }

  setButtonLoading(elements.roadTripButton, true, "Plan Route");
  setRoadTripStatus("Finding useful stops and destination ideas...");
  elements.roadTripResults.classList.add("hidden");

  try {
    const plan = await requestRoadTrip(origin, destination);
    await renderRoute(plan.route);
    renderRoadTripResults(plan);
    setRoadTripStatus("Road trip recommendations ready.");
  } catch (error) {
    setRoadTripStatus(error.message || "Could not plan that road trip.", true);
  } finally {
    setButtonLoading(elements.roadTripButton, false, "Plan Route");
  }
}

async function handleTripPlanResponse(plan) {
  state.plannerThreadId = plan.threadId || state.plannerThreadId;

  if (plan.choiceRequired || plan.status === "needs_choice") {
    state.plannerAwaitingClarification = false;
    clearRoute();
    if (window.TripChoiceModal) {
      window.TripChoiceModal.open(plan);
    } else {
      setStatus(plan.message || plan.prompt || "Choose a place to continue.", true);
    }
    return;
  }

  if (plan.clarificationRequired || plan.status === "needs_clarification") {
    state.plannerAwaitingClarification = true;
    clearRoute();
    elements.tripInstruction.value = "";
    elements.tripInstruction.placeholder = "Type your answer to continue this trip";
    elements.tripInstruction.focus();
    setStatus(plan.clarificationMessage || plan.prompt || "More information is needed.", true);
    return;
  }

  state.plannerAwaitingClarification = false;
  state.plannerThreadId = "";
  elements.tripInstruction.placeholder = "Start at home, pick up my friend in Subang Jaya, grab dinner, then return home avoiding tolls.";
  await renderRoute(plan);
  setStatus("Trip route ready.");
}

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

function updateFatigueDashboard(result) {
  elements.fatigueFaceStatus.textContent = result.faceDetected ? "Face detected" : "No face detected";
  updateFatigueScore(result.fatigueLevel, result.fatigueScore);
  updateFatigueCounters(result.symptomCounts);
  updateFatigueSymptoms(result.symptoms, result.symptomCounts);
  drawFatigueLandmarks(result.landmarks || {});

  if (result.alert && !state.fatigue.alertLocked) {
    state.fatigue.alertLocked = true;
    stopFatigueFrameLoop();
    setFatigueStatus("Fatigue alert active", "error");
    elements.fatigueAlertModal.classList.remove("hidden");
    elements.fatigueAlertModal.setAttribute("aria-hidden", "false");
  }
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
    "Frequent blinking": counts.blinks,
    Yawning: counts.yawns,
    "Head nodding": counts.headNods,
  };
  const count = countBySymptom[symptom];
  return count ? `${symptom} x${count}` : symptom;
}

function updateFatigueSymptoms(symptoms, counts = {}) {
  elements.fatigueSymptomsList.innerHTML = "";

  if (!symptoms || symptoms.length === 0) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = "No symptoms detected";
    elements.fatigueSymptomsList.appendChild(emptyItem);
    return;
  }

  symptoms.forEach((symptom) => {
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

function acknowledgeFatigueAlert() {
  state.fatigue.alertLocked = false;
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

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.mode === "simple") {
    await submitSimpleRoute();
  }
});

elements.sidebarToggle.addEventListener("click", toggleSidebar);
elements.sidebarClose.addEventListener("click", closeSidebar);
elements.sidebarScrim.addEventListener("click", closeSidebar);
elements.sidebarActions.addEventListener("click", (event) => {
  const button = event.target.closest("[data-mode]");
  if (!button) {
    return;
  }
  event.preventDefault();
  switchSidebarMode(button.dataset.mode);
});
elements.gpsButton.addEventListener("click", switchToSimpleMode);
elements.plannerButton.addEventListener("click", switchToPlannerMode);
elements.roadTripAppButton.addEventListener("click", switchToRoadTripMode);
elements.fatigueButton.addEventListener("click", openFatigueMonitor);
elements.editTagsButton.addEventListener("click", switchToTagsMode);
elements.settingsButton.addEventListener("click", switchToSettingsMode);
elements.tripButton.addEventListener("click", submitTripPlan);
elements.roadTripButton.addEventListener("click", submitRoadTripPlan);
elements.roadTripOrigin.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    submitRoadTripPlan();
  }
});
elements.roadTripDestination.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    submitRoadTripPlan();
  }
});
elements.saveHomeButton.addEventListener("click", () => saveTag("home"));
elements.saveWorkButton.addEventListener("click", () => saveTag("work"));
elements.saveCurrentLocationButton.addEventListener("click", saveCurrentLocation);
elements.fatigueStartButton.addEventListener("click", startFatigueDetection);
elements.fatigueStopButton.addEventListener("click", stopFatigueDetection);
elements.fatigueCloseButton.addEventListener("click", closeFatigueMonitor);
elements.fatigueAlertOkButton.addEventListener("click", acknowledgeFatigueAlert);
elements.fatigueMonitorDrag.addEventListener("mousedown", startFatigueDrag);
elements.fatigueMonitorDrag.addEventListener("touchstart", startFatigueDrag, { passive: true });
document.addEventListener("mousemove", dragFatigueMonitor);
document.addEventListener("touchmove", dragFatigueMonitor, { passive: false });
document.addEventListener("mouseup", stopFatigueDrag);
document.addEventListener("touchend", stopFatigueDrag);
window.addEventListener("resize", () => {
  syncFatigueCanvasSize();
  if (!elements.fatigueMonitor.classList.contains("hidden")) {
    const rect = elements.fatigueMonitor.getBoundingClientRect();
    const position = clampFatigueMonitorPosition(rect.left, rect.top);
    elements.fatigueMonitor.style.left = `${position.left}px`;
    elements.fatigueMonitor.style.top = `${position.top}px`;
    elements.fatigueMonitor.style.right = "auto";
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (!elements.fatigueAlertModal.classList.contains("hidden")) {
      acknowledgeFatigueAlert();
      return;
    }
    closeSidebar();
  }
});

updateClock();
setInterval(updateClock, 30_000);
preloadTags();
preloadSettings();

window.CarplayApp = {
  requestRoute,
  renderRoute,
  handleTripPlanResponse,
  setPlannerStatus(message, isError = false) {
    state.mode = "planner";
    setStatus(message, isError);
  },
};

loadMapConfig().catch((error) => {
  setStatus(error.message, true);
});
