const state = {
  map: null,
  geocoder: null,
  routePolyline: null,
  routeHighlight: null,
  markers: [],
  mode: "simple",
  tags: {
    home: "",
    work: "",
  },
};

const elements = {
  form: document.querySelector("#route-form"),
  plannerButton: document.querySelector("#planner-app-button"),
  simplePanel: document.querySelector("#simple-route-panel"),
  plannerPanel: document.querySelector("#planner-panel"),
  origin: document.querySelector("#origin"),
  destination: document.querySelector("#destination"),
  routeButton: document.querySelector("#route-button"),
  status: document.querySelector("#status"),
  plannerStatus: document.querySelector("#planner-status"),
  tripInstruction: document.querySelector("#trip-instruction"),
  tripButton: document.querySelector("#trip-button"),
  addTagsButton: document.querySelector("#add-tags-button"),
  tagPanel: document.querySelector("#tag-panel"),
  tagSelect: document.querySelector("#tag-select"),
  tagAddress: document.querySelector("#tag-address"),
  saveTagButton: document.querySelector("#save-tag-button"),
  currentTags: document.querySelector("#current-tags"),
  duration: document.querySelector("#duration-text"),
  distance: document.querySelector("#distance-text"),
  arrival: document.querySelector("#arrival-time"),
  clock: document.querySelector("#clock"),
};

function activeStatusElement() {
  return state.mode === "planner" ? elements.plannerStatus : elements.status;
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

function createRouteMarker(position, waypoint, index) {
  return new google.maps.Marker({
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

function renderCurrentTags() {
  elements.currentTags.innerHTML = `
    <div>Home: ${state.tags.home || "Not set"}</div>
    <div>Work: ${state.tags.work || "Not set"}</div>
  `;
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
  renderCurrentTags();
}

async function saveSelectedTag() {
  const tag = elements.tagSelect.value;
  const address = elements.tagAddress.value.trim();

  if (!address) {
    setStatus("Enter an address for the selected tag.", true);
    return;
  }

  setButtonLoading(elements.saveTagButton, true, "Save Tag");

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
    renderCurrentTags();
    setStatus(`${tag.charAt(0).toUpperCase()}${tag.slice(1)} tag saved.`);
  } catch (error) {
    setStatus(error.message || "Could not save tag.", true);
  } finally {
    setButtonLoading(elements.saveTagButton, false, "Save Tag");
  }
}

function syncTagInput() {
  elements.tagAddress.value = state.tags[elements.tagSelect.value] || "";
}

async function switchToPlannerMode() {
  state.mode = "planner";
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.remove("hidden");
  elements.plannerButton.classList.add("active");
  elements.plannerStatus.classList.remove("error");
  elements.plannerStatus.textContent = "Describe your whole trip in one instruction.";

  try {
    await loadTags();
    syncTagInput();
  } catch (error) {
    setStatus(error.message || "Could not load saved tags.", true);
  }
}

async function submitSimpleRoute() {
  const origin = elements.origin.value.trim();
  const destination = elements.destination.value.trim();

  if (!origin || !destination) {
    setStatus("Origin and destination are required.", true);
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

elements.plannerButton.addEventListener("click", switchToPlannerMode);
elements.tripButton.addEventListener("click", submitTripPlan);
elements.addTagsButton.addEventListener("click", () => {
  elements.tagPanel.classList.toggle("hidden");
  syncTagInput();
});
elements.tagSelect.addEventListener("change", syncTagInput);
elements.saveTagButton.addEventListener("click", saveSelectedTag);

updateClock();
setInterval(updateClock, 30_000);

loadMapConfig().catch((error) => {
  setStatus(error.message, true);
});
