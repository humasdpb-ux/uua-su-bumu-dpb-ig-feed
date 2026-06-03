import json
import os
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


ACCOUNTS_FILE = "accounts.txt"
OUTPUT_DIR = "output"

POST_LIMIT = 1
REEL_LIMIT = 1

# Naikkan supaya scraper mengambil lebih banyak kandidat posting.
FETCH_LIMIT = 50

# Naikkan supaya akun yang jarang update tidak langsung kosong.
RECENT_DAYS = 7

TIMEZONE = "Asia/Jakarta"


def now_jakarta():
    return datetime.now(ZoneInfo(TIMEZONE))


def now_jakarta_iso():
    return now_jakarta().isoformat()


def clean_username(username):
    username = username.strip()
    username = username.replace("@", "")
    username = username.replace("https://www.instagram.com/", "")
    username = username.replace("https://instagram.com/", "")
    username = username.strip("/")
    return username


def load_previous_result(username):
    output_path = os.path.join(OUTPUT_DIR, f"{username}.json")

    if not os.path.exists(output_path):
        return None

    try:
        with open(output_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def run_gallery_dl_url(url):
    command = [
        "gallery-dl",
        "--config",
        "gallery-dl.conf",
        "--dump-json",
        "--range",
        f"1-{FETCH_LIMIT}",
    ]

    if os.path.exists("cookies.txt"):
        command.extend(["--cookies", "cookies.txt"])

    command.append(url)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=90,
        )
        return result

    except subprocess.TimeoutExpired:
        class TimeoutResult:
            pass

        result = TimeoutResult()
        result.stdout = ""
        result.stderr = "Timeout: proses akun terlalu lama, dilewati otomatis."
        result.returncode = 124
        return result


def run_gallery_dl(username):
    # Tambahkan URL profil utama sebagai fallback.
    # Sebagian akun kadang tidak stabil kalau hanya dibaca dari /posts/ dan /reels/.
    urls = [
        f"https://www.instagram.com/{username}/",
        f"https://www.instagram.com/{username}/posts/",
        f"https://www.instagram.com/{username}/reels/",
    ]

    combined_stdout = ""
    combined_stderr = ""
    return_code = 0

    for url in urls:
        print(f"Fetching {url}", flush=True)
        result = run_gallery_dl_url(url)

        combined_stdout += "\n" + (result.stdout or "")
        combined_stderr += "\n" + (result.stderr or "")

        if result.returncode != 0:
            return_code = result.returncode

    class CombinedResult:
        pass

    combined = CombinedResult()
    combined.stdout = combined_stdout
    combined.stderr = combined_stderr
    combined.returncode = return_code

    return combined


def collect_gallery_items(obj):
    items = []

    if isinstance(obj, list):
        if len(obj) >= 2 and obj[0] == 2 and isinstance(obj[1], dict):
            data = obj[1]
            data["_gallery_message_type"] = 2
            items.append(data)

        elif len(obj) >= 3 and obj[0] == 3 and isinstance(obj[1], str) and isinstance(obj[2], dict):
            data = obj[2]
            data["_gallery_message_type"] = 3
            data["_media_url"] = obj[1]
            items.append(data)

        else:
            for child in obj:
                items.extend(collect_gallery_items(child))

    elif isinstance(obj, dict):
        for value in obj.values():
            items.extend(collect_gallery_items(value))

    return items


def parse_gallery_output(stdout):
    stdout = stdout.strip()

    if not stdout:
        return []

    items = []
    decoder = json.JSONDecoder()
    index = 0
    length = len(stdout)

    while index < length:
        while index < length and stdout[index].isspace():
            index += 1

        if index >= length:
            break

        try:
            parsed, next_index = decoder.raw_decode(stdout, index)
            items.extend(collect_gallery_items(parsed))
            index = next_index
        except json.JSONDecodeError:
            index += 1

    return items


