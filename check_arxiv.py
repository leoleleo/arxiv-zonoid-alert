import os
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ============================================================
# SETTINGS
# ============================================================

SEARCH_QUERY = 'ti:zonoid OR abs:zonoid OR ti:zonotope OR abs:zonotope'

ARXIV_API_URL = "https://export.arxiv.org/api/query?"

SEEN_FILE = "seen_papers.json"


# ============================================================
# SEARCH ARXIV
# ============================================================

encoded_query = urllib.parse.quote(SEARCH_QUERY)

url = (
    ARXIV_API_URL
    + f"search_query={encoded_query}"
    "&start=0"
    "&max_results=50"
    "&sortBy=submittedDate"
    "&sortOrder=descending"
)

request = urllib.request.Request(
    url,
    headers={"User-Agent": "arxiv-zonoid-alert/1.0"}
)

with urllib.request.urlopen(request) as response:
    data = response.read()

root = ET.fromstring(data)

namespace = {
    "atom": "http://www.w3.org/2005/Atom"
}


# ============================================================
# READ PAPERS
# ============================================================

papers = []

for entry in root.findall("atom:entry", namespace):

    arxiv_url = entry.find("atom:id", namespace).text.strip()

    # Extract stable arXiv ID.
    # Example:
    # http://arxiv.org/abs/2602.08103v1
    # becomes:
    # 2602.08103
    arxiv_id = arxiv_url.rstrip("/").split("/")[-1]

    if "v" in arxiv_id:
        arxiv_id = arxiv_id.rsplit("v", 1)[0]

    title = entry.find("atom:title", namespace).text.strip()

    summary = entry.find("atom:summary", namespace).text.strip()

    published = entry.find("atom:published", namespace).text.strip()

    authors = []

    for author in entry.findall("atom:author", namespace):
        name = author.find("atom:name", namespace)
        if name is not None:
            authors.append(name.text.strip())

    papers.append({
        "id": arxiv_id,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "title": " ".join(title.split()),
        "summary": " ".join(summary.split()),
        "published": published,
        "authors": authors
    })


# ============================================================
# LOAD PAPERS WE HAVE ALREADY SEEN
# ============================================================

if os.path.exists(SEEN_FILE):

    with open(SEEN_FILE, "r") as f:
        old_seen = json.load(f)

else:
    old_seen = []


# Convert old entries such as:
# http://arxiv.org/abs/2602.08103v1
# into:
# 2602.08103

seen = set()

for item in old_seen:

    item = item.rstrip("/")

    if "/" in item:
        item = item.split("/")[-1]

    if "v" in item:
        item = item.rsplit("v", 1)[0]

    seen.add(item)


# ============================================================
# FIND NEW PAPERS
# ============================================================

new_papers = [
    paper for paper in papers
    if paper["id"] not in seen
]


# ============================================================
# SAVE SEEN PAPERS
# ============================================================

# Add every paper currently returned by arXiv.
for paper in papers:
    seen.add(paper["id"])


with open(SEEN_FILE, "w") as f:
    json.dump(sorted(seen), f, indent=2)


# ============================================================
# SEND EMAIL IF THERE ARE NEW PAPERS
# ============================================================

if not new_papers:

    print("No new matching papers.")
    exit()


sender = os.environ["EMAIL_ADDRESS"]
password = os.environ["EMAIL_PASSWORD"]
recipient = os.environ["EMAIL_RECIPIENT"]


message = MIMEMultipart()

message["From"] = sender
message["To"] = recipient

if len(new_papers) == 1:
    message["Subject"] = "New arXiv paper mentioning 'zonoid' or 'zonotope'"
else:
    message["Subject"] = (
        f"{len(new_papers)} new arXiv papers mentioning 'zonoid'or 'zonotope'"
    )


body = ""

for paper in new_papers:

    body += "========================================\n\n"

    body += f"TITLE:\n{paper['title']}\n\n"

    body += "AUTHORS:\n"

    if paper["authors"]:
        body += ", ".join(paper["authors"]) + "\n\n"
    else:
        body += "Not available\n\n"

    body += f"PUBLISHED:\n{paper['published'][:10]}\n\n"

    body += f"ARXIV:\n{paper['url']}\n\n"

    body += f"ABSTRACT:\n{paper['summary']}\n\n"


message.attach(MIMEText(body, "plain"))


# ============================================================
# SEND THROUGH GMAIL
# ============================================================

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:

    server.login(sender, password)

    server.send_message(message)


print(
    f"Sent notification for {len(new_papers)} new paper(s)."
)
