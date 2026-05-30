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
        "--dump-json",
        "--range",
        f"1-{POST_LIMIT}",
        url,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=180,
    )

    return result


def extract_shortcode(data):
    for key in ["shortcode", "code"]:
        if data.get(key):
            return data.get(key)

    post_url = data.get("post_url") or data.get("url") or data.get("webpage_url") or ""
    if "/p/" in post_url:
        return post_url.split("/p/")[1].split("/")[0]
    if "/reel/" in post_url:
        return post_url.split("/reel/")[1].split("/")[0]

    return ""


def extract_post_url(data, shortcode):
    for key in ["post_url", "webpage_url", "permalink"]:
        if data.get(key):
            return data.get(key)

    if shortcode:
        return f"https://www.instagram.com/p/{shortcode}/"

    return ""


def extract_image_url(data):
    for key in ["display_url", "thumbnail", "thumbnail_url", "image", "url"]:
        value = data.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value

    return ""


def extract_caption(data):
    for key in ["description", "caption", "title"]:
        value = data.get(key)
        if isinstance(value, str):
            return value

    return ""


def extract_date(data):
    for key in ["date", "timestamp", "datetime"]:
        value = data.get(key)
        if value:
            return str(value)

    return ""


def normalize_item(data, username):
    shortcode = extract_shortcode(data)
    url = extract_post_url(data, shortcode)
    caption = extract_caption(data)
    image_url = extract_image_url(data)
    date = extract_date(data)

    is_reel = "/reel/" in url
    is_video = bool(data.get("is_video") or data.get("video_url") or data.get("duration"))

    return {
        "username": username,
        "shortcode": shortcode,
        "url": url,
        "caption": caption,
        "caption_short": caption[:180] if caption else "",
        "date": date,
        "image_url": image_url,
        "is_video": is_video,
        "is_reel": is_reel,
    }


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
        print(f"Processing {username}...")

        account_result = {
            "username": username,
            "generated_at": now_jakarta(),
            "posts": [],
            "error": None,
        }

        try:
            result = run_gallery_dl(username)

            if result.returncode != 0:
                account_result["error"] = result.stderr.strip() or result.stdout.strip()
                print(f"Error {username}: {account_result['error']}")
            else:
                lines = [line for line in result.stdout.splitlines() if line.strip()]

                seen_urls = set()

                for line in lines:
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    item = normalize_item(data, username)

                    if not item["url"] and not item["image_url"]:
                        continue

                    unique_key = item["url"] or item["image_url"]

                    if unique_key in seen_urls:
                        continue

                    seen_urls.add(unique_key)
                    account_result["posts"].append(item)

                    if len(account_result["posts"]) >= POST_LIMIT:
                        break

        except Exception as e:
            account_result["error"] = str(e)
            print(f"Error {username}: {e}")

        output_path = os.path.join(OUTPUT_DIR, f"{username}.json")

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(account_result, file, ensure_ascii=False, indent=2)

        index_data["accounts"].append({
            "username": username,
            "file": f"{username}.json",
            "post_count": len(account_result["posts"]),
            "error": account_result["error"],
        })

    with open(os.path.join(OUTPUT_DIR, "index.json"), "w", encoding="utf-8") as file:
        json.dump(index_data, file, ensure_ascii=False, indent=2)

    print("Done.")


if __name__ == "__main__":
    main()
