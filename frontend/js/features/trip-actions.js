async function submitSimpleRoute() {
  const origin = elements.origin.value.trim();
  const destination = elements.destination.value.trim();

  if (!destination) {
    setStatus("Destination is required.", true);
    return;
  }

  setButtonLoading(elements.routeButton, true, "Go");
  setStatus("Calculating route...");

  try {
    const route = await requestRoute(origin, destination);
    await renderRoute(route);
    setStatus("Route ready.");
  } catch (error) {
    setStatus(error.message || "Something went wrong while loading the route.", true);
  } finally {
    setButtonLoading(elements.routeButton, false, "Go");
  }
}

async function submitTripPlan() {
  const instruction = elements.tripInstruction.value.trim();

  if (!instruction) {
    setStatus("Describe your trip first.", true);
    return;
  }

  setButtonLoading(elements.tripButton, true, "Plan");
  setStatus("Planning trip...");

  try {
    const plan = state.plannerAwaitingClarification && state.plannerThreadId
      ? await resumeTripPlan(instruction)
      : await requestTripPlan(instruction);
    await handleTripPlanResponse(plan);
  } catch (error) {
    setStatus(error.message || "Could not plan that trip.", true);
  } finally {
    setButtonLoading(elements.tripButton, false, "Plan");
  }
}

function setRoadTripStatus(message, isError = false) {
  elements.roadTripStatus.textContent = message;
  elements.roadTripStatus.classList.toggle("error", isError);
}

async function submitRoadTripPlan() {
  const origin = elements.roadTripOrigin.value.trim();
  const destination = elements.roadTripDestination.value.trim();

  if (!origin || !destination) {
    setRoadTripStatus("Enter both origin and destination.", true);
    return;
  }

  setButtonLoading(elements.roadTripButton, true, "Plan Route");
  setRoadTripStatus("Finding useful stops and destination ideas...");
  elements.roadTripResults.classList.add("hidden");

  try {
    const plan = await requestRoadTrip(origin, destination);
    await renderRoute(plan.route);
    await registerActiveRoadTrip(origin, destination, plan.route);
    renderRoadTripResults(plan);
    setRoadTripStatus("Road trip recommendations ready.");
  } catch (error) {
    setRoadTripStatus(error.message || "Could not plan that road trip.", true);
  } finally {
    setButtonLoading(elements.roadTripButton, false, "Plan Route");
  }
}

async function handleTripPlanResponse(plan) {
  state.plannerThreadId = plan.threadId || state.plannerThreadId;

  if (plan.choiceRequired || plan.status === "needs_choice") {
    state.plannerAwaitingClarification = false;
    clearRoute();
    if (window.TripChoiceModal) {
      window.TripChoiceModal.open(plan);
    } else {
      setStatus(plan.message || plan.prompt || "Choose a place to continue.", true);
    }
    return;
  }

  if (plan.clarificationRequired || plan.status === "needs_clarification") {
    state.plannerAwaitingClarification = true;
    clearRoute();
    elements.tripInstruction.value = "";
    elements.tripInstruction.placeholder = "Type your answer to continue this trip";
    elements.tripInstruction.focus();
    setStatus(plan.clarificationMessage || plan.prompt || "More information is needed.", true);
    return;
  }

  state.plannerAwaitingClarification = false;
  state.plannerThreadId = "";
  elements.tripInstruction.placeholder = "Start at home, pick up my friend in Subang Jaya, grab dinner, then return home avoiding tolls.";
  await renderRoute(plan);
  setStatus("Trip route ready.");
}

