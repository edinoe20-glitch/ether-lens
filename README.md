# 💎 Ether Lens Station

Personal Video Remastering Station (Web Interface).
Mengubah video TikTok/IG menjadi 60FPS HD menggunakan GTX 1650 dan menyimpannya di Cloudflare R2.

## Fitur
- **Web UI:** Cyberpunk aesthetic, mobile friendly.
- **AI Engine:** RIFE (Interpolation) & Real-ESRGAN (Upscaling).
- **Cloud Storage:** Direct upload to Cloudflare R2.
- **Queue System:** Background processing with FastAPI.

## Cara Install
1. Clone repo ini.
2. Download `rife-ncnn-vulkan` taruh di folder `bin/`.
3. Buat file `.env` (lihat contoh).
4. `pip install -r requirements.txt`
5. `python main.py`
