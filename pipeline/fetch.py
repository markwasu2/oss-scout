from dotenv import load_dotenv
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
import re
from math import log1p
from sentence_transformers import SentenceTransformer

load_dotenv()  # 👈 THIS LINE IS THE KEY

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

HEALTH_CACHE_PATH = Path("data/cache/github_health.json")
METRICS_SNAPSHOT_PATH = Path("data/cache/metrics_snapshot.json")
CACHE_TTL_HOURS = 12

def load_config():
    """Load configuration from config.json"""
    config_path = Path("pipeline/config.json")
    with open(config_path) as f:
        return json.load(f)

def load_tag_overrides():
    """Load manual tag overrides from tag_overrides.json"""
    overrides_path = Path("pipeline/tag_overrides.json")
    if not overrides_path.exists():
        return {}
    try:
        with open(overrides_path) as f:
            data = json.load(f)
            # Filter out comment keys starting with _
            return {k: v for k, v in data.items() if not k.startswith('_')}
    except:
        return {}

def load_health_cache():
    """Load health cache from disk"""
    if not HEALTH_CACHE_PATH.exists():
        return {}
    try:
        with open(HEALTH_CACHE_PATH) as f:
            return json.load(f)
    except:
        return {}

def save_health_cache(cache):
    """Save health cache to disk"""
    HEALTH_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HEALTH_CACHE_PATH, 'w') as f:
        json.dump(cache, f, indent=2)

def load_metrics_snapshot():
    """Load previous metrics snapshot for momentum calculation"""
    if not METRICS_SNAPSHOT_PATH.exists():
        return {}
    try:
        with open(METRICS_SNAPSHOT_PATH) as f:
            return json.load(f)
    except:
        return {}

def save_metrics_snapshot(snapshot):
    """Save current metrics snapshot for next run"""
    METRICS_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(METRICS_SNAPSHOT_PATH, 'w') as f:
        json.dump(snapshot, f, indent=2)

def is_cache_valid(cached_entry):
    """Check if cached entry is still valid (< 12 hours old)"""
    if not cached_entry or 'fetched_at' not in cached_entry:
        return False
    fetched_at = datetime.fromisoformat(cached_entry['fetched_at'])
    age_hours = (datetime.utcnow() - fetched_at).total_seconds() / 3600
    return age_hours < CACHE_TTL_HOURS

