# OSS Scout - Product Strategy

> **Purpose:** Define what "good" means for this discovery tool. These are human judgment calls that shape how the tool behaves.

---

## 1. Core Categories (Top 5-10)

**Question:** What types of projects do you care about most?

### Current Focus (from config.json):
- [ ] **Diffusion models** (Stable Diffusion, SDXL, video diffusion)
- [ ] **Inference engines** (ComfyUI, A1111, custom servers)
- [ ] **LLMs** (training, finetune, agents, RAG)
- [ ] **Multimodal** (VLMs, image-text, video-text)
- [ ] **Real-time / Interactive** (streaming, low-latency)
- [ ] **ComfyUI ecosystem** (nodes, plugins, workflows)
- [ ] **Production tooling** (serving, deployment, MLOps)
- [ ] **Eval / Benchmarks** (research-grade measurement)
- [ ] **3D / NeRF** (Gaussian splatting, 3D generation)
- [ ] **Audio** (TTS, ASR, music generation)

**Your Call:** Which 3-5 are most important? (Order matters for default rankings)

1. _____________________
2. _____________________
3. _____________________
4. _____________________
5. _____________________

---

## 2. Default Lens

**Question:** When someone lands on the site, what should they see first?

Current options:
- **All** (sorted by health) - Safest, shows everything
- **Hidden Gems** - Under-recognized but healthy
- **Production-Ready** - Safe for prod use
- **Composable Builders** - Tools you can integrate
- **Rising Stars** - Recent momentum
- **Research-Alive** - Active research projects
- **Single-Maintainer Risk** - Popular but fragile

**Your Default:** _____________________ (and why?)

---

## 3. What is "Healthy"?

**Question:** When you filter for "Alive", what should that mean?

Current definition:
- `health_score >= 70`
- Based on: last maintainer event, merged PRs, unique contributors, issue throughput

**Your Adjustments:**
- Minimum contributors_90d: ___ (currently: implicit in score)
- Minimum PRs merged: ___ (currently: implicit)
- Max days since push: ___ (currently: no hard limit)
- Should single-maintainer projects ever be "Alive"? ___

---

## 4. Lens Tuning

**Question:** How should each lens behave?

### Hidden Gems
- [ ] Should it exclude *all* high-popularity projects? (current: median cutoff)
- [ ] Min contributors: ___ (current: 2)
- [ ] Should it show HF models or GitHub only? (current: both)

### Production-Ready
- [ ] Is "steady" health acceptable for prod? (current: yes)
- [ ] Should it require a LICENSE file? (current: no hard filter)
- [ ] Should it prefer projects with CI/CD? (current: not tracked)

### Composable Builders
- [ ] Should it include *only* libraries/nodes/plugins? (current: yes)
- [ ] Should it exclude full applications? (current: no explicit filter)

### Real-Time / Interactive
- [ ] How do you identify "real-time"? (current: keywords like "realtime", "streaming")
- [ ] Should it include "quantized" models? (current: yes via on-device tag)

### Single-Maintainer Risk
- [ ] Should this show *all* solo projects or only popular ones? (current: popular only)
- [ ] Is contributors_90d <= 1 the right threshold? (current: yes)

---

## 5. Blocklist / Quality Gates

**Question:** What should be automatically excluded?

Current gates (from config.json):
- Forks: excluded
- Archived: excluded
- No license: excluded
- No README: excluded
- Min commits (90d): 5

**Your Additions:**
- Min stars for GitHub: ___ (current: 100)
- Min downloads for HF: ___ (current: 100)
- Exclude organizations: _____ (e.g., "examples", "tutorials")
- Exclude specific repos: _____ (add to `pipeline/blocklist.json`)

---

## 6. Tag Priorities

**Question:** Which tags matter most for filtering?

Current taxonomy has 6 categories. Rank by importance:

1. _____ (e.g., Modality - image/video/audio)
2. _____ (e.g., Ecosystem - diffusers/comfyui)
3. _____ (e.g., Task - t2i/i2v/tts)
4. _____ (e.g., Pipeline - inference/training)
5. _____ (e.g., Control - controlnet/lora)
6. _____ (e.g., License - permissive/restricted)

**Missing tags you want:**
- ___________________
- ___________________

---

## 7. Curation Strategy

**Question:** How much manual curation do you want?

Options:
- **Minimal** - Let heuristics do the work, fix only broken cases
- **Moderate** - Curate top 50-100 projects with overrides
- **Heavy** - Hand-tag all important projects, heuristics for long tail

**Your Choice:** _____________________

**Overrides to add now:**
- `pipeline/tag_overrides.json` - Add specific project tags
- `pipeline/blocklist.json` - Remove noise/spam repos

Example override:
```json
{
  "github:comfyanonymous/ComfyUI": ["comfyui", "node-graph", "ui", "inference", "image", "video"],
  "github:lllyasviel/ControlNet": ["controlnet", "conditioning", "diffusers", "i2i", "image"]
}
```

---

## 8. Scale Decision

**Question:** How many projects should the tool handle?

Current state: ~119 items in one JSON (~6MB with health cache)

**Your Target:**
- [ ] Small (500-1k) - Keep single JSON, fast, manageable
- [ ] Medium (1k-5k) - Single JSON is OK but consider pagination in UI
- [ ] Large (5k-20k) - Need to split: index.json + lazy-load details
- [ ] Very Large (20k+) - Move to SQLite/DB + API routes

**Your Choice:** _____________________

If > 5k, implement:
- `web/public/data/index.json` - Lightweight list (no descriptions/health)
- `web/public/data/details/{id}.json` - Full project data
- Or: SQLite + Next.js API routes

---

## 9. Success Metrics

**Question:** How do you know if this tool is "good"?

Answer these:
- Can you find a project you *didn't know existed* in < 2 minutes? ___
- Can you trust the "Hidden Gems" lens? ___
- Does "Production-Ready" feel safe? ___
- Are there more than 3 false positives in the top 20? ___

**Your Weekly Audit:**
1. Run each lens
2. Check top 10 results
3. Note what feels wrong
4. Update overrides or tune scoring

---

## 10. Next Features (Post-Launch)

Rank these by importance (1 = highest):

- [ ] ___ Semantic search (embedding-based)
- [ ] ___ Dependency graph (what uses what)
- [ ] ___ Changelogs / Release notes parsing
- [ ] ___ Community signals (Reddit/Twitter/Discord mentions)
- [ ] ___ Author profiles (contributor portfolios)
- [ ] ___ "Similar to X" recommendations
- [ ] ___ Weekly digest email
- [ ] ___ API for programmatic access
- [ ] ___ Browser extension
- [ ] ___ Mobile app

**Your Top 3:**
1. _____________________
2. _____________________
3. _____________________

---

## How to Use This Doc

1. **Fill it out** (30 minutes of thinking)
2. **Adjust code** based on your answers (pipeline/config.json, tag_overrides.json)
3. **Run `./pipeline/build.sh`**
4. **Evaluate results** (see Section 9)
5. **Iterate weekly**

This is the **human judgment layer** that makes your scout tool different from GitHub Trending.

