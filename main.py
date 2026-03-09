
import tempfile
import concurrent.futures
import io
import json
import multiprocessing
import os
import random
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from math import log2
from queue import Empty, Queue
from threading import Lock
from urllib.parse import parse_qsl, urlparse, urlsplit
import urllib.parse
import sys
import threading
import time
import fitz  # PyMuPDF
import pandas as pd
import pytesseract
import requests
from bs4 import BeautifulSoup, Comment
from deep_translator import GoogleTranslator
from langdetect import detect
from PIL import Image, ImageOps
from pyzbar.pyzbar import decode as zbar_decode
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


LLM_ENABLED = True
LLM_MODEL = os.getenv("LLM_MODEL", "phi4:14b")
OLLAMA_URL = "..."
STORE_ONLY_CONFIRMED = True
TOTAL_TO_PROCESS = 0
STOP_PROGRESS = False
PROGRESS_EVERY = 25
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
})

SAVE_HTTP_REQUESTS_DB = False
pdf_leak_found = False
SCREENSHOT_FOLDER = ""
HTML_FOLDER = ""
OCR_SCREENSHOT_FOLDER = ""
OCR_HTML_FOLDER = ""
PDF_FOLDER = ""

RESULTS_DB = ".db"
NUM_THREADS = 10
url_queue = Queue()
results_queue = Queue(maxsize=5000)
scanned_log_q = Queue(maxsize=10000)


