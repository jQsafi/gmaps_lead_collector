import io
import streamlit as st
import pandas as pd
from scraper import scrape_google_maps, batch_scrape, DEFAULT_FIELDS
from whatsapp_sender import (
    format_whatsapp_number,
    check_login_status,
    launch_whatsapp_login_window,
    bulk_send_whatsapp
)

st.set_page_config(
    page_title="Google Maps Lead & Phone Collector",
    page_icon="📍",
    layout="wide"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-text {
        font-size: 1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    button[kind="primary"] {
        background-color: #2563EB !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        height: 3rem !important;
    }
    button[kind="secondary"] {
        border-radius: 6px !important;
        font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📍 Google Maps Lead & Phone Collector</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Extract business names, phone numbers, ratings, addresses, and websites directly from Google Maps into Excel / CSV.</div>', unsafe_allow_html=True)

# Tabs: Single Search vs Batch Multi-Location Search vs WhatsApp Automation
tab1, tab2, tab3 = st.tabs(["🔍 Single Search", "🗺️ Multi-Location / Multi-Keyword Search", "💬 WhatsApp Automation"])

with tab1:
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1.2])
    with col1:
        single_query = st.text_input(
            "Search Query & Location:",
            value="stationary shop around uttara",
            placeholder="e.g. pharmacy in gulshan, stationary shop in uttara"
        )
    with col2:
        single_limit = st.number_input("Max Results:", min_value=5, max_value=300, value=25, step=5, key="single_lim")
    with col3:
        phone_only_1 = st.checkbox("📱 Phone Only", value=False, help="Only include businesses that have a phone number", key="po_1")
    with col4:
        show_browser_1 = st.checkbox("👁️ Open Visible Browser", value=False, help="Open external browser window (unchecked runs in background headless mode)", key="sb_1")

    # Fields selection
    with st.expander("📋 Select Fields to Collect", expanded=True):
        pcol1, pcol2, pcol3, pcol4 = st.columns([2, 1, 1, 1])
        with pcol1:
            st.caption("Customize which fields to scrape and export:")
        with pcol2:
            if st.button("All Fields", key="btn_all_1", use_container_width=True):
                st.session_state["fields_1"] = list(DEFAULT_FIELDS)
                st.rerun()
        with pcol3:
            if st.button("Contact Info", key="btn_cnt_1", use_container_width=True):
                st.session_state["fields_1"] = ["Name", "Phone", "WhatsApp", "Address", "Website"]
                st.rerun()
        with pcol4:
            if st.button("Minimal", key="btn_min_1", use_container_width=True):
                st.session_state["fields_1"] = ["Name", "Phone", "WhatsApp"]
                st.rerun()

        if "fields_1" not in st.session_state:
            st.session_state["fields_1"] = list(DEFAULT_FIELDS)

        selected_fields_1 = st.multiselect(
            "Fields:",
            options=DEFAULT_FIELDS,
            key="fields_1",
            help="Choose the data fields you want in your scraped results",
            label_visibility="collapsed"
        )

    start_single = st.button("🚀 Start Single Search", key="btn_single", type="primary", use_container_width=True)

    if start_single:
        if not single_query.strip():
            st.warning("⚠️ Please enter a search query.")
        elif not selected_fields_1:
            st.error("⚠️ Please select at least one field to collect.")
        else:
            col_table, col_screen = st.columns([1.2, 1])
            with col_table:
                progress_bar = st.progress(0)
                status_text = st.empty()
                grid_placeholder = st.empty()
            with col_screen:
                screen_placeholder = st.empty()
                with screen_placeholder.container():
                    st.markdown("### 🖥️ Live Browser Simulation `🔴 LIVE`")
                    st.info("Browser starting... Live Google Maps actions will stream here.")

            latest_shot = [None]

            def update_progress(current, total, msg, current_df=None, screenshot=None):
                pct = min(1.0, current / total) if total > 0 else 0
                progress_bar.progress(pct)
                status_text.markdown(f"**[{current}/{total}]** {msg}")
                if current_df is not None and not current_df.empty:
                    with grid_placeholder.container():
                        st.markdown(f"### 📋 Live Extracted Leads ({len(current_df)} collected)")
                        st.dataframe(current_df, width="stretch")
                if screenshot is not None:
                    latest_shot[0] = screenshot
                    with screen_placeholder.container():
                        st.markdown("### 🖥️ Live Browser Simulation `🔴 LIVE`")
                        st.image(screenshot, caption=f"Action: {msg}", use_container_width=True)

            try:
                df = scrape_google_maps(
                    search_query=single_query,
                    max_results=single_limit,
                    headless=not show_browser_1,
                    phone_only=phone_only_1,
                    fields=selected_fields_1,
                    progress_callback=update_progress
                )
                
                if not df.empty:
                    st.session_state["active_leads_df"] = df
                    st.success(f"🎉 Successfully collected {len(df)} leads!")
                    with grid_placeholder.container():
                        st.markdown(f"### 📋 Extracted Leads ({len(df)} total)")
                        st.dataframe(df, width="stretch")
                    with screen_placeholder.container():
                        st.markdown("### 🖥️ Browser Simulation `✅ Complete`")
                        if latest_shot[0] is not None:
                            st.image(latest_shot[0], caption="Finished Scraping", use_container_width=True)
                        else:
                            st.success("Scraping finished successfully!")

                    # Export buttons
                    c1, c2 = st.columns(2)
                    
                    # Excel
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Leads')
                    
                    c1.download_button(
                        label="📥 Download Excel (.xlsx)",
                        data=buf.getvalue(),
                        file_name=f"leads_{single_query.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    # CSV
                    csv_data = df.to_csv(index=False).encode('utf-8-sig')
                    c2.download_button(
                        label="📥 Download CSV (.csv)",
                        data=csv_data,
                        file_name=f"leads_{single_query.replace(' ', '_')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("No listings found matching your criteria.")
            except Exception as e:
                st.error(f"Scraping error: {str(e)}")

with tab2:
    st.markdown("Enter multiple keywords or locations (one per line):")
    batch_input = st.text_area(
        "Search Queries:",
        value="stationary shop in uttara\nstationary shop in mirpur\nstationary shop in dhanmondi",
        height=120
    )
    
    col_b1, col_b2, col_b3 = st.columns([2, 1, 1.2])
    with col_b1:
        batch_limit = st.number_input("Max Results Per Query:", min_value=5, max_value=100, value=15, step=5, key="batch_lim")
    with col_b2:
        phone_only_2 = st.checkbox("📱 Phone Only", value=False, key="po_2")
    with col_b3:
        show_browser_2 = st.checkbox("👁️ Open Visible Browser", value=False, help="Open external browser window (unchecked runs in background headless mode)", key="sb_2")

    # Fields selection for batch
    with st.expander("📋 Select Fields to Collect", expanded=True):
        pcol_b1, pcol_b2, pcol_b3, pcol_b4 = st.columns([2, 1, 1, 1])
        with pcol_b1:
            st.caption("Customize which fields to scrape and export:")
        with pcol_b2:
            if st.button("All Fields", key="btn_all_2", use_container_width=True):
                st.session_state["fields_2"] = list(DEFAULT_FIELDS)
                st.rerun()
        with pcol_b3:
            if st.button("Contact Info", key="btn_cnt_2", use_container_width=True):
                st.session_state["fields_2"] = ["Name", "Phone", "WhatsApp", "Address", "Website"]
                st.rerun()
        with pcol_b4:
            if st.button("Minimal", key="btn_min_2", use_container_width=True):
                st.session_state["fields_2"] = ["Name", "Phone", "WhatsApp"]
                st.rerun()

        if "fields_2" not in st.session_state:
            st.session_state["fields_2"] = list(DEFAULT_FIELDS)

        selected_fields_2 = st.multiselect(
            "Fields:",
            options=DEFAULT_FIELDS,
            key="fields_2",
            help="Choose the data fields you want in your scraped results",
            label_visibility="collapsed"
        )

    start_batch = st.button("🚀 Start Batch Search", key="btn_batch", type="primary", use_container_width=True)

    if start_batch:
        if not batch_input.strip():
            st.warning("⚠️ Please enter at least one search query.")
        elif not selected_fields_2:
            st.error("⚠️ Please select at least one field to collect.")
        else:
            queries = [q.strip() for q in batch_input.split("\n") if q.strip()]
            if queries:
                col_b_table, col_b_screen = st.columns([1.2, 1])
                with col_b_table:
                    progress_bar_batch = st.progress(0)
                    status_text_batch = st.empty()
                    grid_placeholder_batch = st.empty()
                with col_b_screen:
                    screen_placeholder_batch = st.empty()
                    with screen_placeholder_batch.container():
                        st.markdown("### 🖥️ Live Browser Simulation `🔴 LIVE`")
                        st.info("Browser starting... Live Google Maps actions will stream here.")

                latest_batch_shot = [None]

                def update_progress_batch(current, total, msg, current_df=None, screenshot=None):
                    pct = min(1.0, current / total) if total > 0 else 0
                    progress_bar_batch.progress(pct)
                    status_text_batch.markdown(f"**[{current}/{total}]** {msg}")
                    if current_df is not None and not current_df.empty:
                        with grid_placeholder_batch.container():
                            st.markdown(f"### 📋 Live Extracted Leads ({len(current_df)} collected)")
                            st.dataframe(current_df, width="stretch")
                    if screenshot is not None:
                        latest_batch_shot[0] = screenshot
                        with screen_placeholder_batch.container():
                            st.markdown("### 🖥️ Live Browser Simulation `🔴 LIVE`")
                            st.image(screenshot, caption=f"Action: {msg}", use_container_width=True)

                try:
                    df_batch = batch_scrape(
                        queries=queries,
                        max_per_query=batch_limit,
                        headless=not show_browser_2,
                        phone_only=phone_only_2,
                        fields=selected_fields_2,
                        progress_callback=update_progress_batch
                    )

                    if not df_batch.empty:
                        st.session_state["active_leads_df"] = df_batch
                        st.success(f"🎉 Batch search finished! Collected {len(df_batch)} total unique leads.")
                        with grid_placeholder_batch.container():
                            st.markdown(f"### 📋 Extracted Leads ({len(df_batch)} total)")
                            st.dataframe(df_batch, width="stretch")
                        with screen_placeholder_batch.container():
                            st.markdown("### 🖥️ Browser Simulation `✅ Complete`")
                            if latest_batch_shot[0] is not None:
                                st.image(latest_batch_shot[0], caption="Finished Batch Scraping", use_container_width=True)
                            else:
                                st.success("Batch scraping finished!")

                        c1, c2 = st.columns(2)
                        
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                            df_batch.to_excel(writer, index=False, sheet_name='All_Leads')
                        
                        c1.download_button(
                            label="📥 Download Combined Excel (.xlsx)",
                            data=buf.getvalue(),
                            file_name="combined_batch_leads.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )

                        csv_data = df_batch.to_csv(index=False).encode('utf-8-sig')
                        c2.download_button(
                            label="📥 Download Combined CSV (.csv)",
                            data=csv_data,
                            file_name="combined_batch_leads.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.warning("No listings found.")
                except Exception as e:
                    st.error(f"Error during batch scrape: {str(e)}")

with tab3:
    st.markdown("### 💬 Automated WhatsApp Web Campaign")
    st.markdown("Send personalized messages automatically to your collected leads using browser-automated WhatsApp Web.")

    is_logged_in = check_login_status()
    col_auth1, col_auth2 = st.columns([2.5, 1])
    with col_auth1:
        if is_logged_in:
            st.success("🟢 **WhatsApp Web Session Active** (Saved session found)")
        else:
            st.warning("⚪ **WhatsApp Web Session Not Connected** (Please scan QR Code once to authenticate)")
    with col_auth2:
        if st.button("🔑 Connect / Scan QR Code", key="btn_wa_login", use_container_width=True):
            with st.spinner("Opening browser window... Please scan the WhatsApp QR Code with your phone."):
                success = launch_whatsapp_login_window(timeout_minutes=2)
                if success:
                    st.success("🎉 Successfully connected to WhatsApp Web!")
                    st.rerun()
                else:
                    st.error("Login timed out or window was closed before scanning.")

    st.markdown("---")

    # Step 1: Select Leads
    st.markdown("#### 1️⃣ Select Leads to Message")
    has_active_leads = "active_leads_df" in st.session_state and not st.session_state["active_leads_df"].empty

    source_option = st.radio(
        "Choose leads source:",
        options=["Recent Search Results", "Upload Excel / CSV File"],
        horizontal=True,
        key="wa_source_radio"
    )

    wa_leads_df = pd.DataFrame()
    if source_option == "Recent Search Results":
        if has_active_leads:
            wa_leads_df = st.session_state["active_leads_df"]
            st.info(f"Loaded **{len(wa_leads_df)} leads** from your latest search session.")
        else:
            st.warning("⚠️ No leads found in current session. Run a search in Tab 1 or Tab 2, or upload a file below.")
    else:
        uploaded_file = st.file_uploader("Upload leads file (.xlsx or .csv)", type=["xlsx", "csv"], key="wa_file_uploader")
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    wa_leads_df = pd.read_csv(uploaded_file)
                else:
                    wa_leads_df = pd.read_excel(uploaded_file)
                st.success(f"Loaded **{len(wa_leads_df)} leads** from uploaded file.")
            except Exception as e:
                st.error(f"Failed to read file: {e}")

    if not wa_leads_df.empty:
        # Filter leads with phone numbers
        if "Phone" in wa_leads_df.columns:
            valid_phone_leads = wa_leads_df[wa_leads_df["Phone"].astype(str).str.strip().ne("")].copy()
            show_cols = [c for c in ["Name", "Phone", "Category", "Address"] if c in valid_phone_leads.columns]
            st.dataframe(valid_phone_leads[show_cols].head(15), width="stretch")
            st.caption(f"Showing sample preview. Total valid recipient leads: **{len(valid_phone_leads)}**")
        else:
            valid_phone_leads = wa_leads_df
            st.dataframe(valid_phone_leads.head(15), width="stretch")

        st.markdown("---")
        st.markdown("#### 2️⃣ Compose Message & Automation Settings")

        col_msg, col_settings = st.columns([1.5, 1])
        with col_msg:
            default_template = "Hello {Name}, I noticed your business ({Category}) in {Address}. Are you currently accepting new orders/clients?"
            message_template = st.text_area(
                "Message Template (Supports dynamic variables):",
                value=default_template,
                height=130,
                key="wa_msg_tmpl"
            )
            st.caption("💡 Supported variables: `{Name}`, `{Phone}`, `{Category}`, `{Address}`, `{Website}`")

        with col_settings:
            country_code = st.text_input("Default Country Code (without +):", value="880", help="e.g. 880 for Bangladesh, 1 for USA, 44 for UK", key="wa_cc")
            delay = st.slider("Safety Delay Between Messages (seconds):", min_value=5, max_value=30, value=8, help="Recommended to prevent WhatsApp spam flags", key="wa_delay")
            show_wa_browser = st.checkbox("👁️ Open Visible WhatsApp Browser", value=False, help="Open external browser window (unchecked runs in background headless mode)", key="wa_watch_browser")

        start_campaign = st.button("🚀 Start Automated WhatsApp Campaign", key="btn_start_wa", type="primary", use_container_width=True)

        if start_campaign:
            if not check_login_status():
                st.error("⚠️ WhatsApp Web is not logged in! Please click '🔑 Connect / Scan QR Code' above first.")
            elif valid_phone_leads.empty:
                st.error("⚠️ No leads with valid phone numbers available.")
            else:
                col_wa_l, col_wa_r = st.columns([1.2, 1])
                with col_wa_l:
                    wa_progress = st.progress(0)
                    wa_status = st.empty()
                    wa_log_placeholder = st.empty()
                with col_wa_r:
                    wa_screen_placeholder = st.empty()
                    with wa_screen_placeholder.container():
                        st.markdown("### 🖥️ WhatsApp Live Stream `🔴 LIVE`")
                        st.info("WhatsApp automation starting...")

                delivery_records = []

                def wa_callback(current, total, lead, res_dict, screenshot=None):
                    pct = min(1.0, current / total) if total > 0 else 0
                    wa_progress.progress(pct)
                    status_text_msg = res_dict.get("status", "")
                    lead_name = lead.get("Name", "") if lead else ""
                    phone_val = res_dict.get("phone", "")
                    wa_status.markdown(f"**[{current}/{total}]** Sending to **{lead_name}** ({phone_val}): `{status_text_msg}`")

                    if res_dict and lead:
                        record_entry = {
                            "Name": lead_name,
                            "Phone": phone_val,
                            "Status": status_text_msg,
                            "Error": res_dict.get("error") or "None"
                        }
                        delivery_records.append(record_entry)
                        with wa_log_placeholder.container():
                            st.markdown(f"### 📋 Message Delivery Log ({len(delivery_records)} processed)")
                            st.dataframe(pd.DataFrame(delivery_records), width="stretch")

                    if screenshot is not None:
                        with wa_screen_placeholder.container():
                            st.markdown("### 🖥️ WhatsApp Live Stream `🔴 LIVE`")
                            st.image(screenshot, caption=f"Action: {status_text_msg}", use_container_width=True)

                leads_list = valid_phone_leads.to_dict("records")
                try:
                    results = bulk_send_whatsapp(
                        leads=leads_list,
                        message_template=message_template,
                        default_country_code=country_code,
                        delay_between_messages=delay,
                        headless=not show_wa_browser,
                        progress_callback=wa_callback
                    )
                    st.success(f"🎉 WhatsApp Campaign Completed! Processed {len(results)} leads.")
                    with wa_screen_placeholder.container():
                        st.markdown("### 🖥️ WhatsApp Stream `✅ Complete`")
                        st.success("All messages sent!")
                except Exception as err:
                    st.error(f"WhatsApp automation error: {str(err)}")
