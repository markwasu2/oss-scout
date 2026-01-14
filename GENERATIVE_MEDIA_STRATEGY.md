# OSS Scout: Generative Media Discovery Engine

## Strategic Positioning

**OSS Scout is the discovery engine for open-source video, audio, and 3D generation tools.**

We don't try to cover all of open source. We focus on the specific domain where:
- New models and tools emerge **weekly**
- Quality signals are **hard to parse** (stars don't mean production-ready)
- Users have a **genuine discovery problem**: "What should I look at today?"

---

## The Wedge: Generative Media

### Target Users
1. **VC Scouts** - Finding next-gen video/audio/3D startups
2. **Creative Technologists** - Discovering tools for production pipelines
3. **Platform Teams** - Evaluating models for integration
4. **Research Engineers** - Tracking emerging architectures

### Why This Works
- **Specific pain**: "I wake up wondering what I'm missing" (real quote)
- **High engagement**: Visual outputs, concrete use cases, shareable
- **Clear quality bars**: License compliance, maintainer responsiveness, real-time capability
- **Network effects**: Contributor graphs show ecosystem connections

---

## Corpus Design

### What We Include (32 Topics)

**Core Modalities:**
- Video: `text-to-video`, `image-to-video`, `video-diffusion`
- Audio: `text-to-speech`, `voice-conversion`, `musicgen`, `asr`
- 3D: `nerf`, `3d-gaussian-splatting`, `animation`
- Spatial: `world-model`, `simulation`

**Ecosystems:**
- `diffusers`, `sdxl`, `comfyui`, `controlnet`, `lora`, `kohya`
- `pytorch`, `jax`, `onnx`

**Control/Enhancement:**
- `inpainting`, `upscaling`, `motion-control`, `pose-depth`
- `realtime`, `on-device`

**Pipeline:**
- `training`, `inference`, `plugin`, `ui`

### What We Exclude
- ❌ LLMs (separate market, different quality signals)
- ❌ RAG/Vector DBs (infrastructure, not generation)
- ❌ MLOps/Monitoring (tooling, not creative)
- ❌ Agents/Eval (different user persona)

### Quality Gates
```json
{
  "github": {
    "min_stars": 100,
    "require_license": true,        // Production compliance
    "min_commits_90d": 10,          // Active maintenance
    "exclude_forks": true,
    "exclude_archived": true
  },
  "huggingface": {
    "min_downloads": 500,           // Filter research prototypes
    "min_likes": 5,
    "max_age_days": 365
  }
}
```

**Target Corpus:** 500-1000 projects (not 20k)  
**Why:** Curated signal > comprehensive noise

---

## Discovery Lenses (Opinionated Curation)

### Default: ✨ Hidden Gems (Video/Audio/3D)
**The "what should I look at today?" lens**
- Health ≥ 70 (active, responsive)
- Popularity < 40 (below median - undiscovered)
- People ≥ 60 (multi-maintainer, sustainable)
- Modality: video OR audio OR 3d

**Examples surfaced:**
- New video diffusion models with clean architecture
- TTS systems with real-time capability but <5k stars
- 3D Gaussian splatting tools with strong contributor growth

### Modality Explorers
- 🎬 **Video Generation**: t2v, i2v, video diffusion
- 🎵 **Audio & Voice**: TTS, voice conversion, music gen
- 🧊 **3D & Spatial**: NeRF, Gaussian splatting, world models

### Quality Filters
- 🏗️ **Production-Ready**: Permissive license + ≥3 maintainers + health ≥ 60
- 🚀 **Rising Stars**: Breakout momentum + health ≥ 60
- ⚡ **Real-Time Capable**: On-device, streaming, low-latency

### Risk Indicators
- ⚠️ **Single-Maintainer Risk**: Popular but ≤1 contributor (bus factor)
- 🧟 **Zombies**: Popularity ≥ 70 but health < 30 (use with caution)

### Ecosystem-Specific
- 🔌 **ComfyUI Ecosystem**: Plugins and nodes for ComfyUI workflows

---

## Scoring (Genre-Aware)

### For Generative Models (HF)
- **Popularity (45%)**: Downloads, likes, ecosystem adoption
- **Health (25%)**: Release cadence, maintainer response
- **People (15%)**: Bench depth, bus factor
- **Sustainability (15%)**: License clarity, governance

### For Tools/Plugins (GitHub)
- **Health (35%)**: PR merge latency, issue responsiveness
- **People (30%)**: Active maintainers, contributor diversity
- **Popularity (20%)**: Stars velocity, fork growth
- **Sustainability (15%)**: License, CODEOWNERS, CONTRIBUTING

### Metadata We Surface
**Video Models:**
- Frame rate, resolution, max duration
- "SkyReels V1: 24fps, 544×960, up to 12s"

**Audio Models:**
- Speakers, languages, max context
- "VibeVoice-1.5B: 90min context, multi-speaker"

**Real-Time:**
- Inference latency, GPU requirements
- "VibeVoice-Realtime: ~300ms synthesis"

---

## Why This Beats Generic OSS Tools

| Generic Tools | OSS Scout (Generative Media) |
|--------------|------------------------------|
| All repos | Video/Audio/3D only |
| Stars = quality | Health + People + License |
| Static rankings | Weekly emerging patterns |
| No context | "12s@24fps, 544×960, controlnet" |
| No curation | Opinionated lenses |
| No risk signals | Single-maintainer warnings |

---

## Use Cases (Real Examples)

### VC Scout Workflow
1. **Monday morning**: Check "Rising Stars" lens
2. **See**: HunyuanVideo I2V (13B params, 15s videos)
3. **Insight**: "Breakout momentum + Chinese team + no single-maintainer risk"
4. **Action**: Add to watchlist, check contributor graph

### Creative Technologist
1. **Need**: Real-time TTS for game NPC voices
2. **Filter**: "Real-Time Capable" + "Audio & Voice"
3. **Find**: Kokoro (82M params, fast synthesis, permissive license)
4. **Validate**: Health v2 shows "PRs merged <7d, 5 contributors"

### Platform Team
1. **Requirement**: Enterprise-safe video generation
2. **Lens**: "Production HF" + "Video Generation"
3. **Results**: Models with explicit license + eval reports
4. **Decision**: LTXVideo (12GB VRAM, permissive, documented)

---

## Product Roadmap

### Phase 1: Core Discovery (✅ Done)
- Generative media corpus
- Health/Momentum/People scoring
- Opinionated lenses
- Contributor graph

### Phase 2: Metadata Enrichment (Next)
- [ ] Frame rate / resolution extraction
- [ ] Context length / speaker count
- [ ] Real-time capability flags
- [ ] GPU VRAM requirements

### Phase 3: Engagement Loops
- [ ] Weekly digest: "Top 3 rising video models"
- [ ] Saved searches with alerts
- [ ] Modality icons on cards (🎬🎵🧊)
- [ ] Share wedges (e.g., "ComfyUI + ControlNet + Hidden Gems")

### Phase 4: Community
- [ ] Case studies (studio used X, found Y)
- [ ] Contributor profiles (maintainers of multiple video tools)
- [ ] Ecosystem maps (ComfyUI plugin dependency graph)

---

## Positioning Statement

> **OSS Scout answers one question better than any other tool:**  
> *"What generative media project should I look at today that I probably haven't heard of?"*

We're not:
- ❌ A GitHub ranking site (we have 32 topics, not 2000)
- ❌ A model zoo (we surface **projects**, not just weights)
- ❌ A leaderboard (we care about **health** and **people**, not just metrics)

We are:
- ✅ **Opinionated**: Default to Hidden Gems, not "All"
- ✅ **Contextual**: Show frame rates, latency, license clarity
- ✅ **Risk-aware**: Single-maintainer warnings, zombie detection
- ✅ **Curated**: 500-1000 projects, not 20k noise

---

## Metrics That Matter

**Engagement:**
- % of users landing on "Hidden Gems" (target: 80%)
- Saved wedges per user (target: 2+)
- Weekly return rate (target: 40%)

**Discovery:**
- Projects clicked from "Rising Stars" (should be >50%)
- Modality explorer usage (video > audio > 3d expected)
- Contributor graph clicks (network discovery)

**Quality:**
- False positive rate on "Production-Ready" (target: <10%)
- User feedback: "Found this via OSS Scout" (anecdotal but valuable)

---

## Outreach Strategy

### Target Personas
1. **Small VC funds** (generative AI thesis)
2. **Accelerators** (creative tech focus)
3. **Studio tech leads** (Unreal, Unity, production pipelines)
4. **Research engineers** (FAIR, DeepMind, academic labs)

### Pitch
> "You wake up wondering what generative media projects you're missing.  
> We built the discovery engine to answer that question every day."

### Channels
- **Twitter/X**: Weekly "Rising Star" threads
- **Discord**: Generative AI communities (ComfyUI, Civitai)
- **Hackathons**: "Find your next video tool on OSS Scout"
- **Newsletters**: Sponsor/guest post in creative tech newsletters

---

## Why This Will Work

1. **Narrow is defensible**: Video/audio/3D has unique quality signals
2. **Real pain**: Discovery fatigue is real in fast-moving spaces
3. **Network effects**: Contributor graphs + saved wedges = stickiness
4. **Expansion path**: Add game engines, AR/VR, real-time inference later

**The wedge is the product.** Start narrow, go deep, expand deliberately.

