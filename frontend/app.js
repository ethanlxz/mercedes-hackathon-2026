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
};

const elements = {
  form: document.querySelector("#route-form"),
  sideRail: document.querySelector("#side-rail"),
  sidebarToggle: document.querySelector("#sidebar-toggle"),
  sidebarClose: document.querySelector("#sidebar-close"),
  sidebarScrim: document.querySelector("#sidebar-scrim"),
  gpsButton: document.querySelector("#gps-app-button"),
  plannerButton: document.querySelector("#planner-app-button"),
  editTagsButton: document.querySelector("#edit-tags-button"),
  settingsButton: document.querySelector("#settings-app-button"),
  simplePanel: document.querySelector("#simple-route-panel"),
  plannerPanel: document.querySelector("#planner-panel"),
  tagsPanel: document.querySelector("#tags-panel"),
  settingsPanel: document.querySelector("#settings-panel"),
  origin: document.querySelector("#origin"),
  destination: document.querySelector("#destination"),
  routeButton: document.querySelector("#route-button"),
  status: document.querySelector("#status"),
  plannerStatus: document.querySelector("#planner-status"),
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
};

function activeStatusElement() {
  if (state.mode === "planner") {
    return elements.plannerStatus;
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
    elements.editTagsButton,
    elements.settingsButton,
  ].forEach((button) => {
    button.classList.toggle("active", button === activeButton);
  });
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

function waypointCardContent(waypoint) {
  const rating = formatRating(waypoint.rating);
  return `
    <div class="pin-hover-title">${escapeHtml(waypoint.label || "Location")}</div>
    <div class="pin-hover-address">${escapeHtml(waypoint.address || "")}</div>
    ${rating ? `<div class="pin-hover-rating">${escapeHtml(rating)} Google rating</div>` : ""}
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
  elements.simplePanel.classList.remove("hidden");
  elements.plannerPanel.classList.add("hidden");
  elements.tagsPanel.classList.add("hidden");
  elements.settingsPanel.classList.add("hidden");
  elements.status.classList.remove("error");
  elements.status.textContent = "Enter a destination. Origin can use Current Location or Home.";
  setActiveSidebarAction(elements.gpsButton);
  closeSidebar();
}

function switchToPlannerMode() {
  state.mode = "planner";
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.remove("hidden");
  elements.tagsPanel.classList.add("hidden");
  elements.settingsPanel.classList.add("hidden");
  elements.plannerStatus.classList.remove("error");
  elements.plannerStatus.textContent = "Describe your whole trip in one instruction.";
  setActiveSidebarAction(elements.plannerButton);
  closeSidebar();
}

async function switchToTagsMode() {
  state.mode = "tags";
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.add("hidden");
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
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.add("hidden");
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
    const plan = await requestTripPlan(instruction);
    if (plan.clarificationRequired) {
      clearRoute();
      setStatus(plan.clarificationMessage || "More information is needed.", true);
      return;
    }

    await renderRoute(plan);
    setStatus("Trip route ready.");
  } catch (error) {
    setStatus(error.message || "Could not plan that trip.", true);
  } finally {
    setButtonLoading(elements.tripButton, false, "Plan");
  }
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
elements.gpsButton.addEventListener("click", switchToSimpleMode);
elements.plannerButton.addEventListener("click", switchToPlannerMode);
elements.editTagsButton.addEventListener("click", switchToTagsMode);
elements.settingsButton.addEventListener("click", switchToSettingsMode);
elements.tripButton.addEventListener("click", submitTripPlan);
elements.saveHomeButton.addEventListener("click", () => saveTag("home"));
elements.saveWorkButton.addEventListener("click", () => saveTag("work"));
elements.saveCurrentLocationButton.addEventListener("click", saveCurrentLocation);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeSidebar();
  }
});

updateClock();
setInterval(updateClock, 30_000);
preloadTags();
preloadSettings();

loadMapConfig().catch((error) => {
  setStatus(error.message, true);
});
