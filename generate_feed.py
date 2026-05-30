import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo


ACCOUNTS_FILE = "accounts.txt"
OUTPUT_DIR = "output"
POST_LIMIT = 3
TIMEZONE = "Asia/Jakarta"


def now_jakarta():
    return datetime.now(ZoneInfo(TIMEZONE)).isoformat()


def clean_username(username):
    username = username.strip()
    username = username.replace("@", "")
    username = username.replace("https://www.instagram.com/", "")
    username = username.replace("https://instagram.com/", "")
    username = username.strip("/")
    return username


def run_gallery_dl_url(url):
    command = [
        "gallery-dl",
        "--config",
        "gallery-dl.conf",
        "--dump-json",
        "--range",
        f"1-{POST_LIMIT}",
    ]

    if os.path.exists("cookies.txt"):
        command.extend(["--cookies", "cookies.txt"])

    command.append(url)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=240,
    )

    return result


def run_gallery_dl(username):
    urls = [
        f"https://www.instagram.com/{username}/posts/",
        f"https://www.instagram.com/{username}/reels/",
    ]

    combined_stdout = ""
    combined_stderr = ""
    return_code = 0

    for url in urls:
        print(f"Fetching URL: {url}")
        result = run_gallery_dl_url(url)

        combined_stdout += "\n" + result.stdout
        combined_stderr += "\n" + result.stderr

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
        # gallery-dl message type 2 = metadata/directory item
        if len(obj) >= 2 and obj[0] == 2 and isinstance(obj[1], dict):
            data = obj[1]
            data["_gallery_message_type"] = 2
            items.append(data)

        # gallery-dl message type 3 = actual downloadable media URL
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
    shortcode = get_first_string(
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

    if shortcode:
        return shortcode

    return ""


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


def normalize_item(data, username):
    shortcode = extract_shortcode(data)
    post_url = extract_post_url(data, shortcode)
    image_url = extract_image_url(data)
    caption = extract_caption(data)
    date = extract_date(data)

    is_reel = "/reel/" in post_url or str(data.get("subcategory", "")).lower() == "reels"
    is_video = bool(
        data.get("is_video")
        or data.get("video_url")
        or data.get("duration")
        or data.get("video")
        or data.get("video_versions")
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

        shortcode = item["shortcode"]
        post_url = item["url"]
        image_url = item["image_url"]

        key = shortcode or post_url or image_url

        if not key:
            continue

        if key not in merged:
            merged[key] = item
            continue

        # Lengkapi data yang masih kosong
        for field in ["url", "caption", "caption_short", "date", "image_url", "shortcode"]:
            if not merged[key].get(field) and item.get(field):
                merged[key][field] = item[field]

        merged[key]["is_video"] = bool(merged[key].get("is_video") or item.get("is_video"))
        merged[key]["is_reel"] = bool(merged[key].get("is_reel") or item.get("is_reel"))

    results = []

    for item in merged.values():
        if not item.get("url") and item.get("shortcode"):
            item["url"] = f"https://www.instagram.com/p/{item['shortcode']}/"

        results.append(item)

    return results


def process_account(username):
    print(f"Processing {username}...")

    account_result = {
        "username": username,
        "generated_at": now_jakarta(),
        "posts": [],
        "error": None,
    }

    try:
        result = run_gallery_dl(username)

        print(f"Return code {username}: {result.returncode}")
        print(f"STDOUT preview {username}: {result.stdout[:2500]}")
        print(f"STDERR preview {username}: {result.stderr[:2000]}")

        if result.returncode != 0:
            error_message = result.stderr.strip() or result.stdout.strip()
            account_result["error"] = error_message
            print(f"Error {username}: {error_message}")
            return account_result

        raw_items = parse_gallery_output(result.stdout)
        print(f"Raw items found {username}: {len(raw_items)}")

        merged_items = merge_items_by_post(raw_items, username)

        seen_keys = set()

        for item in merged_items:
            unique_key = item.get("url") or item.get("shortcode") or item.get("image_url")

            if not unique_key:
                continue

            if unique_key in seen_keys:
                continue

            seen_keys.add(unique_key)
            account_result["posts"].append(item)

            if len(account_result["posts"]) >= POST_LIMIT:
                break

    except Exception as e:
        account_result["error"] = str(e)
        print(f"Error {username}: {e}")

    return account_result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
        accounts = [clean_username(line) for line in file if line.strip()]

    index_data = {
        "generated_at": now_jakarta(),
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

    print("Done.")


if __name__ == "__main__":
    main()