# Create folders
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
os.makedirs(HTML_FOLDER, exist_ok=True)
os.makedirs(OCR_SCREENSHOT_FOLDER, exist_ok=True)
os.makedirs(OCR_HTML_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

# Thread-safe variables
screenshot_counter = 1
counter_lock = threading.Lock()


INCLUSIVE_CONFIG = {
    "min_val_length": 16,
    "require_digit": True,
    "require_field_match": True,
    "allow_common_emails": True,
    "accept_placeholders": False,
    "allow_weak_fields": False,
    "match_soft_keywords": False,
    "min_html_length": 150,
    "min_structural_tags": 3,
    "ocr_on_failure_only": True,
    "enable_translation": False,
    "max_translate_chars": 2000,
    "translate_langs": {"ja", "ar", "ru", "uk", "hi", "bn", "zh-cn", "zh-tw", "ko", "es", "pt", "fr", "de", "it"}
}


stats_lock = Lock()
stats = {
    "processed": 0, "live": 0, "dead": 0,
    "regular_ss": 0, "ocr_ss": 0, "ocr_leaks": 0,
    "http_leaks": 0, "non_english": 0,
    "photo_live": 0, "e_signature_live": 0, "paste_live": 0
}
SUSPICIOUS_URL_PARAMS_SET = {

    "envelope_id", "signing_token", "sessionid", "session_id", "session_key", "sign_token", "doc_hash",
    "signature_id", "access_code", "signing_session", "approve_token", "verify_token", "auth_key",
    "esign_request", "contract_id", "legal_doc", "agreement_id",
    "access_token", "refresh_token", "auth_token", "csrf", "xsrf", "session_token",
    "apikey", "api_key", "api_secret", "secret_key", "client_secret", "verification", "verify",
    "private_key", "public_key", "hash", "hmac", "security_code", "verification_code",
    "recovery_token", "reset_token", "oauth_token", "oauth_verifier", "bearer", "state_token",
    "security_login", "client_token", "sso_token", "authenticity_token",
    "csrftoken", "logincsrfparam", "requestverificationtoken", "security_token", "reservas", "csrf-token",
    "webhook_url", "webhook_token", "slack_webhook", "slack_token", "slack_bot_token",
    "discord_invite", "discord_bot_token", "telegram_bot_token", "telegram_chat_id",
    "github_token", "gitlab_token", "jenkins_token", "circleci_token", "ci_build_token",
    "build_hook", "api_webhook", "firebase_token", "twilio_sid", "twilio_token",
    "zendesk_token", "notion_token", "airtable_api_key", "api_url",
    "cart_id", "checkout", "order_number", "invoice_number", "purchase_id", "transaction_id",
    "transaction_token", "checkout_token", "order_reference", "payment_ref", "payment_token",
    "payment_id", "payment_method", "stripe_token", "paypal_token", "square_token",
    "debitcard", "creditcard", "cvc", "bank_account", "iban", "bic",
    "card_number", "account_number", "invoice_id", "receipt_number", "license_key",
    "discount_code", "promo_code", "coupon_code", "voucher_code", "voucher_id",
    "giftcard_number", "loyalty_card_id", "reward_points", "balance_amount", "billing",
    "file", "file_url", "fileid", "attachment", "attachment_id", "doc", "docid", "doc_token",
    "document", "document_id", "download_id", "download_token",
    "gdrive_file_id", "gdrive_share_link", "dropbox_link", "onedrive_link", "s3_bucket",
    "repository_url", "pdf_file", "docx_file", "xlsx_file", "gdrive", "onedrive",
    "backup_file", "database_dump", "config_file", "logfile", "snapshot_id", "backup", "config",
    "boardingpass", "visa", "pasabordo", "ticket", "ticket_id", "reservation_number",
    "booking_reference", "confirmation_number", "flight_number", "itinerary_id",
    "passport_number", "trip_id", "e_ticket_number", "booking_ref", "travel_doc_id",
    "miles_account_id", "frequent_flyer_number",
    "invite_link", "whatsapp_link", "messenger_thread_id", "facebook_id", "instagram_id",
    "snapchat_id", "skype_id", "social_user_id", "group_id", "chat_token",
    "customer_id", "user_id", "account_id", "member_id", "profile_id",
    "aadhaar_number", "nhs_number", "citizen_id", "residence_permit", "ssn_full",
    "student_id", "military_id", "beneficiary_id", "national_id", "social_security_number",
    "ssn", "driver_license_number", "tax_id", "pan_number", "pan_card", "identity_number",
    "ssn_last4", "health_id", "voter_id", "employee_id", "member_number",
    "email_address", "phone_number", "mobile_number", "fax_number", "emergency_contact",
    "billing_address", "shipping_address", "mailing_address", "home_address", "postal_code",
    "zip_code", "full_name", "first_name", "last_name", "middle_name", "dob", "date_of_birth",
    "place_of_birth", "gender", "nationality", "marital_status", "address",
    "insurance_number", "medical_record_id", "health_insurance_id", "vaccination_id",
    "blood_type", "healthcare_id", "dental_record_id", "employer_insurance_id",
    "tracking", "tracking_id", "tracking_number", "shipment_id", "parcel_id", "order_tracking_id",
    "delivery_note_number", "waybill_number", "dispatch_id",
    "employee_number", "staff_id", "internal_reference", "project_id", "vendor_id",
    "supplier_id", "purchase_order_id", "contract_number", "rfq_id", "invoice_reference",
    "wallet", "wallet_address", "crypto_token", "transaction_hash", "eth_address", "btc_address",
    "mnemonic_phrase", "seed_phrase", "keystore", "crypto_api_key", "crypto_secret_key",
    "audit_log_id", "incident_id", "security_alert_id", "fraud_case_id",
    "risk_score", "compliance_report_id",
    "file_name", "filename", "filepath", "doc_link", "dataset", "shared_link",
    "public_link", "direct_link", "temp_link", "auth", "signin", "login",
    "creds", "credentials", "password", "pwd", "passwd",
    "identity", "key", "certificate", "ssh_key", "oauth",
    "profile", "account", "settings", "media", "media_id", "photo",
    "image", "img_url", "video_url", "link"}
SUSPICIOUS_PARAMS_SET = {

    "envelope_id", "signing_token", "sessionid", "session_id", "session_key", "sign_token", "doc_hash",
    "signature_id", "access_code", "signing_session", "approve_token", "verify_token", "auth_key",
    "esign_request", "contract_id", "legal_doc", "agreement_id",
    "access_token", "refresh_token", "auth_token", "xsrf", "session_token", "csrf",
    "apikey", "api_key", "api_secret", "secret_key", "client_secret", "crypto_key", "crypto_address",
    "private_key", "private_key", "hmac", "security_code", "verification_code", "recovery_token", "reset_token", "oauth_token", "oauth_verifier", "crypto_wallet",
    "jwt", "bearer", "state_token", "token", "security-login", "client_token", "sso_token", "authenticity_token", "csrftoken", "logincsrfparam", "requestverificationtoken", "security_token",
    "national_id", "social_security_number", "driver_license_number",
    "tax_id", "pan_number", "pan_card", "identity_number", "ssn_last4", "health_id", "voter_id", "employee_id",
    "cart_id", "order_number", "invoice_number", "purchase_id", "transaction id", "transaction_token", "checkout_token",
    "order_reference", "payment_ref", "payment_token", "payment_id", "payment_method", "debitcard",
    "creditcard",  "bank_account",  "stripe_token", "card_number", "transaction_id",
    "invoice_id", "receipt_number", "account_number", "license_key",
    "fileid", "attachment_id", "docid", "doc_token", "document_id", "download_token",
    "gdrive_file_id", "gdrive_share_link", "dropbox_link", "onedrive_link", "s3_bucket", "repository_url",
    "pdf_file", "docx_file", "xlsx_file", "gdrive", "onedrive/",
    "ticket_id", "reservation_number", "booking_reference",
    "confirmation_number", "flight_number", "itinerary_id", "passport_number", "trip_id", "e_ticket_number", "booking_ref", "Boarding Pass", "Booking Reference", "Reservation Number",
    "Flight Number", "Confirmation Number", "E-Ticket Number",
    "Itinerary ID", "Passport Number", "Trip ID",
    "invite_link", "discord_invite", "discord_bot_token", "slack_webhook", "slack_bot_token",
    "telegram_bot_token", "telegram_chat_id", "social_user_id",
    "whatsapp_link", "facebook_id", "messenger_thread_id", "chat.whatsapp",
    "instagram_id", "snapchat_id", "skype_id",
    "discount_code", "promo_code", "coupon_code", "voucher_code", "voucher_id", "tracking_id",
    "tracking_number", "survey_id", "event_id", "chat_token", "customer_id",
    "citizen_id", "residence_permit",
    "ssn_full", "student_id", "military_id", "beneficiary_id",
    "billing_address", "shipping_address", "mailing_address",
    "insurance_number", "medical_record_id", "health_insurance_id", "vaccination_id",
    "Invoice Number", "Invoice ID", "Invoice #", "Invoice Total", "Invoice Amount", "Order Number", "Order ID", "Order #", "Order Total", "Order Amount",
    "Payment Method", "Payment Type", "Payment ID", "Payment Reference", "Card Number",
    "Credit Card Number", "Card Ending", "Cardholder Name", "Card Type", "Last 4 Digits",
    "Discord Invite", "Slack Invite", "Telegram Bot", "Messenger Thread",
    "WhatsApp Link", "Group ID", "Profile ID",
    "Wallet Address", "Crypto Token", "Transaction Hash", "Mnemonic", "Seed Phrase",
    "Download Link", "Document ID", "GDrive Link", "Dropbox Link",}
WEAK_HTML_HINTS = {
    "envelope_id", "signature_id", "contract_id",
    "agreement_id", "esign_request", "legal_doc",
    "docid", "doc_hash", "doc_token", "document_id",
    "download_token", "fileid", "attachment_id",
    "order_id", "order_number", "order_reference",
    "invoice_id", "invoice_number", "receipt_number",
    "transaction_id", "transaction_token",
    "purchase_id", "checkout_token",
    "payment_id", "payment_ref", "payment_method",
    "license_key",
    "ticket_id", "reservation_number", "booking_reference",
    "booking_ref", "confirmation_number",
    "flight_number", "itinerary_id", "trip_id",
    "e_ticket_number", "passport_number",
    "national_id", "identity_number", "tax_id",
    "pan_number", "pan_card", "ssn_last4",
    "employee_id", "student_id", "citizen_id",
    "residence_permit", "beneficiary_id",
    "gdrive_file_id", "gdrive_share_link", "dropbox_link",
    "onedrive_link", "repository_url", "download_link",
    "invite_link", "discord_invite",
    "telegram_chat_id", "social_user_id",
    "facebook_id", "instagram_id", "snapchat_id",
    "skype_id", "messenger_thread_id", "whatsapp_link",
    "discount_code", "promo_code", "coupon_code",
    "voucher_code", "voucher_id",
    "tracking_id", "tracking_number",
    "survey_id", "event_id", "customer_id",
}
STRONG_HTML_HINTS = {

    "access_token", "refresh_token", "auth_token", "session_token",
    "sessionid", "session_id", "session_key",
    "csrf", "xsrf", "csrftoken", "requestverificationtoken",
    "authenticity_token", "logincsrfparam",
    "apikey", "api_key", "api_secret", "secret_key", "client_secret",
    "oauth_token", "oauth_verifier",
    "jwt", "bearer", "state_token", "sso_token",
    "security_token", "signing_token", "sign_token", "approve_token",
    "verify_token", "recovery_token", "reset_token",
    "private_key", "hmac", "crypto_key", "crypto_wallet",
    "wallet_address", "crypto_token", "transaction_hash",
    "mnemonic", "seed_phrase",
    "card_number", "creditcard", "credit_card_number",
    "bank_account", "account_number", "stripe_token",
    "payment_token",
    "discord_bot_token", "slack_bot_token",
    "telegram_bot_token", "slack_webhook",
}

E_SIGNATURE_DOMAINS = [

    "esignlive.com", "sandbox.esignlive.com", "docusign.net", "docusign.com", "secure.adobesign.com",
    "adobesign.com", "hellosign.com", "onespan.com", "signnow.com", "pandadoc.com", "dropboxsign.com",
    "rightsignature.com", "zohosign.com", "signrequest.com", "eversign.com", "assuresign.com",
    "formstack.com", "signeasy.com", "sertifi.com", "signable.com", "legalesign.com", "esignly.com",
    "signx.wondershare.com", "docsketch.com", "getaccept.com", "signaturit.com"
]

PHOTO_DOMAINS = [
    "photos.google.com", "lh3.googleusercontent.com", "drive.google.com",
    "dropboxusercontent.com", "imgur.com", "i.imgur.com", "i.redd.it", "preview.redd.it",
    "cdn.discordapp.com", "fbcdn.net", "scontent.xx.fbcdn.net", "telegra.ph",
    "cdn4.telegram-cdn.org", "mmg.whatsapp.net", "onedrive.live.com", "1drv.ms",
    "s3.amazonaws.com", "bucket.s3.amazonaws.com", "flickr.com", "staticflickr.com",
    "wetransfer.com", "transfer.sh", "user-images.githubusercontent.com", "prnt.sc",
    "snag.gy", "gyazo.com", "mail-attachment.googleusercontent.com", "attachments.office.net",
    "tinypic.com", "imageshack.us", "postimg.cc", "ibb.co", "freeimage.host", "imagevenue.com",
    "pixhost.to"
]

PASTE_DOMAINS = [
    "paste2.org", "jsbin.com", "play.golang.org", "paste.debian.net",
    "pastehtml.com", "pastebin.com", "snipplr.com", "snipt.net",
    "heypasteit.com", "pastebin.fr", "slexy.org", "hastebin.com",
    "dumpz.org", "codepad.org", "jsitor.com", "dpaste.org",
    "textsnip.com", "bitpaste.app", "justpaste.it", "jsfiddle.net",
    "dpaste.com", "codepen.io", "dartpad.dartlang.org",
    "ide.codingblocks.com", "dotnetfiddle.net", "ideone.com",
    "paste.fedoraproject.org", "paste.frubar.net", "repl.it",
    "paste.opensuse.org", "rextester.com", "paste.org.ru",
    "paste.ubuntu.com", "paste.pound-python.org", "paste.lisp.org",
    "paste.xinu.at", "try.ceylon-lang.org", "paste.org",
    "phpfiddle.org", "ide.geeksforgeeks.org"
]


PHOTO_DOMAINS = [d.lower() for d in PHOTO_DOMAINS]
PASTE_DOMAINS = [d.lower() for d in PASTE_DOMAINS]
E_SIGNATURE_DOMAINS = [d.lower() for d in E_SIGNATURE_DOMAINS]

SUSPICIOUS_URL_PARAMS_SET = {
    re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_') for s in SUSPICIOUS_URL_PARAMS_SET
}
SUSPICIOUS_PARAMS_SET = {
    re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_') for s in SUSPICIOUS_PARAMS_SET
}

def norm_key(
    s: str) -> str: return re.sub(r'[^a-z0-9]+', '_', (s or '').lower()).strip('_')


COMMON_JUNK = {
    "yes", "true", "ok", "none", "email", "submit", "click", "value", "button", "form",
    "name", "open", "more", "back", "next", "account", "password", "search", "video",
    "login", "register", "send", "go", "apply", "filter", "sort", "confirm", "cancel",
    "reset", "continue", "save", "update", "download", "upload", "admin", "user", "test",
    "e-mail", "name@host.com", "123456", "email or phone", "phone number", "enter your name", "sign in"
}
BAD_VALUES = COMMON_JUNK
JUNK_VALUES = COMMON_JUNK


STRONG_TYPE_HINTS = [
    "access_code", "access_token", "account_number", "airtable_api_key",
    "api_key", "api_secret", "apikey", "auth", "auth_key", "auth_token",
    "authenticity_token", "backup_file", "bank_account", "bearer",
    "beneficiary_id", "card_number", "certificate", "chat_token",
    "checkout_token", "ci_build_token", "circleci_token", "client_secret",
    "client_token", "config", "config_file", "creds", "credentials",
    "credit_card_number", "creditcard", "crypto_api_key", "crypto_key",
    "crypto_secret_key", "crypto_token", "crypto_wallet", "csrf",
    "csrf_token", "csrftoken", "database_dump", "debitcard",
    "dental_record_id", "discord_bot_token", "doc_token", "download_link",
    "download_token", "dropbox_link", "employer_insurance_id",
    "firebase_token", "gitlab_token", "github_token", "gdrive_link",
    "gdrive_share_link", "hash", "health_id", "health_insurance_id",
    "healthcare_id", "hmac", "identity_number", "insurance_number",
    "jenkins_token", "jwt", "keystore", "key", "license_key", "logfile",
    "logincsrfparam", "login", "medical_record_id", "military_id",
    "mnemonic", "mnemonic_phrase", "notion_token", "oauth", "oauth_token",
    "oauth_verifier", "onedrive_link", "pan_card", "pan_number", "password",
    "payment_token", "private_key", "public_key", "pwd", "recovery_token",
    "refresh_token", "repository_url", "reset_token", "residence_permit",
    "secret_key", "security_code", "security_login", "security_token",
    "seed_phrase", "session_id", "session_key", "session_token", "sessionid",
    "signature_id", "signing_session", "signing_token", "signin",
    "slack_bot_token", "slack_token", "slack_webhook",
    "social_security_number", "ssh_key", "snapshot_id", "sso_token",
    "state_token", "stripe_token", "student_id", "tax_id",
    "telegram_bot_token", "transaction_token", "twilio_token",
    "vaccination_id", "verification_code", "verify_token", "voter_id",
    "xsrf", "zendesk_token"
]

WEAK_TYPE_HINTS = [
    "aadhaar_number", "account", "account_id", "address", "agreement_id", "token",
    "api_url", "api_webhook", "attachment", "attachment_id", "audit_log_id",
    "backup", "balance_amount", "bic", "billing", "billing_address",
    "blood_type", "booking_ref", "booking_reference", "btc_address",
    "build_hook", "card_ending", "card_type", "cart_id", "chat_whatsapp",
    "checkout", "citizen_id", "compliance_report_id", "confirmation_number",
    "contract_id", "contract_number", "coupon_code", "crypto_address",
    "crypto_token", "customer_id", "cvc", "dataset", "date_of_birth",
    "delivery_note_number", "discount_code", "dispatch_id", "discord_invite",
    "doc", "doc_hash", "doc_link", "docid", "document", "document_id",
    "dob", "download_id", "driver_license_number", "e_ticket_number",
    "email_address", "emergency_contact", "employee_id", "employee_number",
    "envelope_id", "esign_request", "eth_address", "event_id", "facebook_id",
    "fax_number", "file", "file_name", "file_url", "fileid", "filename",
    "filepath", "first_name", "flight_number", "fraud_case_id",
    "frequent_flyer_number", "full_name", "gender", "giftcard_number",
    "gdrive", "gdrive_file_id", "group_id", "home_address", "iban",
    "identity", "incident_id", "instagram_id", "internal_reference",
    "invoice", "invoice_amount", "invoice_id", "invoice_number",
    "invoice_total", "invoice_reference", "invite_link", "itinerary_id",
    "last4_digits", "last_name", "legal_doc", "link", "loyalty_card_id",
    "mailing_address", "marital_status", "media", "media_id", "member_id",
    "member_number", "messenger_thread", "messenger_thread_id",
    "middle_name", "miles_account_id", "mobile_number", "national_id",
    "nationality", "nhs_number", "onedrive", "order", "order_amount",
    "order_id", "order_number", "order_total", "order_reference",
    "order_tracking_id", "parcel_id", "passport_number", "payment_id",
    "payment_method", "payment_reference", "payment_type", "payment_ref",
    "pdf_file", "phone_number", "photo", "place_of_birth", "postal_code",
    "profile", "profile_id", "project_id", "promo_code", "purchase_id",
    "receipt_number", "reservation_number", "reservas", "reward_points",
    "rfq_id", "risk_score", "s3_bucket", "security_alert_id", "settings",
    "shipment_id", "shared_link", "skype_id", "slack_invite", "snapchat_id",
    "social_user_id", "ssn_full", "ssn_last4", "staff_id", "supplier_id",
    "survey_id", "telegram_bot", "telegram_chat_id", "tracking",
    "tracking_id", "tracking_number", "transaction_id", "transaction_hash",
    "travel_doc_id", "trip_id", "twilio_sid", "user_id", "vendor_id",
    "verify", "verification", "visa", "voucher_code", "voucher_id",
    "wallet", "wallet_address", "waybill_number", "webhook_url",
    "whatsapp_link", "xlsx_file", "zip_code"
]

STRONG_HTML_HINTS = {norm_key(x) for x in STRONG_HTML_HINTS}
WEAK_HTML_HINTS = {norm_key(x) for x in WEAK_HTML_HINTS}

STRONG_URL_HINTS = {norm_key(x) for x in STRONG_TYPE_HINTS}
WEAK_URL_HINTS = {norm_key(x) for x in WEAK_TYPE_HINTS}


# Chrome options# Chrome options
chrome_options = Options()
chrome_options.binary_location = "/opt/google/chrome/chrome"


def make_driver():
    import os
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options

    chrome_options = Options()

    prefs = {
        "profile.managed_default_content_settings.fonts": 2,
        "profile.managed_default_content_settings.stylesheets": 1,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    os.environ.pop("CHROME_BIN", None)
    chrome_options.binary_location = "/opt/google/chrome/chrome"
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1280x800")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--metrics-recording-only")
    chrome_options.add_argument("--renderer-process-limit=1")

   

    service = Service(
        "...chromedriver-linux64/chromedriver..."
    )

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


# Initialize DB


def init_results_db():
    os.makedirs(os.path.dirname(RESULTS_DB), exist_ok=True)

    conn = sqlite3.connect(RESULTS_DB)
    c = conn.cursor()

    # Main results table
    c.execute("""
        CREATE TABLE IF NOT EXISTS leaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            status TEXT,
            matched_url TEXT,
            matched_html TEXT,
            screenshot_path TEXT,
            html_path TEXT,
            type TEXT,
            category TEXT
        )
    """)

    conn.commit()
    conn.close()


folder = "..."


all_urls = []


def load_urls_from_db(db_path, table_name, column_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT DISTINCT {column_name} FROM {table_name}")
    urls = [row[0] for row in cursor.fetchall()
            if row[0] and row[0].startswith("https://")]
    conn.close()
    return urls



def check_special_domain(url):
    try:
        host = (urllib.parse.urlparse(url).netloc or "").lower()
        if "@" in host:
            host = host.split("@", 1)[-1]
        if ":" in host:
            host = host.split(":", 1)[0]
        if host.startswith("www."):
            host = host[4:]
        if not host:
            return None

        def in_list_suffix(hostname, domain_list):
            for d in domain_list:
                d = (d or "").lower().strip()
                if not d:
                    continue
                if hostname == d or hostname.endswith("." + d):
                    return True
            return False

        if in_list_suffix(host, PHOTO_DOMAINS):
            return "photo"
        if in_list_suffix(host, E_SIGNATURE_DOMAINS):
            return "e_signature"
        if in_list_suffix(host, PASTE_DOMAINS):
            return "paste"

        return None
    except Exception:
        return None


def llm_gate_url_keep(url: str, reason: str, no_leak_drop_conf: float = 0.85) -> bool:
    """
You are a precise security triager. Decide whether a URL
potentially exposes sensitive material.
Return STRICT JSON with keys:
{"keep": true|false,
"reason": "<short>",
"signals": ["<k=v>"],
"confidence": <float between 0 and 1>}
Guidance:
- KEEP the URL if any of the following structural conditions hold:
(i) the URL contains at least five parameters, or any
parameter/field name longer than seven characters;
(ii) the total URL length exceeds 150 characters;
(iii) the path contains four or more directory levels.
- SKIP static assets: fonts, css, js,
svg, webp, gif, scss, woff, woff2,
ttf, otf, eot, ico, mp3, wav, ogg. mp4. mov, avi. webm.
    """
    try:
        payload = build_llm_payload(
            url=url,
            matched_url=reason,
            leaks=[],
            visible_text="",
            html_excerpt="",
        )
        payload["url_only_mode"] = True

        out = llm_verify(payload)
        print("LLM_URL_GATE", url, "reason=", reason, "verdict=", out)

        verdict = str(out.get("verdict", "uncertain")).strip().lower()
        conf = float(out.get("confidence") or 0.0)

        if verdict == "leak":
            return True

        if verdict == "no_leak":
            # Only trust no_leak if the model is very confident.
            if conf >= no_leak_drop_conf:
                return False   # DROP (model very confident no leak)
            return True        # KEEP (not confident enough to drop)
            # low conf => KEEP, high conf => DROP

        # uncertain (or anything unexpected) => KEEP
        return True

    except Exception as e:
        print("LLM_URL_GATE_ERROR", url, reason, e)
        # Fail-open (safer for research collection; avoids losing candidates)
        return True


def is_special_domain_candidate(url):
    try:
        p = urllib.parse.urlparse(url)
        path = (p.path or "").strip("/")
        if not path:
            return "special_domain_homepage"
        segs = [s for s in path.split("/") if s]
        last = segs[-1] if segs else ""
        if len(last) >= 10:
            return "special_domain_resource_id"
        for kw in ["document", "doc", "envelope", "agreement", "sign", "view", "share", "download", "raw", "clip", "file", "token", "oauth"]:
            if kw in path.lower():
                return "special_domain_resource_path"
        return "special_domain_other_path"
    except Exception:
        return "special_domain_other_path"


def filter_useful_urls(url_list):
    useful_urls = []
    skipped_reasons = {"static_file": 0, "no_signal": 0}

    bad_exts = {
        ".gif", ".css", ".svg", ".woff", ".ico", ".mp4", ".webp",
        ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".heic", ".webm",
        ".zip", ".tar", ".gz", ".7z", ".rar"
    }

    STRONG_URL_HINTS = {norm_key(x) for x in STRONG_TYPE_HINTS}
    WEAK_URL_HINTS = {norm_key(x) for x in WEAK_TYPE_HINTS}

    for url in url_list:
        url = (url or "").strip()
        if not url:
            skipped_reasons["no_signal"] += 1
            continue

        if url.startswith("//"):
            url = "https:" + url
        elif not re.match(r"^https?://", url, re.I):
            if "." in url.split("/")[0]:
                url = "https://" + url

        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                skipped_reasons["no_signal"] += 1
                continue
            url_path = (parsed.path or "").lower()
        except Exception:
            continue

        try:
            query_params = urllib.parse.parse_qs(
                parsed.query, keep_blank_values=True)
        except Exception:
            query_params = {}

        try:
            path = (parsed.path or "").strip() or "/"
            if not query_params and path == "/":
                skipped_reasons["no_signal"] += 1
                continue
        except Exception:
            pass

        domain_type = check_special_domain(url)

        if domain_type not in {"photo", "e_signature", "paste"}:
            if any(
                url_path.endswith(ext)
                and ".php" not in url_path
                and ".asp" not in url_path
                for ext in bad_exts
            ):
                skipped_reasons["static_file"] += 1
                continue

        norm_map = {}
        for k, vals in query_params.items():
            nk = norm_key(k)
            if nk not in norm_map:
                norm_map[nk] = (k, vals)

        param_keys = set(norm_map.keys())

        strong_hits = STRONG_URL_HINTS & param_keys
        weak_hits = WEAK_URL_HINTS & param_keys

        # ---------- STRONG URL → NO URL GATE ----------
        if strong_hits:
            pairs = "; ".join(
                f"{k}:{norm_map[k][1][0] if norm_map[k][1] else ''}"
                for k in strong_hits
            )
            useful_urls.append({
                "url": url,
                "matched_url": pairs,
                "tier": "strict"
            })
            continue

        # ---------- WEAK URL → URL GATE ----------
        if weak_hits:
            hint = "; ".join(sorted(weak_hits))
            keep = llm_gate_url_keep(url, f"weak_url_hint:{hint}")
            if keep:
                useful_urls.append({
                    "url": url,
                    "matched_url": hint,
                    "tier": "loose",
                    "needs_url_gate": True
                })
            continue

        # ---------- SPECIAL DOMAIN → URL GATE ----------
        if domain_type in {"photo", "e_signature", "paste"}:
            reason = f"{domain_type}:{is_special_domain_candidate(url)}"
            keep = llm_gate_url_keep(url, reason)
            if keep:
                useful_urls.append({
                    "url": url,
                    "matched_url": reason,
                    "tier": "loose",
                    "needs_url_gate": True
                })
            continue

        # ---------- HEURISTIC → URL GATE ----------
        hint = is_high_signal_heuristic(url, query_params)
        if hint:
            keep = llm_gate_url_keep(url, hint)
            if keep:
                useful_urls.append({
                    "url": url,
                    "matched_url": hint,
                    "tier": "loose",
                    "needs_url_gate": True
                })
            continue

        skipped_reasons["no_signal"] += 1

    return useful_urls


def is_high_signal_heuristic(url, query_params):
    parsed = urllib.parse.urlparse(url)
    url_path = parsed.path.lower()
    path_segments = url_path.strip("/").split("/")

    long_keys = any(len(k) >= 1600 for k in query_params.keys())
    many_params = len(query_params) >= 1000

    if many_params and long_keys:
        return "heuristic: many long query params"

    if len(url) >= 22000 and url.count("/") >= 6:
        return "heuristic: long URL with depth"

    if any(len(seg) > 3000 for seg in path_segments):
        return "heuristic: long path segment"

    return None


def decode_barcodes_from_pil(img):
    try:
        if img.mode != "RGB":
            img = img.convert("RGB")
        # optionally increase contrast / invert for tricky images:
        # img = ImageOps.autocontrast(img)
        decoded = zbar_decode(img)
        out = []
        for d in decoded:
            data = d.data.decode("utf-8", errors="ignore")
            out.append({
                "type": d.type,
                "data": data,
                "rect": tuple(d.rect)  # (left, top, width, height)
            })
        return out
    except Exception as e:
        print(f" decode_barcodes_from_pil error: {e}")
        return []


def decode_image_file(path):
    try:
        img = Image.open(path)
    except Exception as e:
        print(f" open image failed: {e}")
        return []
    return decode_barcodes_from_pil(img)


def decode_pdf_file(pdf_path, dpi=200, max_pages=None):
    results = []
    try:
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        pages = range(page_count) if not max_pages else range(
            min(page_count, max_pages))
        for pi in pages:
            page = doc.load_page(pi)
            mat = fitz.Matrix(dpi/72, dpi/72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            decs = decode_barcodes_from_pil(img)
            for d in decs:
                d["page"] = pi + 1
                results.append(d)
        doc.close()
    except Exception as e:
        print(f" decode_pdf_file error: {e}")
    return results


def looks_random(val: str) -> bool:
    v = (val or "").strip()
    if len(v) < 12:
        return False
    # reject obvious junk like emails/urls
    if "@" in v or v.startswith(("http://", "https://")):
        return False
    # check character class diversity
    classes = sum([
        any(c.islower() for c in v),
        any(c.isupper() for c in v),
        any(c.isdigit() for c in v),
        any(c in "-_.~+/=" for c in v),
    ])
    if classes < 2:
        return False
    # normalized Shannon entropy
    probs = [v.count(c)/len(v) for c in set(v)]
    H = -sum(p*log2(p) for p in probs)
    Hnorm = H / log2(len(set(v))) if len(set(v)) > 1 else 0
    return Hnorm >= 0.85


def extract_dynamic_inputs(driver, suspicious_keywords, config):
    leaks = []
    inputs = driver.find_elements(By.TAG_NAME, "input")

    for inp in inputs:
        try:
            name = (inp.get_attribute("name")
                    or inp.get_attribute("id") or "").lower()
            value = inp.get_attribute("value") or ""

            if not value or value.lower() in JUNK_VALUES:
                continue

            matched_type = None
            for keyword in suspicious_keywords:
                if keyword in name:
                    matched_type = keyword
                    break

            if config.get("require_field_match") and not matched_type:
                continue

            if is_valid_leak_value(value, config):
                leaks.append({
                    "type": matched_type or "input_value",
                    "value": value.strip(),
                    "field": name,
                    "source": "input_dynamic"
                })

                print(
                    f"Extracted dynamic input: type={matched_type or 'input_value'}, field={name}, value={value.strip()}")

        except Exception as e:
            print(f" Error in dynamic input extraction: {e}")
            continue

    return leaks


def is_url_live(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        # === HEAD request — allow 200–399
        head_resp = requests.head(
            url, headers=headers, timeout=12, allow_redirects=False)
        if 200 <= head_resp.status_code < 400:
            return True, url

        # === Fallback to GET request — allow redirects now
        get_resp = SESSION.get(url, headers=headers,
                               timeout=12, allow_redirects=True)
        html_snip = (get_resp.text or "")[:4000].lower()

        # Accept 200–399
        if not (200 <= get_resp.status_code < 400):
            return False, url

        # Softer blocked keywords: log but don’t block
        blocked_keywords = [
            "not found", "access denied", "you need permission",
            "403 forbidden", "you have been blocked",
            "error 404", "page doesn't exist", "404"
        ]
        if any(phrase in html_snip for phrase in blocked_keywords):

            print(f" Blocked/404 detected → treating as dead: {url}")
            return False, url

        return True, url

    except requests.exceptions.RequestException as e:
        # print(f" Network error: {e}")
        return False, url

    except Exception as e:
        print(f" Unexpected error for {url}: {e}")
        return False, url


def head_is_pdf(url):
    try:
        r = SESSION.head(url, timeout=10, allow_redirects=True)
        ctype = (r.headers.get("content-type", "") or "").lower()
        if "application/pdf" in ctype:
            return True
        return False
    except Exception:
        return False


def take_screenshot(url, prefix="test", screenshot_dir=None, html_dir=None):
    global chrome_options

    if screenshot_dir is None:
        screenshot_dir = SCREENSHOT_FOLDER
    if html_dir is None:
        html_dir = HTML_FOLDER

    try:
        os.makedirs(screenshot_dir, exist_ok=True)
        os.makedirs(html_dir, exist_ok=True)
    except Exception as e:
        print(f" Dir creation failed: {e}")
        return None, None, None

    timestamp = int(time.time() * 1000)
    ss_path = os.path.join(screenshot_dir, f"{prefix}_{timestamp}.png")
    html_path = os.path.join(html_dir, f"{prefix}_{timestamp}.html")

    driver = None
    try:
        driver = make_driver()
        driver.set_page_load_timeout(20)

        try:
            driver.get(url)
        except TimeoutException:
            print(f" TimeoutException — skipping: {url}")
            with open("skipped_timeout_urls.txt", "a") as f:
                f.write(url + "\n")
            return None, None, None

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))
        scroll_height = driver.execute_script(
            "return document.body.scrollHeight")
        driver.set_window_size(1280, min(scroll_height, 2500))
        time.sleep(0.2)

        driver.save_screenshot(ss_path)
        page_html = driver.page_source

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page_html)

        # print(f" Screenshot + HTML saved: {url}")
        return ss_path, html_path, page_html

    except Exception as e:
        print(f" Screenshot failed for {url}: {type(e).__name__}: {e}")
        return None, None, None

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        time.sleep(0.1)


def safe_screenshot_with_timeout(url, prefix="test", timeout=30):
    def _take():
        return take_screenshot(url, prefix=prefix)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_take)
            ss, html, _ = future.result(timeout=timeout)
            return ss, html
    except concurrent.futures.TimeoutError:
        print(f" Timeout exceeded → screenshot failed for: {url}")
        return None, None
    except Exception as e:
        print(
            f" Screenshot thread crashed for {url}: {type(e).__name__}: {e}")
        return None, None


