

import requests
import pandas as pd
import time
import os


# Domains to scan for URLs

DOMAINS = [

    "paypal.com", "stripe.com", "squareup.com", "checkout.stripe.com",
    "venmo.com", "pay.google.com", "appleid.apple.com", "secure.adyen.com",
    "braintreepayments.com", "payoneer.com", "payu.com",
    "skrill.com", "revolut.com", "cash.app", "zellepay.com",


    "facebook.com", "messenger.com", "instagram.com", "whatsapp.com",
    "linkedin.com", "twitter.com", "x.com", "t.me", "discord.com",
    "snapchat.com", "pinterest.com", "reddit.com", "tiktok.com", "wechat.com",


    "drive.google.com", "docs.google.com", "onedrive.live.com",
    "dropbox.com", "box.com", "mega.nz", "nextcloud.com", "owncloud.com",
    "icloud.com", "sharepoint.com", "wetransfer.com", "transfer.sh",
    "send.firefox.com",


    "github.com", "gitlab.com", "bitbucket.org", "npmjs.com", "pypi.org",
    "hub.docker.com", "maven.org", "api.github.com", "git.io",
    "cdn.jsdelivr.net", "cdnjs.cloudflare.com",


    "accounts.google.com", "appleid.apple.com",
    "auth0.com", "okta.com", "onelogin.com", "sso.squarespace.com",
    "signin.aws.amazon.com", "keycloak.org",


    "booking.com", "expedia.com", "airbnb.com", "tripadvisor.com",
    "skyscanner.com", "hotels.com", "trainline.com", "ticketmaster.com",
    "eventbrite.com", "stubhub.com", "checkmytrip.com", "ryanair.com",
    "boardingpass.ryanair.com", "s3.com"


    "amazon.com", "alibaba.com", "aliexpress.com", "ebay.com", "shopify.com",
    "bigcommerce.com", "wix.com", "woocommerce.com", "etsy.com",
    "bestbuy.com", "walmart.com", "flipkart.com",


    "bit.ly", "t.co", "goo.gl", "tinyurl.com", "is.gd", "rebrandly.com",
    "buff.ly", "ow.ly", "shorte.st", "adf.ly",


    "paste2.org", "jsbin.com", "play.golang.org", "paste.debian.net", "pastehtml.com", "pastebin.com", "snipplr.com", "snipt.net",
    "heypasteit.com", "pastebin.fr", "slexy.org", "hastebin.com", "dumpz.org", "codepad.org", "jsitor.com", "dpaste.org", "textsnip.com",
    "bitpaste.app", "justpaste.it", "jsfiddle.net", "dpaste.com", "codepen.io", "dartpad.dartlang.org", "ide.codingblocks.com", "dotnetfiddle.net", "ideone.com",
    "paste.fedoraproject.org", "paste.frubar.net", "repl.it", "paste.opensuse.org", "rextester.com", "paste.org.ru", "paste.ubuntu.com", "paste.pound-python.org", "paste.lisp.org",
    "paste.xinu.at", "try.ceylon-lang.org", "paste.org", "phpfiddle.org", "ide.geeksforgeeks.org"


    "esignlive.com", "sandbox.esignlive.com", "docusign.net", "docusign.com", "adobesign.com",
    "hellosign.com", "onespan.com", "signnow.com", "pandadoc.com", "dropboxsign.com",
    "rightsignature.com", "zohosign.com", "signrequest.com", "eversign.com", "assuresign.com",
    "keepsolid.com", "formstack.com", "signeasy.com", "sertifi.com", "signable.com",
    "legalesign.com", "esignly.com", "sandbox.esignlive.com", "esignlive", "quick-demo",
    "docusign.net", "docusign.com", "adobesign.com", "hellosign.com", "onespan.com",
    "signnow.com", "pandadoc.com", "dropboxsign.com", "rightsignature.com",
    "zohosign.com", "signrequest.com", "eversign.com", "assuresign.com"




]


API_KEY = "..."
EXCEL_FILE = "....xlsx"


# VirusTotal v2 endpoint
VT_DOMAIN_REPORT = "https://www.virustotal.com/vtapi/v2/domain/report"


def get_urls_for_domain(domain):
    params = {"apikey": API_KEY, "domain": domain}
    response = requests.get(VT_DOMAIN_REPORT, params=params)

    if response.status_code == 200:
        data = response.json()
        urls = []

        # Extract from detected_urls
        for entry in data.get("detected_urls", []):
            url = entry.get("url")
            if url:
                urls.append(url)

        # Extract from undetected_urls (safe but still interesting)
        for entry in data.get("undetected_urls", []):
            url = entry[0] if isinstance(entry, list) and entry else None
            if url:
                urls.append(url)

        return urls

    elif response.status_code == 204:
        print(f" No content for {domain} (204). Skipping...")
    elif response.status_code == 403:
        print(f" Forbidden for {domain} (check your quota or key).")
    else:
        print(f" Error {response.status_code} for {domain}: {response.text}")

    return []


def main():
    all_urls = []

    for domain in DOMAINS:
        print(f" Scanning: {domain}")
        urls = get_urls_for_domain(domain)
        all_urls.extend(urls)
        time.sleep(16)

    print(f"\n Fetched {len(all_urls)} raw URLs.")

    # Load existing results
    if os.path.exists(EXCEL_FILE):
        existing_df = pd.read_excel(EXCEL_FILE)
    else:
        existing_df = pd.DataFrame(columns=["URL"])

    new_df = pd.DataFrame(all_urls, columns=["URL"])
    final_df = pd.concat([existing_df, new_df]
                         ).drop_duplicates().reset_index(drop=True)

    final_df.to_excel(EXCEL_FILE, index=False)
    print(f" Total saved URLs: {len(final_df)}")


if __name__ == "__main__":
    main()

