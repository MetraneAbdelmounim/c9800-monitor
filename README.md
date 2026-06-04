# Cisco C9800 WLC Network Monitor

A full-stack monitoring application for Cisco Catalyst 9800 Wireless LAN Controllers.

- **Backend**: Python Flask REST API using RESTCONF
- **Frontend**: Angular 17 with a dark NOC-style dashboard

---

## Features

- **System Info**: Hostname, IOS-XE version, uptime
- **CPU & Memory**: Real-time gauges and trends
- **Access Points**: Full AP inventory with model, IP, location
- **Wireless Clients**: Client count by band (2.4/5/6 GHz)
- **WLANs/SSIDs**: Configuration and status overview
- **RF Data**: Radio Resource Management metrics
- **Client Experience**: Search any client -> RSSI, SNR, quality score, data rate, retries

---

## Prerequisites

- **Python 3.9+**
- **Node.js 18+** and **npm 9+**
- **Angular CLI 17+**
- Access to a Cisco C9800 WLC with RESTCONF enabled

---

## Quick Start

### 1. Enable RESTCONF on your C9800

```
configure terminal
  restconf
  ip http secure-server
  ip http authentication local
end
write memory
```

### 2. Backend Setup

```bash
cd backend

# (Optional) Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Edit configuration
# Open config.py and update:
#   WLC_HOST     = "your-wlc-ip"
#   WLC_USERNAME = "your-username"
#   WLC_PASSWORD = "your-password"

# Run the API server
python app.py
```

The API will start on **http://localhost:5000**.

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
ng serve
# OR if Angular CLI is not global:
npx ng serve
```

The frontend will start on **http://localhost:4200**.

Open your browser and go to **http://localhost:4200**.

---

## API Endpoints

| Method | Endpoint                    | Description                        |
|--------|-----------------------------|------------------------------------|
| GET    | /api/health                 | WLC connectivity check             |
| GET    | /api/system                 | Hostname, version, uptime          |
| GET    | /api/cpu                    | CPU utilization (5s, 1m, 5m)       |
| GET    | /api/memory                 | Memory pools usage                 |
| GET    | /api/aps                    | All Access Points                  |
| GET    | /api/aps/<mac>              | Single AP detail                   |
| GET    | /api/clients                | Client count by band               |
| GET    | /api/clients/detail         | All clients with RF metrics        |
| GET    | /api/clients/search?q=      | Search by MAC/IP/username/hostname |
| GET    | /api/clients/<mac>          | Single client full detail          |
| GET    | /api/clients/stats          | Aggregated client experience stats |
| GET    | /api/wlans                  | WLAN/SSID list                     |
| GET    | /api/rf                     | RF/RRM operational data            |
| GET    | /api/interfaces             | Interface status                   |
| GET    | /api/dashboard              | Aggregated all-in-one              |

---

## Troubleshooting

- **CORS errors**: The Flask backend includes CORS headers. Make sure backend runs on port 5000.
- **Connection refused**: Verify RESTCONF is enabled on the WLC and the IP/credentials are correct.
- **SSL errors**: By default verify_ssl=False. For production, use valid certificates.
- **Angular CLI not found**: Run npm install -g @angular/cli or use npx ng serve.
