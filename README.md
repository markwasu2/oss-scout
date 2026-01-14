# OSS Scout 🎬🎵🧊
## The Discovery Engine for Generative Media

**OSS Scout** is a specialized discovery tool for open-source video, audio, and 3D generation projects. We help VCs, creative technologists, and platform teams find the next breakthrough generative model before it goes mainstream.

---

## 🎯 Why OSS Scout?

The generative media space is **exploding**:
- New video diffusion models drop weekly (Mochi, HunyuanVideo, SkyReels)
- Audio generation leaps forward monthly (VibeVoice, Kokoro, FishAudio)
- 3D techniques evolve rapidly (NeRF, 3D Gaussian Splatting)

**The Problem:** You wake up wondering *"What am I missing?"*

**The Solution:** OSS Scout curates generative media projects with:
- ✨ **Hidden Gems** - High health, low popularity projects worth exploring
- 📊 **3-Score System** - Popularity, Health, People (not just stars)
- 💡 **Explainable Scoring** - See WHY a project matters
- 🔍 **Semantic Search** - Find similar projects by meaning
- 📌 **Saved Wedges** - Track your niche, get alerts for new matches

---

## 🚀 Features

### Opinionated Discovery Lenses
- **Hidden Gems (Video/Audio/3D)** - Default view for emerging projects
- **Production-Ready** - Permissive license + high health + team-maintained
- **Real-Time/Interactive** - Low-latency, streaming, on-device
- **Rising Stars** - Breakout growth detection
- **Enterprise HF** - HuggingFace models with explicit licensing + eval
- **Single-Maintainer Risk** - Popular but risky bus factor

### Analyst-Grade Intelligence
- **Health v3** - "active this week • 12 contributors • PRs merged <7d"
- **Momentum v3** - "🚀 35% growth • +15⭐/wk • +2.3k⬇️/wk"
- **HF Vetting** - Training type, license clarity, eval presence

### Built for Scale
- 20k+ items supported (sharded static index)
- $0 hosting cost (Vercel free tier)
- Fast initial load (~5-10MB vs 50MB)
- Lazy-load details on click

---

## 🎬 What We Cover

### Video Generation
- Text-to-video, image-to-video, video diffusion
- Video editing, upscaling, inpainting
- Motion control, pose/depth estimation
- ComfyUI nodes, plugins, workflows

### Audio Generation
- Text-to-speech, voice cloning, voice conversion
- Music generation (MusicGen, etc.)
- Audio editing and enhancement
- Real-time audio synthesis

### 3D Generation
- NeRF, 3D Gaussian Splatting
- 3D generation, mesh generation
- Animation, world models, simulation

### Ecosystem Tools
- Diffusers, SDXL, ComfyUI, Automatic1111
- ControlNet, LoRA, Kohya
- Training frameworks, inference engines
- Plugins, nodes, and deployment tools

---

## 🏃 Quick Start

### 1. Generate Data
```bash
git clone https://github.com/yourusername/oss-scout.git
cd oss-scout

# Set up environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r pipeline/requirements.txt

# Add tokens
cat > .env <<EOF
GITHUB_TOKEN=your_github_token_here
HF_TOKEN=your_hf_token_here
EOF

# Run pipeline (generates sharded index)
./pipeline/build.sh
```

### 2. Start UI
```bash
cd web
npm install
npm run dev
```

Open: http://localhost:3000

---

## 📊 How It Works

### Data Pipeline
1. **Fetch** - GitHub topics + Hugging Face queries (generative media only)
2. **Enrich** - Health signals (PR latency, contributor churn)
3. **Score** - Popularity, Health, People (orthogonal metrics)
4. **Explain** - Generate human-readable reasons
5. **Shard** - Output manifest + lightweight index + full details
6. **Embed** - Generate semantic embeddings for search

### Quality Gates
- ✅ Exclude forks, archived repos
- ✅ Min 100 stars (GitHub), 500 downloads (HF)
- ✅ Min 10 commits in 90 days (active development)
- ✅ Require README (no empty projects)

### Scoring Philosophy
**Popularity** (0-100): Stars, downloads, likes (log-scaled)  
**Health** (0-100): PR latency, issue responsiveness, contributor diversity  
**People** (0-100): Active maintainers, bench depth, bus factor  

All scores are **explainable** with reason strings.

---

## 🎯 Who Is This For?

### VC Scouts
- Find breakout generative models before Series A
- Track momentum (growth rates, contributor velocity)
- Assess bus factor risk (single-maintainer projects)
- Save wedges for your thesis (e.g., "real-time video on-device")

### Creative Technologists
- Discover video/audio models for production use
- Filter by license (permissive vs restrictive)
- Find ComfyUI nodes and plugins
- Evaluate health signals (PR responsiveness, recent updates)

### Platform Teams
- Assess enterprise-readiness (license clarity, eval presence)
- Find inference engines and deployment tools
- Track ecosystem maturity (ControlNet, LoRA, Diffusers)
- Monitor single-maintainer risk

### Researchers
- Track state-of-the-art in video/audio/3D
- Find eval-reported models with benchmarks
- Discover research-alive projects (papers + maintained code)
- Semantic search for "similar to X"

---

## 🔮 Roadmap

### Phase 1 (Done) ✅
- Health v2 (PR/issue latency, contributor churn)
- Momentum v2 (breakout detection)
- Saved wedges + alerts
- Semantic search
- Sharded static index (20k+ scale)
- Health v3 (explainable reasons)
- HF vetting lenses

### Phase 2 (Next)
- [ ] Modality icons (🎬🎵🧊) on cards
- [ ] Weekly digest (top 3 video/audio/3D)
- [ ] GenMedia Curator prompt (pattern discovery)
- [ ] Landing page redesign (positioning)
- [ ] Case studies (creative studio, game dev, VC)

### Phase 3 (Future)
- [ ] Frame rate, resolution, duration metadata (video)
- [ ] Speaker count, languages, context length (audio)
- [ ] Real-time capability flags
- [ ] Comparative view (model A vs B)
- [ ] Share saved wedges publicly
- [ ] API access

---

## 🤝 Contributing

OSS Scout is focused on **generative media** discovery. If you have:
- New generative media GitHub topics to track
- Better quality gates for video/audio/3D models
- Metadata extraction ideas (frame rates, resolutions)
- Lens suggestions (new discovery patterns)

Open an issue or PR!

---

## 📄 License

MIT

---

## 🙏 Acknowledgments

Built on shoulders of giants:
- [Hugging Face](https://huggingface.co) - Model hosting
- [GitHub](https://github.com) - Code hosting
- [Next.js](https://nextjs.org) - Frontend framework
- [sentence-transformers](https://www.sbert.net) - Embeddings

Inspired by analysis of:
- SkyReels V1, HunyuanVideo, Mochi 1 (video)
- VibeVoice, Kokoro, FishAudio (audio)
- NeRF, 3D Gaussian Splatting (3D)

---

**OSS Scout** - Because you shouldn't wake up wondering what you missed.

