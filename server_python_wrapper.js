const express = require('express');
const { exec } = require('child_process');
const fetch = require('node-fetch');
const app = express();

app.use(express.json());

// Helper: Python extractor process එක call කිරීම
function runExtractor(mode, url, opt = 'video') {
    return new Promise((resolve) => {
        const cmd = `python3 extract_pw.py "${mode}" "${url}" "${opt}"`;
        exec(cmd, { timeout: 50000, maxBuffer: 15 * 1024 * 1024 }, (error, stdout, stderr) => {
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

// 1. YouTube Info Route (Video / Audio)
app.get('/api/info', async (req, res) => {
    const url = req.query.url;
    const type = req.query.type || 'video';
    if (!url) return res.status(400).json({ success: false, error: 'URL query parameter is required' });

    console.log(`📡 [YouTube Request] Type: ${type} | URL: ${url}`);
    const data = await runExtractor('youtube', url, type);
    res.json(data);
});

// 2. TeraBox Route
app.get('/api/terabox', async (req, res) => {
    const url = req.query.url;
    if (!url) return res.status(400).json({ success: false, error: 'URL query parameter is required' });

    console.log(`📦 [TeraBox Request] URL: ${url}`);
    const data = await runExtractor('terabox', url);
    res.json(data);
});

// 3. DiskWala Route
app.get('/api/diskwala', async (req, res) => {
    const url = req.query.url;
    if (!url) return res.status(400).json({ success: false, error: 'URL query parameter is required' });

    console.log(`🎬 [DiskWala Request] URL: ${url}`);
    const data = await runExtractor('diskwala', url);
    res.json(data);
});

// 4. Direct Streaming Proxy Route (WhatsApp streaming support)
app.get('/stream', async (req, res) => {
    const streamUrl = req.query.url;
    if (!streamUrl) return res.status(400).send('Stream URL required');

    try {
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        };
        if (req.headers.range) {
            headers['Range'] = req.headers.range;
        }

        const streamResponse = await fetch(streamUrl, { headers });
        res.status(streamResponse.status);
        for (const [k, v] of streamResponse.headers.entries()) {
            res.setHeader(k, v);
        }
        streamResponse.body.pipe(res);
    } catch (err) {
        console.error('Stream Proxy Error:', err.message);
        if (!res.headersSent) res.status(500).send(err.message);
    }
});

// 5. Health Check & Live Runner Status Route
app.get(['/', '/health'], (req, res) => {
    res.json({
        status: 'online',
        service: 'DMC™ Backup Downloader Runner',
        engines: {
            youtube: 'yt-dlp + Playwright Chromium',
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
