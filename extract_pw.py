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

# 🚀 Ultra-Fast RAM Disk Storage (16GB Runner RAM - Zero Disk Latency)
RAM_DISK = "/dev/shm/media"
MEDIA_DIR = RAM_DISK if os.path.exists("/dev/shm") else "/tmp/media"
os.makedirs(MEDIA_DIR, exist_ok=True)

# Cookie Path Auto-Detection
COOKIE_FILE = "cookies.txt" if os.path.exists("cookies.txt") else None

def get_base_ytdlp_args():
    args = [
        "yt-dlp",
        "--no-check-certificates",
        "--geo-bypass",
        "--no-warnings"
    ]
    if COOKIE_FILE:
        args.extend(["--cookies", COOKIE_FILE])
    return args

def extract_video_id(url):
    m = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else url

# ══════════════════════════════════════════════════════════════════
# 👑 ENGINE 2: PLAYWRIGHT HEADLESS CHROMIUM ENGINE (ZERO-COOKIE BYPASS)
# ══════════════════════════════════════════════════════════════════
def download_youtube_playwright(url, extract_type="video"):
    """
    Playwright Headless Chromium Engine.
    Simulates a real Chrome browser to bypass YouTube's datacenter bot walls.
    Loads the embed player, intercepts high-speed googlevideo streams, and saves directly to RAM.
    """
    video_id = extract_video_id(url)
    embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1"
    vurls = []
    aurls = []
    title = "YouTube Video"
    file_id = str(uuid.uuid4())[:10]
    ext = "mp3" if extract_type == "audio" else "mp4"
    out_file = f"{MEDIA_DIR}/{file_id}.{ext}"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        def on_request(request):
            u = request.url
            if "videoplayback" in u:
                if "mime=audio" in u or "itag=140" in u or "itag=251" in u:
                    if u not in aurls:
                        aurls.append(u)
                else:
                    if u not in vurls:
                        vurls.append(u)

        page.on("request", on_request)

        try:
            # 1. Navigate to embed URL
            page.goto(embed_url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(3000)

            # 2. Click play button if needed
            try:
                play_btn = page.query_selector("button.ytp-large-play-button, button[aria-label*='Play' i]")
                if play_btn:
                    play_btn.click()
                    page.wait_for_timeout(3000)
            except Exception:
                pass

            # 3. Extract metadata from DOM
            try:
                res_data = page.evaluate("""() => {
                    const d = window.ytInitialPlayerResponse || {};
                    const t = (d.videoDetails && d.videoDetails.title) || document.title;
                    const fmts = (d.streamingData && d.streamingData.formats) || [];
                    const prog = fmts.find(f => f.url && f.mimeType && f.mimeType.includes('video/mp4'));
                    return {
                        title: t,
                        direct_url: prog ? prog.url : null
                    };
                }""")
                if res_data:
                    if res_data.get("title"):
                        clean_t = re.sub(r"\s*-\s*YouTube.*$", "", res_data["title"], flags=re.IGNORECASE).strip()
                        if clean_t and clean_t != "YouTube":
                            title = clean_t
                    if res_data.get("direct_url") and not vurls:
                        vurls.insert(0, res_data["direct_url"])
            except Exception:
                pass

            # 4. If embed is restricted, fallback to mobile page
            if not vurls and not aurls:
                mobile_url = f"https://m.youtube.com/watch?v={video_id}"
                page.goto(mobile_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
                try:
                    p_btn = page.query_selector("button[aria-label*='Play' i], .video-thumbnail")
                    if p_btn:
                        p_btn.click()
                        page.wait_for_timeout(3000)
                except Exception:
                    pass

        except Exception as e:
            print(f"[Playwright Engine Warning]: {e}", file=sys.stderr)
        finally:
            browser.close()

    # 5. Download the captured stream using ffmpeg or yt-dlp
    target_stream = aurls[0] if (extract_type == "audio" and aurls) else (vurls[0] if vurls else (aurls[0] if aurls else None))
    if not target_stream:
        return {"success": False, "error": "Playwright could not capture video stream"}

    try:
        ua_header = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36\r\n"
        if extract_type == "audio":
            ff_cmd = [
                "ffmpeg", "-y",
                "-headers", ua_header,
                "-i", target_stream,
                "-vn", "-acodec", "libmp3lame", "-q:a", "2",
                out_file
            ]
        else:
            if vurls and aurls and vurls[0] != aurls[0]:
                ff_cmd = [
                    "ffmpeg", "-y",
                    "-headers", ua_header,
                    "-i", vurls[0],
                    "-headers", ua_header,
                    "-i", aurls[0],
                    "-c:v", "copy", "-c:a", "aac",
                    out_file
                ]
            else:
                ff_cmd = [
                    "ffmpeg", "-y",
                    "-headers", ua_header,
                    "-i", target_stream,
                    "-c", "copy",
                    out_file
                ]

        subprocess.run(ff_cmd, capture_output=True, text=True, timeout=60)
        if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
            return {
                "success": True,
                "title": title,
                "media_file": os.path.basename(out_file),
                "size_bytes": os.path.getsize(out_file)
            }
    except Exception as ex:
        print(f"[FFmpeg Warning]: {ex}", file=sys.stderr)

    # Secondary Stream Download via yt-dlp
    try:
        yt_cmd = ["yt-dlp", target_stream, "-o", out_file, "--no-playlist"]
        subprocess.run(yt_cmd, capture_output=True, text=True, timeout=45)
        if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
            return {
                "success": True,
                "title": title,
                "media_file": os.path.basename(out_file),
                "size_bytes": os.path.getsize(out_file)
            }
    except Exception:
        pass

    return {"success": False, "error": "Playwright stream could not be converted to file"}

# ══════════════════════════════════════════════════════════════════
# 👑 MAIN YOUTUBE DOWNLOAD ROUTER (HYBRID: DIRECT COOKIES ──► PLAYWRIGHT)
# ══════════════════════════════════════════════════════════════════
def download_youtube(url, extract_type="video"):
    """
    1. Primary: Fast Direct yt-dlp with cookies.txt (Instant 1-2s Download into RAM)
    2. Fallback: Playwright Headless Chromium Engine (100% Lifetime Zero-Cookie Bypass)
    """
    file_id = str(uuid.uuid4())[:10]
    ext = "mp3" if extract_type == "audio" else "mp4"
    out_tmpl = f"{MEDIA_DIR}/{file_id}.%(ext)s"

    title = "YouTube Video"

    # Multi-client priority: web_embedded -> tv_embedded -> ios -> android
    client_chains = [
        "web_embedded,ios",
        "tv_embedded,web_embedded",
        "ios,mweb",
        "android"
    ]

    # Step A: Fast Title Extraction
    for client in client_chains:
        try:
            t_cmd = get_base_ytdlp_args() + [
                "--extractor-args", f"youtube:player_client={client}",
                "--get-title",
                url
            ]
            t_res = subprocess.run(t_cmd, capture_output=True, text=True, timeout=10)
            if t_res.returncode == 0 and t_res.stdout.strip():
                first_line = t_res.stdout.strip().split('\n')[0].strip()
                if first_line and first_line != "YouTube":
                    title = first_line
                    break
        except Exception:
            pass

    # Step B: Fast yt-dlp Download Attempt into RAM (/dev/shm)
    for client in client_chains:
        if extract_type == "audio":
            cmd = get_base_ytdlp_args() + [
                "--extractor-args", f"youtube:player_client={client}",
                "-x", "--audio-format", "mp3",
                "--audio-quality", "192k",
                "-o", out_tmpl,
                "--no-playlist",
                url
            ]
        else:
            cmd = get_base_ytdlp_args() + [
                "--extractor-args", f"youtube:player_client={client}",
                "-f", "18/best[ext=mp4]/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best",
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
        except Exception:
            pass

    # Step C: If yt-dlp hit bot-check or failed, Trigger PLAYWRIGHT HEADLESS CHROMIUM ENGINE!
    print(f"⚠️ [yt-dlp Bot-Check Detected] Launching Playwright Headless Chromium Engine...", file=sys.stderr)
    pw_res = download_youtube_playwright(url, extract_type)
    if pw_res and pw_res.get("success"):
        return pw_res

    # Step D: Final Fallback - Direct Stream Link (-g)
    try:
        g_fmt = "ba/b" if extract_type == "audio" else "18/best"
        g_cmd = get_base_ytdlp_args() + [
            "-g", "-f", g_fmt,
            "--extractor-args", "youtube:player_client=web_embedded,ios",
            url
        ]
        g_res = subprocess.run(g_cmd, capture_output=True, text=True, timeout=12)
        if g_res.returncode == 0 and g_res.stdout.strip():
            stream_url = g_res.stdout.strip().split('\n')[0].strip()
            if stream_url.startswith("http"):
                return {
                    "success": True,
                    "title": title,
                    "video_url": stream_url,
                    "download_url": stream_url,
                    "size_bytes": 0
                }
    except Exception:
        pass

    return pw_res if pw_res else {"success": False, "error": "All YouTube extraction engines failed"}

def scrape_terabox(url):
    title = "TeraBox Video"
    vurls = []
    size_bytes = 0

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
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 Chrome/120.0.0.6099.210 Mobile Safari/537.36",
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
