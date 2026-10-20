import os
import sys
import json
import re
import subprocess
import uuid
import glob
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

MEDIA_DIR = "/tmp/media"
os.makedirs(MEDIA_DIR, exist_ok=True)

def download_youtube(url, extract_type="video"):
    """
    Downloads YouTube video/audio directly on the runner with 1Gbps speed.
    Bypasses Google Video IP-lock completely by outputting clean MP4/MP3.
    """
    file_id = str(uuid.uuid4())[:10]
    out_tmpl = f"{MEDIA_DIR}/{file_id}.%(ext)s"

    title = "YouTube Video"
    try:
        t_res = subprocess.run(
            ["yt-dlp", "--extractor-args", "youtube:player_client=android,web", "--get-title", url],
            capture_output=True, text=True, timeout=10
        )
        if t_res.returncode == 0 and t_res.stdout.strip():
            title = t_res.stdout.strip().split('\n')[0]
    except Exception:
        pass

    if extract_type == "audio":
        cmd = [
            "yt-dlp",
            "--extractor-args", "youtube:player_client=android,web",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "192k",
            "-o", out_tmpl,
            "--no-playlist",
            url
        ]
    else:
        cmd = [
            "yt-dlp",
            "--extractor-args", "youtube:player_client=android,web",
            "-f", "18/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", out_tmpl,
            "--no-playlist",
            url
        ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=50)
        matches = glob.glob(f"{MEDIA_DIR}/{file_id}.*")
        if matches:
            final_file = matches[0]
            size = os.path.getsize(final_file)
            filename = os.path.basename(final_file)
            return {
                "success": True,
                "title": title,
                "media_file": filename,
                "size_bytes": size
            }
        else:
            err_msg = res.stderr.strip()[:250] if res.stderr else "Download failed"
            return {"success": False, "error": err_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}

