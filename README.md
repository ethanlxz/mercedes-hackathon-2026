# Mercedes-Benz MBUX Mobility Assistant Prototype

This repository contains a hackathon prototype for a **proactive, safe, and personalized driving assistant** built for Mercedes-Benz. 

The application features a modern, premium **MBUX Digital Cockpit Dashboard** dashboard that visualizes a simulated road trip from Kuala Lumpur (KL) to Penang, complete with real-time telemetry, automated driver fatigue tracking, EV battery management, long-term driver memory integration, and a mobility wallet.

---

## 🌟 Key Features

1. **Long-Term Memory**
   - Learns driver preferences and frequent stops over time.
   - When driving from **KL to Penang**, the agent recalls historical driver preferences (e.g. coffee stop at **Starbucks Ipoh**, charging at **Shell Recharge Tapah**) and proactively displays them.
   - Stores user preferences like target cabin climate and music tastes.

2. **Attention Assist (Safety Alert)**
   - Monitors driver drowsiness using a simulated fatigue index.
   - Triggers proactive **Rest Stop** recommendations when driver fatigue scales to **Medium** or **High**.
   - Accepts manual override to demonstrate instant safety alerting.

3. **EV Driving Simulation**
   - Automatically tracks vehicle speeds, battery discharge rate (SoC), and route progress on a Leaflet map.
   - When SoC falls below **25%**, the agent proactively prompts the driver to pull over at a charging station.
   - Adjust simulation multiplier speeds (**1x**, **10x**, **50x**) to run tests quickly.

4. **Structured JSON AI Recommendations Engine**
   - A built-in Rule-Engine Agent handles telemetry diagnostics and conversational text inputs.
   - Returns structured JSON payloads mapping out recommendation type (`rest_stop`, `charging`, `climate`, `digital_extra`), locations, reasoning, and confidence.
   - Interactive UI features a **JSON Inspector** displaying live response payloads.

5. **Integrated Mobility Wallet**
   - Simulates tolls, chargers, coffee shops, and digital extras purchases.
   - Fully integrated backend endpoints `/wallet/topup` and `/wallet/charge` log balance fluctuations directly to long-term memory.

---

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python 3.12+), Pydantic, Uvicorn
- **Frontend**: Vanilla HTML5, Vanilla CSS3 (Glassmorphism layout), Vanilla JavaScript
- **Mapping**: Leaflet.js using `CARTO Dark Matter` tile styling

---

## 📂 Project Structure

```text
mercedes/
├── backend/
│   ├── main.py          # FastAPI application server & recommendation agent
│   ├── requirements.txt # Python dependency file
│   └── memory.json      # Long-term memory JSON database
├── frontend/
│   ├── index.html       # MBUX dashboard user interface
│   ├── style.css        # Premium dark obsidian vehicle cabin styles
│   └── app.js           # Driving simulator & API connector logic
└── README.md            # Project documentation (this file)
```

---

## 🚀 Setup & Launch Instructions

### Step 1: Start the FastAPI Backend

1. Navigate to the project root directory.
2. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Run the FastAPI development server using Uvicorn:
   ```bash
   python backend/main.py
   ```
4. The server will start running at **`http://127.0.0.1:8000`**. You can verify and inspect backend APIs using FastAPI's interactive swagger docs at `http://127.0.0.1:8000/docs`.

### Step 2: Open the Frontend Dashboard

Since the frontend is a purely client-side Single Page Application (SPA), you can open it in any of the following ways:
- **Option A (Easiest)**: Double-click or open `frontend/index.html` in your web browser.
- **Option B (Server)**: Run a local static server inside the `frontend` folder:
  ```bash
  cd frontend
  python -m http.server 8080
  ```
  Then open **`http://localhost:8080`** in your browser.

*Note: The frontend has a robust auto-recovering fallback engine. If the backend server is not running or crashes, it automatically defaults to local mock execution mode so you can still demonstrate all cockpit functionalities.*

---

## 🚗 Interactive Guide: How to Test the Prototype

1. **Activate the Simulation**:
   - Click the **"Start Trip Simulation"** button on the map.
   - The car marker (bright teal pulse) will begin moving along the highway from Kuala Lumpur to Penang.
   - The speedometer, battery, and route progress will update dynamically.

2. **Trigger Attention Assist (Fatigue Safety)**:
   - Select **"High (Fatigued / Sleepy)"** from the *Attention Assist* dropdown.
   - The dashboard alerts trigger (status bar turns red, fatigue card glows).
   - An AI recommendation card pops up in the right panel: "Starbucks Ipoh - Rest Stop".
   - Click **"Rest & Order Coffee"** on the recommendation card. This charges the wallet RM15.00, resets fatigue back to low, and resumes the trip!

3. **EV Charge Low Trigger**:
   - Let the simulation run until battery SoC drops below **25%** (or wait for it during speed tests).
   - A proactive recommendation card "Shell Recharge Tapah" will appear.
   - Click **"Charge EV"**. It pauses simulation, charges the wallet RM45.00, refills battery to **100%**, and resumes.

4. **Conversational Command Inputs**:
   - In the chat console at the bottom-center, try typing:
     - `Plan my trip from KL to Penang` (Loads historical memory preferences).
     - `Where should I stop next?` (Provides progress-aware rest stop hints).
     - `Check battery status` (Inspects current SoC and remaining range).
     - `Play some music` (Triggers digital extra beats based on profile preference).

5. **JSON Payload Inspector**:
   - Click **"AI Recommendations Payload (JSON)"** in the right column to collapse/expand the raw JSON response returned by the backend `/agent/analyze` endpoint for inspection.
