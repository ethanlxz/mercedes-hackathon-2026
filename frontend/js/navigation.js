function switchToSimpleMode() {
  state.mode = "simple";
  setRouteCardLayout(state.mode);
  resetRouteCardScroll();
  elements.simplePanel.classList.remove("hidden");
  elements.plannerPanel.classList.add("hidden");
  elements.roadTripPanel.classList.add("hidden");
  elements.batteryPanel.classList.add("hidden");
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
  elements.batteryPanel.classList.add("hidden");
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
  elements.batteryPanel.classList.add("hidden");
  elements.tagsPanel.classList.add("hidden");
  elements.settingsPanel.classList.add("hidden");
  elements.roadTripStatus.classList.remove("error");
  elements.roadTripStatus.textContent = "Enter an origin and destination to find stops.";
  setActiveSidebarAction(elements.roadTripAppButton);
  closeSidebar();
}

async function switchToBatteryMode() {
  state.mode = "battery";
  setRouteCardLayout(state.mode);
  resetRouteCardScroll();
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.add("hidden");
  elements.roadTripPanel.classList.add("hidden");
  elements.batteryPanel.classList.remove("hidden");
  elements.tagsPanel.classList.add("hidden");
  elements.settingsPanel.classList.add("hidden");
  elements.batteryStatus.classList.remove("error");
  setActiveSidebarAction(elements.batteryButton);
  closeSidebar();

  if (state.batterySummary) {
    renderBatterySummary(state.batterySummary, { models_ready: true });
    await updateBatteryWeekdayPanel();
    return;
  }

  try {
    await loadBatterySummary();
    await submitBatteryPrediction();
  } catch (error) {
    setBatteryModelStatus("Model unavailable", false);
    setBatteryStatus(error.message || "Battery optimizer is unavailable.", true);
  }
}

async function switchToTagsMode() {
  state.mode = "tags";
  setRouteCardLayout(state.mode);
  resetRouteCardScroll();
  elements.simplePanel.classList.add("hidden");
  elements.plannerPanel.classList.add("hidden");
  elements.roadTripPanel.classList.add("hidden");
  elements.batteryPanel.classList.add("hidden");
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
  elements.batteryPanel.classList.add("hidden");
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

function closeRoadTripPanel() {
  if (elements.form) {
    elements.form.classList.add("hidden");
  }
  setActiveSidebarAction(null);
}

function closeSimpleGpsPanel() {
  if (elements.form) {
    elements.form.classList.add("hidden");
  }
  setActiveSidebarAction(null);
}

