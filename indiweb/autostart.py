import requests
import time

# Try 3 times
for i in range(3):
    try:
        r = requests.post("http://localhost:8624/api/server/autostart")
    except Exception:
        time.sleep(1)
        continue
    status_code = r.status_code
    if (status_code == 200):
        exit(0)
    else:
        time.sleep(1)

exit(1)
