# OSS Scout - Tag System

## Overview

**Problem**: HF/GH metadata doesn't explicitly encode "film previz" or "UGC ads" - so we can't build a 50-filter wishlist taxonomy.

**Solution**: Extract **6 high-value tag categories** that actually appear in topics/descriptions and map to real workflows.

---

## The 6 Tag Categories (Fast Path)

### 1. **Modality** (What type of content)
- `image` - Image generation/processing
- `video` - Video generation/editing
- `audio` - Audio/speech/music
- `3d` - 3D models, NeRF, Gaussian Splatting
- `multimodal` - Cross-modal (vision-language, etc.)

**Detection**: Topics, keywords ("text-to-video", "TTS", "3DGS")

---

### 2. **Task** (Generation tasks that show up everywhere)
- `t2i` - Text-to-image
- `i2i` - Image-to-image (edit/inpaint/upscale)
- `t2v` - Text-to-video
- `i2v` - Image-to-video (animation)
- `tts` - Text-to-speech
- `asr` - Speech-to-text

**Detection**: Topics ("text-to-image"), task tags, keywords

---

### 3. **Ecosystem** (How people actually build)
- `diffusers` - HuggingFace Diffusers
- `comfyui` - ComfyUI
- `automatic1111` - Stable Diffusion WebUI
- `sdxl` - Stable Diffusion XL
- `kohya` - Kohya trainer
- `pytorch` - PyTorch
- `jax` - JAX/Flax
- `onnx` - ONNX/TensorRT

**Detection**: Strong signals in topics, READMEs

---

### 4. **Control** (Massive differentiator)
- `controlnet` - ControlNet/conditioning
- `pose-depth` - Pose/depth/normal maps
- `motion-control` - Motion/camera control
- `inpainting` - Inpaint/outpaint/mask
- `lora` - LoRA/adapters/DreamBooth

**Detection**: Very explicit in topics and descriptions

---

### 5. **Pipeline Type** (Builder axis)
- `training` - Training/fine-tuning
- `inference` - Inference/serving
- `eval` - Evaluation/benchmark
- `dataset` - Dataset/corpus
- `ui` - Gradio/Streamlit/web UI
- `plugin` - ComfyUI nodes, A1111 extensions

**Detection**: Keywords + topics

---

### 6. **License Bucket** (Critical for "open source" truthiness)
- `permissive` - MIT/Apache/BSD
- `restricted` - Non-commercial, research-only, GPL
- `unclear-license` - No license or ambiguous

**Detection**: GitHub license field

---

## Bonus Tags (Included)

### Model Family
- `diffusion` - Diffusion models
- `transformer` - Transformers/attention
- `gan` - GANs
- `flow` - Flow matching

### Real-time Signals
- `realtime` - Real-time/streaming/interactive
- `on-device` - Mobile/edge/quantized

### LLM-specific (from old use_cases)
- `agents` - Agents/autonomous/tool-use
- `rag` - RAG/retrieval/vector-db

---

## Implementation Details

### Data Structure

Each project now has:
```json
{
  "tags": [
    "video",      // Modality
    "t2v",        // Task
    "diffusers",  // Ecosystem
    "controlnet", // Control
    "inference",  // Pipeline
    "permissive"  // License
  ],
  "use_cases": ["agents", "rag"]  // Kept for backward compat
}
```

### Tag Extraction

**Function**: `extract_tags(text, topics, license_info)`

**Sources**:
- Description text (lowercase)
- Topics/tags array
- License field (for license bucket)

**Method**: Keyword matching with comprehensive patterns

---

## UI Features

### Dynamic Filtering

**Categories shown** (only if tags exist in data):
1. Modality (purple)
2. Task (blue)
3. Ecosystem (green)
4. Control (orange)
5. Pipeline (indigo)
6. License (not shown separately - can add if needed)

**Format**: `tag (count)`

Example: `video (47)`, `t2i (123)`, `diffusers (89)`

**Behavior**:
- Click tag → filter to projects with that tag
- Multiple tags = OR filter (show if ANY tag matches)
- "Clear all filters" button appears when active
- Empty categories hidden automatically

---

## Why This Works

### ✅ **High Signal**
- These tags **actually appear** in HF/GH metadata
- Won't have empty filters

### ✅ **Low Sparsity**
- Most projects will have 3-6 tags
- No "film previz" with 0 results

### ✅ **Actionable**
- Maps to real workflows developers use
- "Show me all diffusers projects with ControlNet support" = useful query

### ✅ **Extensible**
- Easy to add new tags as patterns emerge
- Can add manual overrides later

---

## Examples

