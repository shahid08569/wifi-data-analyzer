# 📡 WiFi & Hotspot Data Analyzer (वाई-फाई और हॉटस्पॉट डेटा एनालाइज़र)

A lightweight, reliable, real-time and historical **Wi-Fi & Mobile Hotspot Data Usage Monitor** built natively for Windows.

---

## 🌟 Features (मुख्य विशेषताएं)

1. **Connected Devices Tracking (कनेक्टेड डिवाइसेस की निगरानी):**
   - Automatically detects all mobile phones, laptops, and PCs connected to your Wi-Fi or Mobile Hotspot.
   - Shows IP address, MAC address, Hostname, and Hardware Manufacturer (Samsung, Xiaomi, Apple, Intel, etc.).
   - Indicates live online/active status.

2. **Data Usage Filtering (समय के अनुसार फ़िल्टर):**
   - 📅 **Past Month (पिछला महीना / 30 दिन)**: View how much total data each connected device consumed over the last 30 days.
   - ⏱️ **Today (पिछले 24 घंटे)**: Check data usage for the current day.
   - 🗓️ **Last 7 Days**: Weekly summary.
   - ♾️ **All Time**: Cumulative usage since tracking started.
   - 📆 **Custom Date Range**: Choose any `From` and `To` dates.

3. **Special Mobile Hotspot Tracking (हॉटस्पॉट स्पेशल ट्रैकिंग):**
   - **Hotspot Active Duration**: Tracks exactly how long (Hours, Minutes, Seconds) your laptop's Mobile Hotspot was kept on.
   - **Hotspot Data Consumed**: Tracks the exact MB/GB consumed specifically by devices connected to your mobile hotspot.
   - **Session History Log**: Complete timestamped table of each hotspot session (Start time, End time, Duration, Max clients, Data used).

4. **Zero-Cloud & High Privacy:**
   - All data is stored locally in an optimized SQLite database (`backend/wifi_analyzer.db`).
   - No sensitive browsing history is tracked — strictly focused on **bandwidth (data used in MB/GB)**.

---

## 📁 Project Architecture & Branches

The project is organized into dedicated branches and modular directories:

- **`main`**: Complete fullstack application (Backend + Frontend).
- **`backend`**: FastAPI REST API, network scanner, SQLite database, and Windows background monitor.
- **`frontend`**: Responsive web dashboard (HTML5, Glassmorphism CSS, Vanilla JS).

```text
wifi-data-analyzer/
│
├── backend/
│   ├── app.py              # FastAPI server & REST endpoints
│   ├── database.py         # SQLite storage & filtering queries
│   ├── network_scanner.py  # ARP, NetNeighbor & OUI device discovery
│   ├── traffic_monitor.py  # Background bandwidth monitor
│   ├── hotspot_service.py  # Windows Mobile Hotspot state & session logger
│   └── requirements.txt    # Python dependencies
│
├── frontend/
│   ├── index.html          # Web dashboard UI
│   ├── css/style.css       # Clean modern dark theme
│   └── js/app.js           # Filtering & auto-refresh controller
│
├── start.bat               # 1-click startup script for Windows
├── README.md
└── .gitignore
```

---

## 🚀 How to Run (कैसे चलाएं)

### Method 1: One-Click (सबसे आसान तरीका)
Double-click `start.bat` in the project folder.

### Method 2: Manual Terminal
```bash
cd C:\Projects\wifi-data-analyzer\backend
py app.py
```

Then open your browser and go to:
👉 **`http://localhost:8000`**

---

## 🛠️ Tech Stack
- **Backend:** Python 3.13, FastAPI, Uvicorn, psutil, SQLite3
- **Frontend:** Modern HTML5, Responsive CSS3, JavaScript (Fetch API)
- **OS Integration:** Windows PowerShell, NetNeighbor, WinRT Tethering API, ARP
