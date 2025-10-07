import os, csv, io, requests, pickle
from datetime import datetime
import pytz
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from generator.make_one import make_video

SHEET_CSV_URL = os.environ.get('SHEET_CSV_URL','')
TIMEZONE = os.environ.get('LOCAL_TZ','America/New_York')
MAX_PER_DAY = int(os.environ.get('MAX_PER_DAY','6'))
DEFAULT_DURATION = int(os.environ.get('VIDEO_DURATION','30'))
CATEGORY_ID = os.environ.get('VIDEO_CATEGORY','22')
PRIVACY_STATUS = os.environ.get('VIDEO_PRIVACY','public')

with open('token.pickle','rb') as f:
    creds = pickle.load(f)
yt = build('youtube','v3', credentials=creds)

def parse_date(s):
    s=(s or '').strip()
    for fmt in ("%m/%d/%Y","%Y-%m-%d","%m/%d/%y"):
        try: return datetime.strptime(s, fmt).date()
        except: pass
    return None

resp = requests.get(SHEET_CSV_URL, timeout=30)
resp.raise_for_status()
rows = list(csv.DictReader(io.StringIO(resp.text)))

today = datetime.now(pytz.timezone(TIMEZONE)).date()
today_rows = [r for r in rows if parse_date(r.get('date','')) == today][:MAX_PER_DAY]
if not today_rows:
    print("No rows for today. Add rows with today's date in your Google Form/Sheet.")
    raise SystemExit(0)

os.makedirs('output', exist_ok=True)

for i, r in enumerate(today_rows, 1):
    subject = (r.get('subject') or f'Daily Short {i}').strip()
    script  = (r.get('script')  or f"{subject}: quick tip. Take action today.").strip()
    tags    = [t.strip() for t in (r.get('tags') or 'Shorts').split(',') if t.strip()]

    out = f"output/{i:02d}.mp4"
    print(f"Making: {subject}")

    make_video(subject, script, out, duration=DEFAULT_DURATION)


    body = {
      'snippet': {
        'title': (subject[:95] + ' #Shorts') if len(subject) <= 95 else subject[:92] + '... #Shorts',
        'description': (script + "\n\n#Shorts")[:4900],
        'tags': tags, 'categoryId': CATEGORY_ID
      },
      'status': { 'privacyStatus': PRIVACY_STATUS, 'selfDeclaredMadeForKids': False }
    }
    media = MediaFileUpload(out, chunksize=-1, resumable=True)
    req = yt.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status: print(f"Uploaded {int(status.progress()*100)}%")
    print("Video id:", resp.get('id'))

print("All done.")
