# Moneyfest.app

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Open Source](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)](https://opensource.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![GitHub stars](https://img.shields.io/github/stars/your-username/moneyfest?style=social)](https://github.com/your-username/moneyfest) <!-- TODO: update to real repo URL -->
[![Last Commit](https://img.shields.io/github/last-commit/your-username/moneyfest)](https://github.com/your-username/moneyfest/commits/main) <!-- TODO: update to real repo URL -->

**Moneyfest** is a free, open source AI video platform with 3 tools in one: **Clip Generator**, **AI Shorts** (UGC videos with AI actors), and **YouTube Studio**. Self-hosted with Docker. No watermarks, no limits.

## 3 Tools in 1 Platform

### 1. Clip Generator
Turn your long-form videos into viral-ready 9:16 shorts for TikTok, Instagram Reels, and YouTube Shorts.

### 2. AI Shorts
Generate marketing videos with AI actors for any product or business. No camera, no studio, no influencer budget.

### 3. YouTube Studio
Complete free AI YouTube toolkit: thumbnails, titles, descriptions, and direct publishing.

## Key Features

- Viral moment detection with Google Gemini
- Smart 9:16 cropping with face tracking
- Automatic subtitles and AI voice dubbing
- AI-generated hook text overlays and video effects
- Direct social publishing via Upload-Post
- AI UGC video generation with AI actors and lip-sync
- Free thumbnail, title, and description tools for YouTube

## Getting Started

```bash
git clone https://github.com/your-username/moneyfest.git
cd moneyfest
docker compose up --build
```

Open the dashboard at `http://localhost:5175`.

## Environment Variables

- `GEMINI_API_KEY`
- `FAL_KEY`
- `ELEVENLABS_API_KEY`
- `UPLOAD_POST_API_KEY`

## Notes

- Replace the placeholder GitHub URLs with your real Moneyfest repo.
- Placeholder brand assets use the `Moneyfest` wordmark and `MF` monogram.
- The product functionality is unchanged; this pass is branding, visual identity, and copy only.
