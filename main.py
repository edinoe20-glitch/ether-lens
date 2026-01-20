import os
import subprocess
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import yt_dlp

app = FastAPI()

# --- 1. SETUP AGAR HP BISA AKSES ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. BIKIN FOLDER PENYIMPANAN ---
# Video hasil render bakal masuk ke folder 'output' di laptop lu
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Mount folder ini biar bisa dibuka dari internet (lewat tunnel)
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# --- 3. LOKASI MESIN AI (RIFE) ---
# Sesuai path yang kita fix tadi
RIFE_PATH = "bin/rife-ncnn-vulkan/rife-ncnn-vulkan"

@app.get("/")
def home():
    return {"status": "Ether Lens Local Mode", "message": "Siap Tempur! Gak butuh R2/CC."}

@app.post("/render")
def render_video(data: dict):
    video_url = data.get("url")
    if not video_url:
        raise HTTPException(status_code=400, detail="Mana link videonya bang?")

    # Bikin nama file acak biar gak bentrok
    video_id = str(uuid.uuid4())[:8]
    raw_path = f"{OUTPUT_DIR}/{video_id}_raw.mp4"
    final_filename = f"{video_id}_60fps.mp4"
    final_path = f"{OUTPUT_DIR}/{final_filename}"

    print(f"\n⬇️  Mulai Download: {video_url}")

    # --- TAHAP 1: DOWNLOAD VIDEO ---
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': raw_path,
        'quiet': True,
        'no_warnings': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except Exception as e:
        print(f"❌ Error Download: {e}")
        return {"error": "Gagal download video aslinya"}

    print(f"🏎️  Sedang Menggiling AI (60FPS)... Sabar ya, laptop lagi kerja keras.")

    # --- TAHAP 2: RENDER RIFE ---
    # Kita cek dulu apakah file raw berhasil didownload
    if not os.path.exists(raw_path):
         return {"error": "File download gak ketemu!"}

    try:
        # Perintah menjalankan RIFE
        subprocess.run([
            RIFE_PATH,
            "-i", raw_path,
            "-o", final_path,
            "-m", "rife-v4.6" # Model paling stabil
        ], check=True)
    except Exception as e:
        print("⚠️ Model v4.6 error, mencoba model default...")
        try:
            subprocess.run([RIFE_PATH, "-i", raw_path, "-o", final_path], check=True)
        except Exception as e:
            return {"error": f"Gagal Render AI: {str(e)}"}

    # --- TAHAP 3: BERSIH-BERSIH ---
    # Hapus file mentah biar harddisk gak penuh
    if os.path.exists(raw_path):
        os.remove(raw_path)

    print(f"✅ SUKSES! Video jadi: {final_path}")

    # --- TAHAP 4: KIRIM LINK KE HP ---
    # Browser HP bakal otomatis nambahin domain tunnel di depannya
    return {
        "status": "success", 
        "url": f"/output/{final_filename}"
    }

if __name__ == "__main__":
    import uvicorn
    # Host 0.0.0.0 biar bisa diakses dari luar (wajib buat tunnel)
    uvicorn.run(app, host="0.0.0.0", port=8000)
