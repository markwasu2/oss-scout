from dotenv import load_dotenv
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
import re
from math import log1p

load_dotenv()  # 👈 THIS LINE IS THE KEY

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

HEALTH_CACHE_PATH = Path("data/cache/github_health.json")
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

def extract_tags(text, topics, license_info=None):
    """
    Extract practical tags for filtering (modality, task, ecosystem, control, pipeline, license)
    Returns a flat list of tags that actually appear in HF/GH metadata
    """
    text_lower = (text or "").lower()
    all_topics = " ".join(topics).lower() + " " + text_lower
    tags = []
    
    # 1. MODALITY (what type of content)
    if any(kw in all_topics for kw in ["image", "img", "vision", "visual", "picture", "photo"]):
        tags.append("image")
    if any(kw in all_topics for kw in ["video", "vid", "motion", "animation", "clip"]):
        tags.append("video")
    if any(kw in all_topics for kw in ["audio", "sound", "music", "speech", "voice", "tts", "asr"]):
        tags.append("audio")
    if any(kw in all_topics for kw in ["3d", "nerf", "gaussian-splatting", "3dgs", "mesh", "point-cloud"]):
        tags.append("3d")
    if any(kw in all_topics for kw in ["multimodal", "multi-modal", "vision-language", "vlm"]):
        tags.append("multimodal")
    
    # 2. TASK (generation tasks that show up everywhere)
    if any(kw in all_topics for kw in ["text-to-image", "t2i", "text2image"]):
        tags.append("t2i")
    if any(kw in all_topics for kw in ["image-to-image", "i2i", "img2img", "edit", "inpaint", "upscale", "super-resolution"]):
        tags.append("i2i")
    if any(kw in all_topics for kw in ["text-to-video", "t2v", "text2video"]):
        tags.append("t2v")
    if any(kw in all_topics for kw in ["image-to-video", "i2v", "img2video", "animate"]):
        tags.append("i2v")
    if any(kw in all_topics for kw in ["text-to-speech", "tts"]):
        tags.append("tts")
    if any(kw in all_topics for kw in ["speech-to-text", "asr", "transcription", "whisper"]):
        tags.append("asr")
    
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
    if any(kw in all_topics for kw in ["pose", "depth", "normal", "canny", "edge"]):
        tags.append("pose-depth")
    if any(kw in all_topics for kw in ["motion", "motion-control", "camera"]):
        tags.append("motion-control")
    if any(kw in all_topics for kw in ["inpaint", "outpaint", "mask"]):
        tags.append("inpainting")
    if any(kw in all_topics for kw in ["lora", "adapter", "dreambooth"]):
        tags.append("lora")
    
    # 5. PIPELINE TYPE (builder axis)
    if any(kw in all_topics for kw in ["training", "train", "fine-tune", "finetune", "fine-tuning"]):
        tags.append("training")
    if any(kw in all_topics for kw in ["inference", "serving", "deployment", "server", "api"]):
        tags.append("inference")
    if any(kw in all_topics for kw in ["eval", "evaluation", "benchmark", "testing"]):
        tags.append("eval")
    if any(kw in all_topics for kw in ["dataset", "data", "corpus"]):
        tags.append("dataset")
    if any(kw in all_topics for kw in ["gradio", "streamlit", "web-ui", "interface", "demo"]):
        tags.append("ui")
    if any(kw in all_topics for kw in ["plugin", "extension", "node", "custom-node"]):
        tags.append("plugin")
    
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
    
    # Real-time signals
    if any(kw in all_topics for kw in ["realtime", "real-time", "live", "streaming", "interactive"]):
        tags.append("realtime")
    if any(kw in all_topics for kw in ["on-device", "mobile", "edge", "quantized"]):
        tags.append("on-device")
    
    # LLM-specific (keep from old use_cases)
    if any(kw in all_topics for kw in ["agent", "autonomous", "tool-use", "function-calling"]):
        tags.append("agents")
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
        "contributors_90d": 0,
        "prs_merged_60d": 0,
        "issues_opened_60d": 0,
        "issues_closed_60d": 0,
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
        
        # 4. Contributors 90d (approximate from first page sample)
        try:
            url = f"https://api.github.com/repos/{repo_full_name}/commits?since={days_90_ago}&per_page=100&page=1"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                commits = response.json()
                unique_authors = set()
                for c in commits:
                    author_login = c.get("author", {}).get("login") if c.get("author") else None
                    if author_login:
                        unique_authors.add(author_login)
                health["contributors_90d"] = len(unique_authors)
        except:
            pass
        
        # 5. PRs merged 60d
        try:
            url = f"https://api.github.com/repos/{repo_full_name}/pulls?state=closed&per_page=100&page=1"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                prs = response.json()
                cutoff_date = datetime.fromisoformat(days_60_ago.replace("Z", "+00:00"))
                merged_count = 0
                for pr in prs:
                    if pr.get("merged_at"):
                        closed_at = datetime.fromisoformat(pr["closed_at"].replace("Z", "+00:00"))
                        if closed_at >= cutoff_date:
                            merged_count += 1
                health["prs_merged_60d"] = merged_count
        except:
            pass
        
        # 6. Issues opened and closed 60d
        try:
            url = f"https://api.github.com/repos/{repo_full_name}/issues?state=all&since={days_60_ago}&per_page=100&page=1"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                issues = response.json()
                cutoff_date = datetime.fromisoformat(days_60_ago.replace("Z", "+00:00"))
                opened_count = 0
                closed_count = 0
                
                for issue in issues:
                    # Skip PRs
                    if "pull_request" in issue:
                        continue
                    
                    # Count opened
                    created_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                    if created_at >= cutoff_date:
                        opened_count += 1
                    
                    # Count closed
                    if issue.get("closed_at"):
                        closed_at = datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00"))
                        if closed_at >= cutoff_date:
                            closed_count += 1
                
                health["issues_opened_60d"] = opened_count
                health["issues_closed_60d"] = closed_count
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
        
        # B) Activity: Merged PRs + Contributors (more robust than raw commits)
        # Normalize adaptively (75th percentile ~20 PRs, 15 contributors)
        pr_activity = clamp(log1p(health["prs_merged_60d"]) / log1p(20))
        contrib_activity = clamp(log1p(health["contributors_90d"]) / log1p(15))
        activity = 0.6 * pr_activity + 0.4 * contrib_activity
        
        # C) Responsiveness: Issue throughput (not just ratio)
        # Good if closing more than opening (backlog shrinking)
        if health["issues_opened_60d"] > 0:
            throughput = health["issues_closed_60d"] / health["issues_opened_60d"]
            responsiveness = clamp(throughput)  # 1.0 = closing as fast as opening, >1 = catching up
        else:
            # No issues = either very small or uses discussions
            responsiveness = 0.7  # Neutral score
        
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
        
        # Combined health score
        # Emphasize recency (35%) and activity (30%), responsiveness (20%), releases (15%)
        health["health_score"] = 0.35 * rec + 0.30 * activity + 0.20 * responsiveness + 0.15 * release_score
        
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

def save_projects(projects):
    """Save projects to data/projects.json with facets"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    output_file = data_dir / "projects.json"
    
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
        
        # Save
        save_projects(all_projects)
        
        print(f"\n✅ Pipeline completed successfully!")
        print(f"   Total: {len(all_projects)} items")
        print(f"   GitHub: {len([p for p in all_projects if p['source'] == 'github'])}")
        print(f"   HuggingFace: {len([p for p in all_projects if p['source'] == 'huggingface'])}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
