# test_b2.py
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)   # <-- reads your .env into os.environ

import os
from b2sdk.v2 import B2Api, InMemoryAccountInfo

# 1) Load from .env
key_id       = os.getenv("B2_KEY_ID")
application_key = os.getenv("B2_APP_KEY")
bucket_name  = os.getenv("B2_BUCKET_NAME")

print(f"Key ID        : {key_id!r}")
print(f"Application Key: {application_key!r}")
print(f"Bucket        : {bucket_name!r}\n")

# 2) Initialize B2Api
info   = InMemoryAccountInfo()
b2_api = B2Api(info)

# 3) Try US (native) endpoint
print("▶️  Trying native B2 API (US)…")
try:
    # <– must be exactly these three positional args:
    b2_api.authorize_account("production", key_id, application_key)
    print("✅ Connected to US (api.backblazeb2.com)\n")
except Exception as us_e:
    print(f"❌ US failed: {us_e!r}\n")

    # 4) Fall back to EU
    print("▶️  Trying native B2 API (EU)…")
    try:
        # note: realm is a keyword-only arg
        b2_api.authorize_account("production", key_id, application_key, realm="eu-central-001")
        print("✅ Connected to EU (api.eu-central-001.backblazeb2.com)\n")
    except Exception as eu_e:
        print(f"❌ EU failed: {eu_e!r}\n")
