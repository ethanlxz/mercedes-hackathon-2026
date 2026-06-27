async function requestSettings() {
  const response = await fetch("/api/settings");
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Could not load settings.");
  }

  return payload;
}

async function saveCurrentLocation() {
  const address = elements.currentLocationInput.value.trim();

  setButtonLoading(elements.saveCurrentLocationButton, true, "Submit");

  try {
    const response = await fetch("/api/settings/current-location", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not save current location.");
    }

    state.settings.currentLocation = payload.currentLocation || "";
    state.settings.evBatteryLevel = normalizeEVBatteryLevel(payload.evBatteryLevel);
    syncSettingsInputs();
    setStatus(
      state.settings.currentLocation
        ? "Current location saved."
        : "Current location cleared.",
    );
  } catch (error) {
    setStatus(error.message || "Could not save current location.", true);
  } finally {
    setButtonLoading(elements.saveCurrentLocationButton, false, "Submit");
  }
}

async function saveEVBatteryLevel() {
  const level = normalizeEVBatteryLevel(elements.evBatteryLevelInput.value);

  setButtonLoading(elements.saveEvBatteryLevelButton, true, "Submit");

  try {
    const response = await fetch("/api/settings/ev-battery-level", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ level }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not save EV battery level.");
    }

    state.settings.evBatteryLevel = normalizeEVBatteryLevel(payload.evBatteryLevel);
    syncSettingsInputs();
    setStatus("EV battery level saved.");
  } catch (error) {
    setStatus(error.message || "Could not save EV battery level.", true);
  } finally {
    setButtonLoading(elements.saveEvBatteryLevelButton, false, "Submit");
  }
}

async function loadTags() {
  const response = await fetch("/api/location-tags");
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || "Could not load location tags.");
  }

  state.tags = {
    home: payload.home || "",
    work: payload.work || "",
  };
  syncTagInputs();
}

async function loadSettings() {
  const payload = await requestSettings();
  state.settings.currentLocation = payload.currentLocation || "";
  state.settings.evBatteryLevel = normalizeEVBatteryLevel(payload.evBatteryLevel);
  state.preferenceMemory = normalizePreferenceMemory(payload.preferenceMemory);
  syncSettingsInputs();
}

function normalizePreferenceMemory(payload) {
  return {
    preferredStopTypes: Array.isArray(payload?.preferredStopTypes)
      ? payload.preferredStopTypes
      : [],
    dislikedStopTypes: Array.isArray(payload?.dislikedStopTypes)
      ? payload.dislikedStopTypes
      : [],
  };
}

async function saveTag(tag) {
  const addressInput = tag === "home" ? elements.homeAddress : elements.workAddress;
  const saveButton = tag === "home" ? elements.saveHomeButton : elements.saveWorkButton;
  const address = addressInput.value.trim();

  if (!address) {
    setStatus(`Enter a ${tag} address first.`, true);
    return;
  }

  setButtonLoading(saveButton, true, "Submit");

  try {
    const response = await fetch("/api/location-tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag, address }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not save tag.");
    }

    state.tags = {
      home: payload.home || "",
      work: payload.work || "",
    };
    syncTagInputs();
    setStatus(`${tag.charAt(0).toUpperCase()}${tag.slice(1)} tag saved.`);
  } catch (error) {
    setStatus(error.message || "Could not save tag.", true);
  } finally {
    setButtonLoading(saveButton, false, "Submit");
  }
}

function syncTagInputs() {
  elements.homeAddress.value = state.tags.home || "";
  elements.workAddress.value = state.tags.work || "";
}

function syncSettingsInputs() {
  elements.currentLocationInput.value = state.settings.currentLocation || "";
  elements.currentLocationDisplay.textContent = state.settings.currentLocation || "Not set";
  elements.evBatteryLevelInput.value = String(state.settings.evBatteryLevel);
  renderEVBatteryWidget(state.settings.evBatteryLevel);
  syncPreferenceMemoryUI();
}

function preferenceMemoryMarkup(items, emptyText) {
  if (!items.length) {
    return `<p class="preference-memory-empty">${escapeHtml(emptyText)}</p>`;
  }
  return `
    <ul class="preference-memory-list">
      ${items.map((item) => `
        <li>
          <span>${escapeHtml(item.category)}</span>
          <em>${Number(item.count) || 0}</em>
        </li>
      `).join("")}
    </ul>
  `;
}

function syncPreferenceMemoryUI() {
  if (!elements.preferenceMemoryPrefers || !elements.preferenceMemoryDislikes) {
    return;
  }
  elements.preferenceMemoryPrefers.innerHTML = preferenceMemoryMarkup(
    state.preferenceMemory.preferredStopTypes || [],
    "No preferred stop types yet.",
  );
  elements.preferenceMemoryDislikes.innerHTML = preferenceMemoryMarkup(
    state.preferenceMemory.dislikedStopTypes || [],
    "No disliked stop types yet.",
  );
}

async function resetSettingsPreferenceMemory() {
  setButtonLoading(elements.preferenceMemoryResetButton, true, "Reset");

  try {
    const payload = await resetPreferenceMemory();
    state.preferenceMemory = normalizePreferenceMemory(payload);
    syncPreferenceMemoryUI();
    setStatus("Preference memory reset.");
  } catch (error) {
    setStatus(error.message || "Could not reset preference memory.", true);
  } finally {
    setButtonLoading(elements.preferenceMemoryResetButton, false, "Reset");
  }
}

