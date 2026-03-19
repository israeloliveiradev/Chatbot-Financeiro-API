import urllib.request
import urllib.error
import json

data = json.dumps({"number": "11282946236509", "text": "Hello"}).encode('utf-8')
req = urllib.request.Request("http://localhost:8080/message/sendText/MainInstance", data=data)
req.add_header('apikey', 'pa7dQpoEfuuowjYU')
req.add_header('Content-Type', 'application/json')

try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    err = json.loads(e.read().decode('utf-8'))
    with open("log.txt", "w") as f:
        f.write(json.dumps(err, indent=2))
