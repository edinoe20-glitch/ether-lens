import os
import time
import json
import boto3
import subprocess
import shutil
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from botocore.client import Config
from dotenv import load_dotenv

# --- 1. CONFIG & SETUP ---

# Load settingan rahasia dari file .env
load_dotenv()

# Ambil variabel environment
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")
RIFE_PATH = os.getenv("RIFE_PATH", "bin/rife-ncnn-vulkan/rife-ncnn-vulkan") # Default path

# Setup folder data biar rapi
DATA_DIR = "data"
TEMP_DIR = os.path.join(DATA_DIR, "temp")
DB_FILE = os.path.join(DATA_DIR, "db.json")

os.makedirs(TEMP_DIR, exist_ok=True)

# Setup Client Cloudflare R2
s3 = boto3.client('s3',
    endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version='s3v4')
)

app = FastAPI()

# --- 2. FUNGSI DATABASE ---

def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, 'r') as f: return json.load(f)
    except: return []

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

def add_video_to_db(video_data):
    db = load_db()
    db.insert(0, video_data) # Masukin paling atas (terbaru)
    save_db(db)

# --- 3. WORKER (GTX 1650 TASK) ---

def process_video_task(link):
    timestamp = int(time.time())
    job_id = f"job_{timestamp}"
    print(f"⚡ [Ether Lens] Processing: {link}")
    
    # Path File Sementara
    raw_file = os.path.join(TEMP_DIR, f"{job_id}_raw.mp4")
    final_file = os.path.join(TEMP_DIR, f"ether_{timestamp}.mp4")
    thumb_file = os.path.join(TEMP_DIR, f"thumb_{timestamp}.jpg")

    try:
        # STEP 1: Download (Best Quality)
        print(f"⬇️ Downloading...")
        # -S res:1080 biar gak kegedean, atau apus -S kalo mau source asli
        subprocess.run(f'yt-dlp -o "{raw_file}" "{link}"', shell=True, check=True)
        
        # STEP 2: AI Render 60FPS (RIFE)
        print(f"🏎️ Interpolating 60FPS (GTX 1650)...")
        # Command RIFE. Pastikan path binary di .env bener!
        cmd_rife = f'"{RIFE_PATH}" -i "{raw_file}" -o "{final_file}" -m rife-v4.6'
        result = subprocess.run(cmd_rife, shell=True)
        
        if result.returncode != 0:
            raise Exception("Gagal Render AI")

        # STEP 3: Generate Thumbnail
        print(f"🖼️ Extracting Thumbnail...")
        subprocess.run(f'ffmpeg -y -i "{final_file}" -ss 00:00:02.000 -vframes 1 "{thumb_file}"', shell=True)

        # STEP 4: Upload ke Cloudflare R2
        print(f"☁️ Uploading to Cloud...")
        
        # Upload Video
        cloud_vid_name = f"ether_{timestamp}.mp4"
        s3.upload_file(final_file, R2_BUCKET_NAME, cloud_vid_name, ExtraArgs={'ContentType': 'video/mp4'})
        
        # Upload Thumb
        cloud_thumb_name = f"thumb_{timestamp}.jpg"
        s3.upload_file(thumb_file, R2_BUCKET_NAME, cloud_thumb_name, ExtraArgs={'ContentType': 'image/jpeg'})
        
        # STEP 5: Update Database
        new_entry = {
            "id": timestamp,
            "url": f"{R2_PUBLIC_URL}/{cloud_vid_name}",
            "thumb": f"{R2_PUBLIC_URL}/{cloud_thumb_name}",
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "original_link": link
        }
        add_video_to_db(new_entry)
        
        print(f"✅ Success! Video ready at: {new_entry['url']}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    finally:
        # Cleanup: Hapus file sampah lokal biar hardisk gak penuh
        print("🧹 Cleaning up...")
        for f in [raw_file, final_file, thumb_file]:
            if os.path.exists(f): os.remove(f)

# --- 4. API ENDPOINTS ---

# Endpoint buat Web Frontend minta data video
@app.get("/api/videos")
async def get_videos():
    return load_db()

# Endpoint buat submit link dari Web
@app.post("/api/submit")
async def submit_link(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    link = data.get("link")
    
    if not link: 
        return JSONResponse(status_code=400, content={"msg": "Link kosong bro"})
    
    # Jalanin proses di background biar web gak loading lama
    background_tasks.add_task(process_video_task, link)
    
    return {"status": "ok", "msg": "Link diterima, sedang diproses..."}

# Endpoint Utama (Serve HTML)
@app.get("/", response_class=HTMLResponse)
async def home():
    # Pastikan file index.html ada di folder templates
    template_path = os.path.join("templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return "<h1>Error: templates/index.html not found!</h1>"

# --- 5. RUNNER ---

if __name__ == "__main__":
    import uvicorn
    print("💎 Ether Lens Station Starting...")
    print(f"📂 RIFE Path: {RIFE_PATH}")
    # Jalan di localhost port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
