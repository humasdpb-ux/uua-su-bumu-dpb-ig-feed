import instaloader
import json
import os
import time
from datetime import datetime

# Daftar 32 akun
ACCOUNTS = [
    "taxcenterunpad", "lrtf_unpad", "unpadpusatbahasa", "bipaunpad", "biomedik.fkunpad", "pamitran.unpad", "p4kgbfkgunpad", "puspaunpad", "imcarepuspa", "labfmipaunpad", "bale_tatanen_unpad", "labktnt.unpad", "mipacornerunpad", "fikommerce", "diviaunpadtv",
    "rsunpad", "rsgmunpad_official", "klinik.unpad", "klinik.unpadsingaperbangsa", "klinik.unpaddago", "apotek.unpad", "rshunpad", "labsentral.unpad", "bigunpad",
    "mahatmasagi.unpad", "interedu.mmunpad", "mmu.eventtourorganizer", "utcdagohotelbandung", "asrama.balewilasa", "mahatmacoffeebymmu", "pip.unpad", "unpad.edex"
]

L = instaloader.Instaloader(download_pictures=False, download_video_thumbnails=False, download_videos=False, download_comments=False, save_metadata=False)

# --- BAGIAN TAMBAHAN UNTUK LOGIN ---
ig_user = os.environ.get("IG_USERNAME")
ig_pass = os.environ.get("IG_PASSWORD")

if ig_user and ig_pass:
    try:
        L.login(ig_user, ig_pass)
        print("Berhasil login dengan akun:", ig_user)
    except Exception as e:
        print("Gagal login:", e)
# -----------------------------------

os.makedirs("output", exist_ok=True)

for username in ACCOUNTS:
    try:
        print(f"Mengambil data dari: {username}")
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
            
        output_data = {"posts": posts_data}
        with open(f"output/{username}.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
            
        # Jeda diperlama sedikit (15 detik) untuk menghindari limit saat posisi login
        time.sleep(15)
        
    except Exception as e:
        print(f"Error pada {username}: {e}")
