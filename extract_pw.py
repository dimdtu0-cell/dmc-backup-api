import sys
import json
import subprocess
from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else ""
extract_type = sys.argv[2] if len(sys.argv) > 2 else "video"

if not url:
    print(json.dumps({"error": "No URL provided"}))
    sys.exit(1)

def try_ytdlp(url, extract_type):
    try:
        # Fast 1-2s extraction via yt-dlp first
        fmt = "ba/b" if extract_type == "audio" else "b/bv*+ba/b"
        cmd = ["yt-dlp", "-g", "-f", fmt, url]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        if res.returncode == 0 and res.stdout.strip():
            stream_url = res.stdout.strip().split('\n')[0]
            t_res = subprocess.run(["yt-dlp", "--get-title", url], capture_output=True, text=True, timeout=6)
            title = t_res.stdout.strip() if t_res.returncode == 0 and t_res.stdout.strip() else "YouTube Media"
            return {"title": title, "video_url": stream_url}
    except Exception:
        pass
    return None

def extract_playwright(url, extract_type):
    video_url = None
    audio_url = None
    title = "YouTube Video"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def handle_request(request):
            nonlocal video_url, audio_url
            r_url = request.url
            if "googlevideo.com/videoplayback" in r_url:
                if "mime=audio" in r_url or "mime%3Daudio" in r_url:
                    if not audio_url:
                        audio_url = r_url
                else:
                    if not video_url:
                        video_url = r_url

        page.on("request", handle_request)

        try:
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            title = page.title().replace(" - YouTube", "")
        except Exception:
            pass
        finally:
            browser.close()

    target_stream = audio_url if (extract_type == "audio" and audio_url) else (video_url or audio_url)
    if target_stream:
        return {"title": title, "video_url": target_stream}
    return None

if __name__ == "__main__":
    # 1. First try superfast yt-dlp
    result = try_ytdlp(url, extract_type)
    
    # 2. If blocked, fallback to Playwright Chromium Unblocker
    if not result:
        result = extract_playwright(url, extract_type)
        
    if result and result.get("video_url"):
        print(json.dumps(result))
    else:
        print(json.dumps({"error": "Stream not found"}))
