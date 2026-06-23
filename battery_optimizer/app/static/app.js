const form = document.querySelector("#predictionForm");
const resetButton = document.querySelector("#resetButton");
const modelStatus = document.querySelector("#modelStatus");
const datasetRows = document.querySelector("#datasetRows");
const formMessage = document.querySelector("#formMessage");
const requiredBattery = document.querySelector("#requiredBattery");
const expectedDistance = document.querySelector("#expectedDistance");
const expectedUsage = document.querySelector("#expectedUsage");
const tripMessage = document.querySelector("#tripMessage");
const weeklyChart = document.querySelector("#weeklyChart");
const batteryInput = document.querySelector("#batteryInput");
const batteryFill = document.querySelector("#batteryFill");
const batteryGaugeValue = document.querySelector("#batteryGaugeValue");
const batteryKwh = document.querySelector("#batteryKwh");
const batteryStatus = document.querySelector("#batteryStatus");
const weekdayInput = document.querySelector("#weekdayInput");

let modelSummary = null;

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

function toNumber(formData, key) {
  return Number(formData.get(key));
}

function renderBatteryLevel(value) {
  const battery = Math.max(0, Math.min(100, Number(value) || 0));
  batteryFill.style.width = `${battery}%`;
  batteryGaugeValue.textContent = `${Math.round(battery)}%`;

  if (modelSummary) {
    const usable = (battery / 100) * modelSummary.battery_capacity_kwh;
    batteryKwh.textContent = `${usable.toFixed(1)} kWh available of ${modelSummary.battery_capacity_kwh.toFixed(1)} kWh`;
  }

  batteryStatus.textContent = "Separate from trip prediction";
}

function renderWeeklyAverages(dayOfWeek) {
  if (!modelSummary) return;

  const selected = modelSummary.weekday_stats.find((day) => day.day_of_week === dayOfWeek);
  if (!selected) return;

  expectedDistance.textContent = `${selected.expected_distance_km.toFixed(1)} km`;
  expectedUsage.textContent = `${selected.expected_battery_used_percent.toFixed(1)}%`;
}

function renderWeeklyChart(stats, activeDay) {
  if (!stats || !stats.length) {
    weeklyChart.innerHTML = '<p class="text-sm text-zinc-500">Weekly data unavailable.</p>';
    return;
  }

  const maxDistance = Math.max(...stats.map((day) => day.expected_distance_km));
  weeklyChart.innerHTML = stats
    .map((day) => {
      const label = day.day_of_week.slice(0, 3);
      const height = Math.max(24, (day.expected_distance_km / maxDistance) * 205);
      const isActive = day.day_of_week === activeDay;
      return `
        <div class="bar-group">
          <span class="bar-value">${day.expected_distance_km.toFixed(0)}</span>
          <div class="bar ${isActive ? "active" : ""}" style="height: ${height}px"></div>
          <span class="bar-label">${label}</span>
        </div>
      `;
    })
    .join("");
}

function updateWeekdayPanel() {
  const dayOfWeek = weekdayInput.value;
  renderWeeklyAverages(dayOfWeek);

  if (modelSummary) {
    renderWeeklyChart(modelSummary.weekday_stats, dayOfWeek);
  }
}

async function calculatePrediction() {
  const formData = new FormData(form);

  formMessage.textContent = "Calculating battery required...";

  const trip = await requestJson("/api/predict/trip", {
    method: "POST",
    body: JSON.stringify({
      distance_km: toNumber(formData, "distance_km"),
    }),
  });

  requiredBattery.textContent = `${trip.required_battery_percent}%`;
  tripMessage.textContent = trip.message;
  formMessage.textContent = "Prediction updated.";
}

async function loadSummary() {
  const [health, summary] = await Promise.all([
    requestJson("/api/health"),
    requestJson("/api/model/summary"),
  ]);

  modelSummary = summary;
  modelStatus.textContent = health.models_ready ? "Model ready" : "Model loading";
  modelStatus.classList.toggle("ready", health.models_ready);
  datasetRows.textContent = `Dataset: ${summary.row_count} rows`;
  renderBatteryLevel(batteryInput.value);
  updateWeekdayPanel();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  try {
    await calculatePrediction();
  } catch (error) {
    formMessage.textContent = error.message;
    tripMessage.textContent = "Prediction failed. Check the distance and try again.";
  }
});

batteryInput.addEventListener("input", (event) => renderBatteryLevel(event.target.value));
weekdayInput.addEventListener("change", updateWeekdayPanel);

resetButton.addEventListener("click", () => {
  form.reset();
  formMessage.textContent = "Inputs reset.";
});

loadSummary()
  .then(calculatePrediction)
  .catch((error) => {
    modelStatus.textContent = "Model unavailable";
    formMessage.textContent = error.message;
  });
