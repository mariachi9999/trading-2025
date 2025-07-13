
import json

with open("creds.json", "r") as f:
    creds = json.load(f)

print(f'GOOGLE_CREDS_JSON="{json.dumps(creds)}"')
