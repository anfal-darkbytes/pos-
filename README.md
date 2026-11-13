# Pulse POS — Professional Django Edition

<p align="left">
  <img src="static/images/pulse-logo-horizontal.svg" alt="Pulse POS Logo" width="220" />
</p>

A high-performance Point of Sale (POS) system engineered with **Python, Django, Jinja2, Tailwind CSS, and Chart.js**. Designed for real-time vitality, speed, and accuracy in retail operations.

---

## 🏛 Architecture & Design

The application follows an enterprise, domain-driven modular Django architecture:

```
quickpos-python/
│
├── manage.py                          # Django management script
├── requirements.txt                   # Production dependencies
│
├── quickpos_project/                  # Core project configuration
│   ├── settings.py                    # Multi-engine templates, security, session auth
│   ├── urls.py                        # Unified URL router
│   ├── jinja2.py                      # Custom Jinja2 environment (filters, globals, JSON encoder)
│   ├── middleware.py                  # Session/User synchronization middleware
│   ├── wsgi.py                        # WSGI production entry
│   └── asgi.py                        # ASGI asynchronous entry
│
├── apps/
│   ├── accounts/                      # Staff accounts, roles (Admin/Manager/Cashier), OTP reset
│   │   ├── models.py                  # Custom User (AbstractUser), PasswordResetOTP
│   │   ├── views.py                   # Login, Logout, Register, OTP verification, Staff CRUD
│   │   └── urls.py
│   │
│   ├── inventory/                     # Product catalog & stock control
│   │   ├── models.py                  # Category, Product (SKU, barcode, stock, thresholds)
│   │   ├── views.py                   # Catalog manager, stock adjustments, barcode API, CSV export
│   │   └── urls.py
│   │
│   ├── customers/                     # Customer Relationship Management & Loyalty
│   │   ├── models.py                  # Customer (Bronze, Silver, Gold, Platinum tiers)
│   │   ├── views.py                   # Customer CRUD, search, lifetime value, CSV export
│   │   └── urls.py
│   │
│   ├── sales/                         # Point of Sale transactions & checkout engine
│   │   ├── models.py                  # Order, OrderItem
│   │   ├── views.py                   # POS Terminal, atomic checkout API, orders history, invoices
│   │   └── urls.py
│   │
│   ├── analytics/                     # Business intelligence & sales reporting
│   │   ├── views.py                   # Real-time dashboard KPIs, hourly trends, report charts
│   │   └── urls.py
│   │
│   └── core/                          # System configuration, store settings, initialization
│       ├── models.py                  # StoreSettings (currency, tax, store info)
│       ├── views.py                   # Store settings, payment accounts, PWA endpoints
│       ├── utils.py                   # POS template renderer, decorators, CSV utilities
│       └── management/commands/
│           └── init_quickpos.py       # Clean database initialization command
│
├── templates/                         # Jinja2-rendered responsive frontend views
│   ├── base.html                      # App shell, SPA navigation, live clock, sidebar
│   ├── pos.html                       # Touch-friendly POS terminal & cart
│   ├── dashboard.html                 # Executive summary & sales KPI cards
│   ├── products.html                  # Product & category management
│   ├── inventory.html                 # Stock status, alerts, and adjustments
│   ├── orders.html                    # Searchable order history
│   ├── invoices.html                  # Invoice listing & receipt export
│   ├── customers.html                 # CRM & loyalty points
│   ├── reports.html                   # Financial performance charts
│   └── settings.html                  # Store configuration & payment accounts
│
└── static/                            # Static assets
    ├── css/app.css                    # Custom styles, animations, scrollbars
    └── js/pos.js                      # High-speed client-side cart & checkout state
```

---

## ⚡ Key Features

- **Transactional POS Engine**: Atomic database transactions guarantee stock integrity during simultaneous checkouts.
- **Role-Based Access Control**: Configurable user levels (`Admin`, `Manager`, `Cashier`) with protected administration views.
- **Smart Catalog & Barcode Scanner**: Instant product lookups by barcode and SKU for rapid checkout.
- **Customer Loyalty Engine**: Automatic tier upgrades (`Bronze` → `Silver` → `Gold` → `Platinum`) based on purchase volume.
- **Real-Time Analytics**: Visual sales trends, top-selling items, category mix, and payment distribution powered by Chart.js.
- **Progressive Web App (PWA)**: Installable as a native desktop/mobile application with offline caching and background synchronization.
- **Clean Architecture**: Free of mock dummy transactions and bloated test records.

---

## 📲 Progressive Web App (PWA) & App Download

Pulse POS is a fully compliant PWA that can be downloaded and installed as a standalone desktop or mobile application on any operating system:

### How to Install / Download:
1. **Desktop (Windows / macOS / Linux)**:
   - Click the green **"Install App"** button in the top navigation bar or sidebar.
   - Or click the **Install icon (⊕)** in the browser's address bar (Chrome, Edge, Brave).
   - The app installs with a dedicated window, desktop shortcut, and taskbar integration.
2. **Android**:
   - Open Pulse POS in Chrome or Edge and tap **"Install App"** or the browser prompt.
   - The app installs to your app drawer and home screen.
3. **iOS / iPadOS (Safari)**:
   - Tap the **Share** button (`⎋`), scroll down, and select **"Add to Home Screen" (`⊞`)**.
   - Launches in fullscreen standalone mode without browser navigation chrome.
4. **Offline Resilience**:
   - A dedicated Service Worker pre-caches all core POS assets and terminal logic.
   - If the store's internet connection drops, the system seamlessly displays the offline fallback screen with auto-reconnection.

---

## 🚀 Quick Start

### 1. Setup Virtual Environment

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Apply Migrations & Initialize Clean System

```bash
python manage.py migrate
python manage.py init_quickpos
```

### 4. Run the Server

```bash
python manage.py runserver 0.0.0.0:8000
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🔐 Default Administrator Credentials

| Field | Value |
|---|---|
| **Email / User ID** | `admin@pulsepos.com` (or `admin@quickpos.com`) |
| **Password** | `Admin@202600` |
| **Role** | Administrator (`admin`) |

*Default settings and initial categories are automatically created upon running `init_quickpos`.*
