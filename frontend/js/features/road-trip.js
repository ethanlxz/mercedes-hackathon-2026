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

  marker.recommendationId = recommendation.id;
  return marker;
}

function createChargingMarker(station, recommendation, index) {
  const place = station?.place;
  const position = {
    lat: Number(place?.latitude),
    lng: Number(place?.longitude),
  };
  if (!Number.isFinite(position.lat) || !Number.isFinite(position.lng)) {
    return null;
  }

  const marker = new google.maps.Marker({
    position,
    map: state.map,
    label: {
      text: "C",
      color: "#ffffff",
      fontSize: "12px",
      fontWeight: "900",
    },
    icon: {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 12,
      fillColor: "#22c55e",
      fillOpacity: 1,
      strokeColor: "#ffffff",
      strokeOpacity: 0.95,
      strokeWeight: 3,
    },
    title: `${place.name}: ${place.address}`,
    zIndex: 60 + index,
  });

  const hoverWaypoint = {
    role: "charging",
    label: place.name,
    address: place.address,
    rating: place.rating,
    userRatingCount: place.userRatingCount,
    category: "Charging Plan",
    explanation: station.distanceLabel || recommendation.message,
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

  marker.chargingRecommendationId = `${recommendation.id}-${index}`;
  return marker;
}

function formatBatteryPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "--%";
  }
  return `${number.toFixed(1).replace(/\.0$/, "")}%`;
}

function chargingDecisionTone(decision) {
  if (decision === "no_charging_required") {
    return "ready";
  }
  if (decision === "charge_during_trip") {
    return "critical";
  }
  return "warning";
}

function chargingStations(recommendation) {
  if (Array.isArray(recommendation?.stations) && recommendation.stations.length) {
    return recommendation.stations;
  }
  if (recommendation?.place) {
    return [{
      place: recommendation.place,
      distanceLabel: recommendation.distanceLabel || "",
      estimatedDriveSeconds: recommendation.estimatedDriveSeconds,
      distanceMeters: recommendation.distanceMeters,
    }];
  }
  return [];
}

