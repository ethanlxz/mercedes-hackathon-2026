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
function removeRecommendation(id) {
  console.log('removeRecommendation called for id:', id);
  console.log('Markers before removal:', state.markers.length);

  // Remove recommendation from state list
  state.roadTripRecommendations = state.roadTripRecommendations.filter(r => r.id !== id);

  // Iterate over markers in reverse to safely splice
  for (let i = state.markers.length - 1; i >= 0; i--) {
    const marker = state.markers[i];
    if (marker.recommendationId === id) {
      console.log('Removing marker with id', id);
      if (typeof marker.setMap === 'function') {
        marker.setMap(null);
      }
      state.markers.splice(i, 1);
    }
  }

  console.log('Markers after removal:', state.markers.length);

  // Remove the recommendation card from the UI
  const card = document.getElementById(id);
  if (card) {
    console.log('Removing card element', id);
    card.remove();
  }
}

// Expose globally for inline onclick handlers
window.removeRecommendation = removeRecommendation;
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
    <article id="${recommendation.id}" class="recommendation-card recommendation-card-${escapeHtml(section)}">
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
          <button class="recommendation-remove-button" type="button" aria-label="Remove stop" onclick="removeRecommendation('${recommendation.id}')">
            <i class="fa-solid fa-xmark"></i>
          </button>
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

