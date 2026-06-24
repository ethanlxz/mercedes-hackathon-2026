function activeStatusElement() {
  if (state.mode === "planner") {
    return elements.plannerStatus;
  }
  if (state.mode === "roadTrip") {
    return elements.roadTripStatus;
  }
  if (state.mode === "battery") {
    return elements.batteryStatus;
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
    elements.batteryButton,
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
  } else if (state.mode === "battery") {
    setActiveSidebarAction(elements.batteryButton);
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
  elements.form.classList.toggle("route-card-battery", mode === "battery");
  elements.bottomPill.classList.toggle("hidden", mode === "battery");
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
  } else if (mode === "battery") {
    switchToBatteryMode();
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
  script.onerror = () => {
    const error = new Error("Google Maps could not load. Check the browser key and referrer restrictions.");
    rejectMapReady(error);
    setStatus(error.message, true);
  };
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
  resolveMapReady();

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