def get_first_string(data, keys):
    for key in keys:
        value = data.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def extract_shortcode(data):
    return get_first_string(
        data,
        [
            "post_shortcode",
            "sidecar_shortcode",
            "shortcode",
            "short_code",
            "code",
            "display_id",
        ],
    )


def extract_post_url(data, shortcode):
    url = get_first_string(
        data,
        [
            "post_url",
            "webpage_url",
            "permalink",
            "link",
        ],
    )

    if url:
        return url

    media_type = str(data.get("type") or data.get("subcategory") or "").lower()
    is_reel = "reel" in media_type

    if shortcode and is_reel:
        return f"https://www.instagram.com/reel/{shortcode}/"

    if shortcode:
        return f"https://www.instagram.com/p/{shortcode}/"

    return ""


def extract_image_url(data):
    image = get_first_string(
        data,
        [
            "_media_url",
            "display_url",
            "thumbnail_src",
            "thumbnail",
            "thumbnail_url",
            "image",
            "image_url",
            "url",
        ],
    )

    if image.startswith("http"):
        return image

    image_versions = data.get("image_versions2")
    if isinstance(image_versions, dict):
        candidates = image_versions.get("candidates")
        if isinstance(candidates, list) and candidates:
            first = candidates[0]
            if isinstance(first, dict):
                url = first.get("url")
                if isinstance(url, str) and url.startswith("http"):
                    return url

    return ""


def extract_caption(data):
    return get_first_string(
        data,
        [
            "description",
            "caption",
            "title",
        ],
    )


def extract_date(data):
    return get_first_string(
        data,
        [
            "date",
            "post_date",
            "datetime",
            "timestamp",
            "taken_at_timestamp",
        ],
    )


def parse_date(date_text):
    if not date_text:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(str(date_text)[:19], fmt)
            return dt.replace(tzinfo=ZoneInfo(TIMEZONE))
        except ValueError:
            continue

    try:
        timestamp = int(float(date_text))
        return datetime.fromtimestamp(timestamp, ZoneInfo(TIMEZONE))
    except Exception:
        return None


def is_recent(date_text):
    dt = parse_date(date_text)

    if not dt:
        return False

    cutoff = now_jakarta() - timedelta(days=RECENT_DAYS)

    return dt >= cutoff


def normalize_item(data, username):
    shortcode = extract_shortcode(data)
    post_url = extract_post_url(data, shortcode)
    image_url = extract_image_url(data)
    caption = extract_caption(data)
    date = extract_date(data)

    subcategory = str(data.get("subcategory", "")).lower()
    media_type = str(data.get("type", "")).lower()

    is_reel = (
        "/reel/" in post_url
        or subcategory == "reels"
        or "reel" in media_type
    )

    is_video = bool(
        data.get("is_video")
        or data.get("video_url")
        or data.get("duration")
        or data.get("video")
        or data.get("video_versions")
        or is_reel
    )

    return {
        "username": username,
        "shortcode": shortcode,
        "url": post_url,
        "caption": caption,
        "caption_short": caption[:180] if caption else "",
        "date": date,
        "image_url": image_url,
        "is_video": is_video,
        "is_reel": is_reel,
    }


def merge_items_by_post(raw_items, username):
    merged = {}

    for data in raw_items:
        item = normalize_item(data, username)

        key = item.get("shortcode") or item.get("url") or item.get("image_url")

        if not key:
            continue

        if key not in merged:
            merged[key] = item
            continue

        for field in ["url", "caption", "caption_short", "date", "image_url", "shortcode"]:
            if not merged[key].get(field) and item.get(field):
                merged[key][field] = item[field]

        merged[key]["is_video"] = bool(merged[key].get("is_video") or item.get("is_video"))
        merged[key]["is_reel"] = bool(merged[key].get("is_reel") or item.get("is_reel"))

    results = []

    for item in merged.values():
        if not item.get("url") and item.get("shortcode"):
            if item.get("is_reel"):
                item["url"] = f"https://www.instagram.com/reel/{item['shortcode']}/"
            else:
                item["url"] = f"https://www.instagram.com/p/{item['shortcode']}/"

        results.append(item)

    return results


