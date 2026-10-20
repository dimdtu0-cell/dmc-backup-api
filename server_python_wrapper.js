const express = require('express');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const app = express();

app.use(express.json());

const MEDIA_DIR = '/tmp/media';
if (!fs.existsSync(MEDIA_DIR)) {
    fs.mkdirSync(MEDIA_DIR, { recursive: true });
}

// 1. Playable Static Media Server (Serves pure MP4/MP3 to WhatsApp)
app.use('/media', express.static(MEDIA_DIR));

// 2. Auto Cleanup: Delete files older than 30 minutes (plenty of time for large movies)
setInterval(() => {
    try {
        const files = fs.readdirSync(MEDIA_DIR);
        const now = Date.now();
        files.forEach(file => {
            const filePath = path.join(MEDIA_DIR, file);
            const stats = fs.statSync(filePath);
            if (now - stats.mtimeMs > 30 * 60 * 1000) {
                fs.unlinkSync(filePath);
            }
        });
    } catch (e) {}
}, 10 * 60 * 1000);

// Helper to execute Python extractor with 10-Minute Timeout for Movies / 1080p
function runExtractor(mode, url, opt = 'video') {
    return new Promise((resolve) => {
        const cmd = `python3 extract_pw.py "${mode}" "${url}" "${opt}"`;
        exec(cmd, { timeout: 600000, maxBuffer: 100 * 1024 * 1024 }, (error, stdout, stderr) => {
            if (error) {
                console.error(`[Extractor Error] Mode: ${mode} -`, stderr || error.message);
            }
            try {
                const lines = (stdout || '').trim().split('\n');
                const lastJsonLine = lines[lines.length - 1];
                const parsed = JSON.parse(lastJsonLine);
                resolve(parsed);
            } catch (parseErr) {
                resolve({ 
                    success: false, 
                    error: stderr || error?.message || 'Failed to parse extractor output' 
                });
            }
        });
    });
}

// 3. YouTube Route: Returns direct playable file URL over Cloudflare
app.get('/api/info', async (req, res) => {
    const url = req.query.url;
    const type = req.query.type || 'video';
    if (!url) return res.status(400).json({ success: false, error: 'URL query parameter is required' });

    console.log(`📡 [YouTube Request] Downloading ${type} for: ${url}`);
    const data = await runExtractor('youtube', url, type);

    if (data && data.success && data.media_file) {
        const host = req.headers['x-forwarded-host'] || req.headers['host'];
        const proto = req.headers['x-forwarded-proto'] || 'https';
        const fileUrl = `${proto}://${host}/media/${data.media_file}`;

        data.download_url = fileUrl;
        data.video_url = fileUrl;
    }

    res.json(data);
});

// 4. TeraBox Route
app.get('/api/terabox', async (req, res) => {
    const url = req.query.url;
    if (!url) return res.status(400).json({ success: false, error: 'URL query parameter is required' });

    console.log(`📦 [TeraBox Request] URL: ${url}`);
    const data = await runExtractor('terabox', url);
    res.json(data);
});

// 5. DiskWala Route
app.get('/api/diskwala', async (req, res) => {
    const url = req.query.url;
    if (!url) return res.status(400).json({ success: false, error: 'URL query parameter is required' });

    console.log(`🎬 [DiskWala Request] URL: ${url}`);
    const data = await runExtractor('diskwala', url);
    res.json(data);
});

// 6. Health Check Route
app.get(['/', '/health'], (req, res) => {
    res.json({
        status: 'online',
        service: 'DMC™ Backup Downloader Runner (Fast Media Server)',
        engines: {
            youtube: 'yt-dlp Multi-Client + Playwright Chromium + Fast CDN (Unlimited Movie Support)',
            terabox: 'Fast API + Playwright Chromium',
            diskwala: 'Playwright Chromium Mobile/Desktop'
        },
        uptime: process.uptime(),
        timestamp: new Date().toISOString()
    });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 DMC Backup Downloader API listening on port ${PORT}`);
});