def translate_safe(text, target="en", retries=1, delay=0.3):
    if not text:
        return text
    try:
        return GoogleTranslator(source='auto', target=target).translate(text)
    except Exception:
        # one lite retry, then give up silently
        if retries > 0:
            time.sleep(delay)
            try:
                return GoogleTranslator(source='auto', target=target).translate(text)
            except Exception:
                return text
        return text


def extract_from_visible_text(text, suspicious_keywords, config):
    leaks = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or len(line) < 5:
            continue

        lower_line = line.lower()

        for keyword in suspicious_keywords:
            if keyword in lower_line:

                # Try :, =, - split
                parts = None
                for splitter in [":", "=", "-"]:
                    if splitter in line:
                        parts = line.split(splitter, 1)
                        break

                # Extract value
                if parts and len(parts) >= 2:
                    val = parts[1].strip(' \t\n\r;,.')
                else:
                    toks = line.split()
                    if len(toks) >= 2:
                        val = toks[-1].strip(' \t\n\r;,.')
                    else:
                        continue

                # Filters
                if val.startswith("//"):
                    break

                if val.startswith(("http://", "https://")) and not looks_secretish(val):
                    break

                if keyword in {"order", "link"} and len(val) < max(16, config.get("min_val_length", 10)):
                    break

                if is_valid_leak_value(val, config):
                    leaks.append({
                        "type": keyword,
                        "value": val,
                        "source": "visible_text"
                    })

                break

    return leaks


