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

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || `Request failed: ${response.status}`);
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

async function registerActiveRoadTrip(origin, destination, route) {
  const payload = await requestJson("/api/central-agent/active-road-trip", {
    method: "POST",
    body: JSON.stringify({ origin, destination, route }),
  });
  state.centralAgent.activeRouteId = payload.activeRouteId || "";
  return payload;
}

function getBrowserLocation() {
  if (!navigator.geolocation) {
    return Promise.resolve(null);
  }

  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      }),
      () => resolve(null),
      {
        enableHighAccuracy: false,
        maximumAge: 120000,
        timeout: 2200,
      },
    );
  });
}

async function requestFatigueRecommendation(fatigueResult) {
  const location = await getBrowserLocation();
  return requestJson("/api/central-agent/fatigue/recommendation", {
    method: "POST",
    body: JSON.stringify({
      activeRouteId: state.centralAgent.activeRouteId,
      fatigue: {
        faceDetected: Boolean(fatigueResult.faceDetected),
        fatigueLevel: fatigueResult.fatigueLevel || "",
        fatigueScore: Number(fatigueResult.fatigueScore) || 0,
        symptoms: fatigueResult.symptoms || [],
        symptomCounts: fatigueResult.symptomCounts || {},
        alert: Boolean(fatigueResult.alert),
      },
      location,
    }),
  });
}

async function acceptRestStopRecommendation(notification) {
  return requestJson("/api/central-agent/rest-stop/accept", {
    method: "POST",
    body: JSON.stringify({
      activeRouteId: state.centralAgent.activeRouteId,
      notificationId: notification.id,
      place: notification.place,
    }),
  });
}

async function requestChargingRecommendation(activeRouteId) {
  return requestJson("/api/central-agent/charging/recommendation", {
    method: "POST",
    body: JSON.stringify({ activeRouteId }),
  });
}

async function acceptChargingRecommendation(recommendation, place) {
  return requestJson("/api/central-agent/charging/accept", {
    method: "POST",
    body: JSON.stringify({
      activeRouteId: state.centralAgent.activeRouteId,
      notificationId: recommendation.id,
      place,
    }),
  });
}

async function sendPreferenceFeedback(recommendation, action) {
  return requestJson("/api/central-agent/preferences/feedback", {
    method: "POST",
    body: JSON.stringify({
      action,
      id: recommendation.id || "",
      placeId: recommendation.placeId || "",
      name: recommendation.name || "",
      address: recommendation.address || "",
      category: recommendation.category || recommendation.section || "Stop",
      section: recommendation.section || "route",
    }),
  });
}

async function resetPreferenceMemory() {
  return requestJson("/api/central-agent/preferences", {
    method: "DELETE",
  });
}

async function requestBatterySummary() {
  const health = await requestJson("/api/battery/health");
  const summary = await requestJson("/api/battery/model/summary");
  return { health, summary };
}

async function requestBatteryTrip(distanceKm) {
  return requestJson("/api/battery/predict/trip", {
    method: "POST",
    body: JSON.stringify({ distance_km: distanceKm }),
  });
}

async function requestBatteryDaily(dayOfWeek) {
  return requestJson("/api/battery/predict/daily", {
    method: "POST",
    body: JSON.stringify({ day_of_week: dayOfWeek }),
  });
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

