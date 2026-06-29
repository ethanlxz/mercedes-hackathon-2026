elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.mode === "simple") {
    await submitSimpleRoute();
  } else if (state.mode === "battery") {
    await submitBatteryPrediction();
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
[
  elements.routeRecommendations,
  elements.destinationRecommendations,
  elements.foodRecommendations,
].forEach((container) => {
  container.addEventListener("click", handleRecommendationActionClick);
});
if (elements.chargingPlanCloseButton) {
  elements.chargingPlanCloseButton.addEventListener("click", closeChargingPlanModal);
}
if (elements.chargingPlanCollapsedButton) {
  elements.chargingPlanCollapsedButton.addEventListener("click", openChargingPlanModal);
}
if (elements.roadTripCloseButton) {
  elements.roadTripCloseButton.addEventListener("click", closeRoadTripPanel);
}
if (elements.simpleGpsCloseButton) {
  elements.simpleGpsCloseButton.addEventListener("click", closeSimpleGpsPanel);
}
elements.batteryPredictButton.addEventListener("click", submitBatteryPrediction);
elements.batteryResetButton.addEventListener("click", resetBatteryPanel);
elements.batteryWeekdayInput.addEventListener("change", updateBatteryWeekdayPanel);
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
elements.saveEvBatteryLevelButton.addEventListener("click", saveEVBatteryLevel);
elements.preferenceMemoryResetButton.addEventListener("click", resetSettingsPreferenceMemory);
elements.evBatteryLevelInput.addEventListener("input", (event) => {
  renderEVBatteryWidget(event.target.value);
});
elements.fatigueStartButton.addEventListener("click", startFatigueDetection);
elements.fatigueStopButton.addEventListener("click", stopFatigueDetection);
elements.fatigueCloseButton.addEventListener("click", closeFatigueMonitor);
elements.fatigueRestAcceptButton.addEventListener("click", acceptFatigueRestStop);
elements.fatigueAlertDismissButton.addEventListener("click", dismissFatigueAlert);
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
      dismissFatigueAlert();
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
  rejectMapReady(error);
  setStatus(error.message, true);
});

