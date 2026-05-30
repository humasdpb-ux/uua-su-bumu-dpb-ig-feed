import json
import os
from datetime import datetime, timezone

import instaloader


ACCOUNTS_FILE = "accounts.txt"
OUTPUT_DIR = "output"
POST_LIMIT = 6


def clean_username(username):
    username = username.strip()
    username = username.replace("@", "")
    return username


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ig_username = os.getenv("IG_USERNAME")
    ig_password = os.getenv("IG_PASSWORD")

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )

    if ig_username and ig_password:
        print("Login Instagram menggunakan GitHub Secrets...")
        try:
            loader.login(ig_username, ig_password)
            print("Login berhasil.")
        except Exception as e:
            print(f"Login gagal: {e}")
    else:
        print("IG_USERNAME atau IG_PASSWORD belum tersedia. Lanjut tanpa login.")

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
        accounts = [clean_username(line) for line in file if line.strip()]

    index_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_accounts": len(accounts),
        "accounts": [],
    }

    for username in accounts:
        print(f"Processing {username}...")

        account_result = {
            "username": username,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "posts": [],
            "error": None,
        }

        try:
            profile = instaloader.Profile.from_username(loader.context, username)

            for post in profile.get_posts():
                if len(account_result["posts"]) >= POST_LIMIT:
                    break

                caption = post.caption or ""

                account_result["posts"].append({
                    "shortcode": post.shortcode,
                    "url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "caption": caption,
                    "caption_short": caption[:180],
                    "date": post.date_utc.isoformat(),
                    "image_url": post.url,
                    "is_video": post.is_video,
                    "likes": post.likes,
                    "comments": post.comments,
                })

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
