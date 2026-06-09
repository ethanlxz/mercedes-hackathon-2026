const foodCategories = [
  "Mamak",
  "Japanese",
  "Chinese",
  "Hotpot",
  "Indian",
  "Malay",
  "Western",
  "Mall",
];

const modalState = {
  referenceOrigin: "",
  choiceType: "food",
  choiceQuery: "",
  choiceReference: "",
  normalizedPlan: null,
  selectedCategory: foodCategories[0],
  recognition: null,
};

const modalElements = {
  modal: document.querySelector("#trip-choice-modal"),
  title: document.querySelector("#trip-choice-title"),
  close: document.querySelector("#trip-choice-close"),
  input: document.querySelector("#trip-choice-input"),
  voice: document.querySelector("#trip-choice-voice"),
  search: document.querySelector("#trip-choice-search-button"),
  foodTools: document.querySelector("#trip-choice-food-tools"),
  wheelToggle: document.querySelector("#trip-choice-wheel-toggle"),
  wheel: document.querySelector("#trip-choice-wheel"),
  wheelValue: document.querySelector("#trip-choice-wheel-value"),
  spin: document.querySelector("#trip-choice-spin"),
  status: document.querySelector("#trip-choice-status"),
  results: document.querySelector("#trip-choice-results"),
};

function modalEscapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setModalStatus(message, isError = false) {
  modalElements.status.textContent = message;
  modalElements.status.classList.toggle("error", isError);
}

function setModalButtonLoading(button, isLoading, label) {
  button.disabled = isLoading;
  button.textContent = isLoading ? "..." : label;
}

function closeTripChoiceModal() {
  modalElements.modal.classList.add("hidden");
  modalElements.modal.setAttribute("aria-hidden", "true");
  modalElements.results.innerHTML = "";
  setModalStatus("");
}

async function searchNearbyChoices(query) {
  const cleanedQuery = query.trim();
  if (!cleanedQuery) {
    setModalStatus("Tell me what to search for.", true);
    return;
  }

  setModalButtonLoading(modalElements.search, true, "Search");
  setModalStatus("Finding nearby places...");
  modalElements.results.innerHTML = "";

  try {
    const response = await fetch("/api/places/search-nearby", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: cleanedQuery,
        origin: modalState.referenceOrigin,
      }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not search nearby places.");
    }

    modalState.referenceOrigin = payload.referenceOrigin || modalState.referenceOrigin;
    renderChoiceResults(payload.results || []);
  } catch (error) {
    setModalStatus(error.message || "Could not search nearby places.", true);
  } finally {
    setModalButtonLoading(modalElements.search, false, "Search");
  }
}

function renderChoiceResults(results) {
  if (!results.length) {
    setModalStatus("No nearby results found. Try another search.", true);
    return;
  }

  setModalStatus("Choose a destination.");
  modalElements.results.innerHTML = results
    .map((place, index) => {
      const rating = Number(place.rating);
      const ratingMarkup = Number.isFinite(rating)
        ? `<em>${modalEscapeHtml(rating.toFixed(1).replace(/\.0$/, ""))} Google rating</em>`
        : "";
      return `
        <button class="trip-choice-result" type="button" data-choice-index="${index}">
          <strong>${modalEscapeHtml(place.name)}</strong>
          <span>${modalEscapeHtml(place.address)}</span>
          ${ratingMarkup}
        </button>
      `;
    })
    .join("");

  modalElements.results.querySelectorAll("[data-choice-index]").forEach((button) => {
    button.addEventListener("click", async () => {
      const place = results[Number(button.dataset.choiceIndex)];
      await chooseDestination(place);
    });
  });
}

async function chooseDestination(place) {
  if (!window.CarplayApp) {
    setModalStatus("Map app is still loading. Try again in a moment.", true);
    return;
  }

  setModalStatus("Routing to destination...");

  try {
    const response = await fetch("/api/trip-planner/choice-route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        normalizedPlan: modalState.normalizedPlan,
        choiceReference: modalState.choiceReference,
        selectedPlace: place,
      }),
    });
    const route = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(route.detail || "Could not route to that destination.");
    }

    await window.CarplayApp.renderRoute(route);
    window.CarplayApp.setPlannerStatus(`Route ready: ${place.name}.`);
    closeTripChoiceModal();
  } catch (error) {
    setModalStatus(error.message || "Could not route to that destination.", true);
  }
}

function spinFoodWheel() {
  const category = foodCategories[Math.floor(Math.random() * foodCategories.length)];
  modalState.selectedCategory = category;
  modalElements.wheelValue.textContent = category;
  modalElements.input.value = category === "Mall" ? "mall" : `${category} food`;
  searchNearbyChoices(modalElements.input.value);
}

function startVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    setModalStatus("Voice input is not supported in this browser.", true);
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-MY";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  modalState.recognition = recognition;

  recognition.addEventListener("start", () => {
    setModalStatus("Listening...");
  });
  recognition.addEventListener("result", (event) => {
    const transcript = event.results?.[0]?.[0]?.transcript || "";
    modalElements.input.value = transcript;
    setModalStatus("Voice input added.");
  });
  recognition.addEventListener("error", () => {
    setModalStatus("Could not hear that clearly. Try typing instead.", true);
  });
  recognition.start();
}

function openTripChoiceModal(plan) {
  modalState.referenceOrigin = plan.referenceOrigin || "";
  modalState.choiceType = plan.choiceType || "food";
  modalState.choiceQuery = plan.choiceQuery || "";
  modalState.choiceReference = plan.choiceReference || "";
  modalState.normalizedPlan = plan.normalizedPlan || null;
  modalElements.title.textContent = plan.message || "What would you like?";
  modalElements.input.value = "";
  modalElements.results.innerHTML = "";
  modalElements.foodTools.classList.toggle("hidden", modalState.choiceType !== "food");
  modalElements.wheel.classList.add("hidden");
  setModalStatus("");

  modalElements.modal.classList.remove("hidden");
  modalElements.modal.setAttribute("aria-hidden", "false");
  modalElements.input.focus();

  if (modalState.choiceType === "location" && modalState.choiceQuery) {
    modalElements.input.value = modalState.choiceQuery;
    searchNearbyChoices(modalState.choiceQuery);
  }
}

modalElements.close.addEventListener("click", closeTripChoiceModal);
modalElements.modal.addEventListener("click", (event) => {
  if (event.target === modalElements.modal) {
    closeTripChoiceModal();
  }
});
modalElements.search.addEventListener("click", () => {
  searchNearbyChoices(modalElements.input.value);
});
modalElements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchNearbyChoices(modalElements.input.value);
  }
});
modalElements.voice.addEventListener("click", startVoiceInput);
modalElements.wheelToggle.addEventListener("click", () => {
  modalElements.wheel.classList.toggle("hidden");
});
modalElements.spin.addEventListener("click", spinFoodWheel);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !modalElements.modal.classList.contains("hidden")) {
    closeTripChoiceModal();
  }
});

window.TripChoiceModal = {
  open: openTripChoiceModal,
  close: closeTripChoiceModal,
};
