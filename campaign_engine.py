import os
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable
import pandas as pd
from playwright.sync_api import sync_playwright

import database
import whatsapp_sender
DEFAULT_SESSION_DIR = getattr(whatsapp_sender, "DEFAULT_SESSION_DIR", os.path.abspath("./whatsapp_session"))
DEFAULT_CHROME_UA = getattr(
    whatsapp_sender,
    "DEFAULT_CHROME_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
format_whatsapp_number = getattr(whatsapp_sender, "format_whatsapp_number", lambda p, cc="880": p)
send_whatsapp_message = getattr(whatsapp_sender, "send_whatsapp_message", lambda **kw: {"status": "Failed"})
check_login_status = getattr(whatsapp_sender, "check_login_status", lambda s=None: False)

def close_whatsapp_session(session_dir=None):
    if hasattr(whatsapp_sender, "close_whatsapp_session"):
        return whatsapp_sender.close_whatsapp_session(session_dir) if session_dir else whatsapp_sender.close_whatsapp_session()
    try:
        from pathlib import Path
        s_dir = session_dir or DEFAULT_SESSION_DIR
        p = Path(s_dir)
        marker = p / "session_active.marker"
        if marker.exists():
            marker.unlink()
        for lock in p.glob("Singleton*"):
            try:
                lock.unlink()
            except Exception:
                pass
        return True
    except Exception:
        return False
from scraper import clean_phone_number, clean_address, make_whatsapp_link, DEFAULT_FIELDS

def run_campaign(
    campaign_id: int,
    campaign_name: str,
    message_template: str,
    queries_or_locations: List[str],
    max_per_location: int = 20,
    default_country_code: str = "880",
    delay_between_messages: int = 6,
    show_browser: bool = False,
    media_path: Optional[str] = None,
    db_url: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    control_state: Optional[Dict] = None
) -> Dict:
    """
    Executes an end-to-end Automated Campaign:
    1. Connects to WhatsApp Web.
    2. Sequentially searches Google Maps for each location/keyword.
    3. As each business is extracted:
       - Immediately archives all listing fields to the database.
       - If valid phone number found:
         - Checks if phone was already messaged under this campaign (duplicate prevention).
         - If already sent: logs as 'Skipped Duplicate'.
         - If not sent: personalizes message, sends via WhatsApp Web, and logs result.
       - Dispatches live updates to UI grid with status and browser screenshot.
       - Supports real-time Pause, Resume, and Stop controls.
    4. Upon completion or stop, cleanly closes the WhatsApp session.
    """
    if control_state is None:
        control_state = {"paused": False, "stopped": False}

    stats = {
        "scraped": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "status": "Running"
    }

    live_grid_records = []
    database.update_campaign_status(campaign_id, "Running", db_url=db_url)

    def notify(msg: str, screenshot=None, latest_row=None):
        if latest_row:
            live_grid_records.append(latest_row)
        if progress_callback:
            progress_callback(
                msg=msg,
                stats=stats,
                screenshot=screenshot,
                grid_df=pd.DataFrame(live_grid_records) if live_grid_records else pd.DataFrame()
            )

    notify("🚀 Initializing Campaign automation engines...")

    with sync_playwright() as p:
        # 1. Launch WhatsApp Web persistent context
        notify("🔑 Connecting to WhatsApp Web session...")
        wa_context = p.chromium.launch_persistent_context(
            user_data_dir=DEFAULT_SESSION_DIR,
            headless=not show_browser,
            viewport={"width": 1280, "height": 900},
            user_agent=DEFAULT_CHROME_UA,
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        wa_context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        wa_page = wa_context.pages[0] if wa_context.pages else wa_context.new_page()

        try:
            wa_page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            notify(f"⚠️ WhatsApp Web load warning: {e}")

        # Wait up to 15 seconds for WhatsApp Web chat list to be ready
        start_wa_wait = time.time()
        wa_ready = False
        while time.time() - start_wa_wait < 15:
            if (
                wa_page.locator('#pane-side').count() > 0 or
                wa_page.locator('div[data-testid="chat-list"]').count() > 0 or
                wa_page.locator('div[aria-label*="chat list" i]').count() > 0 or
                wa_page.locator('header').count() > 0
            ):
                wa_ready = True
                break
            time.sleep(1.0)

        if not wa_ready:
            # Check for QR canvas
            if wa_page.locator('canvas, div[data-ref]').count() > 0:
                wa_shot = wa_page.screenshot()
                notify("⚠️ WhatsApp Web requires authentication. Please connect in Step 4 first.", screenshot=wa_shot)
                wa_context.close()
                database.update_campaign_status(campaign_id, "Stopped", db_url=db_url)
                return stats

        notify("🟢 WhatsApp Web connected and ready! Initializing Google Maps engine...")

        # 2. Launch Google Maps browser
        maps_browser = p.chromium.launch(
            headless=not show_browser,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        maps_context = maps_browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=DEFAULT_CHROME_UA
        )
        maps_page = maps_context.new_page()

        completed_locations = set()

        while True:
            # Handle Pause / Resume loop
            while control_state.get("paused") and not control_state.get("stopped"):
                database.update_campaign_status(campaign_id, "Paused", db_url=db_url)
                notify("⏸️ Campaign paused. Waiting for resume...")
                time.sleep(1.5)

            if control_state.get("stopped"):
                notify("⏹️ Campaign stopped by user.")
                break

            # Dynamically fetch current target locations from control_state (supports user edits)
            current_locations = control_state.get("locations", queries_or_locations)
            remaining_locs = [l.strip() for l in current_locations if l.strip() and l.strip() not in completed_locations]
            if not remaining_locs:
                # All target locations completed
                break

            loc_query = remaining_locs[0]
            completed_locations.add(loc_query)
            loc_idx = len(completed_locations)
            total_locs = len(current_locations)

            notify(f"🔍 Searching Google Maps for: '{loc_query}' [{loc_idx}/{total_locs}]...")

            encoded_query = urllib.parse.quote(loc_query)
            maps_url = f"https://www.google.com/maps/search/{encoded_query}?hl=en"

            try:
                maps_page.goto(maps_url, wait_until="domcontentloaded", timeout=40000)
            except Exception as nav_e:
                notify(f"Error loading Google Maps for {loc_query}: {nav_e}")
                continue

            # Accept cookies dialog if present
            try:
                consent_btn = maps_page.locator('button:has-text("Accept all"), button:has-text("I agree"), form[action*="consent"] button').first
                if consent_btn.count() > 0 and consent_btn.is_visible():
                    consent_btn.click()
                    time.sleep(1.0)
            except Exception:
                pass

            time.sleep(2.5)

            # Wait for feed or result panels
            feed_locator = maps_page.locator('div[role="feed"]')
            try:
                feed_locator.wait_for(state="visible", timeout=12000)
            except Exception:
                pass

            seen_names = set()
            scroll_attempts = 0
            max_scrolls = 25
            loc_collected = 0

            while loc_collected < max_per_location and scroll_attempts < max_scrolls:
                # Handle Pause / Resume loop
                while control_state.get("paused"):
                    database.update_campaign_status(campaign_id, "Paused", db_url=db_url)
                    notify("⏸️ Campaign paused. Waiting for resume...")
                    time.sleep(1.5)
                    if control_state.get("stopped"):
                        break

                if control_state.get("stopped"):
                    break

                # Scroll results feed
                if feed_locator.count() > 0:
                    try:
                        feed_locator.evaluate("el => el.scrollBy(0, 1000)")
                    except Exception:
                        pass
                else:
                    maps_page.keyboard.press("PageDown")

                time.sleep(1.5)
                scroll_attempts += 1

                # Locate listing card anchors
                anchors = maps_page.locator('a[href*="/maps/place/"]').all()
                if not anchors:
                    anchors = maps_page.locator('div[role="article"]').all()

                for a_elem in anchors:
                    if loc_collected >= max_per_location or control_state.get("stopped"):
                        break

                    # Check pause
                    while control_state.get("paused") and not control_state.get("stopped"):
                        time.sleep(1.0)

                    try:
                        # Extract title / name
                        raw_name = a_elem.get_attribute("aria-label") or ""
                        if not raw_name:
                            name_el = a_elem.locator('div.fontHeadlineSmall, div.qBF1Pd').first
                            if name_el.count() > 0:
                                raw_name = name_el.text_content() or ""

                        name = raw_name.strip()
                        if not name or name in seen_names:
                            continue

                        # Click listing to load detail panel
                        a_elem.scroll_into_view_if_needed(timeout=2000)
                        a_elem.click(timeout=3000)
                        time.sleep(1.8)

                        # Extract Phone
                        phone = ""
                        phone_btn = maps_page.locator('*[data-item-id*="phone:"], button[data-tooltip*="phone" i], button[data-tooltip*="ফোন" i], button[aria-label*="Phone" i], button[aria-label*="ফোন" i]').first
                        if phone_btn.count() > 0:
                            raw_p = phone_btn.get_attribute("aria-label") or phone_btn.text_content() or ""
                            phone = clean_phone_number(raw_p)

                        # Address
                        address = ""
                        addr_btn = maps_page.locator('*[data-item-id="address"], button[data-tooltip*="address" i], button[data-tooltip*="ঠিকানা" i], button[aria-label*="Address" i]').first
                        if addr_btn.count() > 0:
                            address = clean_address(addr_btn.get_attribute("aria-label") or addr_btn.text_content() or "")

                        # Category
                        category = ""
                        cat_el = maps_page.locator('button.DkEaL').first
                        if cat_el.count() > 0:
                            category = cat_el.text_content() or ""

                        # Website
                        website = ""
                        web_el = maps_page.locator('a[data-item-id="authority"]').first
                        if web_el.count() > 0:
                            website = web_el.get_attribute("href") or ""

                        # Rating & Reviews
                        rating = ""
                        reviews_count = ""
                        rat_el = maps_page.locator('div.F7nice span[aria-hidden="true"]').first
                        if rat_el.count() > 0:
                            rating = rat_el.text_content() or ""
                        rev_el = maps_page.locator('div.F7nice span[aria-label*="reviews"]').first
                        if rev_el.count() > 0:
                            r_match = re.findall(r'[\d,]+', rev_el.get_attribute("aria-label") or "")
                            if r_match:
                                reviews_count = r_match[0]

                        listing_url = maps_page.url

                        lead_record = {
                            "Query": loc_query,
                            "Name": name,
                            "Phone": phone,
                            "WhatsApp": make_whatsapp_link(phone, default_country_code),
                            "Category": category.strip(),
                            "Rating": rating.strip(),
                            "Reviews": reviews_count.strip(),
                            "Address": address.strip(),
                            "Website": website.strip(),
                            "Google Maps URL": listing_url
                        }

                        # 1. Immediately record listing into leads database
                        try:
                            database.save_leads_to_db([lead_record], db_url=db_url)
                        except Exception as dbe:
                            print(f"Database save error: {dbe}")

                        seen_names.add(name)
                        loc_collected += 1
                        stats["scraped"] += 1
                        database.update_campaign_stats(campaign_id, scraped_delta=1, db_url=db_url)

                        # Take screenshot of live action
                        try:
                            live_shot = maps_page.screenshot()
                        except Exception:
                            live_shot = None

                        # 2. Check phone and handle WhatsApp outreach
                        formatted_phone = format_whatsapp_number(phone, default_country_code) if phone else ""
                        msg_status = "No Phone"
                        sent_content = ""

                        if not formatted_phone:
                            msg_status = "No Phone Found"
                        else:
                            # Rule check: Check if phone was already messaged under this campaign
                            already_messaged = database.has_campaign_messaged_phone(
                                campaign_id=campaign_id,
                                phone=formatted_phone,
                                db_url=db_url
                            )

                            if already_messaged:
                                msg_status = "Skipped (Duplicate under this campaign)"
                                stats["skipped"] += 1
                                database.update_campaign_stats(campaign_id, skipped_delta=1, db_url=db_url)
                                database.log_campaign_message(
                                    campaign_id=campaign_id,
                                    campaign_name=campaign_name,
                                    lead_name=name,
                                    phone=formatted_phone,
                                    message_text="[Skipped Duplicate]",
                                    status="Skipped Duplicate",
                                    db_url=db_url
                                )
                            else:
                                # Prepare personalized message
                                active_template = control_state.get("message_template", message_template)
                                personalized_text = active_template
                                personalized_text = personalized_text.replace("{Name}", name)
                                personalized_text = personalized_text.replace("{Category}", category or "Business")
                                personalized_text = personalized_text.replace("{Address}", address or loc_query)
                                personalized_text = personalized_text.replace("{Phone}", phone or "")
                                personalized_text = personalized_text.replace("{Website}", website or "")
                                sent_content = personalized_text

                                notify(f"💬 Sending WhatsApp outreach to {name} ({formatted_phone})...", screenshot=live_shot)

                                # Send via active WhatsApp Web page
                                send_res = send_whatsapp_message(
                                    page=wa_page,
                                    phone=formatted_phone,
                                    message=personalized_text,
                                    media_path=media_path,
                                    timeout_ms=35000
                                )

                                res_status = send_res.get("status", "Failed")
                                if res_status == "Sent":
                                    msg_status = "Sent"
                                    stats["sent"] += 1
                                    database.update_campaign_stats(campaign_id, sent_delta=1, db_url=db_url)
                                    database.update_whatsapp_status(phone, "Sent", db_url=db_url)
                                else:
                                    msg_status = f"Failed ({send_res.get('error', res_status)})"
                                    stats["failed"] += 1
                                    database.update_campaign_stats(campaign_id, failed_delta=1, db_url=db_url)

                                database.log_campaign_message(
                                    campaign_id=campaign_id,
                                    campaign_name=campaign_name,
                                    lead_name=name,
                                    phone=formatted_phone,
                                    message_text=personalized_text,
                                    status=res_status,
                                    error_message=send_res.get("error"),
                                    db_url=db_url
                                )

                                # Safety delay between WhatsApp messages
                                time.sleep(delay_between_messages)

                        # Update Live Grid Row
                        grid_row = {
                            "Time": datetime.now().strftime("%H:%M:%S"),
                            "Business Name": name,
                            "Phone": phone or "N/A",
                            "Location / Query": loc_query,
                            "WhatsApp Status": msg_status,
                            "Rating": rating or "N/A",
                            "Category": category or "N/A"
                        }

                        notify(f"[{stats['scraped']} leads | {stats['sent']} sent] Processed: {name}", screenshot=live_shot, latest_row=grid_row)

                    except Exception as listing_err:
                        print(f"Listing extraction error: {listing_err}")
                        continue

            if control_state.get("stopped"):
                break

        # Finalize and close browsers
        maps_browser.close()
        wa_context.close()

        final_status = "Stopped" if control_state.get("stopped") else "Completed"
        stats["status"] = final_status
        database.update_campaign_status(campaign_id, final_status, db_url=db_url)

        # Rule: Close old WhatsApp connection after campaign is finished as specified
        close_whatsapp_session()

        notify(f"🎉 Campaign {final_status}! Total Scraped: {stats['scraped']}, Sent: {stats['sent']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}.")
        return stats
