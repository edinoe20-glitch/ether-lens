import os
import subprocess
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import yt_dlp

app = FastAPI()

# --- 1. SETUP FOLDER ---
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

RIFE_PATH = "bin/rife-ncnn-vulkan/rife-ncnn-vulkan"

# --- 2. TAMPILAN CYBERPUNK (FRONTEND) ---
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>ETHER LENS // 60FPS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            background-color: #0d0d0d; color: #00ff9d;
            font-family: 'Courier New', monospace;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            height: 100vh; margin: 0; padding: 20px;
        }
        h1 { text-shadow: 0 0 10px #00ff9d; margin-bottom: 20px; }
        .container {
            border: 2px solid #00ff9d; padding: 20px;
            box-shadow: 0 0 20px rgba(0, 255, 157, 0.2);
            background: rgba(0, 20, 0, 0.8); max-width: 400px; width: 100%;
            text-align: center; border-radius: 10px;
        }
        input {
            width: 90%; padding: 10px; margin-bottom: 15px;
            background: #000; border: 1px solid #00ff9d; color: #fff;
            font-family: inherit; outline: none;
        }
        button {
            width: 100%; padding: 10px; background: #00ff9d; color: #000;
            border: none; font-weight: bold; cursor: pointer;
            font-family: inherit; text-transform: uppercase;
        }
        button:hover { background: #fff; box-shadow: 0 0 15px #fff; }
        #status { margin-top: 15px; font-size: 0.9em; min-height: 20px; color: #ff0055; }
        .success { color: #00ff9d !important; }
        .loader { display: none; color: yellow; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>ETHER LENS</h1>
    <div class="container">
        <p>PASTE LINK (TIKTOK/IG/YT)</p>
        <input type="text" id="urlInput" placeholder="https://...">
        <button onclick="processVideo()">RENDER 60FPS</button>
        <div id="loader" class="loader">⚙️ PROCESSING... (WAIT 1-2 MIN)</div>
        <div id="status"></div>
    </div>

    <script>
        async function processVideo() {
            const url = document.getElementById('urlInput').value;
            const status = document.getElementById('status');
            const loader = document.getElementById('loader');

            if (!url) { status.innerText = "❌ ISI LINK DULU WOY!"; return; }

            status.innerText = "";
            loader.style.display = "block";

            try {
                const response = await fetch('/render', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();

                if (data.status === "success") {
                    status.innerHTML = `<a href="${data.url}" target="_blank" style="color:#00ff9d; font-size:1.2em; font-weight:bold;">✅ DOWNLOAD HASIL DISINI</a>`;
                    status.classList.add("success");
                } else {
                    status.innerText = "❌ ERROR: " + (data.error || "Gagal");
                }
            } catch (e) {
                status.innerText = "❌ SERVER ERROR / TIMEOUT";
            } finally {
                loader.style.display = "none";
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return html_content

@app.post("/render")
def render_video(data: dict):
    video_url = data.get("url")
    if not video_url: return {"error": "Link kosong"}
    
    # Generate ID
    video_id = str(uuid.uuid4())[:8]
    raw_path = f"{OUTPUT_DIR}/{video_id}_raw.mp4"
    final_filename = f"{video_id}_60fps.mp4"
    final_path = f"{OUTPUT_DIR}/{final_filename}"

    print(f"⬇️ Download: {video_url}")
    
    # Download
    ydl_opts = {'format': 'mp4', 'outtmpl': raw_path, 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([video_url])
    except: return {"error": "Gagal download video"}

    # Render RIFE
    print("⚙️ Rendering AI...")
    try:
        subprocess.run([RIFE_PATH, "-i", raw_path, "-o", final_path, "-m", "rife-v4.6"], check=True)
    except:
        subprocess.run([RIFE_PATH, "-i", raw_path, "-o", final_path], check=True)

    # Cleanup
    if os.path.exists(raw_path): os.remove(raw_path)
    print("✅ Selesai!")
    
    return {"status": "success", "url": f"/output/{final_filename}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
