# 📍 Google Maps Lead & Mobile Number Collector

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Automated_Scraping-green.svg?logo=playwright&logoColor=white)](https://playwright.dev/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Interactive_UI-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful, automated lead generation and business contact extraction tool for **Google Maps**. Extracts essential B2B details—including business names, verified mobile/phone numbers, categories, review metrics, physical addresses, websites, and direct Google Maps URLs—with support for both an **interactive Web UI** and a **scriptable Command-Line Interface (CLI)**.

---

## 📑 Table of Contents

- [Key Features](#-key-features)
- [Data Fields Extracted](#-data-fields-extracted)
- [Architecture & Workflow](#-architecture--workflow)
- [Prerequisites](#-prerequisites)
- [Quick Start Installation](#-quick-start-installation)
- [Usage: Web Interface (Streamlit)](#-usage-mode-1-interactive-web-interface)
- [Usage: Command Line (CLI)](#-usage-mode-2-command-line-cli)
- [CLI Reference](#-cli-arguments-reference)
- [Project Structure](#-project-structure)
- [Best Practices for Lead Generation](#-best-practices-for-lead-generation)
- [Troubleshooting & FAQ](#-troubleshooting--faq)
- [Legal & Ethical Disclaimer](#-legal--ethical-disclaimer)
- [License](#-license)

---

## ✨ Key Features

- **⚡ Dual Operation Modes**:
  - **Interactive Streamlit Web Dashboard**: Visual search interface with live progress bars, real-time lead tables, and one-click downloads.
  - **Command Line Interface (CLI)**: Ideal for headless server jobs, cron schedules, or automated scripts.
- **📱 Focused on Phone / Mobile Contacts**:
  - Automatically cleans, extracts, and normalizes contact numbers.
  - Built-in `--phone-only` filter to ignore listings lacking phone numbers, saving time during cold outreach campaigns.
- **🗺️ Multi-Location & Batch Scraping**:
  - Scrape multiple search queries sequentially (e.g., across multiple cities or distinct niches).
  - Automatically deduplicates records based on Business Name and Phone Number.
- **🛡️ Built-in Anti-Bot & Stealth Configuration**:
  - Randomized scrolling behavior and deliberate interaction delays.
  - Custom browser User-Agent and forced `en-US` locale.
  - Automatic handling and dismissal of Google cookie consent and prompt overlays.
- **📋 Customizable Field Selection**:
  - Choose exactly which fields you want to collect and export in both the UI and CLI (e.g. collect only Name, Phone, and Address).
  - One-click presets ("All Fields", "Contact Info", "Minimal") in the Web UI.
  - Skips unnecessary page lookups for unselected fields, speeding up extraction.
- **💬 Automated WhatsApp Outreach & Direct Chat Links**:
  - Automatically generates ready-to-click WhatsApp Web links (`https://wa.me/...`) for every phone number in Excel and CSV exports.
  - Dedicated **WhatsApp Automation Dashboard (Tab 3)** with QR code login, custom message templates with dynamic variables (`{Name}`, `{Category}`, etc.), safety delays, and live screen preview.
  - CLI script (`whatsapp_sender.py`) to automate messaging or test single numbers from the terminal.
- **📊 Export Formats**:
  - **Excel (`.xlsx`)**: Formatted spreadsheet ready for sales teams.
  - **CSV (`.csv`)**: Exported with `UTF-8 with BOM` (`utf-8-sig`) encoding to ensure international and localized characters display cleanly in Microsoft Excel.

---

## 📋 Data Fields Extracted

Every extracted lead includes the following structured fields:

| Field | Description | Example |
| :--- | :--- | :--- |
| **`Query`** | The search keyword / location used | `stationary shop around uttara` |
| **`Name`** | Official business or store name | `Shah Telecom & Stationery` |
| **`Phone`** | Cleaned contact number | `01915-438003` |
| **`WhatsApp`** | One-click direct chat link (`wa.me`) | `https://wa.me/8801915438003` |
| **`Category`** | Google Maps business category | `Stationery store` |
| **`Rating`** | Average customer star rating (out of 5.0) | `4.4` |
| **`Reviews`** | Total number of published reviews | `120` |
| **`Address`** | Full street address / landmark | `Dewancity, Uttara, Dhaka 1230` |
| **`Website`** | Official business website | `https://shahtelecom.com` |
| **`Google Maps URL`** | Permanent direct link to the listing | `https://www.google.com/maps/place/...` |

---

## 🔄 Architecture & Workflow

```
┌─────────────────────────────────┐
│ User Query (Web UI or Terminal) │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     Playwright Chromium Engine   │  <-- Anti-bot headers, en-US locale,
│   (Headless or Visible Window)  │      Consent prompt auto-dismissal
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│      Infinite Scroll Feed       │  <-- Dynamically loads places until
│     (div[role="feed"])          │      target limit or list end is reached
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│    Detailed Attribute Parser    │  <-- Clicks each card to open sidebar,
│  (Name, Phone, Category, etc.)  │      extracts phone, address, ratings
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│    Deduplication & Filtering    │  <-- Filters by phone-only if enabled,
│        (Pandas DataFrame)       │      removes duplicate businesses
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Export to Excel (.xlsx) / CSV  │
└─────────────────────────────────┘
```

---

## 🛠️ Prerequisites

- **Python**: Version `3.9` or higher
- **Operating System**: macOS, Linux, or Windows
- **Internet Connection**: Stable network access to `google.com/maps`

---

## 🚀 Quick Start Installation

1. **Clone or Navigate to the Project Directory**:
   ```bash
   cd gmaps_lead_collector
   ```

2. **Create and Activate a Virtual Environment**:
   - **macOS / Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright Browser Engine**:
   ```bash
   playwright install chromium
   ```
   *(On Linux servers without GUI libraries, you may also need: `playwright install-deps chromium`)*

---

## 🖥️ Usage Mode 1: Interactive Web Interface

Launch the Streamlit web dashboard:

```bash
streamlit run app_ui.py
```

The application will open automatically in your browser at `http://localhost:8501`.

### Web Dashboard Features:
1. **🔍 Single Search Tab**:
   - Specify your search query and target location (e.g., `pharmacy in gulshan`).
   - Set maximum results count (up to 300).
   - Toggle **📱 Phone Number Only** to exclude businesses without contact numbers.
   - Monitor real-time scraping progress and view a live tabular preview of results.
   - Download directly as **Excel (.xlsx)** or **CSV (.csv)** with one click.

2. **🗺️ Multi-Location / Multi-Keyword Search Tab**:
   - Enter multiple queries (one per line):
     ```text
     stationary shop in uttara
     stationary shop in mirpur
     stationary shop in dhanmondi
     ```
   - Automatically executes sequential searches, unifies all records, deduplicates identical businesses, and provides a combined downloadable file.

3. **💬 WhatsApp Automation Tab**:
   - **QR Code One-Click Connect**: Authenticate WhatsApp Web directly and store your persistent session locally in `./whatsapp_session`.
   - **Leads Source**: Message recent search results directly or upload any CSV/Excel file of leads.
   - **Personalized Template Editor**: Write custom outreach templates supporting dynamic variables (`{Name}`, `{Category}`, `{Address}`, `{Website}`, `{Phone}`).
   - **Safety Delay Controls**: Set configurable intervals (default: 8s) between messages to protect your account.
   - **Live Progress & Streaming**: Watch a real-time stream of WhatsApp Web actions side-by-side with delivery status logs.

---

## 💻 Usage Mode 2: Command Line (CLI)

The CLI tool (`scraper.py`) is suitable for automation, background tasks, and headless servers.

### Common Examples:

- **Basic Search (Excel Output)**:
  ```bash
  python scraper.py --query "stationary shop around uttara" --limit 30 --output uttara_shops.xlsx
  ```

- **Select Specific Fields to Collect**:
  ```bash
  python scraper.py --query "doctor chamber in uttara" --fields "Name,Phone,WhatsApp,Address,Website" --output doctors.xlsx
  ```

- **Filter Only Leads with Phone Numbers**:
  ```bash
  python scraper.py --query "doctor chamber in uttara" --limit 50 --phone-only --output doctors.xlsx
  ```

- **Export Directly to CSV**:
  ```bash
  python scraper.py --query "car repair in chittagong" --limit 40 --output car_repairs.csv
  ```

- **Batch Search Across Multiple Queries (Comma-Separated)**:
  ```bash
  python scraper.py --query "plumber in gulshan, plumber in banani, plumber in dhanmondi" --limit 25 --output plumbers_dhaka.xlsx
  ```

- **Visible Browser Window (Debugging Mode)**:
  ```bash
  python scraper.py --query "gyms in mohakhali" --limit 15 --visible
  ```

---

## 💬 Usage Mode 3: WhatsApp Outreach CLI (`whatsapp_sender.py`)

Send automated messages or test WhatsApp connectivity directly from the terminal:

- **Connect / Scan WhatsApp QR Code**:
  ```bash
  python whatsapp_sender.py --login
  ```

- **Verify Login Session**:
  ```bash
  python whatsapp_sender.py --check
  ```

- **Send Test Message to a Single Number**:
  ```bash
  python whatsapp_sender.py --phone "01932356801" --name "Dr. Ahmed" --template "Hello {Name}, are you accepting new patients?" --visible
  ```

- **Run Bulk Campaign from CSV or Excel**:
  ```bash
  python whatsapp_sender.py --file uttara_shops.csv --template "Hello {Name}, we noticed your business in {Address}. Are you open today?" --delay 10
  ```

---

## ⚙️ CLI Arguments Reference

### `scraper.py`
| Flag | Short | Default | Description |
| :--- | :---: | :---: | :--- |
| `--query` | `-q` | `stationary shop around uttara` | Search term or comma-separated list of search queries. |
| `--limit` | `-l` | `20` | Maximum number of results to collect per query. |
| `--output` | `-o` | `gmaps_leads.xlsx` | Output file path (`.xlsx` or `.csv`). |
| `--phone-only` | | `False` | Only retain records that contain a valid phone number. |
| `--fields` | `-f` | All fields | Comma-separated list of fields to collect (`Query, Name, Phone, WhatsApp, Category, Rating, Reviews, Address, Website, Google Maps URL`). |
| `--visible` | | `False` | Run browser with GUI window visible instead of headless mode. |

### `whatsapp_sender.py`
| Flag | Short | Default | Description |
| :--- | :---: | :---: | :--- |
| `--login` | | | Open visible browser window to scan QR code and save session. |
| `--check` | | | Check if authenticated WhatsApp session is saved. |
| `--file` | `-f` | | Path to Excel or CSV file containing leads to message. |
| `--phone` | `-p` | | Single phone number for a direct test message. |
| `--template` | `-t` | | Message template (supports `{Name}`, `{Address}`, etc.). |
| `--cc` | | `880` | Default country code prefix without `+` (e.g. `880`, `1`, `44`). |
| `--delay` | | `8` | Safety delay in seconds between messages. |
| `--visible` | | `False` | Run visible browser window instead of headless mode. |

---

## 📂 Project Structure

```
gmaps_lead_collector/
├── scraper.py          # Core Playwright scraping engine and CLI entry point
├── app_ui.py           # Streamlit web application frontend (Search + WhatsApp)
├── whatsapp_sender.py  # WhatsApp automation engine (Web automation & CLI)
├── requirements.txt    # Project Python dependencies
└── README.md           # Project documentation and user guide
```

---

## 💡 Best Practices for Lead Generation

1. **Specific Geographic Terms**: Use precise location indicators in your query (e.g., `coffee shop in Soho London` rather than just `coffee shop`).
2. **Handling Regional Character Sets**: If searching in non-English regions, the scraper retains local alphabets and formats them cleanly via UTF-8-BOM.
3. **Respect Rate Limits**: Google Maps may throttle rapid successive queries from a single IP. When doing massive bulk extractions, keep batch queries reasonable or space them out.
4. **Phone Number Formatting**: Some businesses report landlines, others report mobile numbers. The scraper strips prefixes like `Phone:` and `+Call` to keep the raw number clean.

---

## 🔧 Troubleshooting & FAQ

#### 1. `Executable doesn't exist at /Users/.../playwright/chromium...`
Run the Playwright installer command in your virtual environment:
```bash
playwright install chromium
```

#### 2. Why are some results missing phone numbers?
Not all business owners register their phone number on Google Business Profiles. To ensure your export only contains actionable contacts, check the **Phone Number Only** box in the UI or pass `--phone-only` in the CLI.

#### 3. Google Maps shows a consent or CAPTCHA prompt
The scraper automatically attempts to accept cookie consent dialogs. If you encounter a CAPTCHA due to high search frequency, run with the `--visible` flag to manually resolve it, or pause requests.

#### 4. The scraper stops before reaching the requested limit
Google Maps listings in specific geographical areas can be finite. If there are only 14 businesses matching the query in that area, the scraper will detect the end of the feed (`"You've reached the end of the list"`) and complete gracefully.

---

## ⚖️ Legal & Ethical Disclaimer

This project is intended strictly for personal research, educational purposes, and legitimate B2B contact discovery. Users must comply with Google's Terms of Service and applicable privacy regulations (such as GDPR, CAN-SPAM, or TCPA). The developers assume no liability for misuse of this tool.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE). Feel free to modify and adapt it for your lead generation workflows.
