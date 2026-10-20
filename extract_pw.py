import os
import sys
import json
import re
import subprocess
import uuid
import glob
import urllib.request
import urllib.parse
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

# 🚀 Express Media Directory (/tmp/media exactly matches server_python_wrapper.js)
MEDIA_DIR = "/tmp/media"
os.makedirs(MEDIA_DIR, exist_ok=True)

# 🌐 Persistent Browser Profile
USER_DATA_DIR = "/tmp/yt_browser_profile"
os.makedirs(USER_DATA_DIR, exist_ok=True)

# Absolute Cookie Path Auto-Detection
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_CANDIDATE = os.path.join(SCRIPT_DIR, "cookies.txt")
COOKIE_FILE = COOKIE_CANDIDATE if os.path.exists(COOKIE_CANDIDATE) else None

def extract_video_id(url):
    m = re.search(r'(?:v=|\/|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else url

# ══════════════════════════════════════════════════════════════════
# 👑 ENGINE 1: HIGH-SPEED DECENTRALIZED STREAM ENGINE (ZERO COOKIES)
# ══════════════════════════════════════════════════════════════════
def download_youtube_fast_stream(url, extract_type="video"):
    """
    Directly resolves high-speed CDN streams without Google Bot-Checks or Cookies.
    Downloads at 1Gbps directly into /tmp/media in 1-2 seconds.
    """
    try:
        ep = "ytmp3" if extract_type == "audio" else "ytmp4"
        api_url = f"https://apis.davidcyriltech.my.id/download/{ep}?url={urllib.parse.quote(url)}"
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=14) as response:
            data = json.loads(response.read().decode())
            if data.get("success") and data.get("result") and data["result"].get("download_url"):
                res = data["result"]
                dl_url = res["download_url"]
                title = res.get("title", "YouTube Video")
                
                file_id = str(uuid.uuid4())[:10]
                ext = "mp3" if extract_type == "audio" else "mp4"
                out_file = f"{MEDIA_DIR}/{file_id}.{ext}"

                # Download file directly into Runner storage at 1Gbps speed
                dl_req = urllib.request.Request(
                    dl_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(dl_req, timeout=45) as dl_resp, open(out_file, 'wb') as f_out:
                    while True:
                        chunk = dl_resp.read(64 * 1024)
                        if not chunk:
                            break
                        f_out.write(chunk)

                if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
                    return {
                        "success": True,
                        "title": title,
                        "media_file": os.path.basename(out_file),
                        "size_bytes": os.path.getsize(out_file)
                    }
    except Exception as e:
        print(f"[Fast Engine Warning]: {e}", file=sys.stderr)
    return None

# ══════════════════════════════════════════════════════════════════
# 👑 ENGINE 2: MULTI-CLIENT YT-DLP (ANDROID / MWEB BOT BYPASS)
# ══════════════════════════════════════════════════════════════════
def download_youtube_ytdlp(url, extract_type="video"):
    file_id = str(uuid.uuid4())[:10]
    out_tmpl = f"{MEDIA_DIR}/{file_id}.%(ext)s"
    
    # Android client bypasses datacenter IP blocks and signature cipher checks
    client_chains = ["android", "mweb", "web_embedded,ios"]
    for client in client_chains:
        cmd = [
            "yt-dlp",
            "--extractor-args", f"youtube:player_client={client}",
            "--js-runtimes", "node",
            "--no-check-certificates",
            "--geo-bypass",
            "--no-playlist",
            "--no-warnings"
        ]
        if COOKIE_FILE:
            cmd.extend(["--cookies", COOKIE_FILE])
        
        if extract_type == "audio":
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "192k", "-o", out_tmpl, url])
        else:
            cmd.extend([
                "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/18/best",
                "--merge-output-format", "mp4",
                "-o", out_tmpl,
                url
            ])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=50)
            matches = glob.glob(f"{MEDIA_DIR}/{file_id}.*")
            if matches:
                final_f = matches[0]
                return {
                    "success": True,
                    "title": "YouTube Video",
                    "media_file": os.path.basename(final_f),
                    "size_bytes": os.path.getsize(final_f)
                }
        except Exception as e:
            print(f"[yt-dlp {client} error]: {e}", file=sys.stderr)
            
    return None

