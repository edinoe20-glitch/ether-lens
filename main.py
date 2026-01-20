import os
import time
import json
import boto3
import subprocess
import asyncio
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from botocore.client import Config

# --- CONFIG ---
# R2 Config (Gudang Cloud)
R2_ACCOUNT_ID = 'GANTI_ID_AKUN_R2_LU'
R2_ACCESS_KEY = 'GANTI_ACCESS_KEY_LU'
R2_SECRET_KEY = 'GANTI_SECRET_KEY_LU'
R2_BUCKET_NAME = 'ether-lens'
R2_PUBLIC_URL = 'https://pub-xxxx.r2.dev'

# Tools Path
RIFE_PATH = "rife-ncnn-vulkan"  # Pastikan file binary ada di folder yang sama/path benar

# Database Lokal (List Video)
DB_FILE = "ether_db.json"

app = FastAPI()

# Setup S3/R2
s3 = boto3.client('s3',
    endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version='s3v4')
)

# --- FUNGSI DATABASE ---
def load_db():
    if not os.path.exists(DB_FILE): return []
    with open(DB_FILE, 'r') as f: return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

# --- WORKER GPU (Jalan di Background) ---
def process_video_task(link):
    timestamp = int(time.time())
    print(f"⚡ [Ether Lens] Processing: {link}")
    
    # Nama File
    raw_file = f"temp_raw_{timestamp}.mp4"
    final_file = f"ether_{timestamp}.mp4"
    thumb_file = f"thumb_{timestamp}.jpg"

    try:
        # 1. Download
        subprocess.run(f'yt-dlp -o "{raw_file}" "{link}"', shell=True)
        
        # 2. Render 60FPS (RIFE)
        # Kalau mau HD + Upscale, tambahin step Real-ESRGAN disini
        subprocess.run(f'{RIFE_PATH} -i {raw_file} -o {final_file} -m rife-v4.6', shell=True)
        
        # 3. Thumbnail
        subprocess.run(f'ffmpeg -i {final_file} -ss 00:00:02.000 -vframes 1 {thumb_file}', shell=True)

        # 4. Upload R2
        print("☁️ Uploading...")
        s3.upload_file(final_file, R2_BUCKET_NAME, final_file, ExtraArgs={'ContentType': 'video/mp4'})
        s3.upload_file(thumb_file, R2_BUCKET_NAME, thumb_file, ExtraArgs={'ContentType': 'image/jpeg'})
        
        # 5. Update Database
        new_entry = {
            "id": timestamp,
            "url": f"{R2_PUBLIC_URL}/{final_file}",
            "thumb": f"{R2_PUBLIC_URL}/{thumb_file}",
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "original_link": link
        }
        
        current_db = load_db()
        current_db.insert(0, new_entry) # Masukin paling atas
        save_db(current_db)
        
        print("✅ Success!")

    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Cleanup
    for f in [raw_file, final_file, thumb_file]:
        if os.path.exists(f): os.remove(f)

# --- API ENDPOINTS ---

@app.get("/api/videos")
async def get_videos():
    return load_db()

@app.post("/api/submit")
async def submit_link(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    link = data.get("link")
    if not link: return {"status": "error", "msg": "Link kosong"}
    
    # Lempar ke worker background biar web gak loading lama
    background_tasks.add_task(process_video_task, link)
    return {"status": "ok", "msg": "Sedang diproses di Background..."}

@app.get("/", response_class=HTMLResponse)
async def home():
    # Load file HTML tampilan
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    # Jalan di port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
