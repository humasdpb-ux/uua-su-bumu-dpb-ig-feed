import os
import json
import requests
from datetime import datetime

# Daftar akun Unit Usaha Unpad
ACCOUNTS = [
    "taxcenterunpad", "lrtf_unpad", "unpadpusatbahasa", "bipaunpad", "biomedik.fkunpad", "pamitran.unpad", "p4kgbfkgunpad", "puspaunpad", "imcarepuspa", "labfmipaunpad", "bale_tatanen_unpad", "labktnt.unpad", "mipacornerunpad", "fikommerce", "diviaunpadtv",
    "rsunpad", "uchemark.id", "padibyunpad", "bigunpad", "rsgmunpad_official", "klinik.unpad", "klinik.unpadsingaperbangsa", "klinik.unpaddago", "apotek.unpad", "rshunpad", "labsentral.unpad", "bigunpad",
    "mahatmasagi.unpad", "interedu.mmunpad", "mmu.eventtourorganizer", "utcdagohotelbandung", "asrama.balewilasa", "mahatmacoffeebymmu", "mangle_1957", "pip.unpad", "unpad.edex"
]

TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IG_ID = os.environ.get("IG_ACCOUNT_ID")

if not TOKEN or not IG_ID:
    print("Error: Token atau IG ID tidak ditemukan di GitHub Secrets!")
    exit(1)

os.makedirs("output", exist_ok=True)

# 1. MENGAMBIL DATA 32 AKUN UNIT USAHA
for username in ACCOUNTS:
    try:
        url = f"https://graph.facebook.com/v19.0/{IG_ID}?fields=business_discovery.username({username}){{media{{media_url,permalink,media_type,timestamp,caption}}}}&access_token={TOKEN}"
        response = requests.get(url).json()
        if "error" in response:
            continue
        media_list = response.get("business_discovery", {}).get("media", {}).get("data", [])
        
        posts_data = []
        for count, post in enumerate(media_list):
            if count >= 2: break
            time_obj = datetime.strptime(post.get("timestamp")[:19], "%Y-%m-%dT%H:%M:%S")
            posts_data.append({
                "url": post.get("permalink", ""),
                "caption_short": post.get("caption", "")[:150] + "..." if post.get("caption") else "",
                "date": time_obj.strftime("%Y-%m-%d %H:%M:%S"),
                "image_url": post.get("media_url", ""),
                "is_video": post.get("media_type") == "VIDEO",
                "is_reel": post.get("media_type") == "VIDEO"
            })
            
        with open(f"output/{username}.json", "w", encoding="utf-8") as f:
            json.dump({"posts": posts_data}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        pass

# 2. MENGAMBIL POST/REELS @dpbunpad (Sekarang ambil 10 agar ada cadangan)
try:
    url_dpb_posts = f"https://graph.facebook.com/v19.0/{IG_ID}/media?fields=media_url,permalink,media_type,timestamp,caption&access_token={TOKEN}"
    resp_dpb = requests.get(url_dpb_posts).json()
    
    if "data" in resp_dpb:
        dpb_posts_data = []
        for post in resp_dpb["data"][:10]: # LIMIT DITAMBAH MENJADI 10
            time_obj = datetime.strptime(post.get("timestamp")[:19], "%Y-%m-%dT%H:%M:%S")
            dpb_posts_data.append({
                "url": post.get("permalink", ""),
                "caption_short": post.get("caption", "")[:150] + "..." if post.get("caption") else "",
                "date": time_obj.strftime("%Y-%m-%d %H:%M:%S"),
                "image_url": post.get("media_url", ""),
                "is_video": post.get("media_type") == "VIDEO",
                "is_reel": post.get("media_type") == "VIDEO"
            })
        with open("output/dpbunpad.json", "w", encoding="utf-8") as f:
            json.dump({"posts": dpb_posts_data}, f, ensure_ascii=False, indent=4)
except Exception as e:
    pass

# 3. MENGAMBIL STORIES @dpbunpad (Maksimal 4)
try:
    url_dpb_stories = f"https://graph.facebook.com/v19.0/{IG_ID}/stories?fields=media_url,permalink,media_type,timestamp&access_token={TOKEN}"
    resp_stories = requests.get(url_dpb_stories).json()
    
    if "data" in resp_stories and len(resp_stories["data"]) > 0:
        dpb_stories_data = []
        for story in resp_stories["data"][:4]:
            time_obj = datetime.strptime(story.get("timestamp")[:19], "%Y-%m-%dT%H:%M:%S")
            dpb_stories_data.append({
                "url": story.get("permalink", ""),
                "date": time_obj.strftime("%Y-%m-%d %H:%M:%S"),
                "image_url": story.get("media_url", ""),
                "is_video": story.get("media_type") == "VIDEO",
                "is_reel": False
            })
        with open("output/dpbunpad-stories.json", "w", encoding="utf-8") as f:
            json.dump({"posts": dpb_stories_data}, f, ensure_ascii=False, indent=4)
except Exception as e:
    pass
