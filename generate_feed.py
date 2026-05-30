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


def run_gallery_dl(username):
    url = f"https://www.instagram.com/{username}/"

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


def collect_dicts(obj):
    found = []

    if isinstance(obj, dict):
        found.append(obj)
        for value in obj.values():
            found.extend(collect_dicts(value))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_dicts(item))

    return found


def parse_gallery_output(stdout):
    stdout = stdout.strip()

    if not stdout:
        return []

    objects = []

    try:
        parsed = json.loads(stdout)
        objects.extend(collect_dicts(parsed))
        return objects
    except json.JSONDecodeError:
        pass

    for line in stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            parsed = json.loads(line)
            objects.extend(collect_dicts(parsed))
        except json.JSONDecodeError:
            continue

    return objects


def extract_shortcode(data):
    for key in ["shortcode", "code", "short_code"]:
        value = data.get(key)
        if value:
            return str(value)

    for key in ["post_url", "url", "webpage_url", "permalink", "display_url"]:
        post_url = data.get(key)

        if not isinstance(post_url, str):
            continue

        if "/p/" in post_url:
            return post_url.split("/p/")[1].split("/")[0]

        if "/reel/" in post_url:
            return post_url.split("/reel/")[1].split("/")[0]

    return ""


def extract_post_url(data, shortcode):
    for key in ["post_url", "webpage_url", "permalink"]:
        value = data.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value

    typename = str(data.get("__typename", "")).lower()
    is_reel = "reel" in typename or data.get("is_reel")

    if shortcode and is_reel:
        return f"https://www.instagram.com/reel/{shortcode}/"

    if shortcode:
        return f"https://www.instagram.com/p/{shortcode}/"

    return ""


def extract_image_url(data):
    for key in [
        "display_url",
        "thumbnail_src",
        "thumbnail",
        "thumbnail_url",
        "image",
        "image_url",
        "url",
    ]:
        value = data.get(key)

        if isinstance(value, str) and value.startswith("http"):
            return value

    return ""


def extract_caption(data):
    for key in ["description", "caption", "title", "edge_media_to_caption"]:
        value = data.get(key)

        if isinstance(value, str):
            return value

        if isinstance(value, dict):
            edges = value.get("edges")
            if isinstance(edges, list) and edges:
                node = edges[0].get("node", {})
                text = node.get("text")
                if isinstance(text, str):
                    return text

    return ""


def extract_date(data):
    for key in ["date", "timestamp", "datetime", "taken_at_timestamp"]:
        value = data.get(key)

        if value:
            return str(value)

    return ""


def looks_like_media_item(data):
    shortcode = extract_shortcode(data)
    image_url = extract_image_url(data)
    post_url = extract_post_url(data, shortcode)

    if shortcode and (image_url or post_url):
        return True

    return False


def normalize_item(data, username):
    shortcode = extract_shortcode(data)
    post_url = extract_post_url(data, shortcode)
    image_url = extract_image_url(data)
    caption = extract_caption(data)
    date = extract_date(data)

    is_reel = "/reel/" in post_url
    is_video = bool(
        data.get("is_video")
        or data.get("video_url")
        or data.get("duration")
        or data.get("video")
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
        print(f"STDOUT preview {username}: {result.stdout[:1200]}")
        print(f"STDERR preview {username}: {result.stderr[:1200]}")

        if result.returncode != 0:
            error_message = result.stderr.strip() or result.stdout.strip()
            account_result["error"] = error_message
            print(f"Error {username}: {error_message}")
            return account_result

        objects = parse_gallery_output(result.stdout)
        seen_keys = set()

        for data in objects:
            if not looks_like_media_item(data):
                continue

            item = normalize_item(data, username)

            unique_key = item["url"] or item["image_url"] or item["shortcode"]

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
