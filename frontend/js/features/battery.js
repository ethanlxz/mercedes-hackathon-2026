function normalizeEVBatteryLevel(value) {
  const level = Number(value);
  if (!Number.isFinite(level)) {
    return 82;
  }
  return Math.min(Math.max(Math.round(level), 0), 100);
}

function renderEVBatteryWidget(value) {
  const level = normalizeEVBatteryLevel(value);
  elements.evBatteryWidgetValue.textContent = `${level}%`;
  elements.evBatteryWidgetFill.style.width = `${level}%`;
  elements.evBatteryWidgetFill.classList.toggle("low", level <= 20);
  elements.evBatteryWidgetFill.classList.toggle("medium", level > 20 && level <= 50);
}

function setBatteryStatus(message, isError = false) {
  elements.batteryStatus.textContent = message;
  elements.batteryStatus.classList.toggle("error", isError);
}

function setBatteryModelStatus(message, isReady = false) {
  elements.batteryModelStatus.textContent = message;
  elements.batteryModelStatus.classList.toggle("ready", isReady);
}

function renderBatteryWeeklyChart(stats, activeDay) {
  if (!stats?.length) {
    elements.batteryWeeklyChart.innerHTML = '<p class="empty-recommendations">Weekly data unavailable.</p>';
    return;
  }

  const maxDistance = Math.max(...stats.map((day) => Number(day.expected_distance_km) || 0), 1);
  elements.batteryWeeklyChart.innerHTML = stats
    .map((day) => {
      const label = String(day.day_of_week || "").slice(0, 3);
      const distance = Number(day.expected_distance_km) || 0;
      const height = Math.max(24, (distance / maxDistance) * 160);
      const isActive = day.day_of_week === activeDay;
      return `
        <div class="battery-bar-group">
          <span>${Math.round(distance)}</span>
          <div class="battery-bar ${isActive ? "active" : ""}" style="height: ${height}px"></div>
          <em>${escapeHtml(label)}</em>
        </div>
      `;
    })
    .join("");
}

function renderBatterySummary(summary, health) {
  state.batterySummary = summary;
  setBatteryModelStatus(health.models_ready ? "Model ready" : "Model loading", health.models_ready);
  elements.batteryDatasetRows.textContent = `Dataset: ${summary.row_count} rows`;
  renderBatteryWeeklyChart(summary.weekday_stats || [], elements.batteryWeekdayInput.value);
}

async function loadBatterySummary() {
  setBatteryModelStatus("Model loading", false);
  setBatteryStatus("Loading battery model...");

  const { health, summary } = await requestBatterySummary();
  renderBatterySummary(summary, health);
  await updateBatteryWeekdayPanel();
  setBatteryStatus("Battery optimizer ready.");
}

async function submitBatteryPrediction() {
  const distanceKm = Number(elements.batteryDistanceInput.value);
  if (!Number.isFinite(distanceKm) || distanceKm <= 0) {
    setBatteryStatus("Enter a trip distance greater than 0 km.", true);
    return;
  }

  setButtonLoading(elements.batteryPredictButton, true, "Calculate Battery");
  setBatteryStatus("Calculating battery required...");

  try {
    const trip = await requestBatteryTrip(distanceKm);
    elements.batteryRequiredValue.textContent = `${trip.required_battery_percent}%`;
    setBatteryStatus(trip.message || "Battery prediction updated.");
  } catch (error) {
    setBatteryStatus(error.message || "Battery prediction failed.", true);
  } finally {
    setButtonLoading(elements.batteryPredictButton, false, "Calculate Battery");
  }
}

async function updateBatteryWeekdayPanel() {
  const dayOfWeek = elements.batteryWeekdayInput.value;

  if (state.batterySummary) {
    renderBatteryWeeklyChart(state.batterySummary.weekday_stats || [], dayOfWeek);
  }

  try {
    const daily = await requestBatteryDaily(dayOfWeek);
    elements.batteryExpectedDistance.textContent = `${daily.expected_distance_km} km`;
    elements.batteryExpectedUsage.textContent = `${daily.expected_battery_used_percent}%`;
  } catch (error) {
    setBatteryStatus(error.message || "Could not load weekday prediction.", true);
  }
}

function resetBatteryPanel() {
  elements.batteryDistanceInput.value = "80";
  elements.batteryWeekdayInput.value = "Tuesday";
  elements.batteryRequiredValue.textContent = "--%";
  elements.batteryExpectedDistance.textContent = "-- km";
  elements.batteryExpectedUsage.textContent = "--%";
  if (state.batterySummary) {
    renderBatteryWeeklyChart(state.batterySummary.weekday_stats || [], "Tuesday");
  }
  setBatteryStatus("Battery inputs reset.");
}

