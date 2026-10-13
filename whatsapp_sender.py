import os
import re
import time
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

DEFAULT_SESSION_DIR = os.path.abspath("./whatsapp_session")
DEFAULT_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

def format_whatsapp_number(phone: str, default_country_code: str = "880") -> str:
    """Format phone number with country code for WhatsApp Web."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', str(phone))
    if not digits:
        return ""
    cc = default_country_code.lstrip('+')
    # If starts with leading 0 (e.g. 01712345678 in Bangladesh)
    if digits.startswith('0') and len(digits) == 11 and cc == '880':
        digits = '88' + digits
    elif digits.startswith('0') and cc:
        digits = cc + digits[1:]
    elif not digits.startswith(cc) and len(digits) <= 10:
        digits = cc + digits
    return digits

def check_login_status(session_dir: str = DEFAULT_SESSION_DIR) -> bool:
    """Check if WhatsApp Web session is already authenticated."""
    session_path = Path(session_dir)
    if not session_path.exists():
        return False
    marker = session_path / "session_active.marker"
    if marker.exists():
        return True
    idb = session_path / "Default" / "IndexedDB"
    if idb.exists() and any(idb.glob("*")):
        return True
    contents = list(session_path.glob("*"))
    return len(contents) > 3

def is_headless_environment() -> bool:
    """Detect if running on a headless cloud server without an X11 desktop display."""
    import platform
    if platform.system() == "Linux" and not os.environ.get("DISPLAY"):
        return True
    return False

def launch_whatsapp_login_window(
    session_dir: str = DEFAULT_SESSION_DIR, 
    timeout_minutes: int = 3,
    qr_callback = None,
    headless = None
) -> bool:
    """
    Opens browser for the user to scan WhatsApp QR code.
    If running in a headless cloud environment (like Streamlit Cloud), runs headless
    and streams QR code screenshots via qr_callback.
    """
    os.makedirs(session_dir, exist_ok=True)
    if headless is None:
        headless = is_headless_environment()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=headless,
            viewport={"width": 1280, "height": 900},
            user_agent=DEFAULT_CHROME_UA,
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")
        
        print("[*] Waiting for user to scan WhatsApp Web QR Code...")
        start_time = time.time()
        max_duration = timeout_minutes * 60
        logged_in = False

        while time.time() - start_time < max_duration:
            # Check for chat list, left pane, search box, or navigation icons indicating login completion
            if (
                page.locator('#pane-side').count() > 0 or
                page.locator('div[data-testid="chat-list"]').count() > 0 or
                page.locator('div[aria-label*="chat list" i]').count() > 0 or
                page.locator('div[aria-label*="chats" i]').count() > 0 or
                page.locator('div[data-testid="conversation-panel-wrapper"]').count() > 0 or
                page.locator('div[data-testid="intro-title"]').count() > 0 or
                page.locator('header[data-testid="chatlist-header"]').count() > 0 or
                page.locator('button[aria-label*="menu" i]').count() > 0 or
                page.locator('button[aria-label*="new chat" i]').count() > 0 or
                page.locator('span[data-icon="menu"]').count() > 0 or
                page.locator('span[data-icon="chat"]').count() > 0 or
                page.locator('span[data-icon="chats-outline"]').count() > 0 or
                page.locator('div[role="textbox"]').count() > 0
            ):
                logged_in = True
                print("[+] WhatsApp Web successfully logged in!")
                if qr_callback:
                    qr_callback(None, "Logged in successfully!")
                break

            # Check if QR code is still visible or if phone has been scanned
            qr_el = page.locator('div[data-ref], canvas').first
            has_qr = qr_el.count() > 0 and qr_el.is_visible()

            # Stream screenshot & live status note
            if qr_callback:
                try:
                    if has_qr:
                        shot = qr_el.screenshot(type="jpeg", quality=80)
                        qr_callback(shot, "Please scan the QR code with WhatsApp on your phone")
                    else:
                        shot = page.screenshot(type="jpeg", quality=60)
                        qr_callback(shot, "Phone connected! Syncing WhatsApp messages, please wait a moment...")
                except Exception:
                    pass

            time.sleep(2.0)
            
        if logged_in:
            marker = Path(session_dir) / "session_active.marker"
            try:
                marker.write_text(str(int(time.time())))
            except Exception:
                pass
            # Give Chromium 5 seconds to flush IndexedDB & session credentials to disk
            time.sleep(5)

        context.close()
        return logged_in

def send_whatsapp_message(
    page, 
    phone: str, 
    message: str, 
    media_path: str = None,
    timeout_ms: int = 35000
) -> dict:
    """
    Sends a single message (with optional media attachment) to a phone number via WhatsApp Web.
    """
    try:
        if media_path and os.path.exists(media_path):
            # 1. Open chat directly without pre-filling text in URL so text is placed in the media caption
            url = f"https://web.whatsapp.com/send?phone={phone}"
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            
            # Wait for chat input or invalid number alert
            start_wait = time.time()
            chat_ready = False
            while time.time() - start_wait < 25:
                invalid_alert = page.locator("div:has-text('Phone number shared via url is invalid'), div:has-text('URL is invalid'), div:has-text('invalid phone number')").first
                if invalid_alert.count() > 0 and invalid_alert.is_visible():
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                    return {"phone": phone, "status": "Invalid Number", "error": "Number not registered on WhatsApp"}
                
                # Check if chat interface or attachment button is ready
                if (
                    page.locator('button[aria-label="Attach"]').count() > 0 or
                    page.locator('span[data-icon="plus"]').count() > 0 or
                    page.locator('span[data-icon="attach-menu-plus"]').count() > 0 or
                    page.locator('div[contenteditable="true"]').count() > 0
                ):
                    chat_ready = True
                    break
                time.sleep(1.0)
                
            if not chat_ready:
                return {"phone": phone, "status": "Timeout", "error": "Chat interface did not load within timeout"}
            
            time.sleep(1.5)
            # 2. Attach media file via file input or attach menu
            try:
                file_input = page.locator('input[type="file"]').first
                if file_input.count() > 0:
                    file_input.set_input_files(media_path)
                else:
                    attach_btn = page.locator('button[aria-label="Attach"], div[title="Attach"], span[data-icon="plus"], span[data-icon="attach-menu-plus"]').first
                    if attach_btn.count() > 0 and attach_btn.is_visible():
                        attach_btn.click()
                        time.sleep(1.0)
                        file_input = page.locator('input[type="file"]').first
                        file_input.set_input_files(media_path)
            except Exception as up_err:
                return {"phone": phone, "status": "Upload Failed", "error": f"Failed to attach media: {up_err}"}

            # 3. Wait for Media Preview / Caption box to appear
            time.sleep(2.5)
            try:
                caption_box = page.locator('div[aria-label*="caption" i], div[contenteditable="true"]').last
                if caption_box.count() > 0 and message:
                    caption_box.focus()
                    caption_box.fill(message)
                    time.sleep(1.0)
            except Exception:
                pass

            # 4. Click send button
            send_btn = page.locator('span[data-icon="send"], div[aria-label="Send"], button:has(span[data-icon="send"]), span[data-icon="wds-ic-send-filled"]').last
            if send_btn.count() > 0 and send_btn.is_visible():
                send_btn.click()
            else:
                page.keyboard.press("Enter")

            # Wait for upload completion
            time.sleep(4.0)
            return {"phone": phone, "status": "Sent", "error": None}

        else:
            # Standard text-only message via direct URL
            encoded_text = urllib.parse.quote(message)
            url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_text}"
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            
            start_wait = time.time()
            while time.time() - start_wait < 25:
                invalid_alert = page.locator("div:has-text('Phone number shared via url is invalid'), div:has-text('URL is invalid'), div:has-text('invalid phone number')").first
                if invalid_alert.count() > 0 and invalid_alert.is_visible():
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                    return {"phone": phone, "status": "Invalid Number", "error": "Number not registered on WhatsApp"}

                # Send button
                send_btn = page.locator('button[data-tab="11"], button[aria-label="Send"], span[data-icon="send"], button:has(span[data-icon="send"]), span[data-icon="wds-ic-send-filled"], button[aria-label*="send" i]').first
                if send_btn.count() > 0 and send_btn.is_visible():
                    send_btn.click()
                    time.sleep(2.0)
                    return {"phone": phone, "status": "Sent", "error": None}

                # Input box Enter key fallback
                input_box = page.locator('div[contenteditable="true"]').last
                if input_box.count() > 0 and input_box.is_visible():
                    input_box.focus()
                    page.keyboard.press("Enter")
                    time.sleep(2.0)
                    return {"phone": phone, "status": "Sent", "error": None}

                time.sleep(1.0)
                
            return {"phone": phone, "status": "Timeout", "error": "Chat or send button did not load within timeout"}

    except Exception as e:
        return {"phone": phone, "status": "Failed", "error": str(e)}

def bulk_send_whatsapp(
    leads: list,
    message_template: str,
    default_country_code: str = "880",
    delay_between_messages: int = 8,
    headless: bool = True,
    session_dir: str = DEFAULT_SESSION_DIR,
    progress_callback = None,
    use_ai_personalization: bool = False,
    ai_offer: str = "",
    media_path: str = None
) -> list:
    """
    Automates bulk messaging to a list of leads using Playwright and WhatsApp Web.
    
    :param leads: List of dicts representing leads (must have 'Name', 'Phone', etc.)
    :param message_template: Message with placeholders e.g. "Hello {Name}, we noticed {Address}..."
    :param default_country_code: Default international prefix if missing
    :param delay_between_messages: Safety delay in seconds between messages
    :param headless: Run in headless mode (headless=False recommended for WhatsApp Web)
    :param session_dir: Path to saved WhatsApp persistent profile
    :param progress_callback: Callback(current_idx, total, current_lead, status_dict, screenshot)
    :param use_ai_personalization: Use Groq LLM to write custom messages per business
    :param ai_offer: Description of your service or offer for Groq AI copywriter
    :param media_path: Optional path to an image, PDF, or video file to attach
    """
    os.makedirs(session_dir, exist_ok=True)
    results = []
    total = len(leads)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=headless,
            viewport={"width": 1280, "height": 900},
            user_agent=DEFAULT_CHROME_UA,
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        page = context.pages[0] if context.pages else context.new_page()
        
        # Navigate to WhatsApp Web first to check session readiness
        if progress_callback:
            progress_callback(0, total, None, {"status": "Connecting to WhatsApp Web..."}, None)
            
        page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded", timeout=45000)
        
        # Hydrate session for up to 12 seconds
        start_wait_ready = time.time()
        is_ready = False
        while time.time() - start_wait_ready < 12:
            if (
                page.locator('#pane-side').count() > 0 or
                page.locator('div[data-testid="chat-list"]').count() > 0 or
                page.locator('div[aria-label*="chat list" i]').count() > 0 or
                page.locator('header').count() > 0
            ):
                is_ready = True
                break
            
            qr_canvas = page.locator('canvas, div[data-ref]').first
            if qr_canvas.count() > 0 and qr_canvas.is_visible() and (time.time() - start_wait_ready > 6):
                context.close()
                raise RuntimeError("WhatsApp Web is not logged in. Please scan the QR code first via the Connect button.")
            time.sleep(1.5)

        if not is_ready:
            qr_canvas = page.locator('canvas, div[data-ref]').first
            if qr_canvas.count() > 0 and qr_canvas.is_visible():
                context.close()
                raise RuntimeError("WhatsApp Web is not logged in. Please scan the QR code first via the Connect button.")

        for idx, lead in enumerate(leads):
            raw_phone = lead.get("Phone", "")
            formatted_phone = format_whatsapp_number(raw_phone, default_country_code)
            lead_name = lead.get("Name", "Business Owner")
            
            if not formatted_phone:
                res = {"phone": raw_phone, "name": lead_name, "status": "Skipped (No Phone)", "error": "Missing phone number"}
                results.append(res)
                if progress_callback:
                    progress_callback(idx + 1, total, lead, res, None)
                continue

            # Determine message: either Groq AI personalized or template
            if use_ai_personalization:
                try:
                    import groq_helper
                    msg = groq_helper.generate_personalized_message(lead, offering=ai_offer or message_template)
                except Exception:
                    msg = message_template
                    for k, v in lead.items():
                        msg = msg.replace(f"{{{k}}}", str(v) if v else "")
                    msg = msg.replace("{Name}", lead_name).replace("{Phone}", raw_phone)
            else:
                msg = message_template
                for k, v in lead.items():
                    msg = msg.replace(f"{{{k}}}", str(v) if v else "")
                msg = msg.replace("{Name}", lead_name).replace("{Phone}", raw_phone)

            # Send message (with optional media)
            send_res = send_whatsapp_message(page, formatted_phone, msg, media_path=media_path)
            send_res["name"] = lead_name
            results.append(send_res)

            # Capture screenshot if possible
            shot = None
            try:
                shot = page.screenshot(type="jpeg", quality=45)
            except Exception:
                shot = None

            if progress_callback:
                progress_callback(idx + 1, total, lead, send_res, shot)

            # Delay between messages to avoid rate limits / account restrictions
            if idx < total - 1:
                time.sleep(delay_between_messages)

        context.close()
        
    return results

def send_test_whatsapp_message(
    phone: str,
    message: str,
    default_country_code: str = "880",
    headless: bool = True,
    session_dir: str = DEFAULT_SESSION_DIR,
    progress_callback = None,
    media_path: str = None
) -> dict:
    """
    Sends a single test message using the active WhatsApp Web session.
    Safely captures all errors to prevent crashing caller.
    """
    try:
        leads = [{
            "Name": "Test Contact",
            "Phone": phone,
            "Category": "Test Business",
            "Address": "Test Location",
            "Website": ""
        }]
        results = bulk_send_whatsapp(
            leads=leads,
            message_template=message,
            default_country_code=default_country_code,
            delay_between_messages=1,
            headless=headless,
            session_dir=session_dir,
            progress_callback=progress_callback,
            use_ai_personalization=False,
            media_path=media_path
        )
        if results:
            return results[0]
        return {"phone": phone, "status": "Failed", "error": "No delivery response returned"}
    except Exception as e:
        return {"phone": phone, "status": "Failed", "error": str(e)}

def parse_manual_numbers(raw_text: str) -> list:
    """
    Parses manually pasted/typed numbers into lead records.
    Supports formats:
    - 01712345678
    - 01712345678, Business Name
    - 01712345678, Business Name, Category, Address
    """
    import re
    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    records = []
    for line in lines:
        parts = [p.strip() for p in re.split(r'[,;\t]', line)]
        if not parts or not parts[0]:
            continue
        phone = parts[0]
        name = parts[1] if len(parts) > 1 and parts[1] else "Business Owner"
        cat = parts[2] if len(parts) > 2 and parts[2] else "General"
        addr = parts[3] if len(parts) > 3 and parts[3] else ""
        records.append({
            "Name": name,
            "Phone": phone,
            "Category": cat,
            "Address": addr,
            "Website": ""
        })
    return records

def generate_whatsapp_link(phone: str, default_country_code: str = "880") -> str:
    """Generate direct wa.me link for one-click chat."""
    digits = format_whatsapp_number(phone, default_country_code)
    if digits:
        return f"https://wa.me/{digits}"
    return ""

if __name__ == "__main__":
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser(description="WhatsApp Automation & Outreach Tool for Google Maps Leads")
    parser.add_argument("--login", action="store_true", help="Launch visible browser to scan WhatsApp QR code")
    parser.add_argument("--check", action="store_true", help="Check if existing WhatsApp session is logged in")
    parser.add_argument("--file", "-f", help="Path to Excel or CSV file containing leads")
    parser.add_argument("--phone", "-p", help="Single phone number to send message to (for testing)")
    parser.add_argument("--name", "-n", default="Business Owner", help="Name for single phone test")
    parser.add_argument("--template", "-t", default="Hello {Name}, are you currently accepting new orders?", help="Message template")
    parser.add_argument("--cc", default="880", help="Default country code (default: 880)")
    parser.add_argument("--delay", type=int, default=8, help="Delay between messages in seconds (default: 8)")
    parser.add_argument("--visible", action="store_true", help="Run visible browser instead of headless")
    parser.add_argument("--ai", action="store_true", help="Use Groq AI to personalize each message dynamically")

    args = parser.parse_args()

    if args.login:
        print("[*] Launching browser to scan WhatsApp QR Code...")
        success = launch_whatsapp_login_window(timeout_minutes=3)
        if success:
            print("[+] Successfully logged in to WhatsApp Web and saved session!")
        else:
            print("[-] WhatsApp Web login timed out or window was closed.")
    elif args.check:
        logged_in = check_login_status()
        if logged_in:
            print("[+] WhatsApp Web session exists and is active!")
        else:
            print("[-] WhatsApp Web session not found. Run with --login first.")
    elif args.phone:
        leads = [{"Name": args.name, "Phone": args.phone}]
        print(f"[*] Sending message to {args.phone} (AI mode: {args.ai})...")
        results = bulk_send_whatsapp(
            leads=leads,
            message_template=args.template,
            default_country_code=args.cc,
            delay_between_messages=args.delay,
            headless=not args.visible,
            use_ai_personalization=args.ai,
            ai_offer=args.template
        )
        print(f"[+] Result: {results}")
    elif args.file:
        if args.file.endswith(".csv"):
            df = pd.read_csv(args.file)
        else:
            df = pd.read_excel(args.file)
        leads = df.to_dict("records")
        print(f"[*] Starting bulk WhatsApp campaign for {len(leads)} leads from {args.file} (AI mode: {args.ai})...")
        results = bulk_send_whatsapp(
            leads=leads,
            message_template=args.template,
            default_country_code=args.cc,
            delay_between_messages=args.delay,
            headless=not args.visible,
            use_ai_personalization=args.ai,
            ai_offer=args.template
        )
        print(f"[+] Campaign finished! {len(results)} leads processed.")
    else:
        parser.print_help()