URL_RE = re.compile(r'^https?://', re.I)
EXT_RE = re.compile(
    r'\.(html?|css|js|png|jpe?g|gif|svg|pdf|txt)(?:\?|#|$)', re.I)
PATH_RE = re.compile(r'^(/[A-Za-z0-9._%~-]+){2,}$')
UUID_RE = re.compile(
    r'\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b', re.I)
# 24/32/40/64+ hex
HEX_RE = re.compile(r'\b[0-9a-f]{24,}\b', re.I)
# URL-safe base64
B64_RE = re.compile(r'^[A-Za-z0-9+/_-]{32,}={0,2}$')
JWT_RE = re.compile(
    r'^[A-Za-z0-9-_]{20,}\.[A-Za-z0-9-_]{20,}\.[A-Za-z0-9-_]{20,}$')

DENY_FIELDS = {
    'shareurl', 'returnurl', 'redirect', 'return_url', 'url', 'href', 'lang', 'locale', 'sort', 'page',
    'search', 'query', 'filter', 'q', 's', 'ref', 'referrer', 'source', 'utm', 'gclid', 'fbclid', 'input'
}


def is_denied_field(name: str) -> bool:
    if not name:
        return False
    n = name.lower()
    if n in DENY_FIELDS:
        return True
    # treat these as prefixes too (utm_*, input_*, ref_…)
    for p in ('utm', 'input', 'ref', 'return_url', 'gclid', 'fbclid'):
        if n.startswith(p) or n.startswith(p+'_'):
            return True
    return False


def shannon_bpc(s: str) -> float:
    from math import log2
    if not s:
        return 0.0
    L = len(s)
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    H = -sum((n/L) * log2(n/L) for n in freq.values())
    return H  # absolute bits/char; threshold tuned below


def looks_secretish(v: str, min_len: int = 16) -> bool:
    v = (v or '').strip()
    if len(v) < min_len or ' ' in v:
        return False
    if '@' in v and '.' in v.split('@')[-1]:
        return False  # email-like
    if JWT_RE.match(v) or UUID_RE.search(v) or HEX_RE.search(v) or B64_RE.match(v):
        return True
    digits = sum(c.isdigit() for c in v)
    letters = sum(c.isalpha() for c in v)
    if digits >= 6 and letters >= 6:
        return True
    return shannon_bpc(v) >= 3.5


def is_valid_leak_value(val: str, config: dict) -> bool:
    if not val:
        return False
    v = val.strip()
    if v.lower() in BAD_VALUES:
        return False

    # URL values: first check query for suspicious key + secretish value
    if URL_RE.match(v):
        u = urlsplit(v)
        q = dict(parse_qsl(u.query))

        if any(norm_key(k) in SUSPICIOUS_URL_PARAMS_SET for k in q) and \
           any(len(q[k]) >= 16 and looks_secretish(q[k])
               for k in q if norm_key(k) in SUSPICIOUS_URL_PARAMS_SET):
            return True

        # then reject obvious static/resource URLs by path/extension
        if EXT_RE.search(u.path or "") or PATH_RE.match(u.path or ""):
            return False

        # no qualifying query secrets → reject URL values
        return False

    # Non-URL values: drop obvious paths/files
    if EXT_RE.search(v) or PATH_RE.match(v):
        return False

    # Config gates
    min_len = config.get("min_val_length", 10)
    if len(v) < min_len:
        return False
    if config.get("require_digit") and not any(c.isdigit() for c in v):
        return False

    # Strong accept for long tokens; else shape check
    if len(v) >= 30 and ' ' not in v:
        return True
    return looks_secretish(v, min_len=max(16, min_len))


