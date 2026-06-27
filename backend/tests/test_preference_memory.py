import json

from backend.app.schemas.preferences import StopPreferenceFeedbackRequest
from backend.app.services import memory_service


def test_central_agent_memory_defaults_merge_with_old_file(tmp_path, monkeypatch):
    memory_file = tmp_path / "user_memory.json"
    memory_file.write_text(
        json.dumps(
            {
                "locationTags": {"home": "Home address", "work": ""},
                "preferences": {"avoidTolls": True},
                "settings": {"currentLocation": "KL Sentral", "evBatteryLevel": 64},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(memory_service, "MEMORY_FILE", memory_file)

    memory = memory_service.load_memory()

    assert memory["locationTags"]["home"] == "Home address"
    assert memory["settings"]["evBatteryLevel"] == 64
    assert memory["centralAgentMemory"]["preferredStopTypes"] == {}
    assert memory["centralAgentMemory"]["dislikedStopTypes"] == {}


def test_stop_preference_feedback_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_service, "MEMORY_FILE", tmp_path / "user_memory.json")
    feedback = StopPreferenceFeedbackRequest(
        action="love",
        id="food-123",
        placeId="place-123",
        name="Coffee House",
        address="Jalan Coffee",
        category="Cafe",
        section="food",
    )

    first = memory_service.record_stop_preference_feedback(feedback)
    second = memory_service.record_stop_preference_feedback(feedback)

    assert first.preferredStopTypes[0].category == "Cafe"
    assert second.preferredStopTypes[0].count == 1
    assert second.dislikedStopTypes == []


def test_stop_preference_feedback_can_unlove(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_service, "MEMORY_FILE", tmp_path / "user_memory.json")
    love = StopPreferenceFeedbackRequest(
        action="love",
        id="food-123",
        placeId="place-123",
        name="Coffee House",
        address="Jalan Coffee",
        category="Cafe",
        section="food",
    )
    unlike = love.model_copy(update={"action": "unlove"})

    memory_service.record_stop_preference_feedback(love)
    summary = memory_service.record_stop_preference_feedback(unlike)

    assert summary.preferredStopTypes == []
    assert summary.dislikedStopTypes == []


def test_reset_stop_preference_memory_preserves_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_service, "MEMORY_FILE", tmp_path / "user_memory.json")
    memory_service.save_memory(
        {
            "locationTags": {"home": "Home address", "work": "Work address"},
            "preferences": {"avoidTolls": True},
            "settings": {"currentLocation": "KL Sentral", "evBatteryLevel": 64},
            "centralAgentMemory": {
                "preferredStopTypes": {"Cafe": 2},
                "dislikedStopTypes": {"Scenic stop": 1},
                "lovedPlaces": {"place:cafe": {"category": "Cafe"}},
                "dismissedPlaces": {"place:view": {"category": "Scenic stop"}},
            },
        }
    )

    summary = memory_service.reset_stop_preference_memory()
    memory = memory_service.load_memory()

    assert summary.preferredStopTypes == []
    assert summary.dislikedStopTypes == []
    assert memory["locationTags"]["home"] == "Home address"
    assert memory["preferences"]["avoidTolls"] is True
    assert memory["settings"]["evBatteryLevel"] == 64
