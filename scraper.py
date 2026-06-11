import instaloader
import json
import os
import time
from datetime import datetime

# Daftar 32 akun dari data CSV Unit Usaha Unpad
ACCOUNTS = [
    "taxcenterunpad", "lrtf_unpad", "unpadpusatbahasa", "bipaunpad", "biomedik.fkunpad", "pamitran.unpad", "p4kgbfkgunpad", "puspaunpad", "imcarepuspa", "labfmipaunpad", "bale_tatanen_unpad", "labktnt.unpad", "mipacornerunpad", "fikommerce", "diviaunpadtv",
    "rsunpad", "rsgmunpad_official", "klinik.unpad", "klinik.unpadsingaperbangsa", "klinik.unpaddago", "apotek.unpad", "rshunpad", "labsentral.unpad", "bigunpad",
    "mahatmasagi.unpad", "interedu.mmunpad", "mmu.eventtourorganizer", "utcdagohotelbandung", "asrama.balewilasa", "mahatmacoffeebymmu", "pip.unpad", "unpad.edex"
]

# Inisialisasi Instaloader
L = instaloader.Instaloader(
    download_pictures=False, 
    download_video_thumbnails=False, 
    download_videos=False, 
    download_comments=False, 
    save_metadata=False,
    max_connection_attempts=1 # Mempercepat skip jika terjadi error/blokir
)

# --- BAGIAN LOGIN VIA SESSION ID ---
session_id = os.environ.get("IG_SESSIONID")

if session_id:
    try:
        # Memasukkan cookie sessionid langsung ke sesi Instaloader
        L.context._session.cookies.set("sessionid", session_id, domain=".instagram.com")
        print("Berhasil memasukkan kredensial via Session ID")
    except Exception as e:
        print("Gagal set Session ID:", e)
else:
    print("Peringatan: IG_SESSIONID tidak ditemukan di GitHub Secrets!")
# -----------------------------------

# Pastikan folder output/ ada
os.makedirs("output", exist_ok=True)

for username in ACCOUNTS:
    try:
        print(f"\nMengambil data dari: {username}")
        profile = instaloader.Profile.from_username(L.context, username)
        
        posts_data = []
        count = 0
        for post in profile.get_posts():
            if count >= 2:
                break
            
            posts_data.append({
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "caption_short": post.caption[:150] + "..." if post.caption else "",
                "date": post.date_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "image_url": post.url,
                "is_video": post.is_video,
                "is_reel": post.typename == "GraphVideo"
            })
            count += 1
            
        # Simpan ke format JSON di folder output/
        output_data = {"posts": posts_data}
        with open(f"output/{username}.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
            
        print(f"-> Sukses! Jeda 15 detik untuk menghindari blokir...")
        time.sleep(15)
        
    except Exception as e:
        print(f"-> Error pada {username}: {e}")
