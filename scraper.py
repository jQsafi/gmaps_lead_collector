import time
import re
import argparse
import pandas as pd
from playwright.sync_api import sync_playwright

DEFAULT_FIELDS = [
    "Query",
    "Name",
    "Phone",
    "WhatsApp",
    "Category",
    "Rating",
    "Reviews",
    "Address",
    "Website",
    "Google Maps URL"
]

def make_whatsapp_link(phone: str, default_country_code: str = "880") -> str:
    """Generate direct click-to-chat WhatsApp link (https://wa.me/...)."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', str(phone))
    if not digits:
        return ""
    cc = default_country_code.lstrip('+')
    if digits.startswith('0') and len(digits) == 11 and cc == '880':
        digits = '88' + digits
    elif digits.startswith('0') and cc:
        digits = cc + digits[1:]
    elif not digits.startswith(cc) and len(digits) <= 10:
        digits = cc + digits
    return f"https://wa.me/{digits}"


def clean_phone_number(raw_phone: str) -> str:
    """Extract clean phone number string without language prefixes (English & Bengali)."""
    if not raw_phone:
        return ""
    # Remove known prefixes in English and Bengali
    cleaned = re.sub(
        r'^(phone:tel:|tel:|ফোন\s*(?:নম্বর)?(?:\s*কপি\s*করুন)?[:\s]*|মোবাইল\s*(?:নম্বর)?[:\s]*|কল\s*করুন[:\s]*|Phone[:\s]*|Mobile[:\s]*|Tel(?:ephone)?[:\s]*|Copy\s*phone\s*number[:\s]*|\+?Call[:\s]*)',
        '',
        raw_phone,
        flags=re.IGNORECASE
    ).strip()
    # Strip any remaining leading non-digit/non-phone symbols (e.g. icons, colons, labels)
    cleaned = re.sub(r'^[^\d+(]+', '', cleaned).strip()
    # Strip any trailing non-digit/non-phone symbols
    cleaned = re.sub(r'[^\d)]+$', '', cleaned).strip()
    return cleaned

def clean_address(raw_addr: str) -> str:
    """Extract clean address string without language prefixes (English & Bengali)."""
    if not raw_addr:
        return ""
    cleaned = re.sub(
        r'^(ঠিকানা\s*(?:কপি\s*করুন)?[:\s]*|Address[:\s]*|Copy\s*address[:\s]*)',
        '',
        raw_addr,
        flags=re.IGNORECASE
    ).strip()
    return cleaned

def scrape_google_maps(
    search_query: str, 
    max_results: int = 50, 
    headless: bool = True,
    phone_only: bool = False,
    fields: list = None,
    progress_callback = None
):
    """
    Searches Google Maps and extracts business details (Name, Phone, Category, Rating, Address, Website, etc.)
    
    :param search_query: Search query string (e.g. 'stationary shop around uttara')
    :param max_results: Maximum number of records to extract
    :param headless: Run browser in headless mode (no GUI window)
    :param phone_only: Only return listings that have a phone/mobile number
    :param fields: List of specific field names to collect (defaults to all)
    :param progress_callback: Optional callback function(current_count, max_results, status_msg, current_df)
    """
    target_fields = [f for f in fields if f in DEFAULT_FIELDS] if fields else list(DEFAULT_FIELDS)
    if not target_fields:
        target_fields = list(DEFAULT_FIELDS)
    active_fields = set(target_fields)

    print(f"\n[*] Starting search for: '{search_query}' (Target limit: {max_results})")
    print(f"[*] Target fields: {', '.join(target_fields)}")
    if progress_callback:
        progress_callback(0, max_results, f"Opening Google Maps for '{search_query}'...", pd.DataFrame(columns=target_fields))

    results = []
    
    with sync_playwright() as p:
        # Launch browser with anti-bot headers & English locale
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--lang=en-US",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            locale="en-US",
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = context.new_page()
        
        def notify(current_count, total, msg, current_df, take_screenshot=True):
            if not progress_callback:
                return
            shot = None
            if take_screenshot:
                try:
                    shot = page.screenshot(type="jpeg", quality=50)
                except Exception:
                    shot = None
            try:
                progress_callback(current_count, total, msg, current_df, shot)
            except TypeError:
                try:
                    progress_callback(current_count, total, msg, current_df)
                except TypeError:
                    progress_callback(current_count, total, msg)

        # Navigate to Google Maps search (forced English via ?hl=en)
        url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}?hl=en"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        notify(0, max_results, f"Opening Google Maps for '{search_query}'...", pd.DataFrame(columns=target_fields))
        
        # Handle cookie consent or sign-in prompts if they pop up
        try:
            accept_button = page.locator("button:has-text('Accept all'), form:has(button) >> text='Accept all', button:has-text('Agree')").first
            if accept_button.is_visible(timeout=3000):
                accept_button.click()
        except Exception:
            pass

        feed_selector = 'div[role="feed"]'
        try:
            page.wait_for_selector(feed_selector, timeout=15000)
        except Exception:
            print("[!] Results feed not found immediately. Checking if it's a direct place or slow load...")

        # Scroll the results feed to load listings
        print("[*] Scrolling to load places...")
        notify(0, max_results, "Scrolling results feed...", pd.DataFrame(columns=target_fields))
            
        feed = page.locator(feed_selector)
        
        prev_count = 0
        scroll_attempts = 0
        
        while scroll_attempts < 15:
            items = page.locator('div[role="article"], div.Nv2PK').all()
            if len(items) >= max_results:
                break
            
            # Scroll feed
            if feed.count() > 0:
                feed.evaluate("el => el.scrollBy(0, 1200)")
            else:
                page.mouse.wheel(0, 1200)
                
            time.sleep(1.2)
            
            current_count = len(items)
            if current_count == prev_count:
                scroll_attempts += 1
                page_content = page.content().lower()
                if "you've reached the end" in page_content or "end of list" in page_content:
                    print("[*] Reached end of search results.")
                    break
            else:
                scroll_attempts = 0
                prev_count = current_count
                print(f"[*] Loaded {current_count} listings so far...")
                notify(0, max_results, f"Scrolling feed ({current_count} listings loaded)...", pd.DataFrame(columns=target_fields))

        # Extract listings
        listing_elements = page.locator('div[role="article"], div.Nv2PK').all()
        print(f"[*] Total loaded: {len(listing_elements)}. Extracting details...")
        
        seen_names = set()

        for idx, item in enumerate(listing_elements):
            if len(results) >= max_results:
                break

            try:
                # Scroll item into view and click its primary link to open sidebar details
                item.scroll_into_view_if_needed()
                time.sleep(0.3)
                link_el = item.locator('a.hfpxzc, a[href*="/maps/place/"]').first
                if link_el.count() > 0:
                    link_el.click()
                else:
                    item.click()

                # Wait for details panel to load and scroll down to reveal virtualized buttons
                time.sleep(1.2)
                main_pane = page.locator('div[role="main"]').first
                if main_pane.count() > 0:
                    main_pane.evaluate('el => el.scrollBy(0, 450)')
                    time.sleep(0.5)
                
                # 1. Business Name (always extracted for deduplication and logging)
                name = ""
                name_el = page.locator('h1.DUwDvf, h1.fontHeadlineLarge').first
                if name_el.count() > 0:
                    name = name_el.text_content(timeout=2000) or ""
                
                if not name:
                    if link_el.count() > 0:
                        name = link_el.get_attribute("aria-label") or ""

                name = name.strip()
                if not name or name in seen_names:
                    continue

                # Notify live action: viewing details
                notify(len(results), max_results, f"Viewing details: {name}", pd.DataFrame(results))

                # 2. Phone / Mobile Number
                phone = ""
                if "Phone" in active_fields or phone_only:
                    candidates = page.locator('*[data-item-id^="phone:"], a[href^="tel:"], button[aria-label^="Phone:" i], button[aria-label^="ফোন:" i]').all()
                    for cand in candidates:
                        aria = cand.get_attribute("aria-label") or ""
                        if "send to phone" in aria.lower():
                            continue
                        data_id = cand.get_attribute("data-item-id") or ""
                        href = cand.get_attribute("href") or ""
                        txt = cand.text_content() or ""
                        
                        # Prefer aria-label if it has digits (usually has formatted number e.g. 01744-462333)
                        if any(ch.isdigit() for ch in aria):
                            cleaned = clean_phone_number(aria)
                        else:
                            cleaned = clean_phone_number(data_id or href or txt)
                        
                        if any(ch.isdigit() for ch in cleaned):
                            phone = cleaned
                            break

                # Skip if phone_only is required and phone is missing
                if phone_only and not phone:
                    continue

                seen_names.add(name)

                # 3. Address
                address = ""
                if "Address" in active_fields:
                    addr_btn = page.locator('*[data-item-id="address"], button[data-tooltip*="address" i], button[data-tooltip*="ঠিকানা" i], button[aria-label*="Address" i], button[aria-label*="ঠিকানা" i]').first
                    if addr_btn.count() > 0:
                        raw_addr = addr_btn.get_attribute("aria-label") or addr_btn.text_content() or ""
                        address = clean_address(raw_addr)

                # 4. Rating & Reviews
                rating = ""
                reviews_count = ""
                if "Rating" in active_fields:
                    rating_el = page.locator('div.F7nice span[aria-hidden="true"]').first
                    if rating_el.count() > 0:
                        rating = rating_el.text_content() or ""
                
                if "Reviews" in active_fields:
                    reviews_el = page.locator('div.F7nice span[aria-label*="reviews"]').first
                    if reviews_el.count() > 0:
                        rev_text = reviews_el.get_attribute("aria-label") or ""
                        digits = re.findall(r'[\d,]+', rev_text)
                        if digits:
                            reviews_count = digits[0]

                # 5. Category
                category = ""
                if "Category" in active_fields:
                    cat_el = page.locator('button.DkEaL').first
                    if cat_el.count() > 0:
                        category = cat_el.text_content() or ""

                # 6. Website
                website = ""
                if "Website" in active_fields:
                    website_el = page.locator('a[data-item-id="authority"]').first
                    if website_el.count() > 0:
                        website = website_el.get_attribute("href") or ""

                # 7. Google Maps URL
                maps_url = ""
                if "Google Maps URL" in active_fields:
                    maps_url = page.url

                raw_record = {
                    "Query": search_query,
                    "Name": name,
                    "Phone": phone,
                    "WhatsApp": make_whatsapp_link(phone),
                    "Category": category.strip(),
                    "Rating": rating.strip(),
                    "Reviews": reviews_count.strip(),
                    "Address": address.strip(),
                    "Website": website.strip(),
                    "Google Maps URL": maps_url
                }
                
                record = {k: raw_record[k] for k in target_fields}
                results.append(record)
                print(f"[{len(results)}/{max_results}] {name} | Phone: {phone or 'N/A'}")

                notify(len(results), max_results, f"Collected: {name}", pd.DataFrame(results))
                
            except Exception as err:
                continue
                
        browser.close()

    if results:
        df = pd.DataFrame(results)
    else:
        df = pd.DataFrame(columns=target_fields)
    return df

def batch_scrape(
    queries: list, 
    max_per_query: int = 30, 
    headless: bool = True, 
    phone_only: bool = False, 
    fields: list = None,
    progress_callback = None
):
    """Scrapes multiple search queries sequentially with live progress and real-time grid updates."""
    all_dfs = []
    total_queries = len(queries)
    all_results_records = []

    for q_idx, q in enumerate(queries):
        q = q.strip()
        if not q:
            continue
        
        def sub_progress(curr, max_r, msg, curr_df=None, shot=None):
            if progress_callback:
                prefix = f"Query [{q_idx+1}/{total_queries}] '{q}': "
                if curr_df is not None and not curr_df.empty:
                    combined_so_far = pd.concat([pd.DataFrame(all_results_records), curr_df], ignore_index=True)
                else:
                    combined_so_far = pd.DataFrame(all_results_records)
                try:
                    progress_callback(len(combined_so_far), max_per_query * total_queries, prefix + msg, combined_so_far, shot)
                except TypeError:
                    progress_callback(len(combined_so_far), max_per_query * total_queries, prefix + msg, combined_so_far)

        df_q = scrape_google_maps(
            search_query=q,
            max_results=max_per_query,
            headless=headless,
            phone_only=phone_only,
            fields=fields,
            progress_callback=sub_progress if progress_callback else None
        )
        if not df_q.empty:
            all_dfs.append(df_q)
            all_results_records.extend(df_q.to_dict('records'))
    
    target_cols = [f for f in fields if f in DEFAULT_FIELDS] if fields else list(DEFAULT_FIELDS)
    if not target_cols:
        target_cols = list(DEFAULT_FIELDS)

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        # Drop duplicates by available identifier fields
        dedup_subset = [c for c in ["Name", "Phone", "Google Maps URL"] if c in combined.columns]
        if dedup_subset:
            combined = combined.drop_duplicates(subset=dedup_subset)
        else:
            combined = combined.drop_duplicates()
        return combined
    return pd.DataFrame(columns=target_cols)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Maps Business & Mobile Number Scraper")
    parser.add_argument("--query", "-q", type=str, default="stationary shop around uttara", help="Search query (or comma-separated queries)")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Max results per search")
    parser.add_argument("--output", "-o", type=str, default="gmaps_leads.xlsx", help="Output file (.xlsx or .csv)")
    parser.add_argument("--phone-only", action="store_true", help="Only save leads with phone numbers")
    parser.add_argument("--fields", "-f", type=str, default=None, help=f"Comma-separated list of fields to collect ({', '.join(DEFAULT_FIELDS)}). Defaults to all.")
    parser.add_argument("--visible", action="store_true", help="Open browser visibly (for debugging)")
    parser.add_argument("--save-to-db", action="store_true", help="Automatically save scraped leads to remote/local database")
    parser.add_argument("--db-url", type=str, default=None, help="Database connection URI (or read from DATABASE_URL env var)")
    
    args = parser.parse_args()
    
    queries = [x.strip() for x in args.query.split(",") if x.strip()]
    
    chosen_fields = None
    if args.fields:
        field_lookup = {f.lower().replace(" ", ""): f for f in DEFAULT_FIELDS}
        parsed = []
        for f in args.fields.split(","):
            norm = f.strip().lower().replace(" ", "")
            if norm in field_lookup:
                parsed.append(field_lookup[norm])
            else:
                print(f"[!] Warning: Unknown field '{f.strip()}'. Ignored.")
        if parsed:
            chosen_fields = parsed
    
    if len(queries) > 1:
        df_final = batch_scrape(
            queries=queries,
            max_per_query=args.limit,
            headless=not args.visible,
            phone_only=args.phone_only,
            fields=chosen_fields
        )
    else:
        df_final = scrape_google_maps(
            search_query=queries[0],
            max_results=args.limit,
            headless=not args.visible,
            phone_only=args.phone_only,
            fields=chosen_fields
        )
    
    if not df_final.empty:
        if args.output.endswith(".csv"):
            df_final.to_csv(args.output, index=False, encoding="utf-8-sig")
        else:
            df_final.to_excel(args.output, index=False)
        print(f"\n[+] Successfully saved {len(df_final)} records to '{args.output}'!")

        if args.save_to_db:
            try:
                import database
                db_res = database.save_leads_to_db(df_final, db_url=args.db_url)
                print(f"[+] Saved to database: {db_res['inserted']} inserted, {db_res['duplicates']} updated/deduplicated.")
            except Exception as dbe:
                print(f"[!] Error saving to database: {dbe}")
    else:
        print("\n[-] No records found.")