def load_page_source_only(url):
    global chrome_options
    driver = None
    try:
        driver = make_driver()
        driver.set_page_load_timeout(30)
        driver.get(url)
        WebDriverWait(driver, 35).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(0.5)
        html = driver.page_source
        return html
    except Exception as e:
        print(f" Failed to load page source for {url}: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def extract_from_inputs(soup, suspicious_keywords, config):
    leaks = []

    PLACEHOLDER_JUNK = {
        "username", "password", "email", "admin", "test", "user", "login",
        "name@host.com", "e-mail", "123456", "email or phone",
        "phone number", "enter your name", "sign in", "submit"
    }

    for inp in soup.find_all(["input", "textarea"]):
        input_type = inp.get("type", "text").lower()
        if input_type in {"submit", "button", "checkbox", "radio", "file", "reset"}:
            continue

        name = (inp.get("name") or inp.get("id") or "").lower()
        value = (inp.get("value") or inp.get("placeholder") or "").strip()
        if inp.name == "textarea":
            value = inp.text.strip() or value
        if not value or value.lower() in PLACEHOLDER_JUNK:
            continue

        # === Match on keyword in field name
        matched_type = None
        for keyword in suspicious_keywords:
            if keyword in name:
                matched_type = keyword
                break

        # === If no keyword match, skip in aggressive mode
        if config.get("require_field_match") and not matched_type:
            continue
        if not matched_type:
            continue  # Skip if no real keyword match (force strictness)
        # name is already lowercased
        if is_denied_field(name):
            continue
        if config.get("require_field_match", True) and not any(kw in name for kw in suspicious_keywords):
            # optionally allow hidden fields:
            if input_type != 'hidden':
                continue

        # === Check value quality
        if is_valid_leak_value(value, config):
            leaks.append({
                "type": matched_type or "input_value",
                "value": value,
                "field": name,
                "source": "input"
            })

    return leaks


def extract_from_meta_and_data_attrs(soup, suspicious_keywords, config):
    leaks = []
# === 1. Extract from <meta> tags
    for meta in soup.find_all("meta"):
        name = meta.get("name", "") or meta.get("property", "")
        content = meta.get("content", "")
        if not content or len(content.strip()) < config.get("min_val_length", 10):
            continue

    # Lowercase for comparison
        content_lower = content.strip().lower()

    # Skip junk values
        if content_lower in JUNK_VALUES:
            continue

        for keyword in suspicious_keywords:
            if keyword.lower() in name.lower():
                if is_valid_leak_value(content, config):
                    leaks.append({
                        "type": keyword,
                        "value": content.strip(),
                        "field": name,
                        "source": "meta"
                    })

    # === 2. Extract from data-* attributes
    for tag in soup.find_all(True):
        for attr, val in tag.attrs.items():
            if attr.startswith("data-") and isinstance(val, str):
                for keyword in suspicious_keywords:
                    if keyword.lower() in attr.lower():
                        if is_valid_leak_value(val, config):
                            leaks.append({
                                "type": keyword,
                                "value": val.strip(),
                                "field": attr,
                                "source": "data-attribute"
                            })

    return leaks


SET_COOKIE_RE = re.compile(r'^\s*([^=;\s]+)\s*=\s*([^;]*)')


def collect_response_cookies(req_index):
    out = []
    for r in req_index:
        hdrs = r.get("resp_headers") or {}
        sc = hdrs.get("Set-Cookie") or hdrs.get("set-cookie")
        if not sc:
            continue
        parts = re.split(r'[\r\n](?=\S+=)|,(?=\s*\S+=)', sc)
        for p in parts:
            ck = parse_set_cookie(p.strip())
            if ck:
                out.append(ck)
    seen, uniq = set(), []
    for ck in out:
        k = (ck["name"], ck["value"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(ck)
    return uniq


def correlate_cookie_leaks(page_url, page_domain, cookies, req_index):
    leaks = []
    if not cookies:
        return leaks

    def domain_of(u):
        try:
            return urllib.parse.urlparse(u).netloc.split(':')[0].lower()
        except:
            return ""

    all_urls, refs, locs, auths, bodies = [], [], [], [], []
    for r in req_index:
        all_urls.append(r.get("url") or "")
        h = r.get("headers") or {}
        refs.append(h.get("Referer") or h.get("referer") or "")
        a = h.get("Authorization") or h.get("authorization") or ""
        if a:
            auths.append(a)
        rh = r.get("resp_headers") or {}
        locs.append(rh.get("Location") or rh.get("location") or "")
        if r.get("postData"):
            bodies.append(str(r["postData"])[:8000])

    def variants(s):
        S = set()
        if not s:
            return S
        S.add(s)
        try:
            S.add(urllib.parse.unquote(s))
        except:
            pass
        if s.lower().startswith("bearer "):
            S.add(s[7:].strip())
        return S

    for ck in cookies:
        v = (ck["value"] or "").strip()
        if len(v) < 12 or not looks_secretish(v, min_len=12):
            # still record policy issues below
            pass
        # policy issues as pseudo-leaks
        for isu in ck["issues"]:
            leaks.append({"type": f"cookie_policy:{ck['name']}:{isu}",
                          "value": ck["samesite"] or "-", "source": "set-cookie"})

        vset = variants(v)
        if not vset:
            continue

        for u in all_urls:
            if any(x and x in u for x in vset):
                leaks.append({"type": f"cookie_in_url:{ck['name']}",
                              "value": v[:64],
                              "source": "runtime_url_same" if domain_of(u) == page_domain else "runtime_url_cross",
                              "sink": u})

        for rf in refs:
            if rf and any(x in rf for x in vset):
                leaks.append({"type": f"cookie_in_referer:{ck['name']}",
                              "value": v[:64], "source": "referer", "sink": rf})

        for lc in locs:
            if lc and any(x in lc for x in vset):
                leaks.append({"type": f"cookie_in_redirect:{ck['name']}",
                              "value": v[:64],
                              "source": "redirect_same" if domain_of(lc) == page_domain else "redirect_cross",
                              "sink": lc})

        for ah in auths:
            if any(x in ah for x in vset):
                leaks.append({"type": f"cookie_in_authorization:{ck['name']}",
                              "value": v[:64], "source": "authorization"})

        for bd in bodies:
            if any(x in bd for x in vset):
                leaks.append({"type": f"cookie_in_body:{ck['name']}",
                              "value": v[:64], "source": "body"})

    # de-dupe
    uniq, seen = [], set()
    for l in leaks:
        k = (l["type"], l.get("sink", ""), l["value"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(l)
    return uniq


def extract_from_js_variables(soup, suspicious_keywords, config):
    leaks = []

    # Grab all <script> tags that are inline (no src)
    for script in soup.find_all("script"):
        if script.has_attr("src") or not script.string:
            continue

        js_code = script.string

        # Match patterns like: let/var/const keyword = "value";
        pattern = r"\b([a-zA-Z0-9_\-$]+)\s*[:=]\s*['\"]([^'\"]{4,})['\"]"
        matches = re.findall(pattern, js_code)

        for var_name, var_value in matches:
            var_name_lower = var_name.lower()
            var_value_clean = var_value.strip()

            # Match if var name OR value contains a suspicious keyword
            for keyword in suspicious_keywords:
                keyword_lower = keyword.lower()
                if (keyword_lower in var_name_lower):
                    if is_valid_leak_value(var_value_clean, config):
                        leaks.append({
                            "type": keyword,
                            "value": var_value_clean,
                            "field": var_name,
                            "source": "js-var"
                        })

    return leaks


def extract_from_screenshot_text(ss_path, suspicious_keywords, config):
    leaks = []

    try:
        image = Image.open(ss_path)
        text = pytesseract.image_to_string(image).lower()
        # print(" OCR text extracted from screenshot.")

        leaks_ocr = extract_from_visible_text(
            text, suspicious_keywords, config)
        leaks.extend(leaks_ocr)

    except Exception as e:
        print(f" OCR failed for {ss_path}: {e}")

    return leaks


def deduplicate_leaks(leak_list):
    seen = set()
    unique_leaks = []
    for leak in leak_list:
        key = f"{leak['type']}:{leak['value']}"
        if key not in seen:
            seen.add(key)
            unique_leaks.append(leak)
    return unique_leaks


def _safe_json_loads(s):
    try:
        return json.loads(s)
    except Exception:
        return None


def capture_network_traffic(driver, max_entries=1500):
    events = []
    try:
        raw = driver.get_log("performance")
    except Exception:
        return events

    for item in raw[-max_entries:]:
        msg = _safe_json_loads(item.get("message", ""))
        if not msg:
            continue
        m = msg.get("message", {})
        method = m.get("method", "")
        if not method.startswith("Network."):
            continue
        params = m.get("params", {})
        events.append({"method": method, "params": params})
    return events


def normalize_request_index(events):
    reqs = {}
    for ev in events:
        m = ev["method"]
        p = ev["params"]
        if m == "Network.requestWillBeSent":
            r = p.get("request", {})
            rid = p.get("requestId")
            if not rid:
                continue
            reqs.setdefault(rid, {}).update({
                "url": r.get("url"),
                "method": r.get("method"),
                "headers": r.get("headers", {}),
                "postData": r.get("postData", None),  # may be absent
                "ts": p.get("timestamp"),
                "type": p.get("type"),  # ResourceType
            })
        elif m == "Network.responseReceived":
            rid = p.get("requestId")
            if not rid or rid not in reqs:
                continue
            resp = p.get("response", {})
            reqs[rid].update({
                "status": resp.get("status"),
                "resp_headers": resp.get("headers", {}),
                "mime": resp.get("mimeType"),
            })
    # flatten
    return [v for v in reqs.values() if v.get("url")]


def extract_secrets_from_requests(req_list, suspicious_keys, config):
    leaks = []

    for r in req_list:
        url = r.get("url") or ""
        method = (r.get("method") or "").upper()
        headers = r.get("headers") or {}
        postData = r.get("postData") or ""
        status = r.get("status")

        # 1) URL query params
        try:
            u = urlsplit(url)
            q = dict(parse_qsl(u.query))
            for k, v in q.items():
                k_norm = re.sub(r'[^a-z0-9]+', '_',
                                (k or "").lower()).strip('_')
                if k_norm in suspicious_keys and is_valid_leak_value(v, config):
                    leaks.append({"type": f"HTTP-layer:{k_norm}",
                                 "value": v, "source": f"http_{method}"})
        except Exception:
            pass

        # 2) Authorization / Cookie headers
        auth = headers.get("Authorization") or headers.get("authorization")
        if auth and is_valid_leak_value(auth.replace("Bearer ", "").strip(), config):
            leaks.append({"type": "header_authorization",
                         "value": auth, "source": f"http_{method}"})

        cookie = headers.get("Cookie") or headers.get("cookie")
        if cookie and any(tk in cookie.lower() for tk in ("session", "token", "jwt", "auth")):
            # Store cookie string conservatively (already in headers)
            if is_valid_leak_value(cookie, config):
                leaks.append({"type": "header_cookie",
                             "value": cookie, "source": f"http_{method}"})

        # 3) POST body (JSON or form-encoded if present in log)
        if isinstance(postData, str) and len(postData) >= config.get("min_val_length", 16):
            # Try JSON first
            parsed = _safe_json_loads(postData)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if not isinstance(v, str):
                        continue
                    k_norm = re.sub(r'[^a-z0-9]+', '_',
                                    (k or "").lower()).strip('_')
                    if k_norm in suspicious_keys and is_valid_leak_value(v, config):
                        leaks.append({"type": f"req_body:{k_norm}",
                                     "value": v, "source": f"http_{method}"})
            else:
                # Fallback: form-encoded k=v&… (best-effort)
                try:
                    pairs = dict(parse_qsl(postData))
                    for k, v in pairs.items():
                        k_norm = re.sub(r'[^a-z0-9]+', '_',
                                        (k or "").lower()).strip('_')
                        if k_norm in suspicious_keys and is_valid_leak_value(v, config):
                            leaks.append(
                                {"type": f"req_body:{k_norm}", "value": v, "source": f"http_{method}"})
                except Exception:
                    pass

    return deduplicate_leaks(leaks)


def process_ocr_leaks(url, driver, prefix, leak_type="ocr"):

    if driver is None:
        return

    # take screenshot using the existing driver (no new selenium)
    try:
        os.makedirs(OCR_SCREENSHOT_FOLDER, exist_ok=True)
        os.makedirs(OCR_HTML_FOLDER, exist_ok=True)
    except Exception:
        pass

    ts = int(time.time() * 1000)
    ocr_ss_path = os.path.join(OCR_SCREENSHOT_FOLDER, f"{prefix}_{ts}.png")
    ocr_html_path = os.path.join(OCR_HTML_FOLDER, f"{prefix}_{ts}.html")

    html_now = ""
    try:
        html_now = driver.page_source or ""
    except Exception:
        html_now = ""

    try:
        driver.save_screenshot(ocr_ss_path)
        with open(ocr_html_path, "w", encoding="utf-8") as f:
            f.write(html_now)
    except Exception:
        print(" No screenshot available for OCR.")
        return

    with stats_lock:
        stats["ocr_ss"] += 1

    # 1) OCR text -> leaks
    leaks_ocr = extract_from_screenshot_text(
        ocr_ss_path, STRONG_HTML_HINTS | WEAK_HTML_HINTS, INCLUSIVE_CONFIG
    )
    unique_ocr_leaks = deduplicate_leaks(leaks_ocr)

    # 2) Decode QR/barcodes
    codes = decode_image_file(ocr_ss_path) if ocr_ss_path else []
    barcode_leaks = []
    for c in (codes or []):
        data = (c.get("data") or "").strip()
        if not data:
            continue
        if data.startswith("http://") or data.startswith("https://") or looks_secretish(data, min_len=16):
            barcode_leaks.append({
                "type": f"barcode:{c.get('type', 'unknown')}",
                "value": data[:300],
                "source": "barcode"
            })

    merged = deduplicate_leaks(unique_ocr_leaks + barcode_leaks)

    if merged:
        with stats_lock:
            stats["ocr_leaks"] += 1

        # copy to main folders (only if leak)
        try:
            os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
            os.makedirs(HTML_FOLDER, exist_ok=True)
        except Exception:
            pass

        dest_ss = os.path.join(
            SCREENSHOT_FOLDER, os.path.basename(ocr_ss_path))
        dest_html = os.path.join(HTML_FOLDER, os.path.basename(ocr_html_path))

        try:
            if ocr_ss_path != dest_ss:
                shutil.copy(ocr_ss_path, dest_ss)
            if ocr_html_path != dest_html:
                shutil.copy(ocr_html_path, dest_html)
        except Exception:
            dest_ss = ocr_ss_path
            dest_html = ocr_html_path

        _, _, matched_pairs = format_leaks(merged)
        results_queue.put({
            "url": url,
            "status": "Live",
            "matched_url": matched_pairs,
            "matched_html": matched_pairs,
            "screenshot_path": dest_ss if os.path.exists(dest_ss) else (ocr_ss_path or "N/A"),
            "html_path": dest_html if os.path.exists(dest_html) else (ocr_html_path or "N/A"),
            "type": leak_type
        })
        return

    # no leaks -> delete OCR artifacts
    try:
        if ocr_ss_path and os.path.exists(ocr_ss_path):
            os.remove(ocr_ss_path)
        if ocr_html_path and os.path.exists(ocr_html_path):
            os.remove(ocr_html_path)
    except Exception:
        pass


def save_http_requests(page_url, req_list):
    try:
        conn = sqlite3.connect(RESULTS_DB)
        c = conn.cursor()
        for r in req_list:
            c.execute("""
                INSERT INTO http_requests (page_url, req_url, method, status, req_headers, post_data, mime, ts)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                page_url,
                r.get("url"),
                r.get("method"),
                r.get("status"),
                json.dumps(r.get("headers") or {}, ensure_ascii=False),
                (r.get("postData") or "")[:5000],
                r.get("mime"),
                r.get("ts"),
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f" DB save http_requests failed: {e}")


def build_llm_payload(url, matched_url, leaks, visible_text, html_excerpt):
    def _clip(s, n):
        s = (s or "").strip()
        return s[:n]

    # keep only best evidence lines
    best = []
    for l in (leaks or [])[:80]:
        t = (l.get("type") or "")[:60]
        v = (l.get("value") or "")
        s = (l.get("source") or "")[:25]

        v = (v or "").strip()
        if not v:
            continue

        # keep strong-looking values, or strong sources
        if looks_secretish(v, min_len=16) or JWT_RE.match(v) or UUID_RE.search(v) or HEX_RE.search(v) or ("http_" in s) or ("cookie" in s) or ("input" in s):
            best.append({"type": t, "value": v[:120], "source": s})

        if len(best) >= 12:
            break

    # reduce text; we only need enough context for a human-like decision
    vt = _clip(visible_text, 900)          # was 2500
    he = _clip(html_excerpt, 900)          # was 2500

    return {
        "url": _clip(url, 600),
        "matched_url": _clip(matched_url, 240),
        "pipeline_hits": best,
        "visible_text_excerpt": vt,
        "html_excerpt": he,
    }
def llm_check_viewable(url, visible_text, timeout=8):
    if not LLM_ENABLED:
        return True

    system_prompt = """
You are a web-accessibility checker. Decide whether the page
below is meaningfully viewable by a human user.

Return STRICT JSON:
{"viewable": true|false,
"reason": "<short>",
"confidence": <float between 0 and 1>}

Guidance:
- VIEWABLE if meaningful page content is visible without authentication.
- NOT VIEWABLE if access is blocked, incomplete, expired, or requires login or verification.
"""

    user_prompt = f"""
Rendered page excerpt:
{visible_text[:1500]}
"""

    body = {
        "model": LLM_MODEL,
        "prompt": system_prompt + "\n" + user_prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_predict": 80
        }
    }

    try:
        r = requests.post(OLLAMA_URL, json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        txt = (data.get("response") or "").strip()

        parsed = json.loads(txt)
        return bool(parsed.get("viewable", True))

    except Exception:
        return True

def llm_verify(payload, timeout=10):
    if not LLM_ENABLED:
        return {"verdict": "uncertain", "leak_type": "unknown", "confidence": 0.0, "reason": "LLM disabled"}

    system_rules = (
        """You are a web-security analyst. Inspect the HTML or text below
and identify any exposed sensitive data.

Return STRICT JSON:
{
  "leaks": [
    {"type": "<category>",
     "value": "<exact snippet>",
     "confidence": <float between 0 and 1>}
  ],
  "summary": "<short explanation>"
}

A leak is reported only when the content exposes concrete,
usable sensitive data whose disclosure could enable misuse,
unauthorized access, or inference across authentication,
financial, personal, transactional, organizational,
or document-related categories...

Guidance:
- Report a leak only if a concrete, non-placeholder value is
  exposed.
- Ignore examples, templates, documentation snippets,
  masked values, or illustrative strings (e.g., TOKEN_HERE,
  <api_key>, ****1234).
- Do not infer leaks from terminology alone; require an
  observable value.

HTML/TEXT from <URL> (truncated):
\"\"\"<HTML_OR_TEXT_SAMPLE>\"\"\"
"""    )

    user_msg = (
        "Verify exposure. JSON only.\n"
        "Schema:\n"
        "{"
        "\"verdict\":\"leak|no_leak|uncertain\","
        "\"leak_type\":\"auth|financial|pii|travel|document|cookie|other\","
        "\"confidence\":0.0,"
        "\"reason\":\"short\","
        "\"evidence\":[{\"type\":\"...\",\"value\":\"...\",\"source\":\"...\"}]"
        "}\n\n"
        "Payload:\n" + json.dumps(payload, ensure_ascii=False)
    )

    body = {
        "model": LLM_MODEL,
        "prompt": system_rules + "\n\n" + user_msg,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_predict": 220,   # hard cap output length
            "top_p": 0.9,
        }
    }

    try:
        r = requests.post(OLLAMA_URL, json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json()

        txt = data.get("response", "") or ""
        txt = txt.strip()

        parsed = None
        try:
            parsed = json.loads(txt)
        except Exception:
            m = re.search(r"\{.*\}", txt, flags=re.S)
            if m:
                parsed = json.loads(m.group(0))

        if not isinstance(parsed, dict):
            return {"verdict": "uncertain", "leak_type": "unknown", "confidence": 0.0, "reason": "bad_json", "raw": txt[:500]}

        verdict = (parsed.get("verdict") or "").strip().lower()
        if verdict not in ("leak", "no_leak", "uncertain"):
            verdict = "uncertain"

        return {
            "verdict": verdict,
            "leak_type": (parsed.get("leak_type") or "unknown")[:30],
            "confidence": float(parsed.get("confidence") or 0.0),
            "reason": (parsed.get("reason") or "")[:200],
            "evidence": parsed.get("evidence") if isinstance(parsed.get("evidence"), list) else []
        }

    except Exception as e:
        return {"verdict": "uncertain", "leak_type": "unknown", "confidence": 0.0, "reason": f"llm_error:{type(e).__name__}"}


def llm_evidence_to_pairs(verdict, fallback_leaks=None, max_items=12, max_len=160):
    ev = verdict.get("evidence") or []
    out = []

    if isinstance(ev, list):
        for x in ev[:max_items]:
            t = str(x.get("type", "evidence"))[:60]
            v = str(x.get("value", ""))[:max_len]
            s = str(x.get("source", "llm"))[:40]
            if v:
                out.append({"type": t, "value": v, "source": s})

    if not out and fallback_leaks:
        for x in fallback_leaks[:max_items]:
            t = str(x.get("type", "evidence"))[:60]
            v = str(x.get("value", ""))[:max_len]
            s = str(x.get("source", "pipeline"))[:40]
            if v:
                out.append({"type": t, "value": v, "source": s})

    return out


def extract_pdf_text(pdf_path, max_pages=2, max_chars=3000):
    try:
        reader = PdfReader(pdf_path)
        out = []
        for i, page in enumerate(reader.pages[:max_pages]):
            try:
                t = page.extract_text() or ""
                if t.strip():
                    out.append(t.strip())
            except Exception:
                pass
        txt = "\n".join(out).strip()
        return txt[:max_chars]
    except Exception:
        return ""


def try_http_cookie_and_http_layer(url, driver):

    import os
    import time
    import re
    from urllib.parse import urlparse

    try:
        if driver is None:
            return (False, None)

        def _host(u: str) -> str:
            try:
                return (urlparse(u).hostname or "").lower()
            except Exception:
                return ""

        page_host = _host(url)
        if not page_host:
            return (False, None)

        def is_first_party(req_host: str) -> bool:
            if not req_host:
                return False
            req_host = req_host.lower()
            return req_host == page_host or req_host.endswith("." + page_host)

        THIRD_PARTY_BLOCK = {
            "google-analytics.com", "www.google-analytics.com",
            "googletagmanager.com", "www.googletagmanager.com",
            "doubleclick.net", "stats.g.doubleclick.net",
            "connect.facebook.net",
            "cdn.segment.com", "api.segment.io",
            "api.mixpanel.com",
            "static.hotjar.com",
            "browser.sentry-cdn.com",
            "logs.datadoghq.com",
            "clarity.ms",
            "bam.nr-data.net",
            "api.amplitude.com",
            "cloudflareinsights.com",
        }

        NOISY_PARAM_KEYS = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "gclid", "fbclid", "msclkid", "yclid", "igshid",
            "_ga", "_gid", "_fbp", "_gac", "_gcl_aw", "_gcl_dc",
            "ref", "referrer", "ref_url", "source", "campaign",
            "nonce", "state", "code_challenge", "code_verifier",
            "trace", "trace_id", "span_id", "request_id", "rid",
        }

        COOKIE_NAME_ALLOW = re.compile(
            r"(?i)\b("
            r"access[_-]?token|refresh[_-]?token|id[_-]?token|auth|authorization|bearer|jwt|"
            r"session|sessionid|sid|sso|oauth|api[_-]?key|secret|csrftoken|xsrf"
            r")\b"
        )
        COOKIE_NAME_DENY = re.compile(
            r"(?i)\b(_ga|_gid|_gat|_fbp|_fbc|_hj|ajs_|mp_|amplitude|optimizely|"
            r"intercom|sentry|datadog|newrelic|clarity|segment)\b"
        )

        JWT_RE = re.compile(
            r"^[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-]+=*$")
        HEX32_RE = re.compile(r"^[A-Fa-f0-9]{32,}$")
        B64URL_RE = re.compile(r"^[A-Za-z0-9_\-]{32,}$")
        UUID_RE = re.compile(
            r"^[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}$")

        def looks_strong_secret(v: str) -> bool:
            if not v:
                return False
            v = v.strip().strip('"').strip("'")
            if len(v) < 20:
                return False
            if UUID_RE.match(v):
                return False
            if JWT_RE.match(v):
                return True
            if HEX32_RE.match(v):
                return True
            if B64URL_RE.match(v) and len(v) >= 40:
                return True
            try:
                if looks_secretish(v, min_len=28):
                    return True
            except Exception:
                pass
            return False

        # Enable CDP
        try:
            driver.execute_cdp_cmd("Network.enable", {
                "maxTotalBufferSize": 10_000_000,
                "maxResourceBufferSize": 5_000_000
            })
            driver.execute_cdp_cmd("Page.enable", {})
        except Exception:
            pass

        # Ensure page loaded
        try:
            if (driver.current_url or "") != url:
                driver.get(url)
            WebDriverWait(driver, 12).until(
                lambda d: d.execute_script(
                    "return document.readyState") == "complete"
            )
            time.sleep(0.35)
        except Exception:
            return (False, None)

        net_events = capture_network_traffic(driver)
        req_index = normalize_request_index(net_events)

        # ---- Cookie scanning (strict) ----
        resp_cookies = collect_response_cookies(req_index)
        cookie_items = collect_cookie_items(url, req_index, resp_cookies)

        cookie_findings = []
        for it in (cookie_items or []):
            name = (it.get("name") or "").strip()
            value = (it.get("value") or "").strip()
            domain = (it.get("domain") or "").lstrip(".").lower()

            if not name or not value:
                continue
            if COOKIE_NAME_DENY.search(name):
                continue
            if not COOKIE_NAME_ALLOW.search(name):
                continue
            if domain and not (domain == page_host or domain.endswith("." + page_host)):
                continue
            if not looks_strong_secret(value):
                continue

            cookie_findings.append({
                "type": f"cookie:{name}",
                "value": value[:300],
                "source": "http_cookie"
            })

        cookie_findings = deduplicate_leaks(cookie_findings)
        if cookie_findings:
            _, _, pairs = format_leaks(cookie_findings)
            return (True, {
                "layer": "http_cookie",
                "pairs": pairs,
                "leaks": cookie_findings,
            })

        # ---- HTTP request/response scanning (first-party only) ----
        filtered_req_index = []
        for r in (req_index or []):
            req_url = (r.get("url") or "").strip()
            if not req_url:
                continue
            h = _host(req_url)
            if not h:
                continue
            if h in THIRD_PARTY_BLOCK:
                continue
            if not is_first_party(h):
                continue
            filtered_req_index.append(r)

        if not filtered_req_index:
            return (False, None)

        leaks_http = extract_secrets_from_requests(
            filtered_req_index, SUSPICIOUS_URL_PARAMS_SET, INCLUSIVE_CONFIG
        )

        strict_http = []
        for it in (leaks_http or []):
            t = (it.get("type") or "").strip()
            v = (it.get("value") or "").strip()
            if not t or not v:
                continue

            low_t = t.lower()

            # reject noisy param keys if your extractor puts them in type
            if "url_param:" in low_t and ":" in t:
                key = t.split(":", 1)[1].strip().lower()
                if key in NOISY_PARAM_KEYS and len(v) < 60:
                    continue

            # require strong values for all HTTP findings
            if not looks_strong_secret(v):
                continue

            strict_http.append({
                "type": t,
                "value": v[:300],
                "source": it.get("source") or "http_layer"
            })

        strict_http = deduplicate_leaks(strict_http)
        if strict_http:
            _, _, pairs = format_leaks(strict_http)
            return (True, {
                "layer": "http_layer",
                "pairs": pairs,
                "leaks": strict_http,
            })

        return (False, None)

    except Exception:
        return (False, None)


def should_run_http_layer(url, matched_url, all_leaks, tier):
    # Run HTTP layer ONLY if we found nothing in HTML inputs/text/meta/js
    if all_leaks:
        return False

    u = (url or "").lower()
    hint = any(x in u for x in ("oauth", "callback",
               "redirect", "sso", "signin", "auth"))
    has_url_signal = bool(matched_url)
    loose = (tier == "loose")

    # Only when URL looks auth/redirect-ish or it was gated/loose
    return hint or has_url_signal or loose


def scanned_logger():
    with open("scanned_urls.log", "a") as f:
        while True:
            url = scanned_log_q.get()
            if url is None:
                break
            f.write(url + "\n")
            scanned_log_q.task_done()


threading.Thread(target=scanned_logger, daemon=True).start()


def fast_visible_text_excerpt(soup, max_chars=2000):

    if not soup:
        return ""

    out = []
    total = 0

    for el in soup.stripped_strings:
        out.append(el)
        total += len(el)
        if total >= max_chars:
            break

    return " ".join(out)[:max_chars]


def save_leak_artifacts_from_driver(driver, html_str, prefix,
                                    screenshot_dir=None, html_dir=None):
    if screenshot_dir is None:
        screenshot_dir = SCREENSHOT_FOLDER
    if html_dir is None:
        html_dir = HTML_FOLDER

    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(html_dir, exist_ok=True)

    ts = int(time.time() * 1000)
    ss_path = os.path.join(screenshot_dir, f"{prefix}_{ts}.png")
    html_path = os.path.join(html_dir, f"{prefix}_{ts}.html")

    try:
        try:
            h = driver.execute_script(
                "return Math.min(document.body.scrollHeight, 2500)")
            driver.set_window_size(1280, int(h) if h else 800)
        except Exception:
            pass

        driver.save_screenshot(ss_path)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_str or "")

        return ss_path, html_path
    except Exception:
        return None, None


def cleanup_artifacts_if_useless(ss_path=None, html_path=None):
    for p in (ss_path, html_path):
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def download_pdf_to_temp(url: str, timeout: int = 25) -> str:
    r = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0"},
        stream=True,
        allow_redirects=True
    )
    r.raise_for_status()

    fd, path = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)
    return path


def worker():
    driver = None

    while True:
        entry = url_queue.get()
        try:
            if entry is None:
                break

            url = entry["url"]
            matched_url = entry.get("matched_url") or ""
            tier = entry.get("tier") or "strict"
            needs_url_gate = bool(entry.get("needs_url_gate", False))

            # ---------------- stats / progress ----------------
            with stats_lock:
                stats["processed"] += 1
                done = stats["processed"]
                total = TOTAL_TO_PROCESS

            if total and (done % PROGRESS_EVERY == 0):
                pct = (done * 100.0) / total
                print(f"Progress {done}/{total} ({pct:.2f}%) | {url}")

            try:
                scanned_log_q.put_nowait(url)
            except Exception:
                pass

            # ---------------- URL gate ----------------
            domain_type = check_special_domain(url)
            should_gate = bool(domain_type) or needs_url_gate

            if should_gate:
                keep = llm_gate_url_keep(
                    url, f"{domain_type or 'heuristic'}:url_gate")
                if not keep:
                    continue

            # ---------------- live check ----------------
            try:
                live, _ = is_url_live(url)
            except Exception:
                continue

            if not live:
                with stats_lock:
                    stats["dead"] += 1
                continue

            with stats_lock:
                stats["live"] += 1

            # ---------------- PDF path ----------------
            try:
                is_pdf_real = head_is_pdf(url)
            except Exception:
                is_pdf_real = False

            if is_pdf_real:
                local_pdf = None
                try:
                    local_pdf = download_pdf_to_temp(url)
                    pdf_text = extract_pdf_text(local_pdf)
                except Exception:
                    pdf_text = ""
                finally:
                    if local_pdf:
                        try:
                            os.remove(local_pdf)
                        except Exception:
                            pass

                leaks_pdf = extract_from_visible_text(
                    pdf_text, STRONG_HTML_HINTS | WEAK_HTML_HINTS, INCLUSIVE_CONFIG
                )

                leaks_pdf = deduplicate_leaks(leaks_pdf)

                strong_hits = []
                weak_hits = []

                for l in leaks_pdf:
                    t = norm_key(l["type"])
                    v = l["value"]
                    if t in STRONG_HTML_HINTS and is_valid_leak_value(v, INCLUSIVE_CONFIG):
                        strong_hits.append(l)
                    elif t in WEAK_HTML_HINTS:
                        weak_hits.append(l)
                if strong_hits:
                    # render PDF in Selenium so artifacts work
                    try:
                        if driver is None:
                            driver = make_driver()
                            driver.set_page_load_timeout(15)
                        driver.get(url)
                        WebDriverWait(driver, 12).until(
                            lambda d: d.execute_script(
                                "return document.readyState") == "complete"
                        )
                        pdf_html = driver.page_source or ""
                    except Exception:
                        pdf_html = ""

                    ss, htmlp = save_leak_artifacts_from_driver(
                        driver, pdf_html, "pdf")
                    _, _, pairs = format_leaks(strong_hits)
                    results_queue.put({
                        "url": url,
                        "status": "Live",
                        "matched_url": matched_url,
                        "matched_html": pairs,
                        "screenshot_path": ss or "N/A",
                        "html_path": htmlp or "N/A",
                        "type": "pdf_strong_pipeline",
                    })
                    continue
                if weak_hits:
                    verdict = llm_verify(build_llm_payload(
                        url, matched_url, weak_hits, "", pdf_text[:3000]
                    ))

                    if verdict.get("verdict") == "leak":
                        # render PDF in Selenium so artifacts work
                        try:
                            if driver is None:
                                driver = make_driver()
                                driver.set_page_load_timeout(15)
                            driver.get(url)
                            WebDriverWait(driver, 12).until(
                                lambda d: d.execute_script(
                                    "return document.readyState") == "complete"
                            )
                            pdf_html = driver.page_source or ""
                        except Exception:
                            pdf_html = ""

                        ss, htmlp = save_leak_artifacts_from_driver(
                            driver, pdf_html, "pdf_llm")
                        ev = llm_evidence_to_pairs(verdict, weak_hits)
                        _, _, pairs = format_leaks(ev)
                        results_queue.put({
                            "url": url,
                            "status": "Live",
                            "matched_url": matched_url,
                            "matched_html": pairs,
                            "screenshot_path": ss or "N/A",
                            "html_path": htmlp or "N/A",
                            "type": "pdf_llm_confirmed",
                            "category": verdict.get("leak_type", "unknown")


                        })

                        # ---------------- Selenium render ----------------
            try:
                if driver is None:
                    driver = make_driver()
                    driver.set_page_load_timeout(15)
                driver.get(url)
                WebDriverWait(driver, 12).until(
                    lambda d: d.execute_script(
                        "return document.readyState") == "complete"
                )
                html = driver.page_source or ""
            except Exception:
                continue

            soup = BeautifulSoup(html, "lxml")

            visible_text = fast_visible_text_excerpt(
                soup, max_chars=INCLUSIVE_CONFIG["max_translate_chars"]
            )
            if not llm_check_viewable(url, visible_text):
                continue

            leaks = []
            leaks += extract_from_visible_text(
                visible_text, STRONG_HTML_HINTS | WEAK_HTML_HINTS, INCLUSIVE_CONFIG)
            leaks += extract_from_inputs(
                soup, STRONG_HTML_HINTS | WEAK_HTML_HINTS, INCLUSIVE_CONFIG)
            leaks += extract_from_meta_and_data_attrs(
                soup, STRONG_HTML_HINTS | WEAK_HTML_HINTS, INCLUSIVE_CONFIG)
            leaks += extract_from_js_variables(
                soup, STRONG_HTML_HINTS | WEAK_HTML_HINTS, INCLUSIVE_CONFIG)
            leaks += extract_dynamic_inputs(
                driver, STRONG_HTML_HINTS | WEAK_HTML_HINTS, INCLUSIVE_CONFIG)

            leaks = deduplicate_leaks(leaks)

            strong_hits = []
            weak_hits = []

            for l in leaks:
                t = norm_key(l["type"])
                v = l["value"]
                if t in STRONG_HTML_HINTS and is_valid_leak_value(v, INCLUSIVE_CONFIG):
                    strong_hits.append(l)
                elif t in WEAK_HTML_HINTS:
                    weak_hits.append(l)

                # STRONG HTML found
            if strong_hits:

                # If URL came from LLM gate → LLM MUST decide
                if needs_url_gate:
                    verdict = llm_verify(build_llm_payload(
                        url, matched_url, strong_hits, visible_text, html[:3000]
                    ))

                    if verdict.get("verdict") == "leak":
                        ss, htmlp = save_leak_artifacts_from_driver(
                            driver, html, "strong_llm")
                        ev = llm_evidence_to_pairs(verdict, strong_hits)
                        _, _, pairs = format_leaks(ev)

                        results_queue.put({
                            "url": url,
                            "status": "Live",
                            "matched_url": matched_url,
                            "matched_html": pairs,
                            "screenshot_path": ss or "N/A",
                            "html_path": htmlp or "N/A",
                            "type": "strong_llm_confirmed",
                            "category": verdict.get("leak_type", "unknown")
                        })

                    # Regardless of verdict → STOP here
                    continue

                # Otherwise → pure pipeline strong hit
                ss, htmlp = save_leak_artifacts_from_driver(
                    driver, html, "strong_pipeline")
                _, _, pairs = format_leaks(strong_hits)

                results_queue.put({
                    "url": url,
                    "status": "Live",
                    "matched_url": matched_url,
                    "matched_html": pairs,
                    "screenshot_path": ss or "N/A",
                    "html_path": htmlp or "N/A",
                    "type": "strong_pipeline",
                })
                continue

       # ---------------- HTTP / COOKIE → LLM ONLY ----------------
            if should_run_http_layer(url, matched_url, leaks, tier):
                found, http_ev = try_http_cookie_and_http_layer(url, driver)

                # Only exit early if we actually confirmed a leak via HTTP layer
                if found:
                    verdict = llm_verify(build_llm_payload(
                        url, http_ev["pairs"], http_ev["leaks"], "", html[:3000]
                    ))
                    if verdict.get("verdict") == "leak":
                        ss, htmlp = save_leak_artifacts_from_driver(
                            driver, html, "http_llm")
                        ev = llm_evidence_to_pairs(verdict, http_ev["leaks"])
                        _, _, pairs = format_leaks(ev)
                        results_queue.put({
                            "url": url,
                            "status": "Live",
                            "matched_url": http_ev["pairs"],
                            "matched_html": pairs,
                            "screenshot_path": ss or "N/A",
                            "html_path": htmlp or "N/A",
                            "type": "http_llm_confirmed",
                            "category": verdict.get("leak_type", "unknown")

                        })
                        continue  # confirmed leak -> stop here

                # If nothing confirmed, fall through to OCR / weak-LLM logic below

            # ---------------- OCR fallback ----------------
            if not leaks:
                process_ocr_leaks(url, driver, prefix="ocr")
                continue

            # ---------------- WEAK HTML → LLM ----------------
            if weak_hits:
                verdict = llm_verify(build_llm_payload(
                    url, matched_url, weak_hits, visible_text, html[:3000]
                ))

                if verdict.get("verdict") == "leak":
                    ss, htmlp = save_leak_artifacts_from_driver(
                        driver, html, "weak_llm")
                    ev = llm_evidence_to_pairs(verdict, weak_hits)
                    _, _, pairs = format_leaks(ev)
                    results_queue.put({
                        "url": url,
                        "status": "Live",
                        "matched_url": matched_url,
                        "matched_html": pairs,
                        "screenshot_path": ss or "N/A",
                        "html_path": htmlp or "N/A",
                        "type": "weak_llm_confirmed",
                        "category": verdict.get("leak_type", "unknown")
                    })
            # else: no weak evidence -> do nothing (and loop continues)

        finally:
            url_queue.task_done()

    if driver:
        try:
            driver.quit()
        except Exception:
            pass


def progress_reporter():

    start = time.time()
    last_print = 0

    while not STOP_PROGRESS:
        time.sleep(0.1)

        with stats_lock:
            done = int(stats.get("processed", 0))
            live = int(stats.get("live", 0))
            dead = int(stats.get("dead", 0))

        total = int(TOTAL_TO_PROCESS) if TOTAL_TO_PROCESS else 0
        if total <= 0:
            continue

        now = time.time()
        elapsed = max(now - start, 1e-6)
        rate = done / elapsed
        remaining = max(total - done, 0)
        eta = remaining / rate if rate > 0 else 0

        # update ~4 times/second max
        if now - last_print < 0.25:
            continue
        last_print = now

        pct = (done / total) * 100.0
        bar_len = 28
        filled = int((done / total) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        msg = (
            f"\r[{bar}] {done}/{total} ({pct:5.1f}%) | "
            f"live={live} dead={dead} | "
            f"{rate:5.2f} url/s | ETA {eta:6.1f}s   "
        )
        sys.stdout.write(msg)
        sys.stdout.flush()

    # finish line
    sys.stdout.write("\n")
    sys.stdout.flush()


def save_result_to_db_cursor(c, res):
    c.execute("""
        INSERT INTO leaks
        (url, status, matched_url, matched_html, screenshot_path, html_path, type, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        res.get("url", ""),
        res.get("status", ""),
        res.get("matched_url", ""),
        res.get("matched_html", ""),
        res.get("screenshot_path", "N/A"),
        res.get("html_path", "N/A"),
        res.get("type", ""),
        res.get("category", "unknown")
    ))


def db_writer():
    conn = sqlite3.connect(RESULTS_DB, check_same_thread=False)
    c = conn.cursor()

    # speed pragmas (same results, faster writes)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA temp_store=MEMORY;")

    buffer = []
    BATCH_SIZE = 500

    while True:
        try:
            res = results_queue.get(timeout=2)
            if res is None:
                break

            buffer.append(res)

            if len(buffer) >= BATCH_SIZE:
                for r in buffer:
                    save_result_to_db_cursor(c, r)
                conn.commit()
                buffer.clear()

        except Empty:
            if buffer:
                for r in buffer:
                    save_result_to_db_cursor(c, r)
                conn.commit()
                buffer.clear()

    if buffer:
        for r in buffer:
            save_result_to_db_cursor(c, r)
        conn.commit()

    conn.close()


def format_leaks(leak_list, max_len=200):
    """You are a cybersecurity analyst. Normalize each detected
leak into a consistent type and broader category.
Return STRICT JSON:
{
"classified": [
{"type": "<normalized_type>",
"value": "<exact value>",
"category": "<broader_group>",
"confidence": <float between 0 and 1>}
]
}
Guidance:
- Use only normalized types already present in the input.
- Assign each type to a stable broader category
(authentication, financial, personal, document, booking, runtime
or ...).
- Do not infer new leaks or modify values.
- If a leak is ambiguous, assign lower confidence.
Raw leaks:
<JSON_SNIPPET>"""
    def _clean(v):
        v = (v or "").replace("\n", " ").replace("\r", " ").strip()
        return (v[:max_len] + "…") if len(v) > max_len else v
    types = "; ".join(_clean(l["type"]) for l in leak_list)
    values = "; ".join(_clean(l["value"]) for l in leak_list)
    pairs = "; ".join(
        f"{_clean(l['type'])}:{_clean(l['value'])}" for l in leak_list)
    return types, values, pairs


def _b64url_try(s):
    try:
        import base64
        pad = '=' * (-len(s) % 4)
        return base64.urlsafe_b64decode((s+pad).encode()).decode('utf-8', 'ignore')
    except Exception:
        return ""


def _jwt_payload_try(tok):
    parts = tok.split('.')
    if len(parts) != 3:
        return ""
    return _b64url_try(parts[1])


def parse_set_cookie(h):
    if not h:
        return None
    m = SET_COOKIE_RE.search(h)
    if not m:
        return None
    name, val = m.group(1), m.group(2)
    low = h.lower()
    has_secure = ('; secure' in low) or low.strip().endswith('secure')
    has_httponly = ('; httponly' in low) or low.strip().endswith('httponly')
    samesite = ""
    for part in h.split(';'):
        p = part.strip()
        if p.lower().startswith('samesite='):
            samesite = p.split('=', 1)[1].strip()
            break
    issues = []
    if not has_secure:
        issues.append('missing_secure')
    if not has_httponly:
        issues.append('missing_httponly')
    if samesite.lower() == 'none' and not has_secure:
        issues.append('samesite_none_without_secure')
    return {"name": name, "value": val, "samesite": samesite, "issues": issues}


def etld1(host):
    parts = (host or "").lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def parse_cookie_header(h):
    names = set()
    if not h:
        return names
    for pair in h.split(";"):
        k = pair.split("=", 1)[0].strip()
        if k:
            names.add(k)
    return names


def assess_cookie_policy(page_url, cookies):
    leaks = []
    if not cookies:
        return leaks
    scheme = urllib.parse.urlsplit(page_url).scheme.lower()
    for ck in cookies:
        name = ck.get("name") or "cookie"
        for isu in ck.get("issues", []):
            leaks.append({"type": f"cookie_policy:{name}:{isu}",
                          "value": ck.get("samesite") or "-", "source": "set-cookie"})
        if scheme == "http" and "missing_secure" in ck.get("issues", []):
            leaks.append({"type": f"cookie_insecure_transport:{name}",
                          "value": "-", "source": "http"})
        if "missing_httponly" in ck.get("issues", []):
            leaks.append({"type": f"cookie_js_readable:{name}",
                          "value": "-", "source": "document.cookie"})
    # de-dupe
    uniq, seen = [], set()
    for l in leaks:
        k = (l["type"], l["source"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(l)
    return uniq


def find_cookie_flow_leaks(page_url, req_index):
    leaks = []
    page_host = urllib.parse.urlparse(page_url).netloc.split(":")[0].lower()
    page_base = etld1(page_host)
    for r in req_index:
        u = r.get("url") or ""
        if not u:
            continue
        parsed = urllib.parse.urlparse(u)
        scheme = (parsed.scheme or "").lower()
        host = (parsed.netloc or "").split(":")[0].lower()
        base = etld1(host)
        hdrs = r.get("headers") or {}
        ch = hdrs.get("Cookie") or hdrs.get("cookie") or ""
        if not ch:
            continue
        names = parse_cookie_header(ch)
        if not names:
            continue
        if scheme == "http":
            for name in names:
                leaks.append({"type": f"cookie_over_http:{name}",
                              "value": "-", "source": u})
        if base and base != page_base:
            for name in names:
                leaks.append({"type": f"cookie_cross_site:{name}",
                              "value": base, "source": u})
    # de-dupe
    uniq, seen = [], set()
    for l in leaks:
        k = (l["type"], l["source"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(l)
    return uniq


def collect_cookie_items(page_url, req_index, resp_cookies):
    items = []
    for ck in (resp_cookies or []):
        items.append({"name": ck.get("name", ""), "value": ck.get(
            "value", ""), "src": "set-cookie"})
    for r in (req_index or []):
        hdrs = r.get("headers") or {}
        ch = hdrs.get("Cookie") or hdrs.get("cookie")
        if not ch:
            continue
        for pair in ch.split(';'):
            k, v = (pair.split('=', 1)+[""])[:2]
            items.append(
                {"name": k.strip(), "value": v.strip(), "src": "cookie"})
    seen, out = set(), []
    for it in items:
        key = (it["name"], it["value"], it["src"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out



LEAK_PATTERNS = {
    # high precision
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),

    "credit_card": re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"
        r"5[1-5][0-9]{14}|"
        r"3[47][0-9]{13}|"
        r"6(?:011|5[0-9]{2})[0-9]{12})\b"
    ),

    "phone": re.compile(
        r"\b(?:\+?\d{1,3}[-.\s]?)?"
        r"(?:\(?\d{2,4}\)?[-.\s]?)?"
        r"\d{3}[-.\s]?\d{4}\b"
    ),

    # IDs are WEAK unless context upgrades them
    "id_like": re.compile(r"\b\d{10,}\b"),

    # explicit secret assignments only
    "api_secret": re.compile(
        r"\b(?:api[_-]?key|api[_-]?secret|access[_-]?token|"
        r"refresh[_-]?token|auth[_-]?token|bearer|"
        r"password|passwd|pwd)\b"
        r"\s*[:=]\s*"
        r"[A-Za-z0-9._\-]{16,}",
        re.I
    ),

    # tokens
    "jwt": JWT_RE,

    # base64 only if long enough (avoid icons, images, etc.)
    "base64": re.compile(
        r"\b(?:[A-Za-z0-9+/]{40,}={0,2})\b"
    ),

    # hex secrets
    "hex_secret": re.compile(r"\b[a-f0-9]{32,}\b", re.I),
}


def detect_sensitive_in_cookies(cookie_items):
    findings = []

    def scan_text(txt, cname, source, tag):
        if not txt or len(txt) < 5:
            return
        for pname, preg in LEAK_PATTERNS.items():
            try:
                if preg.search(txt):
                    findings.append({
                        "type": f"cookie_sensitive:{pname}:{cname}",
                        "value": txt[:80],
                        "source": f"{source}:{tag}"
                    })
            except Exception:
                continue
    for it in (cookie_items or []):
        cname = it["name"]
        val = it["value"]
        src = it["src"]
        scan_text(val, cname, src, "raw")
        try:
            dec = urllib.parse.unquote(val)
            if dec != val:
                scan_text(dec, cname, src, "urldec")
        except Exception:
            pass
        b64txt = _b64url_try(val)
        if b64txt:
            scan_text(b64txt, cname, src, "b64url")
        pay = _jwt_payload_try(val)
        if pay:
            scan_text(pay, cname, src, "jwtpayload")
    # de-dupe
    seen, uniq = set(), []
    for f in findings:
        k = (f["type"], f["source"], f["value"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    return uniq


def is_strong_hit(leaks):

    if not leaks:
        return False

    STRONG_SOURCES = {
        "http_get", "http_post", "http_cookie", "set-cookie", "cookie",
        "input_dynamic", "input"
    }

    for l in leaks:
        t = (l.get("type") or "").lower()
        src = (l.get("source") or "").lower()
        v = (l.get("value") or "")

        if not isinstance(v, str):
            continue
        v = v.strip()

        # 1) HTTP/Cookie/Input sources are strong ONLY if value is secretish (avoid policy-only leaks)
        if src in STRONG_SOURCES:
            if looks_secretish(v, min_len=16) or JWT_RE.match(v) or UUID_RE.search(v) or HEX_RE.search(v):
                return True
            # if it's not secretish, do NOT call it strong
            continue

        # 2) strong type hint must have a secretish value
        if any(h in t for h in STRONG_TYPE_HINTS):
            if looks_secretish(v, min_len=16) or JWT_RE.match(v) or UUID_RE.search(v) or HEX_RE.search(v):
                return True

        # 3) purely value-driven: very long + secretish
        if len(v) >= 40 and looks_secretish(v, min_len=20):
            return True

    return False


def init_stats_defaults():
    with stats_lock:
        for k in [
            "processed", "live", "dead", "regular_ss", "ocr_ss", "ocr_leaks",
            "photo_live", "e_signature_live", "paste_live", "http_leaks",
            "total_input_urls", "passed_filtering"
        ]:
            stats[k] = stats.get(k, 0)


TEST_MODE = False
TEST_LIMIT = 500



def main():
    global url_queue
    init_results_db()
    init_stats_defaults()

    db_thread = threading.Thread(target=db_writer, daemon=True)
    db_thread.start()

    start_time = time.time()

    # ============================
    db_path = ".db"
    print(f"Loading from: {db_path}")

    test_urls = load_urls_from_db(db_path, "urls", "urls")
    # random.shuffle(test_urls)
    test_urls = test_urls[15_000_000:]

    # ============================

    if not test_urls:
        print("No URLs loaded. Aborting.")
        return

    total_loaded = len(test_urls)
    print(f" Loaded {total_loaded} URLs from DB (before filtering)\n")

    print(" First URLs being scanned:")
    for i, u in enumerate(test_urls[:100], 1):
        # print(f"{i:03d}. {u}")
        print("--STARTING IN 3, 2, 1!--")

    with stats_lock:
        stats["total_input_urls"] = total_loaded

    filtered_urls = filter_useful_urls(test_urls)
    total_filtered = len(filtered_urls)
    print(f"\n URLs after 1st filter = {total_filtered}")

    global TOTAL_TO_PROCESS
    TOTAL_TO_PROCESS = total_filtered

    global STOP_PROGRESS
    STOP_PROGRESS = False
    t = threading.Thread(target=progress_reporter, daemon=True)
    t.start()

    if not filtered_urls:
        print(" No URLs passed the filter. Exiting early.")
        return

    with stats_lock:
        stats["passed_filtering"] = total_filtered

    for url in filtered_urls:
        url_queue.put(url)
    for _ in range(NUM_THREADS):
        url_queue.put(None)

    # print(f"\n Starting thread pool with {NUM_THREADS} threads...")
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        for _ in range(NUM_THREADS):
            executor.submit(worker)

    STOP_PROGRESS = True

    results_queue.put(None)   # tell DB writer to stop
    db_thread.join()
    time.sleep(0.3)

    duration = time.time() - start_time

    print("\n Final Stats:")
    print(f"   URLs loaded initially: {total_loaded}")
    print(f"   URLs after filtering: {total_filtered}")
    print(f"   Total URLs processed: {stats.get('processed', 0)}")
    print(f"   Live URLs: {stats.get('live', 0)}")
    print(f"   Dead URLs: {stats.get('dead', 0)}")
    print(f"   Regular screenshots taken: {stats.get('regular_ss', 0)}")
    print(f"   OCR screenshots taken: {stats.get('ocr_ss', 0)}")
    print(f"   OCR-based leaks found: {stats.get('ocr_leaks', 0)}")
    print(f"   Photo domain URLs matched: {stats.get('photo_live', 0)}")
    print(f"   E-sign domain URLs matched: {stats.get('e_signature_live', 0)}")
    print(f"   Paste domain URLs matched: {stats.get('paste_live', 0)}")
    print(f"   HTTP-layer leaks found: {stats.get('http_leaks', 0)}")
    print(f"   Time taken: {round(duration, 2)} seconds")
    print("-----> All results written to DB.")


if __name__ == "__main__":
    main()
