const state = {
  map: null,
  routePolyline: null,
  routeHighlight: null,
  originMarker: null,
  destinationMarker: null,
};

const elements = {
  form: document.querySelector("#route-form"),
  origin: document.querySelector("#origin"),
  destination: document.querySelector("#destination"),
  button: document.querySelector("#route-button"),
  status: document.querySelector("#status"),
  duration: document.querySelector("#duration-text"),
  distance: document.querySelector("#distance-text"),
  arrival: document.querySelector("#arrival-time"),
  clock: document.querySelector("#clock"),
  routeLabel: document.querySelector("#route-label"),
};

function setStatus(message, isError = false) {
  elements.status.textContent = message;
  elements.status.classList.toggle("error", isError);
}

function setLoading(isLoading) {
  elements.button.disabled = isLoading;
  elements.button.textContent = isLoading ? "..." : "Go";
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

  setStatus("Enter an origin and destination.");
}

function clearRoute() {
  if (state.routePolyline) {
    state.routePolyline.setMap(null);
  }
  if (state.routeHighlight) {
    state.routeHighlight.setMap(null);
  }
  if (state.originMarker) {
    state.originMarker.setMap(null);
  }
  if (state.destinationMarker) {
    state.destinationMarker.setMap(null);
  }
}

function routeViewportPadding() {
  if (window.innerWidth <= 760) {
    return {
      top: 230,
      right: 35,
      bottom: 130,
      left: 95,
    };
  }

  return {
    top: 120,
    right: 120,
    bottom: 150,
    left: 520,
  };
}

function renderRoute(payload) {
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

  state.originMarker = new google.maps.Marker({
    position: path[0],
    map: state.map,
    label: "A",
  });
  state.destinationMarker = new google.maps.Marker({
    position: path[path.length - 1],
    map: state.map,
    label: "B",
  });

  elements.duration.textContent = payload.summary.durationText;
  elements.distance.textContent = payload.summary.distanceText;
  elements.arrival.textContent = formatArrival(payload.duration);
  elements.routeLabel.textContent = elements.destination.value.trim();
  elements.routeLabel.classList.remove("hidden");
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

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const origin = elements.origin.value.trim();
  const destination = elements.destination.value.trim();

  if (!origin || !destination) {
    setStatus("Origin and destination are required.", true);
    return;
  }

  setLoading(true);
  setStatus("Calculating route...");

  try {
    const route = await requestRoute(origin, destination);
    renderRoute(route);
    setStatus("Route ready.");
  } catch (error) {
    setStatus(error.message || "Something went wrong while loading the route.", true);
  } finally {
    setLoading(false);
  }
});

updateClock();
setInterval(updateClock, 30_000);

loadMapConfig().catch((error) => {
  setStatus(error.message, true);
});