def scrape_terabox(url):
    title = "TeraBox Video"
    vurls = []
    size_bytes = 0

    # 1. Fast API Extraction
    try:
        surl_match = re.search(r'(?:/s/|surl=)([a-zA-Z0-9_-]+)', url)
        if surl_match:
            surl = surl_match.group(1).lstrip('1')
            api_endpoint = f"https://www.terabox.app/api/shorturlinfo?shorturl={surl}&root=1"
            req = urllib.request.Request(
                api_endpoint,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get("errno") == 0 and data.get("list"):
                    first_file = data["list"][0]
                    dl = first_file.get("dlink")
                    if dl and dl.startswith("http"):
                        return {
                            "success": True,
                            "title": first_file.get("server_filename", "TeraBox Video"),
                            "video_url": dl,
                            "download_url": dl,
                            "size_bytes": int(first_file.get("size", 0))
                        }
    except Exception:
        pass

    # 2. Playwright Headless Chromium Scraper
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        def on_response(response):
            nonlocal size_bytes, title
            try:
                u = response.url.lower()
                ct = (response.headers.get("content-type") or "").lower()
                if "application/json" in ct and ("shorturlinfo" in u or "share/list" in u or "fileinfo" in u):
                    try:
                        j = response.json()
                        file_items = j.get("list") or (j.get("data") and j.get("data").get("list")) or []
                        for item in file_items:
                            if item.get("dlink"):
                                vurls.insert(0, item["dlink"])
                                if item.get("server_filename"):
                                    title = item["server_filename"]
                                if item.get("size"):
                                    size_bytes = int(item["size"])
                    except Exception:
                        pass

                if (any(e in u for e in [".mp4", ".m3u8", ".mkv", ".webm"]) or "video" in ct or "dlink" in u) and response.status < 400:
                    vurls.append(response.url)
            except Exception:
                pass

        page.on("response", on_response)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(4000)

            try:
                for sel in ["button[class*='play']", ".play-btn", "[aria-label*='play' i]", ".download-btn", "button[class*='download']"]:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click()
                        page.wait_for_timeout(2000)
                        break
            except Exception:
                pass

            try:
                js_data = page.evaluate("""() => {
                    const d = window.__INITIAL_STATE__ || window.yunData || window.data || {};
                    const list = d.file_list || d.list || (d.file && [d.file]) || [];
                    if (list.length > 0 && list[0].dlink) {
                        return { dlink: list[0].dlink, title: list[0].server_filename, size: list[0].size };
                    }
                    const fallback = [window.__dlink, window.dlink, window.videoUrl, window.video_url].filter(Boolean)[0];
                    return fallback ? { dlink: fallback } : null;
                }""")
                if js_data and js_data.get("dlink"):
                    vurls.insert(0, js_data["dlink"])
                    if js_data.get("title"):
                        title = js_data["title"]
                    if js_data.get("size"):
                        size_bytes = int(js_data["size"])
            except Exception:
                pass

            try:
                content = page.content()
                dlink_m = re.search(r'["\']dlink["\']\s*:\s*["\']([^"\']+)["\']', content)
                if dlink_m:
                    clean_dl = dlink_m.group(1).replace(r'\/', '/').replace(r'\u0026', '&')
                    if clean_dl.startswith('http'):
                        vurls.insert(0, clean_dl)

                fn_m = re.search(r'["\']server_filename["\']\s*:\s*["\']([^"\']+)["\']', content)
                if fn_m:
                    title = fn_m.group(1).encode().decode('unicode-escape')

                sz_m = re.search(r'["\']size["\']\s*:\s*["\']?(\d+)["\']?', content)
                if sz_m and size_bytes == 0:
                    size_bytes = int(sz_m.group(1))

                t = page.title()
                if t and "TeraBox" in t:
                    parsed_t = re.sub(r"\s*[-|]\s*TeraBox.*$", "", t, flags=re.IGNORECASE).strip()
                    if parsed_t:
                        title = parsed_t
            except Exception:
                pass
        except Exception:
            pass
        finally:
            browser.close()

    if vurls:
        fu = next((v for v in vurls if ".mp4" in v.lower()), vurls[0])
        fu = fu.replace(r'\/', '/').replace(r'\u0026', '&')
        return {
            "success": True,
            "title": title or "TeraBox Video",
            "video_url": fu,
            "download_url": fu,
            "size_bytes": size_bytes
        }

    return {"success": False, "error": "No direct video stream found for TeraBox"}

def scrape_diskwala(url):
    title = "DiskWala Video"
    vurls = []
    size_bytes = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 Chrome/120.0.6099.210 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915}
        )
        page = context.new_page()

        def on_response(response):
            try:
                u = response.url.lower()
                ct = (response.headers.get("content-type") or "").lower()
                if (any(e in u for e in [".mp4", ".m3u8", ".webm"]) or "video" in ct or "stream" in u or "application/x-mpegurl" in ct) and response.status < 400 and "diskwala.com" not in u:
                    vurls.append(response.url)
            except Exception:
                pass

        page.on("response", on_response)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(3000)

            try:
                for sel in ["button[class*='play']", ".video-play-button", "video", ".play", "a[class*='play']"]:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click()
                        page.wait_for_timeout(2000)
                        break
            except Exception:
                pass

            try:
                player_stream = page.evaluate("""() => {
                    const v = document.querySelector('video') || document.querySelector('source');
                    if (v && v.src && v.src.startsWith('http')) return v.src;
                    if (window.player && typeof window.player.getPlaylist === 'function') {
                        const pl = window.player.getPlaylist();
                        if (pl && pl[0] && pl[0].file) return pl[0].file;
                    }
                    return null;
                }""")
                if player_stream:
                    vurls.insert(0, player_stream)
            except Exception:
                pass

            try:
                content = page.content()
                stream_m = re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)(?:\?[^\s"\'<>]*)?', content)
                for s in stream_m:
                    if "diskwala.com" not in s.lower() and s not in vurls:
                        vurls.append(s)

                t = page.title()
                if t:
                    parsed_t = re.sub(r"\s*[-|]\s*(?:DiskWala|Disk Wala).*$", "", t, flags=re.IGNORECASE).strip()
                    if parsed_t:
                        title = parsed_t
            except Exception:
                pass
        except Exception:
            pass
        finally:
            browser.close()

    if vurls:
        fu = next((v for v in vurls if ".mp4" in v.lower()), vurls[0])
        fu = fu.replace(r'\/', '/').replace(r'\u0026', '&')
        return {
            "success": True,
            "title": title or "DiskWala Video",
            "video_url": fu,
            "download_url": fu,
            "size_bytes": size_bytes
        }

    return {"success": False, "error": "No video stream found for DiskWala"}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "youtube"
    target_url = sys.argv[2] if len(sys.argv) > 2 else ""
    opt = sys.argv[3] if len(sys.argv) > 3 else "video"

    if mode.startswith("http://") or mode.startswith("https://"):
        target_url = mode
        opt = sys.argv[2] if len(sys.argv) > 2 else "video"
        lower_u = target_url.lower()
        if any(d in lower_u for d in ["terabox", "1024tera", "mirrobox", "nephobox"]):
            mode = "terabox"
        elif "diskwala" in lower_u:
            mode = "diskwala"
        else:
            mode = "youtube"

    if not target_url:
        print(json.dumps({"success": False, "error": "No URL provided"}))
        sys.exit(1)

    if mode == "terabox":
        res = scrape_terabox(target_url)
    elif mode == "diskwala":
        res = scrape_diskwala(target_url)
    else:
        res = download_youtube(target_url, opt)

    print(json.dumps(res))