def sort_key(item):
    dt = parse_date(item.get("date", ""))
    if not dt:
        return datetime(1970, 1, 1, tzinfo=ZoneInfo(TIMEZONE))
    return dt


def preserve_previous_if_needed(username, account_result, reason):
    previous = load_previous_result(username)

    if previous and isinstance(previous.get("posts"), list) and previous["posts"]:
        account_result["posts"] = previous["posts"]
        account_result["error"] = f"{reason}. Memakai data lama agar website tidak kosong."
        print(f"{username}: {reason}. Preserved previous posts={len(previous['posts'])}", flush=True)
        return account_result

    account_result["error"] = reason
    return account_result


def process_account(username):
    print(f"Processing {username}...", flush=True)

    account_result = {
        "username": username,
        "generated_at": now_jakarta_iso(),
        "posts": [],
        "error": None,
    }

    try:
        result = run_gallery_dl(username)

        if result.returncode != 0 and not result.stdout.strip():
            error_message = result.stderr.strip() or "gallery-dl gagal tanpa output."
            return preserve_previous_if_needed(
                username,
                account_result,
                f"gallery-dl gagal: {error_message[:300]}"
            )

        raw_items = parse_gallery_output(result.stdout)

        if not raw_items:
            stderr_message = result.stderr.strip()[:300] if result.stderr else "Tidak ada raw item dari Instagram."
            return preserve_previous_if_needed(
                username,
                account_result,
                f"Tidak ada data terbaca dari Instagram. {stderr_message}"
            )

        merged_items = merge_items_by_post(raw_items, username)

        recent_items = []

        for item in merged_items:
            if not item.get("url"):
                continue

            if not item.get("date"):
                continue

            if not is_recent(item.get("date")):
                continue

            recent_items.append(item)

        recent_items.sort(key=sort_key, reverse=True)

        posts = [item for item in recent_items if not item.get("is_reel")]
        reels = [item for item in recent_items if item.get("is_reel")]

        selected_items = posts[:POST_LIMIT] + reels[:REEL_LIMIT]
        selected_items.sort(key=sort_key, reverse=True)

        if not selected_items:
            return preserve_previous_if_needed(
                username,
                account_result,
                f"Tidak ada posting terbaru dalam {RECENT_DAYS} hari terakhir"
            )

        account_result["posts"] = selected_items

        print(
            f"{username}: raw={len(raw_items)}, merged={len(merged_items)}, "
            f"recent={len(recent_items)}, posts={len(posts[:POST_LIMIT])}, "
            f"reels={len(reels[:REEL_LIMIT])}, selected={len(selected_items)}",
            flush=True
        )

    except Exception as e:
        return preserve_previous_if_needed(
            username,
            account_result,
            f"Exception: {str(e)[:300]}"
        )

    return account_result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
        accounts = [clean_username(line) for line in file if line.strip()]

    accounts = list(dict.fromkeys(accounts))

    index_data = {
        "generated_at": now_jakarta_iso(),
        "recent_days": RECENT_DAYS,
        "filter_mode": f"last_{RECENT_DAYS}_days",
        "post_limit": POST_LIMIT,
        "reel_limit": REEL_LIMIT,
        "fetch_limit": FETCH_LIMIT,
        "total_accounts": len(accounts),
        "accounts": [],
    }

    for username in accounts:
        account_result = process_account(username)

        output_path = os.path.join(OUTPUT_DIR, f"{username}.json")

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(account_result, file, ensure_ascii=False, indent=2)

        index_data["accounts"].append(
            {
                "username": username,
                "file": f"{username}.json",
                "post_count": len(account_result["posts"]),
                "error": account_result["error"],
            }
        )

    index_path = os.path.join(OUTPUT_DIR, "index.json")

    with open(index_path, "w", encoding="utf-8") as file:
        json.dump(index_data, file, ensure_ascii=False, indent=2)

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
