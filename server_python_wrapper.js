const express = require('express');
const { execFile } = require('child_process');
const fetch = require('node-fetch');

const app = express();
const PORT = 3000;

app.get('/', (req, res) => {
    res.send('👑 DMC Backup Playwright & yt-dlp API is LIVE on Cloudflare!');
});

app.get('/api/info', (req, res) => {
    const videoUrl = req.query.url;
    const type = req.query.type || 'video';
    if (!videoUrl) return res.status(400).json({ error: 'Missing url parameter' });

    execFile('python3', ['extract_pw.py', videoUrl, type], { timeout: 60000 }, (error, stdout, stderr) => {
        if (error) {
            console.error("Extractor error:", error.message, "Stderr:", stderr);
            return res.status(500).json({ error: 'Extractor execution failed' });
        }
        try {
            const lines = stdout.trim().split('\n');
            const jsonLine = lines.reverse().find(l => l.trim().startsWith('{') && l.trim().endsWith('}'));
            if (!jsonLine) throw new Error("No JSON found in extractor output: " + stdout);
            
            const data = JSON.parse(jsonLine);
            if (!data.video_url) {
                return res.status(404).json({ error: data.error || 'Stream not found' });
            }
            const host = req.headers.host;
            const streamUrl = `https://${host}/stream?url=${encodeURIComponent(data.video_url)}&type=${type}`;
            res.json({
                title: data.title || (type === 'audio' ? 'Audio Track' : 'YouTube Video'),
                download_url: streamUrl
            });
        } catch (err) {
            console.error("JSON parse error:", err.message, "Stdout was:", stdout);
            res.status(500).json({ error: 'Invalid response from extractor' });
        }
    });
});

app.get('/stream', async (req, res) => {
    const targetUrl = req.query.url;
    const type = req.query.type || 'video';
    if (!targetUrl) return res.status(400).send('Missing stream URL');

    try {
        const response = await fetch(targetUrl, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        });
        res.setHeader('Content-Type', type === 'audio' ? 'audio/mpeg' : 'video/mp4');
        response.body.pipe(res);
    } catch (err) {
        console.error("Streaming error:", err.message);
        res.status(500).send('Streaming error');
    }
});

app.listen(PORT, () => {
    console.log(`🚀 Backup API running on port ${PORT}`);
});
