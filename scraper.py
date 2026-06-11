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

# ==========================================
# 1. MENGAMBIL DATA 32 AKUN UNIT USAHA
# ==========================================
for username in ACCOUNTS:
    try:
        print(f"\nMengambil data via API dari: {username}")
        # Endpoint Graph API (Business Discovery)
        url = f"https://graph.facebook.com/v19.0/{IG_ID}?fields=business_discovery.username({username}){{media{{media_url,permalink,media_type,timestamp,caption}}}}&access_token={TOKEN}"
        
        response = requests.get(url)
        data = response.json()
        
        if "error" in data:
            print(f"-> Gagal mengambil {username}: {data['error'].get('message')}")
            continue
            
        media_list = data.get("business_discovery", {}).get("media", {}).get("data", [])
        
        posts_data = []
        count = 0
        for post in media_list:
            if count >= 2: 
                break
            time_obj = datetime.strptime(post.get("timestamp")[:19], "%Y-%m-%dT%H:%M:%S")
            formatted_time = time_obj.strftime("%Y-%m-%d %H:%M:%S")
            caption = post.get("caption", "")
            
            posts_data.append({
                "url": post.get("permalink", ""),
                "caption_short": caption[:150] + "..." if caption else "",
                "date": formatted_time,
                "image_url": post.get("media_url", ""),
                "is_video": post.get("media_type") == "VIDEO",
                "is_reel": post.get("media_type") == "VIDEO"
            })
            count += 1
            
        output_data = {"posts": posts_data}
        with open(f"output/{username}.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
        print(f"-> Sukses menyimpan output/{username}.json")
    except Exception as e:
        print(f"-> Error tak terduga pada {username}: {e}")

# ==========================================
# 2. MENGAMBIL POST/REELS KHUSUS @dpbunpad (UNTUK KOLOM KANAN)
# ==========================================
print("\n[INFO] Mengambil data POST/REELS untuk @dpbunpad...")
try:
    # Menggunakan jalur langsung karena kita memegang akses akunnya
    url_dpb_posts = f"https://graph.facebook.com/v19.0/{IG_ID}/media?fields=media_url,permalink,media_type,timestamp,caption&access_token={TOKEN}"
    resp_dpb = requests.get(url_dpb_posts).json()
    
    if "data" in resp_dpb:
        dpb_posts_data = []
        for post in resp_dpb["data"][:2]: # Ambil 2 postingan terbaru
            time_obj = datetime.strptime(post.get("timestamp")[:19], "%Y-%m-%dT%H:%M:%S")
            formatted_time = time_obj.strftime("%Y-%m-%d %H:%M:%S")
            caption = post.get("caption", "")
            
            dpb_posts_data.append({
                "url": post.get("permalink", ""),
                "caption_short": caption[:150] + "..." if caption else "",
                "date": formatted_time,
                "image_url": post.get("media_url", ""),
                "is_video": post.get("media_type") == "VIDEO",
                "is_reel": post.get("media_type") == "VIDEO"
            })
        
        with open("output/dpbunpad.json", "w", encoding="utf-8") as f:
            json.dump({"posts": dpb_posts_data}, f, ensure_ascii=False, indent=4)
        print("-> Sukses menyimpan output/dpbunpad.json")
except Exception as e:
    print(f"-> Error mengambil posts @dpbunpad: {e}")

# ==========================================
# 3. MENGAMBIL STORIES KHUSUS @dpbunpad (UNTUK KOLOM KIRI)
# ==========================================
print("\n[INFO] Mengambil data STORIES harian untuk @dpbunpad...")
try:
    # Menggunakan endpoint khusus Stories
    url_dpb_stories = f"https://graph.facebook.com/v19.0/{IG_ID}/stories?fields=media_url,permalink,media_type,timestamp&access_token={TOKEN}"
    resp_stories = requests.get(url_dpb_stories).json()
    
    # CEK CERDAS: Pastikan ada Story yang tayang (tidak kosong)
    if "data" in resp_stories and len(resp_stories["data"]) > 0:
        dpb_stories_data = []
        for story in resp_stories["data"][:4]: # Ambil maksimal 4 Stories
            time_obj = datetime.strptime(story.get("timestamp")[:19], "%Y-%m-%dT%H:%M:%S")
            formatted_time = time_obj.strftime("%Y-%m-%d %H:%M:%S")
            
            dpb_stories_data.append({
                "url": story.get("permalink", ""),
                "date": formatted_time,
                "image_url": story.get("media_url", ""),
                "is_video": story.get("media_type") == "VIDEO",
                "is_reel": False
            })
        
        # Simpan/Timpa file JSON
        with open("output/dpbunpad-stories.json", "w", encoding="utf-8") as f:
            json.dump({"posts": dpb_stories_data}, f, ensure_ascii=False, indent=4)
        print("-> Sukses menyimpan output/dpbunpad-stories.json (Ada story baru!)")
    else:
        # Jika hari ini Anda tidak buat Story, skrip AKAN MENGABAIKAN PENULISAN FILE
        print("-> Tidak ada Stories baru hari ini. File dpbunpad-stories.json lama tetap dipertahankan!")
except Exception as e:
    print(f"-> Error mengambil stories @dpbunpad: {e}")