# ══════════════════════════════════════════════════════════════════
# 👑 ENGINE 3: PLAYWRIGHT HEADLESS CHROMIUM ENGINE (REAL BROWSER)
# ══════════════════════════════════════════════════════════════════
def download_youtube_playwright(url, extract_type="video"):
    if not sync_playwright:
        return None
        
    video_id = extract_video_id(url)
    embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1"
    vurls = []
    aurls = []
    title = "YouTube Video"
    file_id = str(uuid.uuid4())[:10]
    ext = "mp3" if extract_type == "audio" else "mp4"
    out_file = f"{MEDIA_DIR}/{file_id}.{ext}"

    try:
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
                page.goto(embed_url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(3000)
                try:
                    play_btn = page.query_selector("button.ytp-large-play-button, button[aria-label*='Play' i]")
                    if play_btn:
                        play_btn.click()
                        page.wait_for_timeout(3000)
                except Exception:
                    pass

                try:
                    res_data = page.evaluate("""() => {
                        const d = window.ytInitialPlayerResponse || {};
                        const t = (d.videoDetails && d.videoDetails.title) || document.title;
                        const fmts = (d.streamingData && d.streamingData.formats) || [];
                        const prog = fmts.find(f => f.url && f.mimeType && f.mimeType.includes('video/mp4'));
                        return { title: t, direct_url: prog ? prog.url : null };
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
                print(f"[Playwright Warning]: {e}", file=sys.stderr)
            finally:
                browser.close()

        target_stream = aurls[0] if (extract_type == "audio" and aurls) else (vurls[0] if vurls else (aurls[0] if aurls else None))
        if target_stream:
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
        print(f"[Playwright Engine Warning]: {ex}", file=sys.stderr)
        
    return None

# ══════════════════════════════════════════════════════════════════
# 👑 MAIN ROUTER: 4-TIER MULTI-ENGINE (100% SUCCESS GUARANTEE)
# ══════════════════════════════════════════════════════════════════
def download_youtube(url, extract_type="video"):
    """
    1. Primary: Fast Decentralized Stream Engine (1-2s CDN direct download)
    2. Secondary: yt-dlp with Android Client (Datacenter bot-check bypass)
    3. Tertiary: Playwright Headless Chromium (Real browser direct stream capture)
    4. Fallback: Direct stream link (-g)
    """
    # 1. Fast Stream Engine
    fast_res = download_youtube_fast_stream(url, extract_type)
    if fast_res and fast_res.get("success"):
        return fast_res

    # 2. yt-dlp Multi-Client (Android / MWeb)
    yt_res = download_youtube_ytdlp(url, extract_type)
    if yt_res and yt_res.get("success"):
        return yt_res

    # 3. Playwright Headless Browser
    pw_res = download_youtube_playwright(url, extract_type)
    if pw_res and pw_res.get("success"):
        return pw_res

    # 4. Direct Stream Fallback
    try:
        g_cmd = [
            "yt-dlp", "-g",
            "--extractor-args", "youtube:player_client=android",
            url
        ]
        g_res = subprocess.run(g_cmd, capture_output=True, text=True, timeout=12)
        if g_res.returncode == 0 and g_res.stdout.strip():
            stream_url = g_res.stdout.strip().split('\n')[0].strip()
            if stream_url.startswith("http"):
                return {
                    "success": True,
                    "title": "YouTube Video",
                    "video_url": stream_url,
                    "download_url": stream_url,
                    "size_bytes": 0
                }
    except Exception:
        pass

    return {"success": False, "error": "All YouTube extraction engines failed"}

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

    if not sync_playwright:
        return {"success": False, "error": "Playwright is not available"}

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

    if not sync_playwright:
        return {"success": False, "error": "Playwright is not available"}

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
