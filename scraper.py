import os
import json
import requests
from datetime import datetime

# Daftar 32 akun Unit Usaha Unpad
ACCOUNTS = [
    "taxcenterunpad", "lrtf_unpad", "unpadpusatbahasa", "bipaunpad", "biomedik.fkunpad", "pamitran.unpad", "p4kgbfkgunpad", "puspaunpad", "imcarepuspa", "labfmipaunpad", "bale_tatanen_unpad", "labktnt.unpad", "mipacornerunpad", "fikommerce", "diviaunpadtv",
    "rsunpad", "rsgmunpad_official", "klinik.unpad", "klinik.unpadsingaperbangsa", "klinik.unpaddago", "apotek.unpad", "rshunpad", "labsentral.unpad", "bigunpad",
    "mahatmasagi.unpad", "interedu.mmunpad", "mmu.eventtourorganizer", "utcdagohotelbandung", "asrama.balewilasa", "mahatmacoffeebymmu", "pip.unpad", "unpad.edex"
]

# Mengambil rahasia dari GitHub Secrets
TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IG_ID = os.environ.get("IG_ACCOUNT_ID")

if not TOKEN or not IG_ID:
    print("Error: Token atau IG ID tidak ditemukan di GitHub Secrets!")
    exit(1)

# Membuat folder output jika belum ada
os.makedirs("output", exist_ok=True)

for username in ACCOUNTS:
    try:
        print(f"\nMengambil data via API dari: {username}")
        
        # Endpoint Graph API (Business Discovery) untuk mengambil media, permalink, tipe, waktu, dan caption
        url = f"https://graph.facebook.com/v19.0/{IG_ID}?fields=business_discovery.username({username}){{media{{media_url,permalink,media_type,timestamp,caption}}}}&access_token={TOKEN}"
        
        response = requests.get(url)
        data = response.json()
        
        # Pengecekan jika terjadi error dari API (misal akun target bukan akun bisnis/kreator)
        if "error" in data:
            print(f"-> Gagal mengambil {username}: {data['error'].get('message')}")
            continue
            
        # Mengekstrak list media
        media_list = data.get("business_discovery", {}).get("media", {}).get("data", [])
        
        posts_data = []
        count = 0
        for post in media_list:
            # Sesuai pengaturan sebelumnya, kita hanya mengambil 2 post terbaru
            if count >= 2: 
                break
                
            # Konversi format waktu bawaan API (ISO 8601) ke format string yang biasa digunakan website Anda
            time_obj = datetime.strptime(post.get("timestamp")[:19], "%Y-%m-%dT%H:%M:%S")
            formatted_time = time_obj.strftime("%Y-%m-%d %H:%M:%S")
            
            caption = post.get("caption", "")
            
            posts_data.append({
                "url": post.get("permalink", ""),
                "caption_short": caption[:150] + "..." if caption else "",
                "date": formatted_time,
                "image_url": post.get("media_url", ""),
                "is_video": post.get("media_type") == "VIDEO",
                "is_reel": post.get("media_type") == "VIDEO" # API menganggap Reels sebagai VIDEO
            })
            count += 1
            
        output_data = {"posts": posts_data}
        
        # Simpan file JSON per akun
        with open(f"output/{username}.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
            
        print(f"-> Sukses menyimpan output/{username}.json")
        
    except Exception as e:
        print(f"-> Error tak terduga pada {username}: {e}")
