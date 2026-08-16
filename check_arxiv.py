import os
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Search arXiv for "zonoid" in the title OR abstract
SEARCH_QUERY = 'ti:zonoid OR abs:zonoid'

# arXiv API
encoded_query = urllib.parse.quote(SEARCH_QUERY)
url = (
    "https://export.arxiv.org/api/query?"
    f"search_query={encoded_query}"
    "&start=0&max_results=20"
    "&sortBy=submittedDate&sortOrder=descending"
)

request = urllib.request.Request(
    url,
    headers={"User-Agent": "arxiv-zonoid-alert/1.0"}
)

with urllib.request.urlopen(request) as response:
    data = response.read()

root = ET.fromstring(data)

namespace = {"atom": "http://www.w3.org/2005/Atom"}

papers = []

for entry in root.findall("atom:entry", namespace):
    paper_id = entry.find("atom:id", namespace).text.strip()
    title = entry.find("atom:title", namespace).text.strip()
    summary = entry.find("atom:summary", namespace).text.strip()

    papers.append({
        "id": paper_id,
        "title": " ".join(title.split()),
        "summary": " ".join(summary.split())
    })

# File used to remember papers we've already emailed
seen_file = "seen_papers.json"

if os.path.exists(seen_file):
    with open(seen_file, "r") as f:
        seen = set(json.load(f))
else:
    seen = set()

new_papers = [paper for paper in papers if paper["id"] not in seen]

# Don't send an enormous first email:
# remember all papers currently found, but only email the newest ones.
for paper in papers:
    seen.add(paper["id"])

with open(seen_file, "w") as f:
    json.dump(list(seen), f, indent=2)

if not new_papers:
    print("No new matching papers.")
    exit()

# Email settings come from GitHub Secrets
sender = os.environ["EMAIL_ADDRESS"]
password = os.environ["EMAIL_PASSWORD"]
recipient = os.environ["EMAIL_RECIPIENT"]

message = MIMEMultipart()
message["From"] = sender
message["To"] = recipient
message["Subject"] = f"New arXiv paper(s) mentioning 'zonoid'"

body = "New arXiv paper(s) matching 'zonoid':\n\n"

for paper in new_papers:
    body += f"TITLE:\n{paper['title']}\n\n"
    body += f"ABSTRACT:\n{paper['summary']}\n\n"
    body += f"ARXIV:\n{paper['id']}\n"
    body += "\n" + "-" * 70 + "\n\n"

message.attach(MIMEText(body, "plain"))

# Gmail's SMTP server
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(sender, password)
    server.send_message(message)

print(f"Sent notification for {len(new_papers)} new paper(s).")
