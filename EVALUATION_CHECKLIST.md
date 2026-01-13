# OSS Scout - Evaluation Checklist

> **Use this weekly** to audit your discovery tool's quality.

---

## How to Run This Audit

1. Start the dev server: `cd web && npm run dev`
2. Open http://localhost:3000
3. Run through each test below
4. Note issues in the "Findings" column
5. Update config/overrides/blocklist based on findings

---

## Test Scenarios

### 1. Discovery Lens Quality

| Lens | Query | Expected Behavior | Findings |
|------|-------|-------------------|----------|
| **All** | Default view | Should show mix of GitHub + HF, sorted by health | |
| **Hidden Gems** | Under-recognized quality | Low popularity, high health, multi-maintainer | |
| **Production-Ready** | Safe for prod | Alive/steady, active, documented | |
| **Composable Builders** | Tools you can integrate | Libraries, nodes, plugins only | |
| **Real-Time** | Low-latency systems | Interactive, streaming, on-device | |
| **Research-Alive** | Active research | Benchmarks/eval + still maintained | |
| **Single-Maintainer Risk** | Popular but fragile | High stars + 1 contributor | |

**Questions to ask:**
- Are there false positives (shouldn't be in this lens)?
- Are there obvious missing projects?
- Does the top 10 feel trustworthy?

---

### 2. Tag Filtering Accuracy

Test each tag category by clicking filters in the left rail:

| Category | Example Tag | Expected | Findings |
|----------|-------------|----------|----------|
| **Modality** | `video` | Only video-related projects | |
| **Task** | `t2i` | Text-to-image projects | |
| **Ecosystem** | `comfyui` | ComfyUI nodes/related | |
| **Control** | `controlnet` | ControlNet implementations | |
| **Pipeline** | `inference` | Serving/deployment tools | |

**Questions:**
- Are tags missing from obvious projects?
- Are tags wrongly applied?
- Which tags are underused?

---

### 3. Health Signal Validation

Pick 5 random projects marked "Alive":

| Project | Last Commit | Contributors | PRs/Issues | Actually Alive? | Findings |
|---------|-------------|--------------|------------|-----------------|----------|
| 1. | | | | ☐ Yes ☐ No | |
| 2. | | | | ☐ Yes ☐ No | |
| 3. | | | | ☐ Yes ☐ No | |
| 4. | | | | ☐ Yes ☐ No | |
| 5. | | | | ☐ Yes ☐ No | |

Pick 3 projects marked "Decaying":

| Project | Why Flagged | Actually Dead? | Findings |
|---------|-------------|----------------|----------|
| 1. | | ☐ Yes ☐ No | |
| 2. | | ☐ Yes ☐ No | |
| 3. | | ☐ Yes ☐ No | |

**Questions:**
- False positives (marked alive but dead)?
- False negatives (marked decaying but active)?
- Should the threshold change?

---

### 4. Related Projects Quality

Click on any project and check the "Related" section:

| Source Project | Related #1 | Related #2 | Related #3 | Quality Rating |
|----------------|------------|------------|------------|----------------|
| (Pick 3 projects) | | | | ☐ Good ☐ OK ☐ Poor |
| | | | | ☐ Good ☐ OK ☐ Poor |
| | | | | ☐ Good ☐ OK ☐ Poor |

**Questions:**
- Are related projects actually similar?
- Are there obvious missing relationships?
- Too much noise?

---

### 5. Search Quality

Try these searches:

| Search Term | Found What You Expected? | Top Result Makes Sense? | Findings |
|-------------|--------------------------|-------------------------|----------|
| "stable diffusion" | ☐ Yes ☐ No | ☐ Yes ☐ No | |
| "comfyui node" | ☐ Yes ☐ No | ☐ Yes ☐ No | |
| "video generation" | ☐ Yes ☐ No | ☐ Yes ☐ No | |
| "inference engine" | ☐ Yes ☐ No | ☐ Yes ☐ No | |
| "text to speech" | ☐ Yes ☐ No | ☐ Yes ☐ No | |

---

### 6. Noise / Spam Detection

Scan the feed for junk:

| Issue Type | Count | Examples | Action |
|------------|-------|----------|--------|
| Forks masquerading as original | | | Add to blocklist |
| Tutorial/example repos | | | Add to blocklist |
| Abandoned (>1 year no update) | | | Adjust config filters |
| Duplicate/similar projects | | | Keep best one, override others |
| Mislabeled (wrong tags) | | | Add to tag_overrides.json |

---

### 7. Coverage Gaps

**Question:** What's missing that you expected to see?

Missing projects (add to notes):
- ___________________________
- ___________________________
- ___________________________

Reasons:
- [ ] Below quality thresholds (adjust config)
- [ ] Wrong topic/query (add to config.json)
- [ ] Not popular enough yet (expected)
- [ ] Should be manually added (override)

---

### 8. Contributor Graph Check

Open http://localhost:3000/graph

| Test | Result | Findings |
|------|--------|----------|
| Double-click a contributor node → filters feed | ☐ Works ☐ Broken | |
| Click "View in Graph" from project detail | ☐ Works ☐ Broken | |
| Graph shows meaningful connections | ☐ Yes ☐ No | |
| Top contributors make sense | ☐ Yes ☐ No | |

---

### 9. Performance Check

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Page load time | ___ sec | < 2 sec | ☐ Pass ☐ Fail |
| Time to see results | ___ sec | < 1 sec | ☐ Pass ☐ Fail |
| Lens switch time | ___ ms | < 200 ms | ☐ Pass ☐ Fail |
| Filter response | ___ ms | < 100 ms | ☐ Pass ☐ Fail |

If failing, consider:
- Reduce dataset size
- Split JSON (index + details)
- Add pagination

---

### 10. Mobile / Responsive Check

| Device/Size | Layout OK | Filters Work | Graph Works |
|-------------|-----------|--------------|-------------|
| Desktop (1920px) | ☐ | ☐ | ☐ |
| Laptop (1440px) | ☐ | ☐ | ☐ |
| Tablet (768px) | ☐ | ☐ | ☐ |
| Mobile (375px) | ☐ | ☐ | ☐ |

---

## Action Items Template

After audit, fill this out:

### High Priority (fix this week)
1. _____________________________
2. _____________________________
3. _____________________________

### Medium Priority (next sprint)
1. _____________________________
2. _____________________________
3. _____________________________

### Low Priority / Ideas
1. _____________________________
2. _____________________________
3. _____________________________

### Overrides to Add
```json
// pipeline/tag_overrides.json
{
  "github:owner/repo": ["tag1", "tag2"]
}
```

### Blocklist Additions
```json
// pipeline/blocklist.json
{
  "github": ["owner/spam-repo"],
  "huggingface": ["org/test-model"]
}
```

### Config Changes
- Adjust `min_stars`: ___ (currently: 100)
- Adjust `min_commits_90d`: ___ (currently: 5)
- Add topics: ___________
- Remove topics: ___________

---

## Weekly Ritual (30 min)

1. **Run this audit** (15 min)
2. **Update files** (10 min):
   - `pipeline/tag_overrides.json`
   - `pipeline/blocklist.json`
   - `pipeline/config.json`
3. **Rebuild & verify** (5 min):
   ```bash
   ./pipeline/build.sh
   cd web && npm run dev
   ```

This human-in-the-loop process is what makes your scout tool good.

