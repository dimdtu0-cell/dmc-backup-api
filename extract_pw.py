import sys
import json
import re
import subprocess
from playwright.sync_api import sync_playwright

def try_ytdlp(url, extract_type):
    try:
        fmt = "ba/b" if extract_type == "audio" else "b/bv*+ba/b"
        cmd = ["yt-dlp", "-g", "-f", fmt, url]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        if res.returncode == 0 and res.stdout.strip():
            stream_url = res.stdout.strip().split('\n')[0]
            t_res = subprocess.run(["yt-dlp", "--get-title", url], capture_output=True, text=True, timeout=6)
            title = t_res.stdout.strip() if t_res.returncode == 0 and t_res.stdout.strip() else "YouTube Media"
            return {"success": True, "title": title, "video_url": stream_url}
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
        return {"success": True, "title": title, "video_url": target_stream}
    return None

def scrape_terabox(url):
    title = "TeraBox Video"
    vurls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        def on_response(response):
            try:
                u = response.url.lower()
                ct = (response.headers.get("content-type") or "").lower()
                if (any(e in u for e in [".mp4", ".m3u8", ".mkv", ".webm"]) or "video" in ct or "dlink" in u) and response.status < 400:
                    vurls.append(response.url)
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(4000)

            try:
                btn = page.query_selector("button[class*='play'], .play-btn, [aria-label*='play' i]")
                if btn:
                    btn.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            try:
                js = page.evaluate("() => [window.__dlink, window.dlink, window.videoUrl, window.video_url].filter(Boolean)[0] || null")
                if js and str(js).startswith("http"):
                    vurls.insert(0, js)
            except Exception:
                pass

            try:
                t = page.title()
                title = re.sub(r"\s*[-|]\s*TeraBox.*$", "", t, flags=re.IGNORECASE).strip() or "TeraBox Video"
            except Exception:
                pass
        except Exception:
            pass
        finally:
            browser.close()

    if vurls:
        fu = next((v for v in vurls if ".mp4" in v.lower()), vurls[0])
        return {"success": True, "title": title, "video_url": fu}
    return {"error": "No direct video stream found for TeraBox"}

def scrape_diskwala(url):
    title = "DiskWala Video"
    vurls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 Chrome/120.0.6099.210 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915}
        )
        page = context.new_page()

        def on_response(response):
            try:
                u = response.url.lower()
                ct = (response.headers.get("content-type") or "").lower()
                if (any(e in u for e in [".mp4", ".m3u8", ".webm"]) or "video" in ct or "stream" in u) and response.status < 400 and "diskwala.com" not in u:
                    vurls.append(response.url)
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(3000)

            try:
                for sel in ["button[class*='play']", ".video-play-button", "video"]:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click()
                        page.wait_for_timeout(2000)
                        break
            except Exception:
                pass

            try:
                t = page.title()
                title = re.sub(r"\s*[-|]\s*(?:DiskWala|Disk Wala).*$", "", t, flags=re.IGNORECASE).strip() or "DiskWala Video"
            except Exception:
                pass
        except Exception:
            pass
        finally:
            browser.close()

    if vurls:
        fu = next((v for v in vurls if ".mp4" in v.lower()), vurls[0])
        return {"success": True, "title": title, "video_url": fu}
    return {"error": "No video stream found for DiskWala"}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "youtube"
    target_url = sys.argv[2] if len(sys.argv) > 2 else ""
    opt = sys.argv[3] if len(sys.argv) > 3 else "video"

    # Backward compatibility
    if mode.startswith("http://") or mode.startswith("https://"):
        target_url = mode
        opt = sys.argv[2] if len(sys.argv) > 2 else "video"
        mode = "youtube"

    if not target_url:
        print(json.dumps({"error": "No URL provided"}))
        sys.exit(1)

    if mode == "terabox":
        res = scrape_terabox(target_url)
    elif mode == "diskwala":
        res = scrape_diskwala(target_url)
    else:
        res = try_ytdlp(target_url, opt)
        if not res:
            res = extract_playwright(target_url, opt)

    if res and (res.get("video_url") or res.get("download_url")):
        download_url = res.get("video_url") or res.get("download_url")
        print(json.dumps({"success": True, "title": res.get("title", "Media"), "video_url": download_url}))
    else:
        err = res.get("error") if res else "Extraction failed"
        print(json.dumps({"error": err}))