def parse_link_header(link_header):
    """Parse GitHub Link header to extract last page number"""
    if not link_header:
        return None
    # Look for rel="last"
    match = re.search(r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
    if match:
        return int(match.group(1))
    return None

def clamp(value, min_val=0, max_val=1):
    """Clamp value between min and max"""
    return max(min_val, min(max_val, value))

def compute_momentum(current_metrics, previous_metrics, weeks_elapsed=1.0):
    """
    Compute momentum v2 with breakout detection
    Returns dict with deltas, per-week rates, normalized growth, and v2 labels
    """
    deltas = {
        'stars_delta': current_metrics.get('stars', 0) - previous_metrics.get('stars', 0),
        'forks_delta': current_metrics.get('forks', 0) - previous_metrics.get('forks', 0),
        'downloads_delta': current_metrics.get('downloads', 0) - previous_metrics.get('downloads', 0),
        'likes_delta': current_metrics.get('likes', 0) - previous_metrics.get('likes', 0),
    }
    
    # Per-week rates (Momentum v2)
    stars_per_week = deltas['stars_delta'] / max(1, weeks_elapsed)
    downloads_per_week = deltas['downloads_delta'] / max(1, weeks_elapsed)
    likes_per_week = deltas['likes_delta'] / max(1, weeks_elapsed)
    
    # Normalized growth (relative to baseline, log-scaled for fairness)
    # This makes small and large projects comparable
    if current_metrics.get('stars', 0) > 0:
        stars_momentum = log1p(abs(deltas['stars_delta'])) / log1p(max(1, current_metrics.get('stars', 1)))
    else:
        stars_momentum = 0
    
    if current_metrics.get('downloads', 0) > 0:
        downloads_momentum = log1p(abs(deltas['downloads_delta'])) / log1p(max(1, current_metrics.get('downloads', 1)))
    else:
        downloads_momentum = 0
    
    if current_metrics.get('likes', 0) > 0:
        likes_momentum = log1p(abs(deltas['likes_delta'])) / log1p(max(1, current_metrics.get('likes', 1)))
    else:
        likes_momentum = 0
    
    # Normalized growth score (0-1)
    if current_metrics.get('source') == 'github':
        normalized_growth = stars_momentum
        momentum_score = clamp(stars_momentum * 100)
    else:  # HuggingFace
        normalized_growth = downloads_momentum * 0.7 + likes_momentum * 0.3
        momentum_score = clamp(normalized_growth * 100)
    
    # Momentum v2 labels (breakout detection)
    baseline = current_metrics.get('stars', 0) or current_metrics.get('downloads', 0) or 0
    
    # Breakout: low baseline (<1000) + high normalized growth (>10%)
    if baseline < 1000 and normalized_growth > 0.10:
        momentum_label_v2 = 'breakout'
    # Rising: sustained growth above median (>5%)
    elif normalized_growth > 0.05:
        momentum_label_v2 = 'rising'
    else:
        momentum_label_v2 = 'flat'
    
    # Legacy label for backward compat
    if momentum_score >= 5:
        momentum_label = 'rising'
    elif momentum_score >= 1:
        momentum_label = 'steady'
    else:
        momentum_label = 'flat'
    
    return {
        **deltas,
        'momentum_score': momentum_score,
        'momentum_label': momentum_label,  # v1
        'stars_per_week': round(stars_per_week, 2),  # v2
        'downloads_per_week': round(downloads_per_week, 2),  # v2
        'likes_per_week': round(likes_per_week, 2),  # v2
        'normalized_growth': round(normalized_growth, 4),  # v2
        'momentum_label_v2': momentum_label_v2,  # v2
    }

def extract_tags(text, topics, license_info=None):
    """
    Extract practical tags for filtering (modality, task, ecosystem, control, pipeline, license)
    Returns a flat list of tags that actually appear in HF/GH metadata
    """
    text_lower = (text or "").lower()
    all_topics = " ".join(topics).lower() + " " + text_lower
    tags = []
    
    # 1. MODALITY (what type of content)
    if any(kw in all_topics for kw in ["image", "img", "vision", "visual", "picture", "photo", "t2i", "i2i"]):
        tags.append("image")
    if any(kw in all_topics for kw in ["video", "vid", "motion", "animation", "clip", "t2v", "i2v", "v2v"]):
        tags.append("video")
    if any(kw in all_topics for kw in ["audio", "sound", "music", "speech", "voice", "tts", "asr", "sts"]):
        tags.append("audio")
    if any(kw in all_topics for kw in ["3d", "nerf", "gaussian-splatting", "3dgs", "mesh", "point-cloud", "3d-reconstruction"]):
        tags.append("3d")
    if any(kw in all_topics for kw in ["multimodal", "multi-modal", "vision-language", "vlm", "vision-text"]):
        tags.append("multimodal")
    if any(kw in all_topics for kw in ["world-model", "world model", "simulation", "environment", "physics", "embodied"]):
        tags.append("world")
    
    # 2. TASK (generation tasks that show up everywhere)
    if any(kw in all_topics for kw in ["text-to-image", "t2i", "text2image", "txt2img"]):
        tags.append("t2i")
    if any(kw in all_topics for kw in ["image-to-image", "i2i", "img2img", "image-editing"]):
        tags.append("i2i")
    if any(kw in all_topics for kw in ["text-to-video", "t2v", "text2video", "txt2vid"]):
        tags.append("t2v")
    if any(kw in all_topics for kw in ["image-to-video", "i2v", "img2video", "animate", "animation"]):
        tags.append("i2v")
    if any(kw in all_topics for kw in ["video-to-video", "v2v", "video-editing", "video-enhancement"]):
        tags.append("v2v")
    if any(kw in all_topics for kw in ["text-to-speech", "tts", "speech-synthesis"]):
        tags.append("tts")
    if any(kw in all_topics for kw in ["speech-to-text", "asr", "transcription", "whisper", "speech-recognition"]):
        tags.append("asr")
    if any(kw in all_topics for kw in ["speech-to-speech", "sts", "voice-cloning", "voice-synthesis"]):
        tags.append("sts")
    if any(kw in all_topics for kw in ["voice-conversion", "voice-clone", "vc", "voice-transfer"]):
        tags.append("voice-conversion")
    if any(kw in all_topics for kw in ["speech-enhancement", "noise-reduction", "audio-enhancement"]):
        tags.append("speech-enhancement")
    if any(kw in all_topics for kw in ["music-generation", "musicgen", "audio-generation"]):
        tags.append("musicgen")
    
    # 3. ECOSYSTEM (how people actually build)
    if any(kw in all_topics for kw in ["diffusers", "huggingface-diffusers"]):
        tags.append("diffusers")
    if any(kw in all_topics for kw in ["comfyui", "comfy-ui", "comfy"]):
        tags.append("comfyui")
    if any(kw in all_topics for kw in ["automatic1111", "a1111", "stable-diffusion-webui", "sd-webui"]):
        tags.append("automatic1111")
    if any(kw in all_topics for kw in ["sdxl", "stable-diffusion-xl"]):
        tags.append("sdxl")
    if any(kw in all_topics for kw in ["kohya", "kohya-ss"]):
        tags.append("kohya")
    if any(kw in all_topics for kw in ["pytorch", "torch"]):
        tags.append("pytorch")
    if any(kw in all_topics for kw in ["jax", "flax"]):
        tags.append("jax")
    if any(kw in all_topics for kw in ["onnx", "tensorrt", "openvino"]):
        tags.append("onnx")
    
    # 4. CONTROL & CONDITIONING (massive differentiator)
    if any(kw in all_topics for kw in ["controlnet", "control-net", "conditioning"]):
        tags.append("controlnet")
    if any(kw in all_topics for kw in ["pose", "depth", "normal", "canny", "edge", "openpose"]):
        tags.append("pose-depth")
    if any(kw in all_topics for kw in ["motion", "motion-control", "camera", "temporal"]):
        tags.append("motion-control")
    if any(kw in all_topics for kw in ["inpaint", "outpaint", "mask", "inpainting", "outpainting"]):
        tags.append("inpainting")
    if any(kw in all_topics for kw in ["upscale", "upscaling", "super-resolution", "sr", "enhance"]):
        tags.append("upscaling")
    if any(kw in all_topics for kw in ["lora", "adapter", "dreambooth", "fine-tuning"]):
        tags.append("lora")
    if any(kw in all_topics for kw in ["segmentation", "semantic-seg", "instance-seg", "mask-generation"]):
        tags.append("segmentation")
    
    # 5. PIPELINE TYPE (builder axis)
    if any(kw in all_topics for kw in ["training", "train", "fine-tune", "finetune", "fine-tuning"]):
        tags.append("training")
    if any(kw in all_topics for kw in ["inference", "serving", "deployment", "server", "api"]):
        tags.append("inference")
    if any(kw in all_topics for kw in ["eval", "evaluation", "benchmark", "testing", "metrics"]):
        tags.append("eval")
    if any(kw in all_topics for kw in ["dataset", "data", "corpus"]):
        tags.append("dataset")
    if any(kw in all_topics for kw in ["gradio", "streamlit", "web-ui", "interface", "demo", "webapp"]):
        tags.append("ui")
    if any(kw in all_topics for kw in ["plugin", "extension", "node", "custom-node", "addon"]):
        tags.append("plugin")
    if any(kw in all_topics for kw in ["cli", "command-line", "terminal"]):
        tags.append("cli")
    if any(kw in all_topics for kw in ["library", "sdk", "framework", "toolkit"]):
        tags.append("library")
    if any(kw in all_topics for kw in ["node-graph", "visual-programming", "workflow"]):
        tags.append("node-graph")
    
    # 6. LICENSE BUCKET
    if license_info:
        license_lower = str(license_info).lower()
        if any(lic in license_lower for lic in ["mit", "apache", "bsd", "isc"]):
            tags.append("permissive")
        elif any(lic in license_lower for lic in ["cc-by-nc", "non-commercial", "research-only", "gpl"]):
            tags.append("restricted")
        else:
            tags.append("unclear-license")
    else:
        tags.append("unclear-license")
    
    # Model family (bonus)
    if any(kw in all_topics for kw in ["diffusion", "stable-diffusion", "latent-diffusion"]):
        tags.append("diffusion")
    if any(kw in all_topics for kw in ["transformer", "attention", "llm", "gpt"]):
        tags.append("transformer")
    if any(kw in all_topics for kw in ["gan", "generative-adversarial"]):
        tags.append("gan")
    if any(kw in all_topics for kw in ["flow", "flow-matching", "rectified-flow"]):
        tags.append("flow")
    
    # System properties (latency/deployment)
    if any(kw in all_topics for kw in ["realtime", "real-time", "live", "low-latency"]):
        tags.append("real-time")
    if any(kw in all_topics for kw in ["interactive", "responsive", "fast"]):
        tags.append("interactive")
    if any(kw in all_topics for kw in ["streaming", "stream", "live-stream"]):
        tags.append("streaming")
    if any(kw in all_topics for kw in ["on-device", "mobile", "edge", "quantized", "onnx", "tensorrt"]):
        tags.append("on-device")
    if any(kw in all_topics for kw in ["batch", "offline", "scheduled"]):
        tags.append("batch")
    
    # World-model / simulation / agent
    if any(kw in all_topics for kw in ["world-model", "world model", "predictive-model"]):
        tags.append("world-model")
    if any(kw in all_topics for kw in ["simulation", "simulator", "sim", "physics"]):
        tags.append("simulation")
    if any(kw in all_topics for kw in ["agent", "autonomous", "tool-use", "function-calling", "agentic"]):
        tags.append("agents")
    if any(kw in all_topics for kw in ["environment", "gym", "embodied", "robotics"]):
        tags.append("environment")
    
    # LLM-specific (keep from old use_cases)
    if any(kw in all_topics for kw in ["rag", "retrieval", "vector-db", "embedding"]):
        tags.append("rag")
    
    return list(set(tags))  # Remove duplicates

def compute_scores(item, source):
    """
    Compute 3 orthogonal scores: popularity, health, people
    
    Philosophy:
    - Popularity = Adoption (is it used/known?)
    - Health = Responsiveness + Momentum (are maintainers present? is it evolving?)
    - People = Sustainability (will it survive? bus factor?)
    
    Key improvements over naive scoring:
    - Uses logarithmic scaling (not linear) for robustness
    - Normalizes to adaptive percentiles (not magic numbers)
    - Focuses on maintainer actions (not just commit counts)
    - Uses last maintainer event for recency (not just push)
    - Measures bus factor via ownership distribution (not just count)
    """
    scores = {
        "popularity_score": 0,
        "health_score": 0,
        "people_score": 0,
    }
    
    if source == "github":
        # POPULARITY SCORE (0-100): Adoption / awareness
        stars = item.get("stars", 0)
        forks = item.get("forks", 0)
        
        # Logarithmic scaling (handles full range 100 to 100k+ stars)
        # p95 ~10k stars, p99 ~50k stars (adaptive targets)
        stars_log = clamp(log1p(stars) / log1p(10000)) * 70  # Up to 70 points
        forks_log = clamp(log1p(forks) / log1p(2000)) * 20   # Up to 20 points
        
        # Trend component (not yet available, placeholder)
        # In future: star velocity = (stars gained last 90d / total stars)
        trend_score = 10  # Neutral for now
        
        scores["popularity_score"] = round(min(stars_log + forks_log + trend_score, 100), 1)
        
        # HEALTH SCORE (0-100): is this alive and maintained?
        # Use the computed health_score from health object (already 0-1, scale to 100)
        health_obj = item.get("health", {})
        scores["health_score"] = round(health_obj.get("health_score", 0) * 100, 1)
        
        # PEOPLE SCORE (0-100): Maintainer sustainability
        # Focus on active maintainers, not just contributors
        people = 0
        contributors = item.get("contributors", [])
        health_obj = item.get("health", {})
        
        # 1. Active maintainer count (0-40 points)
        # Use recent contributors as proxy for active maintainers
        active_maintainers = health_obj.get("contributors_90d", len(contributors))
        # Logarithmic scale: 2 maintainers = OK, 5 = good, 10+ = excellent
        maintainer_score = clamp(log1p(active_maintainers) / log1p(10)) * 40
        people += maintainer_score
        
        # 2. Maintainer bench depth (0-30 points)
        # How many people beyond top contributor are active?
        if len(contributors) >= 2:
            # Count contributors with >5% of top contributor's work as "real maintainers"
            if contributors[0].get("contributions", 0) > 0:
                top_contribs = contributors[0]["contributions"]
                significant_maintainers = sum(
                    1 for c in contributors[1:] 
                    if c.get("contributions", 0) > top_contribs * 0.05
                )
                bench_score = clamp(log1p(significant_maintainers) / log1p(5)) * 30
                people += bench_score
        
        # 3. Bus factor / ownership distribution (0-30 points)
        # Lower concentration = better (inverse bus factor)
        if len(contributors) >= 2:
            total_contribs = sum(c.get("contributions", 0) for c in contributors)
            if total_contribs > 0:
                # What % does top maintainer own?
                top_share = contributors[0].get("contributions", 0) / total_contribs
                # Ideal: top person does 20-40% (strong leader, but not solo)
                # Solo (>70%) = risky, too distributed (<15%) = also risky
                if top_share > 0.70:
                    bus_score = 10  # High risk - solo maintainer
                elif top_share > 0.50:
                    bus_score = 20  # Medium risk - dominant maintainer
                elif top_share < 0.15:
                    bus_score = 15  # Many drive-by contributors, unclear ownership
                else:
                    bus_score = 30  # Healthy distribution
                people += bus_score
        else:
            # Solo maintainer
            people += 5  # Penalize for bus factor
        
        scores["people_score"] = round(min(people, 100), 1)
        
    elif source == "hf":
        # POPULARITY SCORE: downloads + likes
        downloads = item.get("downloads", 0)
        likes = item.get("likes", 0)
        scores["popularity_score"] = min(
            (downloads / 10000) * 0.7 + (likes / 100) * 0.3,
            100
        )
        
        # HEALTH SCORE: recency (limited data for HF)
        days_old = item.get("days_since_update", 0)
        if days_old == 0:
            scores["health_score"] = 50  # Unknown, assume moderate
        elif days_old < 30:
            scores["health_score"] = 80
        elif days_old < 90:
            scores["health_score"] = 60
        elif days_old < 180:
            scores["health_score"] = 40
        else:
            scores["health_score"] = 20
        
        # PEOPLE SCORE: N/A for HF, use downloads as proxy
        scores["people_score"] = min((downloads / 50000) * 50, 50)
    
    # Round all scores
    for key in scores:
        scores[key] = round(scores[key], 1)
    
    return scores

def fetch_contributors(repo_full_name, limit=10):
    """Fetch top contributors for a GitHub repo"""
    try:
        url = f"https://api.github.com/repos/{repo_full_name}/contributors?per_page={limit}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            contributors = []
            for c in response.json()[:limit]:
                contributors.append({
                    "login": c["login"],
                    "avatar_url": c["avatar_url"],
                    "contributions": c["contributions"],
                    "url": c["html_url"]
                })
            return contributors
        return []
    except Exception as e:
        print(f"  ⚠ Could not fetch contributors for {repo_full_name}: {e}")
        return []

def fetch_health_signals_comprehensive(repo_full_name, repo_pushed_at, cache):
    """
    Fetch comprehensive health signals with caching
    Returns a dict with health metrics and computed health_score/health_label
    """
    # Check cache first
    if repo_full_name in cache and is_cache_valid(cache[repo_full_name]):
        return cache[repo_full_name]['health']
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    now = datetime.utcnow()
    days_30_ago = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    days_60_ago = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    days_90_ago = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    health = {
        "days_since_push": 0,
        "days_since_release": None,
        "commits_30d": 0,
        "commits_90d": 0,
        "contributors_30d": 0,  # Health v2
        "contributors_90d": 0,
        "new_contributors_90d": 0,  # Health v2
        "prs_merged_60d": 0,
        "issues_opened_60d": 0,
        "issues_closed_60d": 0,
        "pr_merge_latency_days": None,  # Health v2
        "issue_close_latency_days": None,  # Health v2
        "health_score": 0.0,
        "health_label": "decaying"
    }
    
    try:
        # 1. Days since push (from repo data)
        if repo_pushed_at:
            pushed_date = datetime.fromisoformat(repo_pushed_at.replace("Z", "+00:00"))
            health["days_since_push"] = (datetime.now(pushed_date.tzinfo) - pushed_date).days
        
        # 2. Days since release
        try:
            url = f"https://api.github.com/repos/{repo_full_name}/releases/latest"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                release = response.json()
                if release.get("published_at"):
                    release_date = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
                    health["days_since_release"] = (datetime.now(release_date.tzinfo) - release_date).days
        except:
            pass
        
        # 3. Commits 30d and 90d (efficient: use Link header)
        try:
            # 90 days
            url = f"https://api.github.com/repos/{repo_full_name}/commits?since={days_90_ago}&per_page=1"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                link_header = response.headers.get('Link')
                last_page = parse_link_header(link_header)
                health["commits_90d"] = last_page if last_page else len(response.json())
            
            # 30 days
            url = f"https://api.github.com/repos/{repo_full_name}/commits?since={days_30_ago}&per_page=1"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                link_header = response.headers.get('Link')
                last_page = parse_link_header(link_header)
                health["commits_30d"] = last_page if last_page else len(response.json())
        except:
            pass
        
        # 4. Contributors 90d + 30d + churn (Health v2)
        try:
            # 90 days contributors
            url = f"https://api.github.com/repos/{repo_full_name}/commits?since={days_90_ago}&per_page=100&page=1"
            response = requests.get(url, headers=headers, timeout=10)
            contributors_90d_set = set()
            if response.status_code == 200:
                commits = response.json()
                for c in commits:
                    author_login = c.get("author", {}).get("login") if c.get("author") else None
                    if author_login:
                        contributors_90d_set.add(author_login)
                health["contributors_90d"] = len(contributors_90d_set)
            
            # 30 days contributors
            url = f"https://api.github.com/repos/{repo_full_name}/commits?since={days_30_ago}&per_page=100&page=1"
            response = requests.get(url, headers=headers, timeout=10)
            contributors_30d_set = set()
            if response.status_code == 200:
                commits = response.json()
                for c in commits:
                    author_login = c.get("author", {}).get("login") if c.get("author") else None
                    if author_login:
                        contributors_30d_set.add(author_login)
                health["contributors_30d"] = len(contributors_30d_set)
            
            # Contributor churn (new contributors as % of total in 90d)
            # Get all-time contributors to identify "new" vs "returning"
            try:
                url = f"https://api.github.com/repos/{repo_full_name}/contributors?per_page=100&page=1"
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    all_contributors = {c.get("login") for c in response.json() if c.get("login")}
                    # Rough heuristic: if contributor appears in recent but has few total contributions, likely new
                    # For simplicity: count contributors_90d not in top 100 all-time as "new"
                    # This is approximate but sufficient
                    new_contributors_estimate = len(contributors_90d_set - (all_contributors if all_contributors else set()))
                    health["new_contributors_90d"] = max(0, new_contributors_estimate)
                else:
                    health["new_contributors_90d"] = 0
            except:
                health["new_contributors_90d"] = 0
        except:
            health["contributors_30d"] = 0
            health["new_contributors_90d"] = 0
            pass
        
        # 5. PRs merged 60d + PR merge latency (Health v2)
        try:
            url = f"https://api.github.com/repos/{repo_full_name}/pulls?state=closed&per_page=100&page=1"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                prs = response.json()
                cutoff_date = datetime.fromisoformat(days_60_ago.replace("Z", "+00:00"))
                merged_count = 0
                pr_latencies = []
                
                for pr in prs:
                    if pr.get("merged_at"):
                        closed_at = datetime.fromisoformat(pr["closed_at"].replace("Z", "+00:00"))
                        if closed_at >= cutoff_date:
                            merged_count += 1
                            # Calculate PR latency (days from open to merge)
                            created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                            merged_at = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
                            latency_days = (merged_at - created_at).days
                            if latency_days >= 0:  # Sanity check
                                pr_latencies.append(latency_days)
                
                health["prs_merged_60d"] = merged_count
                # Compute median PR merge latency
                if pr_latencies:
                    pr_latencies.sort()
                    health["pr_merge_latency_days"] = pr_latencies[len(pr_latencies) // 2]
                else:
                    health["pr_merge_latency_days"] = None
        except:
            pass
        
        # 6. Issues opened and closed 60d + Issue close latency (Health v2)
        try:
            url = f"https://api.github.com/repos/{repo_full_name}/issues?state=all&since={days_60_ago}&per_page=100&page=1"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                issues = response.json()
                cutoff_date = datetime.fromisoformat(days_60_ago.replace("Z", "+00:00"))
                opened_count = 0
                closed_count = 0
                issue_latencies = []
                
                for issue in issues:
                    # Skip PRs
                    if "pull_request" in issue:
                        continue
                    
                    # Count opened
                    created_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                    if created_at >= cutoff_date:
                        opened_count += 1
                    
                    # Count closed + calculate latency
                    if issue.get("closed_at"):
                        closed_at = datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00"))
                        if closed_at >= cutoff_date:
                            closed_count += 1
                            # Calculate issue close latency
                            latency_days = (closed_at - created_at).days
                            if latency_days >= 0:  # Sanity check
                                issue_latencies.append(latency_days)
                
                health["issues_opened_60d"] = opened_count
                health["issues_closed_60d"] = closed_count
                # Compute median issue close latency
                if issue_latencies:
                    issue_latencies.sort()
                    health["issue_close_latency_days"] = issue_latencies[len(issue_latencies) // 2]
                else:
                    health["issue_close_latency_days"] = None
        except:
            pass
        
        # 7. Compute health_score (0..1) - IMPROVED FORMULA
        
        # A) Recency: Last maintainer event (not just push)
        # Use the most recent maintenance signal
        maint_events = [
            health["days_since_push"],
            health["days_since_release"] if health["days_since_release"] is not None else 999
        ]
        last_maint_event = min(maint_events)
        # Exponential decay with genre-adaptive half-life (30 days for active projects)
        rec = clamp(pow(0.5, last_maint_event / 30.0))
        
        # B) Activity: Merged PRs + Contributors + Diversity (Health v2)
        # Normalize adaptively (75th percentile ~20 PRs, 15 contributors)
        pr_activity = clamp(log1p(health["prs_merged_60d"]) / log1p(20))
        contrib_activity = clamp(log1p(health["contributors_90d"]) / log1p(15))
        
        # Contributor diversity bonus (healthy churn rate ~10-30%)
        if health["contributors_90d"] > 0:
            churn_rate = health["new_contributors_90d"] / health["contributors_90d"]
            # Optimal churn: 0.1-0.3 (healthy growth without instability)
            if 0.1 <= churn_rate <= 0.3:
                diversity_bonus = 1.0
            elif churn_rate < 0.1:
                diversity_bonus = 0.7 + (churn_rate / 0.1) * 0.3  # Low churn OK but not ideal
            else:  # > 0.3
                diversity_bonus = max(0.5, 1.0 - (churn_rate - 0.3) * 0.5)  # High churn = instability
        else:
            diversity_bonus = 0.5
        
        activity = 0.5 * pr_activity + 0.3 * contrib_activity + 0.2 * diversity_bonus
        
        # C) Responsiveness: Latency + Throughput (Health v2)
        # Reward fast response times, not just volume
        responsiveness_components = []
        
        # C1) PR merge latency (lower is better)
        if health.get("pr_merge_latency_days") is not None:
            pr_latency = health["pr_merge_latency_days"]
            # Good: <7 days, OK: <30 days, Slow: >30 days
            if pr_latency < 7:
                pr_resp = 1.0
            elif pr_latency < 30:
                pr_resp = clamp(1.0 - (pr_latency - 7) / 23 * 0.4)  # Decay from 1.0 to 0.6
            else:
                pr_resp = max(0.2, clamp(1.0 - pr_latency / 90))  # Decay to minimum 0.2
            responsiveness_components.append(pr_resp)
        
        # C2) Issue close latency (lower is better)
        if health.get("issue_close_latency_days") is not None:
            issue_latency = health["issue_close_latency_days"]
            # Good: <14 days, OK: <60 days, Slow: >60 days
            if issue_latency < 14:
                issue_resp = 1.0
            elif issue_latency < 60:
                issue_resp = clamp(1.0 - (issue_latency - 14) / 46 * 0.4)  # Decay from 1.0 to 0.6
            else:
                issue_resp = max(0.2, clamp(1.0 - issue_latency / 180))  # Decay to minimum 0.2
            responsiveness_components.append(issue_resp)
        
        # C3) Issue throughput (closing rate)
        if health["issues_opened_60d"] > 0:
            throughput = health["issues_closed_60d"] / health["issues_opened_60d"]
            throughput_resp = clamp(throughput)  # 1.0 = closing as fast as opening
            responsiveness_components.append(throughput_resp)
        
        # Average responsiveness from available components
        if responsiveness_components:
            responsiveness = sum(responsiveness_components) / len(responsiveness_components)
        else:
            responsiveness = 0.7  # Neutral (no signals)
        
        # D) Release cadence (if available)
        if health["days_since_release"] is not None:
            if health["days_since_release"] < 30:
                release_score = 1.0  # Recent release
            elif health["days_since_release"] < 90:
                release_score = 0.7  # Reasonable
            elif health["days_since_release"] < 180:
                release_score = 0.4  # Getting stale
            else:
                release_score = 0.2  # Old release
        else:
            release_score = 0.5  # No releases tracked (neutral)
        
        # Combined health score (Health v2)
        # Emphasize responsiveness (35%) for investor trust, then recency (30%), activity (20%), releases (15%)
        # Responsiveness (PR/issue latency) is the key differentiator vs GitHub Trending
        health["health_score"] = 0.30 * rec + 0.20 * activity + 0.35 * responsiveness + 0.15 * release_score
        
        # 8. Compute health_label
        if health["health_score"] >= 0.70:
            health["health_label"] = "alive"
        elif health["health_score"] >= 0.40:
            health["health_label"] = "steady"
        else:
            health["health_label"] = "decaying"
        
    except Exception as e:
        print(f"    ⚠ Health error for {repo_full_name}: {e}")
    
    # Cache the result
    cache[repo_full_name] = {
        "health": health,
        "fetched_at": now.isoformat()
    }
    
    return health

def fetch_github_projects(config):
    """Fetch trending AI/ML projects from GitHub across multiple topics"""
    print("🔍 Fetching projects from GitHub...")
    
    if not GITHUB_TOKEN:
        raise ValueError("❌ GITHUB_TOKEN not found in .env")
    
    # Load health cache
    health_cache = load_health_cache()
    print(f"   Loaded health cache with {len(health_cache)} entries")
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    gh_config = config["github"]
    since_date = (datetime.utcnow() - timedelta(days=config["since_days"])).strftime("%Y-%m-%d")
    
    all_projects = []
    seen_repos = set()
    filtered_stats = {
        "duplicates": 0,
        "forks": 0,
        "archived": 0,
        "no_license": 0,
        "no_description": 0,
        "low_commits": 0
    }
    
    for topic in gh_config["topics"]:
        print(f"  📌 Fetching topic: {topic}")
        
        query = f"topic:{topic} stars:>={gh_config['min_stars']} pushed:>={since_date}"
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={gh_config['per_topic_limit']}"
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            for repo in data.get("items", []):
                full_name = repo["full_name"]
                
                # Skip duplicates
                if full_name in seen_repos:
                    filtered_stats["duplicates"] += 1
                    continue
                
                # Apply quality gates
                gates = gh_config.get("quality_gates", {})
                
                # Exclude forks
                if gates.get("exclude_forks", True) and repo.get("fork"):
                    filtered_stats["forks"] += 1
                    continue
                
                # Exclude archived
                if gates.get("exclude_archived", True) and repo.get("archived"):
                    filtered_stats["archived"] += 1
                    continue
                
                # Require license
                if gates.get("require_license", True) and not repo.get("license"):
                    filtered_stats["no_license"] += 1
                    continue
                
                # Check for README (has_pages is a proxy, or we can check description)
                if gates.get("require_readme", True) and not repo.get("description"):
                    filtered_stats["no_description"] += 1
                    continue
                
                seen_repos.add(full_name)
                
                # Calculate days since update
                updated_at = datetime.fromisoformat(repo["updated_at"].replace("Z", "+00:00"))
                days_since_update = (datetime.now(updated_at.tzinfo) - updated_at).days
                
                # Fetch contributors
                print(f"    Getting data for {full_name}")
                contributors = fetch_contributors(full_name, gh_config["top_contributors"])
                sleep(0.2)  # Rate limiting
                
                # Fetch comprehensive health signals (with caching)
                health = fetch_health_signals_comprehensive(full_name, repo["pushed_at"], health_cache)
                sleep(0.2)  # Rate limiting
                
                # Build project object
                topics_list = repo.get("topics", [])
                license_info = repo.get("license", {}).get("key") if repo.get("license") else None
                tags = extract_tags(repo.get("description", ""), topics_list, license_info)
                # Keep use_cases for backward compat (subset of tags)
                use_cases = [t for t in tags if t in ["agents", "inference", "eval", "training", "dataset", "rag"]]
                
                project = {
                    "source": "github",
                    "id": f"gh_{repo['id']}",
                    "name": repo["name"],
                    "full_name": full_name,
                    "description": repo["description"] or "No description provided",
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"],
                    "language": repo["language"],
                    "url": repo["html_url"],
                    "topics": topics_list,
                    "created_at": repo["created_at"],
                    "updated_at": repo["updated_at"],
                    "days_since_update": days_since_update,
                    "contributors": contributors,
                    "tags": tags,  # New: comprehensive tag list
                    "use_cases": use_cases,  # Kept for backward compat
                    "health": health,  # Nested health object
                }
                
                # Apply health-based quality gate
                min_commits = gh_config.get("quality_gates", {}).get("min_commits_90d", 0)
                if health.get("commits_90d", 0) < min_commits:
                    filtered_stats["low_commits"] += 1
                    continue
                
                # Compute 3 scores (using health object)
                scores = compute_scores(project, "github")
                project.update(scores)
                
                # Legacy score (average for backward compat)
                project["score"] = round((scores["popularity_score"] + scores["health_score"] + scores["people_score"]) / 3, 1)
                
                all_projects.append(project)
            
            print(f"    ✓ Got {len(data.get('items', []))} repos")
            sleep(1)  # Rate limiting between topics
            
        except Exception as e:
            print(f"    ⚠ Error fetching topic {topic}: {e}")
            continue
    
    # Save health cache
    save_health_cache(health_cache)
    print(f"✓ Fetched {len(all_projects)} unique GitHub projects")
    print(f"✓ Saved health cache ({len(health_cache)} entries)")
    
    # Quality gate summary
    total_filtered = sum(filtered_stats.values())
    if total_filtered > 0:
        print(f"📊 Filtered out {total_filtered} repos:")
        for reason, count in filtered_stats.items():
            if count > 0:
                print(f"   - {reason}: {count}")
    
    return all_projects

def fetch_huggingface_models(config):
    """Fetch models from Hugging Face"""
    print("🤗 Fetching models from Hugging Face...")
    
    if not HF_TOKEN:
        print("⚠ HF_TOKEN not found, skipping Hugging Face")
        return []
    
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=HF_TOKEN)
        
        hf_config = config["huggingface"]
        gates = hf_config.get("quality_gates", {})
        all_models = []
        seen_models = set()
        
        for query in hf_config["queries"]:
            print(f"  📌 Searching: {query}")
            
            try:
                models = list(api.list_models(
                    search=query,
                    sort="downloads",
                    direction=-1,
                    limit=hf_config.get("per_query_limit", 50)
                ))
                
                for model in models:
                    model_id = model.id
                    
                    # Skip duplicates
                    if model_id in seen_models:
                        continue
                    
                    # Apply quality gates
                    downloads = getattr(model, "downloads", 0)
                    likes = getattr(model, "likes", 0)
                    
                    if downloads < gates.get("min_downloads", 0):
                        continue
                    if likes < gates.get("min_likes", 0):
                        continue
                    
                    # Check age
                    if model.lastModified:
                        days_since_update = (datetime.now(model.lastModified.tzinfo) - model.lastModified).days
                        if days_since_update > gates.get("max_age_days", 999999):
                            continue
                    else:
                        days_since_update = 0  # Treat as recent if no date available
                    
                    seen_models.add(model_id)
                    
                    # Build project object
                    hf_tags_raw = model.tags or []
                    extracted_tags = extract_tags(model_id, hf_tags_raw, None)  # HF often lacks explicit license
                    # Keep use_cases for backward compat
                    use_cases = [t for t in extracted_tags if t in ["agents", "inference", "eval", "training", "dataset", "rag"]]
                    
                    # Extract HF-specific metadata (v1)
                    hf_metadata = {
                        "library": getattr(model, "library_name", None),
                        "pipeline_tag": getattr(model, "pipeline_tag", None),
                        "license": None,
                        "base_model": None,
                        "architecture": None,
                        "datasets": [],
                        "paper": None
                    }
                    
                    # HF v2: Enhanced vetting signals
                    hf_v2 = {
                        "architecture_family": None,
                        "training_type": None,
                        "eval_present": False,
                        "benchmark_mentioned": False,
                        "license_clarity": "unknown"
                    }
                    
                    # Try to get more metadata from cardData if available
                    card_data = getattr(model, "cardData", {}) or {}
                    if isinstance(card_data, dict):
                        hf_metadata["license"] = card_data.get("license")
                        hf_metadata["base_model"] = card_data.get("base_model")
                        hf_metadata["datasets"] = card_data.get("datasets", [])[:3] if card_data.get("datasets") else []
                        
                        # Try to extract paper URL from metadata
                        if "arxiv" in card_data:
                            hf_metadata["paper"] = card_data["arxiv"]
                        elif "paper" in card_data:
                            hf_metadata["paper"] = card_data["paper"]
                        
                        # HF v2: License clarity
                        if hf_metadata["license"]:
                            hf_v2["license_clarity"] = "explicit"
                        elif hf_metadata["base_model"]:
                            hf_v2["license_clarity"] = "inherited"
                        
                        # HF v2: Training type inference
                        model_name_lower = model_id.lower()
                        if "lora" in model_name_lower or "adapter" in model_name_lower:
                            hf_v2["training_type"] = "lora"
                        elif "finetune" in model_name_lower or "ft" in model_name_lower or hf_metadata["base_model"]:
                            hf_v2["training_type"] = "finetune"
                        else:
                            hf_v2["training_type"] = "base"
                        
                        # HF v2: Eval/benchmark detection (simple keyword check)
                        card_data_str = str(card_data).lower()
                        if any(kw in card_data_str for kw in ["eval", "benchmark", "metric", "score", "test"]):
                            hf_v2["eval_present"] = True
                        if any(kw in card_data_str for kw in ["mmlu", "hellaswag", "winogrande", "arc", "truthfulqa", "fid", "clip score"]):
                            hf_v2["benchmark_mentioned"] = True
                    
                    # Try to infer architecture from tags or model name
                    for tag in hf_tags_raw:
                        if any(arch in tag.lower() for arch in ["gpt", "llama", "mistral", "falcon", "bert", "t5", "vit", "clip", "sdxl", "stable-diffusion"]):
                            hf_metadata["architecture"] = tag
                            break
                    
                    # HF v2: Architecture family classification
                    all_text = " ".join([model_id.lower()] + hf_tags_raw).lower()
                    if any(kw in all_text for kw in ["diffusion", "stable-diffusion", "sdxl", "latent"]):
                        hf_v2["architecture_family"] = "diffusion"
                    elif any(kw in all_text for kw in ["transformer", "gpt", "llama", "mistral", "bert", "t5"]):
                        hf_v2["architecture_family"] = "transformer"
                    elif any(kw in all_text for kw in ["hybrid", "multimodal", "vlm", "vision-language"]):
                        hf_v2["architecture_family"] = "hybrid"
                    
                    project = {
                        "source": "huggingface",
                        "id": f"hf_{model_id.replace('/', '_')}",
                        "name": model_id.split("/")[-1],
                        "full_name": model_id,
                        "description": f"Hugging Face model: {model_id}",
                        "likes": getattr(model, "likes", 0),
                        "downloads": getattr(model, "downloads", 0),
                        "url": f"https://huggingface.co/{model_id}",
                        "topics": hf_tags_raw[:10],  # Limit original HF tags
                        "updated_at": model.lastModified.isoformat() if model.lastModified else None,
                        "days_since_update": days_since_update,
                        "tags": extracted_tags,  # New: comprehensive tag list
                        "use_cases": use_cases,  # Kept for backward compat
                        "hf": hf_metadata,  # v1: HF-specific metadata
                        "hf_v2": hf_v2,  # v2: Enhanced vetting signals
                    }
                    
                    # Compute 3 scores
                    scores = compute_scores(project, "hf")
                    project.update(scores)
                    
                    # Legacy score (average for backward compat)
                    project["score"] = round((scores["popularity_score"] + scores["health_score"] + scores["people_score"]) / 3, 1)
                    
                    all_models.append(project)
                
                print(f"    ✓ Got {len(models)} models")
                
            except Exception as e:
                print(f"    ⚠ Error fetching query {query}: {e}")
                continue
        
        print(f"✓ Fetched {len(all_models)} unique HF models")
        return all_models
        
    except ImportError:
        print("⚠ huggingface_hub not installed, skipping")
        return []
    except Exception as e:
        print(f"⚠ Error fetching HF models: {e}")
        return []

def apply_tag_overrides(projects):
    """Apply manual tag overrides from tag_overrides.json"""
    overrides = load_tag_overrides()
    if not overrides:
        return projects
    
    for project in projects:
        # Build key: "github:owner/repo" or "huggingface:org/model"
        key = f"{project['source']}:{project.get('full_name') or project['id']}"
        if key in overrides:
            override_tags = overrides[key]
            if isinstance(override_tags, list):
                # Union the override tags with existing tags
                existing_tags = set(project.get('tags', []))
                project['tags'] = list(existing_tags | set(override_tags))
    
    return projects

def compute_facets(projects):
    """Compute facet counts for UI filters"""
    facets = {
        'tags': {},
        'source': {},
        'health_label': {}
    }
    
    for project in projects:
        # Tags
        for tag in project.get('tags', []):
            facets['tags'][tag] = facets['tags'].get(tag, 0) + 1
        
        # Source
        source = project.get('source', 'unknown')
        facets['source'][source] = facets['source'].get(source, 0) + 1
        
        # Health label (GitHub only)
        if project.get('health') and project['health'].get('health_label'):
            label = project['health']['health_label']
            facets['health_label'][label] = facets['health_label'].get(label, 0) + 1
    
    return facets

def check_wedge_alerts(current_projects):
    """
    Check for new matches in saved wedges and update alerts.
    This reads the web app's localStorage wedges (if exported) and detects new matches.
    For MVP: we'll write to alerts.json with project IDs that are new since last run.
    """
    alerts_path = Path("data/alerts.json")
    last_run_path = Path("data/cache/last_run_projects.json")
    
    # Load previous run's project IDs
    last_run_ids = set()
    if last_run_path.exists():
        try:
            with open(last_run_path, 'r') as f:
                last_run = json.load(f)
                last_run_ids = {p['id'] for p in last_run.get('projects', [])}
        except Exception as e:
            print(f"⚠️  Could not load last run data: {e}")
    
    # Find new project IDs (not in last run)
    current_ids = {p['id'] for p in current_projects}
    new_ids = current_ids - last_run_ids
    
    if new_ids:
        print(f"\n🔔 Detected {len(new_ids)} new projects since last run")
        
        # Write alerts (simple format for now)
        alerts = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "new_project_count": len(new_ids),
            "new_project_ids": sorted(list(new_ids)),
        }
        
        with open(alerts_path, 'w') as f:
            json.dump(alerts, f, indent=2)
        
        print(f"   Alerts written to {alerts_path}")
    else:
        print(f"\n✓ No new projects detected (compared to last run)")
    
    # Save current run for next comparison
    last_run_path.parent.mkdir(parents=True, exist_ok=True)
    with open(last_run_path, 'w') as f:
        json.dump({"projects": [{"id": p['id']} for p in current_projects]}, f)

def generate_embeddings(projects):
    """
    Generate semantic embeddings for all projects using sentence-transformers.
    Saves to data/embeddings.json for client-side similarity search.
    """
    print(f"\n🧠 Generating embeddings for {len(projects)} projects...")
    
    try:
        # Load model (caches after first use)
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        print(f"   Model: all-MiniLM-L6-v2 (384 dims)")
        
        # Build text representation for each project
        texts = []
        keys = []
        
        for p in projects:
            # Combine relevant text fields
            if p['source'] == 'github':
                text_parts = [
                    p.get('name', ''),
                    p.get('full_name', '').split('/')[-1],  # org name
                    p.get('description', ''),
                    ' '.join(p.get('topics', [])),
                    ' '.join(p.get('tags', [])),
                ]
            else:  # huggingface
                text_parts = [
                    p.get('id', ''),
                    p.get('name', ''),
                    p.get('description', ''),
                    ' '.join(p.get('tags', [])),
                ]
                # Add HF-specific metadata
                if p.get('hf'):
                    hf = p['hf']
                    if hf.get('pipeline_tag'):
                        text_parts.append(hf['pipeline_tag'])
                    if hf.get('library'):
                        text_parts.append(hf['library'])
                if p.get('hf_v2'):
                    hf_v2 = p['hf_v2']
                    if hf_v2.get('architecture_family'):
                        text_parts.append(hf_v2['architecture_family'])
            
            text = ' '.join([t for t in text_parts if t]).strip()
            texts.append(text)
            keys.append(f"{p['source']}:{p['id']}")
        
        # Generate embeddings (batched automatically by sentence-transformers)
        embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        
        # Save embeddings
        output_dir = Path("data")
        output_dir.mkdir(exist_ok=True)
        embeddings_file = output_dir / "embeddings.json"
        
        # Format: array of {id, source, vec}
        embeddings_data = []
        for i, (key, emb) in enumerate(zip(keys, embeddings)):
            source, proj_id = key.split(':', 1)
            embeddings_data.append({
                "id": proj_id,
                "source": source,
                "vec": emb.tolist()  # Convert numpy to list for JSON
            })
        
        with open(embeddings_file, 'w') as f:
            json.dump({
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "dimensions": 384,
                "count": len(embeddings_data),
                "embeddings": embeddings_data
            }, f)
        
        print(f"   ✓ Embeddings saved to {embeddings_file}")
        print(f"   Size: {len(embeddings_data)} items × 384 dims")
        
    except Exception as e:
        print(f"   ⚠️  Failed to generate embeddings: {e}")
        print(f"   Semantic search will be disabled in UI")

def slugify(text):
    """Convert text to safe filename slug"""
    # Replace / with __, remove unsafe chars
    text = text.replace('/', '__').replace('\\', '__')
    text = re.sub(r'[^\w\-_.]', '_', text)
    return text

def to_index_item(project):
    """Convert full project to lightweight index item for shard files"""
    # Compute "why interesting" string
    parts = []
    if project.get('momentum', {}).get('momentum_label') == 'rising':
        parts.append('Rising')
    elif project.get('health', {}).get('health_label') == 'alive':
        parts.append('Alive')
    
    contrib_count = project.get('health', {}).get('contributors_90d', 0) or len(project.get('contributors', []))
    if contrib_count >= 5:
        parts.append('multi-maintainer')
    elif contrib_count >= 2:
        parts.append('team-maintained')
    
    tags = project.get('tags', [])
    modality = next((t for t in tags if t in ['image', 'video', 'audio', '3d', 'multimodal']), None)
    if modality:
        parts.append(modality)
    
    why = ' • '.join(parts[:4]) or 'Open source project'
    
    # Extract license
    license_str = 'unknown'
    if project.get('hf', {}).get('license'):
        lic = project['hf']['license'].lower()
        if 'mit' in lic:
            license_str = 'mit'
        elif 'apache' in lic:
            license_str = 'apache-2.0'
        elif 'gpl' in lic:
            license_str = 'gpl'
        elif 'cc' in lic:
            license_str = 'cc'
        else:
            license_str = project['hf']['license'][:20]
    elif 'permissive' in tags:
        license_str = 'permissive'
    elif 'restricted' in tags:
        license_str = 'restricted'
    
    return {
        'key': f"{project['source']}:{project['id']}",
        'source': project['source'],
        'id': project['id'],
        'title': project['name'],
        'org': project.get('full_name', project['id']).split('/')[0] if '/' in project.get('full_name', project['id']) else '',
        'url': project['url'],
        'updated_at': project['updated_at'],
        'tags_top': tags[:5] if tags else [],
        'license': license_str,
        'health_label': project.get('health', {}).get('health_label', 'unknown'),
        'health_score': project.get('health_score', 0),
        'momentum_label': project.get('momentum', {}).get('momentum_label', 'flat'),
        'momentum_score': project.get('momentum', {}).get('momentum_score', 0),
        'popularity': {
            'stars': project.get('stars', 0),
            'forks': project.get('forks', 0),
            'downloads': project.get('downloads', 0),
            'likes': project.get('likes', 0),
        },
        'scores': {
            'total': project.get('score', 0),
            'popularity': project.get('popularity_score', 0),
            'health': project.get('health_score', 0),
            'people': project.get('people_score', 0),
        },
        'why': why,
    }

def generate_sharded_index(projects):
    """Generate manifest, shards, and detail item files for static hosting"""
    print(f"\n📦 Generating sharded index for {len(projects)} projects...")
    
    # Create output directories
    index_dir = Path("web/public/data/index")
    shards_dir = index_dir / "shards"
    items_dir = Path("web/public/data/items")
    
    for d in [index_dir, shards_dir, items_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Convert all projects to index items
    index_items = [to_index_item(p) for p in projects]
    
    # 1. Write detail files
    print(f"   Writing {len(projects)} detail files...")
    for project in projects:
        slug = f"{project['source']}__{slugify(project['id'])}.json"
        detail_file = items_dir / slug
        with open(detail_file, 'w') as f:
            json.dump({
                'key': f"{project['source']}:{project['id']}",
                'item': project
            }, f, indent=2)
    
    # 2. Generate shards
    shards_meta = []
    
    # Source shards
    for source in ['github', 'huggingface']:
        source_items = [item for item in index_items if item['source'] == source]
        if source_items:
            shard_file = f"source__{source}.json"
            with open(shards_dir / shard_file, 'w') as f:
                json.dump(source_items, f, indent=2)
            shards_meta.append({
                'type': 'source',
                'name': source,
                'file': shard_file,
                'count': len(source_items)
            })
            print(f"   ✓ source__{source}.json ({len(source_items)} items)")
    
    # Tag shards (for high-density tags)
    tag_counts = {}
    for item in index_items:
        for tag in item.get('tags_top', []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Generate shards for tags with count >= 25
    min_shard_size = 25
    for tag, count in tag_counts.items():
        if count >= min_shard_size:
            tag_items = [item for item in index_items if tag in item.get('tags_top', [])]
            shard_file = f"tag__{tag}.json"
            with open(shards_dir / shard_file, 'w') as f:
                json.dump(tag_items, f, indent=2)
            shards_meta.append({
                'type': 'tag',
                'name': tag,
                'file': shard_file,
                'count': len(tag_items)
            })
            print(f"   ✓ tag__{tag}.json ({len(tag_items)} items)")
    
    # Lens shards (precomputed)
    # Compute median popularity for lens filters
    popularity_scores = [item['scores']['popularity'] for item in index_items]
    median_popularity = sorted(popularity_scores)[len(popularity_scores) // 2] if popularity_scores else 50
    
    lens_definitions = {
        'hidden_gems': lambda item: (
            item['health_label'] == 'alive' and
            item['scores']['popularity'] < median_popularity and
            item['health_score'] >= 60
        ),
        'rising': lambda item: (
            item['momentum_label'] in ['rising', 'breakout'] and
            item['health_label'] != 'decaying'
        ),
        'breakouts': lambda item: (
            item['momentum_label'] == 'breakout'
        ),
        'production_ready': lambda item: (
            item['health_label'] in ['alive', 'steady'] and
            item['health_score'] >= 70 and
            item['scores']['people'] >= 50
        ),
    }
    
    for lens_name, lens_filter in lens_definitions.items():
        lens_items = [item for item in index_items if lens_filter(item)]
        if lens_items:
            shard_file = f"lens__{lens_name}.json"
            with open(shards_dir / shard_file, 'w') as f:
                json.dump(lens_items, f, indent=2)
            shards_meta.append({
                'type': 'lens',
                'name': lens_name,
                'file': shard_file,
                'count': len(lens_items)
            })
            print(f"   ✓ lens__{lens_name}.json ({len(lens_items)} items)")
    
    # 3. Compute facets
    facets = compute_facets(projects)
    
    # 4. Write manifest
    manifest = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'counts': {
            'total': len(projects),
            'github': len([p for p in projects if p['source'] == 'github']),
            'hf': len([p for p in projects if p['source'] == 'huggingface']),
        },
        'facets': facets,
        'shards': shards_meta,
    }
    
    manifest_file = index_dir / 'manifest.json'
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"   ✓ manifest.json")
    print(f"   📊 Total shards: {len(shards_meta)}")
    print(f"   📄 Total detail files: {len(projects)}")

def save_projects(projects):
    """Save projects to data/projects.json with facets and momentum (legacy)"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    output_file = data_dir / "projects.json"
    
    # Load previous metrics snapshot for momentum calculation
    previous_snapshot = load_metrics_snapshot()
    new_snapshot = {}
    
    # Compute momentum for each project
    for project in projects:
        # Build key: "github:owner/repo" or "huggingface:org/model"
        key = f"{project['source']}:{project.get('full_name') or project['id']}"
        
        # Current metrics
        current_metrics = {
            'source': project['source'],
            'stars': project.get('stars', 0),
            'forks': project.get('forks', 0),
            'downloads': project.get('downloads', 0),
            'likes': project.get('likes', 0),
        }
        
        # Get previous metrics
        previous_metrics = previous_snapshot.get(key, {})
        
        # Calculate weeks elapsed for momentum normalization
        weeks_elapsed = 1.0
        if previous_metrics.get('fetched_at'):
            try:
                prev_date = datetime.fromisoformat(previous_metrics['fetched_at'])
                current_date = datetime.utcnow()
                weeks_elapsed = max(1.0, (current_date - prev_date).days / 7.0)
            except:
                weeks_elapsed = 1.0
        
        # Compute momentum v2
        momentum = compute_momentum(current_metrics, previous_metrics, weeks_elapsed)
        project['momentum'] = momentum
        
        # Growth rate weekly (for backward compat and display)
        if project['source'] == 'github':
            project['growth_rate_weekly'] = momentum['stars_per_week']
        else:  # HuggingFace
            project['growth_rate_weekly'] = momentum['downloads_per_week']
        
        # Save to new snapshot
        new_snapshot[key] = {
            **current_metrics,
            'fetched_at': datetime.utcnow().isoformat()
        }
    
    # Save new snapshot for next run
    save_metrics_snapshot(new_snapshot)
    
    # Apply tag overrides
    projects = apply_tag_overrides(projects)
    
    # Sort by score (highest first)
    projects_sorted = sorted(projects, key=lambda x: x.get("score", 0), reverse=True)
    
    # Compute facets
    facets = compute_facets(projects_sorted)
    
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(projects_sorted),
        "facets": facets,
        "projects": projects_sorted
    }
    
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Saved {len(projects_sorted)} projects to {output_file}")
    print(f"✓ Facets: {len(facets['tags'])} unique tags, {len(facets['source'])} sources")
    print(f"✓ Momentum: {len([p for p in projects if p.get('momentum', {}).get('momentum_label') == 'rising'])} rising, {len([p for p in projects if p.get('momentum', {}).get('momentum_label') == 'steady'])} steady")

if __name__ == "__main__":
    # Verify tokens are loaded
    if GITHUB_TOKEN:
        print(f"✓ GitHub token loaded: {GITHUB_TOKEN[:6]}...")
    else:
        print("✗ GitHub token not found!")
        exit(1)
    
    if HF_TOKEN:
        print(f"✓ HF token loaded: {HF_TOKEN[:6]}...")
    else:
        print("⚠ HF token not found (will skip Hugging Face)")
    
    try:
        config = load_config()
        print(f"\n📋 Config:")
        print(f"   GitHub: {len(config['github']['topics'])} topics, {config['github']['per_topic_limit']} per topic")
        print(f"   HuggingFace: {len(config['huggingface']['queries'])} queries, {config['huggingface']['per_query_limit']} per query")
        print(f"   Max total: {config.get('max_total_repos', 'unlimited')}\n")
        
        # Fetch from both sources
        github_projects = fetch_github_projects(config)
        hf_models = fetch_huggingface_models(config)
        
        # Combine
        all_projects = github_projects + hf_models
        
        # Enforce max total if set
        max_total = config.get("max_total_repos")
        if max_total and len(all_projects) > max_total:
            print(f"⚠️  Limiting to top {max_total} projects by score")
            all_projects = sorted(all_projects, key=lambda x: x.get("score", 0), reverse=True)[:max_total]
        
        # Save (legacy format + new sharded index)
        save_projects(all_projects)
        generate_sharded_index(all_projects)
        
        # Check for new matches in saved wedges
        check_wedge_alerts(all_projects)
        
        # Generate embeddings for semantic search
        generate_embeddings(all_projects)
        
        print(f"\n✅ Pipeline completed successfully!")
        print(f"   Total: {len(all_projects)} items")
        print(f"   GitHub: {len([p for p in all_projects if p['source'] == 'github'])}")
        print(f"   HuggingFace: {len([p for p in all_projects if p['source'] == 'huggingface'])}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
