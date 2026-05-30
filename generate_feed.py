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


def parse_gallery_output(stdout):
    items = []

    for line in stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue

        if (
            isinstance(parsed, list)
            and len(parsed) >= 2
            and parsed[0] == 2
            and isinstance(parsed[1], dict)
        ):
            items.append(parsed[1])

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
            "shortcode",
            "short_code",
            "code",
            "display_id",
        ],
    )

    if shortcode:
        return shortcode

    post_id = str(data.get("post_id") or data.get("id") or "")

    if post_id and "_" in post_id:
        return post_id.split("_")[0]

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

    typename = str(data.get("__typename", "")).lower()
    media_type = str(data.get("type") or data.get("typename") or "").lower()
    is_reel = "reel" in typename or "reel" in media_type or bool(data.get("is_reel"))

    if shortcode and is_reel:
        return f"https://www.instagram.com/reel/{shortcode}/"

    if shortcode:
        return f"https://www.instagram.com/p/{shortcode}/"

    return ""


def extract_image_url(data):
    image = get_first_string(
        data,
        [
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

    return ""


def extract_caption(data):
    caption = get_first_string(
        data,
        [
            "description",
            "caption",
            "title",
        ],
    )

    return caption


def extract_date(data):
    date = get_first_string(
        data,
        [
            "date",
            "datetime",
            "timestamp",
            "taken_at_timestamp",
        ],
    )

    return date


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
        print(f"STDOUT preview {username}: {result.stdout[:2000]}")
        print(f"STDERR preview {username}: {result.stderr[:2000]}")

        if result.returncode != 0:
            error_message = result.stderr.strip() or result.stdout.strip()
            account_result["error"] = error_message
            print(f"Error {username}: {error_message}")
            return account_result

        raw_items = parse_gallery_output(result.stdout)
        seen_keys = set()

        for data in raw_items:
            item = normalize_item(data, username)

            unique_key = item["url"] or item["image_url"] or item["shortcode"]

            if not unique_key:
                continue

            if unique_key in seen_keys:
                continue

            seen_keys.add(unique_key)

            if not item["image_url"]:
                continue

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
