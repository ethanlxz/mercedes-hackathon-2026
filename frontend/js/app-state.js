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
    evBatteryLevel: 82,
  },
  preferenceMemory: {
    preferredStopTypes: [],
    dislikedStopTypes: [],
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
  centralAgent: {
    activeRouteId: "",
    requestInFlight: false,
    cooldownUntil: 0,
    pendingNotification: null,
  },
  plannerThreadId: "",
  plannerAwaitingClarification: false,
  roadTripRecommendations: [],
  roadTripChargingRecommendation: null,
  batterySummary: null,
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
  batteryButton: document.querySelector("#battery-app-button"),
  fatigueButton: document.querySelector("#fatigue-app-button"),
  editTagsButton: document.querySelector("#edit-tags-button"),
  settingsButton: document.querySelector("#settings-app-button"),
  simplePanel: document.querySelector("#simple-route-panel"),
  plannerPanel: document.querySelector("#planner-panel"),
  roadTripPanel: document.querySelector("#road-trip-panel"),
  batteryPanel: document.querySelector("#battery-panel"),
  tagsPanel: document.querySelector("#tags-panel"),
  settingsPanel: document.querySelector("#settings-panel"),
  origin: document.querySelector("#origin"),
  destination: document.querySelector("#destination"),
  routeButton: document.querySelector("#route-button"),
  status: document.querySelector("#status"),
  simpleGpsCloseButton: document.querySelector("#simple-gps-close-button"),
  plannerStatus: document.querySelector("#planner-status"),
  roadTripOrigin: document.querySelector("#road-trip-origin"),
  roadTripDestination: document.querySelector("#road-trip-destination"),
  roadTripButton: document.querySelector("#road-trip-button"),
  roadTripCloseButton: document.querySelector("#road-trip-close-button"),
  roadTripStatus: document.querySelector("#road-trip-status"),
  roadTripResults: document.querySelector("#road-trip-results"),
  chargingPlanModal: document.querySelector("#charging-plan-modal"),
  chargingPlanCloseButton: document.querySelector("#charging-plan-close-button"),
  chargingPlanCollapsedButton: document.querySelector("#charging-plan-collapsed-button"),
  chargingPlanModalTitle: document.querySelector("#charging-plan-modal-title"),
  chargingPlanCard: document.querySelector("#charging-plan-card"),
  routeRecommendations: document.querySelector("#route-recommendations"),
  destinationRecommendations: document.querySelector("#destination-recommendations"),
  foodRecommendations: document.querySelector("#food-recommendations"),
  batteryModelStatus: document.querySelector("#battery-model-status"),
  batteryDatasetRows: document.querySelector("#battery-dataset-rows"),
  batteryDistanceInput: document.querySelector("#battery-distance-input"),
  batteryPredictButton: document.querySelector("#battery-predict-button"),
  batteryResetButton: document.querySelector("#battery-reset-button"),
  batteryRequiredValue: document.querySelector("#battery-required-value"),
  batteryStatus: document.querySelector("#battery-status"),
  batteryWeekdayInput: document.querySelector("#battery-weekday-input"),
  batteryExpectedDistance: document.querySelector("#battery-expected-distance"),
  batteryExpectedUsage: document.querySelector("#battery-expected-usage"),
  batteryWeeklyChart: document.querySelector("#battery-weekly-chart"),
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
  evBatteryLevelInput: document.querySelector("#ev-battery-level-input"),
  saveEvBatteryLevelButton: document.querySelector("#save-ev-battery-level-button"),
  preferenceMemoryPrefers: document.querySelector("#preference-memory-prefers"),
  preferenceMemoryDislikes: document.querySelector("#preference-memory-dislikes"),
  preferenceMemoryResetButton: document.querySelector("#preference-memory-reset-button"),
  evBatteryWidgetValue: document.querySelector("#ev-battery-widget-value"),
  evBatteryWidgetFill: document.querySelector("#ev-battery-widget-fill"),
  bottomPill: document.querySelector(".bottom-pill"),
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
  fatigueAlertDialog: document.querySelector(".fatigue-alert-dialog"),
  fatigueAlertEyebrow: document.querySelector("#fatigue-alert-eyebrow"),
  fatigueAlertTitle: document.querySelector("#fatigue-alert-title"),
  fatigueAlertMessage: document.querySelector("#fatigue-alert-message"),
  fatigueRestCard: document.querySelector("#fatigue-rest-card"),
  fatigueRestMeta: document.querySelector("#fatigue-rest-meta"),
  fatigueRestName: document.querySelector("#fatigue-rest-name"),
  fatigueRestAddress: document.querySelector("#fatigue-rest-address"),
  fatigueRestAcceptButton: document.querySelector("#fatigue-rest-accept-button"),
  fatigueAlertDismissButton: document.querySelector("#fatigue-alert-dismiss-button"),
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
let resolveMapReady;
let rejectMapReady;
const mapReadyPromise = new Promise((resolve, reject) => {
  resolveMapReady = resolve;
  rejectMapReady = reject;
});
mapReadyPromise.catch(() => {});

function isMapReady() {
  return Boolean(state.map && window.google?.maps?.geometry?.encoding);
}

async function waitForMapReady() {
  if (isMapReady()) {
    return;
  }

  const timeout = new Promise((_, reject) => {
    window.setTimeout(() => {
      reject(new Error("Google Maps is still loading. Try again in a moment."));
    }, 10_000);
  });

  await Promise.race([mapReadyPromise, timeout]);

  if (!isMapReady()) {
    throw new Error("Google Maps is still loading. Try again in a moment.");
  }
}