### Example 1: Stable Diffusion WebUI Extension
```
Description: "ControlNet extension for AUTOMATIC1111 WebUI"
Topics: ["stable-diffusion", "controlnet", "webui"]

Extracted tags:
- image (modality)
- i2i (task - edit/control)
- automatic1111 (ecosystem)
- controlnet (control)
- plugin (pipeline)
- diffusion (model family)
- permissive (license: MIT)
```

### Example 2: Text-to-Video Model
```
Description: "Text to video generation using Diffusers"
Topics: ["text-to-video", "diffusion", "pytorch"]

Extracted tags:
- video (modality)
- t2v (task)
- diffusers (ecosystem)
- pytorch (ecosystem)
- inference (pipeline - typical for models)
- diffusion (model family)
- unclear-license (no license)
```

### Example 3: ComfyUI LoRA Training
```
Description: "Train LoRA models for ComfyUI"
Topics: ["comfyui", "lora", "training", "stable-diffusion"]

Extracted tags:
- image (modality)
- comfyui (ecosystem)
- lora (control)
- training (pipeline)
- diffusion (model family)
- permissive (license: Apache-2.0)
```

---

## Discovery Workflows Enabled

### Workflow 1: "Show me all diffusers-based video generation"
**Filters**: 
- Ecosystem: `diffusers`
- Modality: `video`
- Task: `t2v` or `i2v`

**Result**: ~15-30 projects (useful, not overwhelming)

### Workflow 2: "Find training tools for LoRA"
**Filters**:
- Control: `lora`
- Pipeline: `training`

**Result**: Training repos, Kohya forks, custom trainers

### Workflow 3: "ComfyUI plugins for control"
**Filters**:
- Ecosystem: `comfyui`
- Pipeline: `plugin`
- Control: any (controlnet, pose-depth, etc.)

**Result**: Custom nodes and extensions

### Workflow 4: "Real-time inference projects"
**Filters**:
- Tags: `realtime`
- Pipeline: `inference`
- Health: `alive`

**Result**: Optimized, actively maintained inference engines

---

## Tag Coverage Stats (Expected)

After running on 1-2k projects:

**High Coverage** (>70% of projects):
- Modality tags: ~90%
- Pipeline tags: ~85%
- License: ~95%

**Medium Coverage** (30-70%):
- Ecosystem: ~60% (many generic)
- Model family: ~50%

**Low Coverage** (10-30%):
- Task (t2i/i2v): ~25% (specific to generative models)
- Control: ~20% (specific to certain workflows)
- Real-time: ~5% (rare but valuable)

---

## Future Enhancements

### Phase 2: Manual Overrides
```json
// overrides.json
{
  "owner/repo": {
    "add_tags": ["film-vfx", "game-dev"],
    "remove_tags": ["unclear-license"]
  }
}
```

### Phase 3: Use Case Detection
- Detect from README content (not just keywords)
- "Previz", "advertising", "game dev" mentions
- Citations, associated papers

### Phase 4: Faceted Search
- Multiple tag selection modes
- AND vs OR operators
- Tag combinations (e.g., "video + realtime")

---

## Testing the Tag System

After regenerating data:

```bash
./pipeline/build.sh
```

Check tag distribution:
```python
import json
data = json.load(open('web/public/data/projects.json'))

# Count tags
tag_counts = {}
for p in data['projects']:
    for tag in p.get('tags', []):
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

# Top tags
sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
print("Top 20 tags:")
for tag, count in sorted_tags[:20]:
    print(f"  {tag}: {count}")
```

Check categorization:
```python
# Projects by category
modalities = [p for p in data['projects'] if any(t in p.get('tags', []) for t in ['image', 'video', 'audio', '3d'])]
print(f"Projects with modality tags: {len(modalities)}/{len(data['projects'])}")

ecosystems = [p for p in data['projects'] if any(t in p.get('tags', []) for t in ['diffusers', 'pytorch', 'comfyui'])]
print(f"Projects with ecosystem tags: {len(ecosystems)}/{len(data['projects'])}")
```

---

## Why NOT 50 Filters

**The trap**: Building a complete taxonomy upfront

**Problems**:
1. **Sparse data** - Most filters would show 0 results
2. **Maintenance hell** - Constant tweaking
3. **Bad UX** - Users see empty options
4. **False precision** - Implies we know more than we do

**The solution**: Start with 6 categories, ~30 total tags, all with good coverage. Add more as patterns emerge organically from the data.

---

## Current Implementation

✅ **Backend**: `extract_tags()` function in `fetch.py`
✅ **Data**: `tags` field on all projects (GitHub + HF)
✅ **UI**: Dynamic tag filters, categorized, with counts
✅ **Backward compat**: `use_cases` field still exists

**Ready to use**: Just regenerate data with `./pipeline/build.sh`