function chargingStationMarkup(recommendation) {
  const stations = chargingStations(recommendation);
  if (!stations.length) {
    if (!recommendation.chargingRequired) {
      return "";
    }
    return `
      <div class="charging-station-card charging-station-empty">
        <span>No charger found nearby yet</span>
        <p>The trip still needs charging. Try a broader origin or destination if this keeps happening.</p>
      </div>
    `;
  }

  return `
    <div class="charging-station-list">
      ${stations.map((station, index) => {
        const place = station.place || {};
        const rating = formatRating(place.rating);
        const reviewCount = formatReviewCount(place.userRatingCount);
        const ratingText = rating
          ? `${rating} Google rating${reviewCount ? ` / ${reviewCount}` : ""}`
          : "Google rating unavailable";
        const mapsLink = place.googleMapsUri
          ? `<a href="${escapeHtml(place.googleMapsUri)}" target="_blank" rel="noreferrer">Open in Maps</a>`
          : "";
        const action = recommendation.chargingRequired
          ? `
            <button class="charging-add-button" type="button" data-charging-action="accept" data-charging-index="${index}">
              <i class="fa-solid fa-plus" aria-hidden="true"></i>
              Add stop
            </button>
          `
          : "";

        return `
          <article class="charging-station-card">
            <div class="charging-station-icon" aria-hidden="true">
              <i class="fa-solid fa-charging-station"></i>
            </div>
            <div class="charging-station-body">
              <span>${escapeHtml(station.distanceLabel || recommendation.distanceLabel || "Recommended charger")}</span>
              <strong>${escapeHtml(place.name || "Charging station")}</strong>
              <p>${escapeHtml(place.address || "Address unavailable")}</p>
              <em>${escapeHtml(ratingText)}</em>
              <div class="charging-station-actions">
                ${mapsLink}
                ${action}
              </div>
            </div>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function renderChargingPlan(recommendation, errorMessage = "") {
  if (!elements.chargingPlanModal || !elements.chargingPlanCard) {
    return;
  }

  state.roadTripChargingRecommendation = recommendation || null;
  elements.chargingPlanModal.classList.remove("hidden");
  elements.chargingPlanModal.setAttribute("aria-hidden", "false");

  if (!recommendation) {
    elements.chargingPlanModal.dataset.decision = "unavailable";
    if (elements.chargingPlanModalTitle) {
      elements.chargingPlanModalTitle.textContent = "Battery estimate unavailable";
    }
    elements.chargingPlanCard.innerHTML = `
      <article class="charging-plan-summary charging-plan-unavailable">
        <div class="charging-plan-topline">
          <span>Charging Plan</span>
          <em>Unavailable</em>
        </div>
        <strong>Battery estimate unavailable</strong>
        <p>${escapeHtml(errorMessage || "The route is ready, but the charging recommendation could not be calculated.")}</p>
      </article>
    `;
    return;
  }

  const tone = chargingDecisionTone(recommendation.decision);
  elements.chargingPlanModal.dataset.decision = recommendation.decision;
  if (elements.chargingPlanModalTitle) {
    elements.chargingPlanModalTitle.textContent = recommendation.title || "Charge estimate";
  }
  elements.chargingPlanCard.innerHTML = `
    <article class="charging-plan-summary charging-plan-${escapeHtml(tone)}">
      <div class="charging-plan-topline">
        <span>${escapeHtml(recommendation.title || "Charging Plan")}</span>
        <em>${recommendation.chargingRequired ? "Charging needed" : "Ready"}</em>
      </div>
      <strong>${escapeHtml(recommendation.message || "Charging recommendation ready.")}</strong>
      <div class="charging-metrics" aria-label="Charging battery metrics">
        <div>
          <span>Current</span>
          <strong>${escapeHtml(formatBatteryPercent(recommendation.currentBatteryPercent))}</strong>
        </div>
        <div>
          <span>Estimate</span>
          <strong>${escapeHtml(formatBatteryPercent(recommendation.requiredBatteryPercent))}</strong>
        </div>
        <div>
          <span>Arrival</span>
          <strong>${escapeHtml(formatBatteryPercent(recommendation.remainingBatteryPercent))}</strong>
        </div>
      </div>
      ${chargingStationMarkup(recommendation)}
    </article>
  `;

  chargingStations(recommendation).forEach((station, index) => {
    const marker = createChargingMarker(station, recommendation, index);
    if (marker) {
      state.markers.push(marker);
    }
  });
}

function closeChargingPlanModal() {
  if (!elements.chargingPlanModal) {
    return;
  }
  elements.chargingPlanModal.classList.add("hidden");
  elements.chargingPlanModal.setAttribute("aria-hidden", "true");
}

function findRecommendation(id) {
  return state.roadTripRecommendations.find((recommendation) => recommendation.id === id);
}

function applyPreferenceMemory(payload) {
  if (!payload) {
    return;
  }
  state.preferenceMemory = {
    preferredStopTypes: payload.preferredStopTypes || [],
    dislikedStopTypes: payload.dislikedStopTypes || [],
  };
  if (typeof syncPreferenceMemoryUI === "function") {
    syncPreferenceMemoryUI();
  }
}

function removeRecommendation(id) {
  state.roadTripRecommendations = state.roadTripRecommendations.filter((recommendation) => recommendation.id !== id);

  for (let i = state.markers.length - 1; i >= 0; i--) {
    const marker = state.markers[i];
    if (marker.recommendationId === id) {
      if (typeof marker.setMap === "function") {
        marker.setMap(null);
      }
      state.markers.splice(i, 1);
    }
  }

  const card = document.getElementById(id);
  if (card) {
    const list = card.closest(".recommendation-list");
    card.remove();
    if (list && !list.querySelector(".recommendation-card")) {
      list.innerHTML = `<p class="empty-recommendations">No recommendations found.</p>`;
    }
  }
}

async function loveRecommendation(id) {
  const recommendation = findRecommendation(id);
  const button = document.querySelector(`[data-recommendation-action="love"][data-recommendation-id="${CSS.escape(id)}"]`);
  if (!recommendation || !button) {
    return;
  }

  const nextLoved = button.getAttribute("aria-pressed") !== "true";
  recommendation.loved = nextLoved;
  button.setAttribute("aria-pressed", nextLoved ? "true" : "false");
  button.classList.toggle("active", nextLoved);
  button.setAttribute("aria-label", nextLoved ? "Unlike stop" : "Love stop");
  button.disabled = true;

  try {
    const payload = await sendPreferenceFeedback(recommendation, nextLoved ? "love" : "unlove");
    applyPreferenceMemory(payload);
    setRoadTripStatus(nextLoved ? "Preference saved." : "Preference removed.");
  } catch (error) {
    recommendation.loved = !nextLoved;
    button.setAttribute("aria-pressed", !nextLoved ? "true" : "false");
    button.classList.toggle("active", !nextLoved);
    button.setAttribute("aria-label", !nextLoved ? "Unlike stop" : "Love stop");
    setRoadTripStatus(error.message || "Could not update that preference.", true);
  } finally {
    button.disabled = false;
  }
}

async function closeRecommendation(id) {
  const recommendation = findRecommendation(id);
  if (!recommendation) {
    removeRecommendation(id);
    return;
  }

  removeRecommendation(id);

  try {
    const payload = await sendPreferenceFeedback(recommendation, "close");
    applyPreferenceMemory(payload);
    setRoadTripStatus("Recommendation removed.");
  } catch (error) {
    setRoadTripStatus(error.message || "Removed locally, but could not save the preference.", true);
  }
}

function handleRecommendationActionClick(event) {
  const button = event.target.closest("[data-recommendation-action]");
  if (!button) {
    return;
  }
  event.preventDefault();

  const id = button.dataset.recommendationId || "";
  if (!id) {
    return;
  }

  if (button.dataset.recommendationAction === "love") {
    loveRecommendation(id);
  } else if (button.dataset.recommendationAction === "close") {
    closeRecommendation(id);
  }
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
  await waitForMapReady();

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
    <article id="${escapeHtml(recommendation.id)}" class="recommendation-card recommendation-card-${escapeHtml(section)}" data-recommendation-id="${escapeHtml(recommendation.id)}">
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
        <div class="recommendation-card-footer">
          ${mapsLink}
          <div class="recommendation-card-actions">
            <button class="recommendation-love-button" type="button" aria-label="${recommendation.loved ? "Unlike stop" : "Love stop"}" aria-pressed="${recommendation.loved ? "true" : "false"}" data-recommendation-action="love" data-recommendation-id="${escapeHtml(recommendation.id)}">
              <i class="fa-solid fa-heart" aria-hidden="true"></i>
            </button>
            <button class="recommendation-remove-button" type="button" aria-label="Remove stop" data-recommendation-action="close" data-recommendation-id="${escapeHtml(recommendation.id)}">
              <i class="fa-solid fa-xmark" aria-hidden="true"></i>
            </button>
          </div>
        </div>
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
  renderChargingPlan(payload.chargingRecommendation, payload.chargingError || "");
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

async function acceptChargingStop(index) {
  const recommendation = state.roadTripChargingRecommendation;
  const station = chargingStations(recommendation)[index] || null;
  const place = station?.place || null;
  if (!place) {
    setRoadTripStatus("No charging station is available to add yet.", true);
    return;
  }

  const button = document.querySelector(`[data-charging-action='accept'][data-charging-index="${index}"]`);
  if (button) {
    button.disabled = true;
    button.textContent = "Adding...";
  }

  try {
    const route = await acceptChargingRecommendation(recommendation, place);
    await renderRoute(route);
    recommendation.added = true;
    if (button) {
      button.textContent = "Added to route";
      button.disabled = true;
    }
    setRoadTripStatus("Charging stop added to your route.");
  } catch (error) {
    setRoadTripStatus(error.message || "Could not add that charging stop.", true);
    if (button) {
      button.disabled = false;
      button.innerHTML = '<i class="fa-solid fa-plus" aria-hidden="true"></i> Add charger stop';
    }
  }
}

function handleChargingPlanClick(event) {
  const button = event.target.closest("[data-charging-action='accept']");
  if (!button) {
    return;
  }
  event.preventDefault();
  acceptChargingStop(Number(button.dataset.chargingIndex) || 0);
}

