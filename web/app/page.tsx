'use client';

import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { embedQuery, loadEmbeddings, findTopSimilar, cosineSimilarity, type EmbeddingsData } from './lib/semantic';

type Project = {
  source: string;
  id: string;
  name: string;
  full_name: string;
  description: string;
  stars?: number;
  likes?: number;
  downloads?: number;
  forks?: number;
  language?: string;
  url: string;
  topics: string[];
  updated_at: string;
  days_since_update: number;
  contributors?: Array<{
    login: string;
    avatar_url: string;
    contributions: number;
    url: string;
  }>;
  tags: string[];
  use_cases: string[];
  score: number;
  popularity_score: number;
  health_score: number;
  people_score: number;
  growth_rate_weekly?: number;
  health?: {
    days_since_push: number;
    days_since_release: number | null;
    commits_30d: number;
    commits_90d: number;
    contributors_90d: number;
    prs_merged_60d: number;
    issues_opened_60d: number;
    issues_closed_60d: number;
    pr_merge_latency_days: number | null;  // Health v2
    issue_close_latency_days: number | null;  // Health v2
    health_score: number;
    health_label: 'alive' | 'steady' | 'decaying';
  };
  momentum?: {
    stars_delta: number;
    forks_delta: number;
    downloads_delta: number;
    likes_delta: number;
    momentum_score: number;
    momentum_label: 'rising' | 'steady' | 'flat';
  };
  hf?: {
    library: string | null;
    pipeline_tag: string | null;
    license: string | null;
    base_model: string | null;
    architecture: string | null;
    datasets: string[];
    paper: string | null;
  };
};

type ProjectData = {
  generated_at: string;
  count: number;
  projects: Project[];
};

// Discovery Lens type
type Lens = {
  id: string;
  label: string;
  description: string;
  filter: (p: Project, median: { popularity: number }) => boolean;
  sortKey: 'health' | 'popularity' | 'people' | 'newest';
};

// Saved Wedge (persistent filter state)
type SavedWedge = {
  id: string;
  name: string;
  createdAt: string;
  state: {
    searchQuery: string;
    sortBy: 'popularity' | 'health' | 'people' | 'newest' | 'momentum';
    sourceFilter: 'all' | 'github' | 'huggingface';
    healthFilter: 'all' | 'hot' | 'steady' | 'decaying';
    useCaseFilter: string[];
    tagFilters: string[];
    maxDaysOld: number;
    activeLens: string;
    minStars: number;
    minContributors: number;
  };
  newMatchCount?: number;
};

const DISCOVERY_LENSES: Lens[] = [
  {
    id: 'all',
    label: 'All',
    description: 'All projects',
    filter: () => true,
    sortKey: 'health',
  },
  {
    id: 'hidden-gems',
    label: 'Hidden Gems',
    description: 'Alive, multi-maintainer, below median popularity',
    filter: (p, median) =>
      p.health?.health_label === 'alive' &&
      p.days_since_update <= 60 &&
      (p.health?.contributors_90d ?? p.contributors?.length ?? 0) >= 2 &&
      p.popularity_score < median.popularity,
    sortKey: 'health',
  },
  {
    id: 'production-ready',
    label: 'Production-Ready',
    description: 'Alive or steady, updated recently, permissive license',
    filter: (p) =>
      (p.health?.health_label === 'alive' || p.health?.health_label === 'steady' || p.days_since_update <= 180) &&
      p.days_since_update <= 180,
    sortKey: 'health',
  },
  {
    id: 'composable-builders',
    label: 'Composable Builders',
    description: 'Node-graph, plugin, library systems in active ecosystems',
    filter: (p) =>
      (p.tags ?? []).some((t) =>
        ['comfyui', 'diffusers', 'automatic1111', 'node-graph', 'plugin', 'library', 'nodes'].includes(t)
      ),
    sortKey: 'health',
  },
  {
    id: 'realtime',
    label: 'Real-Time / Interactive',
    description: 'Low-latency, interactive, streaming, on-device',
    filter: (p) =>
      (p.tags ?? []).some((t) => ['realtime', 'real-time', 'interactive', 'streaming', 'on-device'].includes(t)),
    sortKey: 'health',
  },
  {
    id: 'research-alive',
    label: 'Research-Alive',
    description: 'Benchmark/eval/paper projects still maintained',
    filter: (p) => {
      const allText = [...(p.tags ?? []), ...(p.use_cases ?? []), ...(p.topics ?? [])].join(' ');
      const isResearch = /benchmark|eval|paper|arxiv|metrics|leaderboard/i.test(allText);
      const isAlive =
        p.health?.health_label === 'alive' || (p.source === 'huggingface' && p.days_since_update <= 90);
      return isResearch && isAlive;
    },
    sortKey: 'health',
  },
  {
    id: 'single-maintainer-risk',
    label: 'Single-Maintainer Risk',
    description: 'Popular but maintained by ≤1 person',
    filter: (p, median) =>
      (p.health?.contributors_90d ?? p.contributors?.length ?? 0) <= 1 && p.popularity_score > median.popularity,
    sortKey: 'popularity',
  },
  {
    id: 'rising',
    label: 'Rising',
    description: 'High momentum, active growth, not decaying',
    filter: (p) =>
      p.momentum?.momentum_label === 'rising' &&
      p.days_since_update <= 60 &&
      p.health?.health_label !== 'decaying',
    sortKey: 'health',  // Will use momentum sort when available
  },
];

// Helper: compute "why interesting" one-liner
function computeWhyInteresting(p: Project): string {
  const parts: string[] = [];
  
  if (p.momentum?.momentum_label === 'rising') parts.push('Rising');
  else if (p.health?.health_label === 'alive') parts.push('Alive');
  else if (p.health?.health_label === 'steady') parts.push('Steady');
  
  const contribCount = p.health?.contributors_90d ?? p.contributors?.length ?? 0;
  if (contribCount >= 5) parts.push('multi-maintainer');
  else if (contribCount >= 2) parts.push('team-maintained');
  
  const tags = p.tags ?? [];
  const modality = tags.find((t) => ['image', 'video', 'audio', '3d', 'multimodal', 'world'].includes(t));
  if (modality) parts.push(modality);
  
  const task = tags.find((t) => ['t2i', 'i2i', 't2v', 'i2v', 'v2v', 'tts', 'asr', 'sts', 'voice-conversion'].includes(t));
  if (task) parts.push(task);
  
  const ecosystem = tags.find((t) => ['comfyui', 'diffusers', 'automatic1111', 'pytorch', 'sdxl'].includes(t));
  if (ecosystem) parts.push(ecosystem);
  
  if (p.popularity_score >= 80) parts.push('highly adopted');
  
  return parts.slice(0, 5).join(' • ') || 'Open source project';
}

// Helper: extract license info for display
function getLicenseLabel(p: Project): string | null {
  // Check HF metadata first
  if (p.hf?.license) {
    const lic = p.hf.license.toLowerCase();
    if (lic.includes('mit')) return 'MIT';
    if (lic.includes('apache')) return 'Apache';
    if (lic.includes('bsd')) return 'BSD';
    if (lic.includes('gpl')) return 'GPL';
    if (lic.includes('cc')) return 'CC';
    return p.hf.license.substring(0, 10);
  }
  
  // Check tags
  const tags = p.tags ?? [];
  if (tags.includes('permissive')) return 'Permissive';
  if (tags.includes('restricted')) return 'Restricted';
  if (tags.includes('unclear-license')) return 'Unknown';
  
  return null;
}

// Helper: compute related projects
function computeRelated(selected: Project, allProjects: Project[]): Project[] {
  const others = allProjects.filter((p) => p.id !== selected.id);
  
  if (selected.source === 'github' && selected.contributors && selected.contributors.length > 0) {
    // Rank by shared contributors
    const selectedContribs = new Set(selected.contributors.map((c) => c.login));
    const scored = others
      .filter((p) => p.source === 'github' && p.contributors)
      .map((p) => {
        const overlap = p.contributors!.filter((c) => selectedContribs.has(c.login)).length;
        return { project: p, score: overlap };
      })
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score || b.project.score - a.project.score);
    
    if (scored.length > 0) return scored.slice(0, 6).map((s) => s.project);
  }
  
  // Jaccard similarity on tags/topics/use_cases
  const selectedTokens = new Set([
    ...(selected.tags ?? []),
    ...(selected.use_cases ?? []),
    ...(selected.topics ?? []),
  ]);
  
  if (selectedTokens.size === 0) return [];
  
  const scored = others
    .map((p) => {
      const pTokens = new Set([...(p.tags ?? []), ...(p.use_cases ?? []), ...(p.topics ?? [])]);
      const intersection = [...selectedTokens].filter((t) => pTokens.has(t)).length;
      const union = new Set([...selectedTokens, ...pTokens]).size;
      const jaccard = union > 0 ? intersection / union : 0;
      return { project: p, score: jaccard };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || b.project.score - a.project.score);
  
  return scored.slice(0, 6).map((s) => s.project);
}

export default function Home() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<ProjectData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'popularity' | 'health' | 'people' | 'newest' | 'momentum'>('health');
  const [sourceFilter, setSourceFilter] = useState<'all' | 'github' | 'huggingface'>('all');
  const [healthFilter, setHealthFilter] = useState<'all' | 'hot' | 'steady' | 'decaying'>('all');
  const [useCaseFilter, setUseCaseFilter] = useState<string[]>([]);
  const [tagFilters, setTagFilters] = useState<string[]>([]);
  const [maxDaysOld, setMaxDaysOld] = useState(90);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [contributorFilter, setContributorFilter] = useState<string | null>(null);
  const [activeLens, setActiveLens] = useState<string>('all');
  const [minStars, setMinStars] = useState(0);
  const [minContributors, setMinContributors] = useState(0);
  const [leftRailOpen, setLeftRailOpen] = useState(true);
  const [savedWedges, setSavedWedges] = useState<SavedWedge[]>([]);
  const [showSaveWedgeModal, setShowSaveWedgeModal] = useState(false);
  const [newWedgeName, setNewWedgeName] = useState('');
  const [showWedgesPanel, setShowWedgesPanel] = useState(false);
  const [semanticSearchEnabled, setSemanticSearchEnabled] = useState(false);
  const [embeddingsData, setEmbeddingsData] = useState<EmbeddingsData | null>(null);
  const [semanticQueryVec, setSemanticQueryVec] = useState<Float32Array | null>(null);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [showSimilarProjects, setShowSimilarProjects] = useState(false);
  const [similarProjects, setSimilarProjects] = useState<Project[]>([]);

  // Load saved wedges from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('oss-scout-wedges');
    if (stored) {
      try {
        const wedges = JSON.parse(stored) as SavedWedge[];
        setSavedWedges(wedges);
      } catch (e) {
        console.error('Failed to parse saved wedges:', e);
      }
    }
  }, []);

  // Save wedges to localStorage whenever they change
  useEffect(() => {
    if (savedWedges.length > 0) {
      localStorage.setItem('oss-scout-wedges', JSON.stringify(savedWedges));
    }
  }, [savedWedges]);

  // Load data
  useEffect(() => {
    fetch('/data/projects.json')
      .then((res) => res.json())
      .then((data) => setData(data))
      .catch((err) => console.error('Failed to load projects:', err));
  }, []);

  // Load embeddings for semantic search
  useEffect(() => {
    loadEmbeddings().then((embeddings) => {
      if (embeddings) {
        setEmbeddingsData(embeddings);
        console.log('✓ Semantic search ready');
      }
    });
  }, []);

  // Generate query embedding when semantic search is enabled and query changes
  useEffect(() => {
    if (!semanticSearchEnabled || !searchQuery || !embeddingsData) {
      setSemanticQueryVec(null);
      return;
    }

    const generateQueryEmbedding = async () => {
      setSemanticLoading(true);
      try {
        const vec = await embedQuery(searchQuery);
        setSemanticQueryVec(vec);
      } catch (error) {
        console.error('Failed to generate query embedding:', error);
        setSemanticQueryVec(null);
      } finally {
        setSemanticLoading(false);
      }
    };

    // Debounce embedding generation
    const timeout = setTimeout(generateQueryEmbedding, 500);
    return () => clearTimeout(timeout);
  }, [semanticSearchEnabled, searchQuery, embeddingsData]);

  // Load alerts and update wedge match counts
  useEffect(() => {
    if (!data || savedWedges.length === 0) return;

    fetch('/data/alerts.json')
      .then((res) => res.json())
      .then((alerts) => {
        if (alerts.new_project_ids && alerts.new_project_ids.length > 0) {
          const newIds = new Set(alerts.new_project_ids);
          
          // For each wedge, count how many new projects match its filters
          setSavedWedges((prev) =>
            prev.map((wedge) => {
              // Apply wedge filters to new projects
              const newProjects = data.projects.filter((p) => newIds.has(p.id));
              const matchingNew = newProjects.filter((p) => {
                // Apply wedge filters (simplified - matches the main filter logic)
                if (wedge.state.sourceFilter !== 'all' && p.source !== wedge.state.sourceFilter) return false;
                if (wedge.state.healthFilter !== 'all') {
                  const healthLabel = p.health?.health_label;
                  if (!healthLabel) return wedge.state.healthFilter !== 'hot';
                  if (wedge.state.healthFilter === 'hot' && healthLabel !== 'alive') return false;
                  if (wedge.state.healthFilter === 'steady' && healthLabel !== 'steady') return false;
                  if (wedge.state.healthFilter === 'decaying' && healthLabel !== 'decaying') return false;
                }
                if (wedge.state.tagFilters.length > 0 && !wedge.state.tagFilters.some((tag) => p.tags?.includes(tag))) return false;
                if (p.days_since_update > wedge.state.maxDaysOld && p.days_since_update !== 0) return false;
                return true;
              });

              return { ...wedge, newMatchCount: matchingNew.length };
            })
          );
        }
      })
      .catch((err) => {
        // Alerts file might not exist yet - that's okay
        console.log('No alerts file yet:', err);
      });
  }, [data, savedWedges.length]); // Only rerun when data loads or wedges are added/removed

  // Handle URL params (for contributor filter from graph)
  useEffect(() => {
    const contributor = searchParams?.get('contributor');
    if (contributor) {
      setContributorFilter(contributor);
      setSourceFilter('github'); // Contributors only exist on GitHub (match data source field)
    }
  }, [searchParams]);

  // Available use cases
  const allUseCases = useMemo(() => {
    if (!data) return [];
    const cases = new Set<string>();
    data.projects.forEach((p) => p.use_cases.forEach((uc) => cases.add(uc)));
    return Array.from(cases).sort();
  }, [data]);

  // Available tags with counts (categorized)
  const availableTags = useMemo(() => {
    if (!data) return { modality: [], task: [], ecosystem: [], control: [], pipeline: [], license: [] };
    
    const tagCounts = new Map<string, number>();
    data.projects.forEach((p) => {
      p.tags?.forEach((tag) => {
        tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
      });
    });

    // Categorize tags
    const categories = {
      modality: ['image', 'video', 'audio', '3d', 'multimodal'],
      task: ['t2i', 'i2i', 't2v', 'i2v', 'tts', 'asr'],
      ecosystem: ['diffusers', 'comfyui', 'automatic1111', 'sdxl', 'kohya', 'pytorch', 'jax', 'onnx'],
      control: ['controlnet', 'pose-depth', 'motion-control', 'inpainting', 'lora'],
      pipeline: ['training', 'inference', 'eval', 'dataset', 'ui', 'plugin'],
      license: ['permissive', 'restricted', 'unclear-license'],
    };

    const result: Record<string, Array<{ tag: string; count: number }>> = {};
    
    for (const [category, tags] of Object.entries(categories)) {
      result[category] = tags
        .map((tag) => ({ tag, count: tagCounts.get(tag) || 0 }))
        .filter((item) => item.count > 0)
        .sort((a, b) => b.count - a.count);
    }

    return result;
  }, [data]);

  // Compute median popularity
  const medianPopularity = useMemo(() => {
    if (!data) return 50;
    const scores = data.projects.map((p) => p.popularity_score).sort((a, b) => a - b);
    return scores[Math.floor(scores.length / 2)] ?? 50;
  }, [data]);

  // Filtered and sorted projects
  const filteredProjects = useMemo(() => {
    if (!data) return [];

    let filtered = data.projects;
    let semanticScores: Map<string, number> | null = null;

    // Search (semantic or keyword)
    if (searchQuery) {
      if (semanticSearchEnabled && semanticQueryVec && embeddingsData) {
        // Semantic search: score by similarity
        const embeddingsMap = new Map(
          embeddingsData.embeddings.map((e) => [`${e.source}:${e.id}`, e.vec])
        );

        semanticScores = new Map();
        filtered = filtered.filter((p) => {
          const key = `${p.source}:${p.id}`;
          const vec = embeddingsMap.get(key);
          if (!vec) return false;

          const similarity = cosineSimilarity(semanticQueryVec, vec);
          semanticScores!.set(p.id, similarity);

          // Filter threshold: only show items with similarity > 0.3
          return similarity > 0.3;
        });
      } else {
        // Keyword search
        const q = searchQuery.toLowerCase();
        filtered = filtered.filter(
          (p) =>
            p.name.toLowerCase().includes(q) ||
            p.description.toLowerCase().includes(q) ||
            p.topics.some((t) => t.toLowerCase().includes(q))
        );
      }
    }

    // Source filter
    if (sourceFilter !== 'all') {
      filtered = filtered.filter((p) => p.source === sourceFilter);
    }

    // Health filter
    if (healthFilter !== 'all') {
      filtered = filtered.filter((p) => {
        const healthLabel = p.health?.health_label;
        if (!healthLabel) return healthFilter !== 'hot';
        if (healthFilter === 'hot') return healthLabel === 'alive';
        if (healthFilter === 'steady') return healthLabel === 'steady';
        if (healthFilter === 'decaying') return healthLabel === 'decaying';
        return true;
      });
    }

    // Use case filter
    if (useCaseFilter.length > 0) {
      filtered = filtered.filter((p) =>
        useCaseFilter.some((uc) => p.use_cases.includes(uc))
      );
    }

    // Tag filters
    if (tagFilters.length > 0) {
      filtered = filtered.filter((p) =>
        tagFilters.some((tag) => p.tags?.includes(tag))
      );
    }

    // Contributor filter
    if (contributorFilter) {
      filtered = filtered.filter((p) =>
        p.contributors?.some((c) => c.login === contributorFilter)
      );
    }

    // Activity filter
    filtered = filtered.filter((p) => 
      p.days_since_update === 0 || p.days_since_update <= maxDaysOld
    );

    // Min stars/downloads
    if (minStars > 0) {
      filtered = filtered.filter((p) => {
        const metric = p.stars ?? p.downloads ?? 0;
        return metric >= minStars;
      });
    }

    // Min contributors
    if (minContributors > 0) {
      filtered = filtered.filter((p) => {
        const count = p.health?.contributors_90d ?? p.contributors?.length ?? 0;
        return count >= minContributors;
      });
    }

    // Apply lens filter
    if (activeLens && activeLens !== 'all') {
      const lens = DISCOVERY_LENSES.find((l) => l.id === activeLens);
      if (lens) {
        filtered = filtered.filter((p) => lens.filter(p, { popularity: medianPopularity }));
      }
    }

    // Sort
    filtered = [...filtered].sort((a, b) => {
      // If semantic search is active and we have scores, sort by similarity first
      if (semanticScores && semanticScores.has(a.id) && semanticScores.has(b.id)) {
        const simA = semanticScores.get(a.id)!;
        const simB = semanticScores.get(b.id)!;
        return simB - simA;
      }

      // Otherwise use selected sort
      if (sortBy === 'popularity') return b.popularity_score - a.popularity_score;
      if (sortBy === 'health') return b.health_score - a.health_score;
      if (sortBy === 'people') return b.people_score - a.people_score;
      if (sortBy === 'newest') return a.days_since_update - b.days_since_update;
      if (sortBy === 'momentum') return (b.momentum?.momentum_score ?? 0) - (a.momentum?.momentum_score ?? 0);
      return 0;
    });

    return filtered;
  }, [data, searchQuery, sortBy, sourceFilter, healthFilter, useCaseFilter, tagFilters, contributorFilter, maxDaysOld, minStars, minContributors, activeLens, medianPopularity, semanticSearchEnabled, semanticQueryVec, embeddingsData]);

  // Related projects (for selected project)
  const relatedProjects = useMemo(() => {
    if (!data || !selectedProject) return [];
    return computeRelated(selectedProject, data.projects);
  }, [data, selectedProject]);

  const toggleUseCase = (useCase: string) => {
    setUseCaseFilter((prev) =>
      prev.includes(useCase)
        ? prev.filter((uc) => uc !== useCase)
        : [...prev, useCase]
    );
  };

  const toggleTag = (tag: string) => {
    setTagFilters((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const applyLens = (lensId: string) => {
    const lens = DISCOVERY_LENSES.find((l) => l.id === lensId);
    if (!lens) return;
    
    setActiveLens(lensId);
    setSortBy(lens.sortKey);
    setSearchQuery('');
  };

  const resetFilters = () => {
    setActiveLens('all');
    setSortBy('health');
    setHealthFilter('all');
    setSourceFilter('all');
    setTagFilters([]);
    setUseCaseFilter([]);
    setContributorFilter(null);
    setMinStars(0);
    setMinContributors(0);
    setMaxDaysOld(90);
  };

  // Wedge management functions
  const saveCurrentWedge = () => {
    if (!newWedgeName.trim()) return;
    
    const wedge: SavedWedge = {
      id: `wedge-${Date.now()}`,
      name: newWedgeName.trim(),
      createdAt: new Date().toISOString(),
      state: {
        searchQuery,
        sortBy,
        sourceFilter,
        healthFilter,
        useCaseFilter,
        tagFilters,
        maxDaysOld,
        activeLens,
        minStars,
        minContributors,
      },
      newMatchCount: 0,
    };
    
    setSavedWedges((prev) => [...prev, wedge]);
    setNewWedgeName('');
    setShowSaveWedgeModal(false);
  };

  const loadWedge = (wedge: SavedWedge) => {
    setSearchQuery(wedge.state.searchQuery);
    setSortBy(wedge.state.sortBy);
    setSourceFilter(wedge.state.sourceFilter);
    setHealthFilter(wedge.state.healthFilter);
    setUseCaseFilter(wedge.state.useCaseFilter);
    setTagFilters(wedge.state.tagFilters);
    setMaxDaysOld(wedge.state.maxDaysOld);
    setActiveLens(wedge.state.activeLens);
    setMinStars(wedge.state.minStars);
    setMinContributors(wedge.state.minContributors);
    
    // Clear new match count
    setSavedWedges((prev) =>
      prev.map((w) => (w.id === wedge.id ? { ...w, newMatchCount: 0 } : w))
    );
    setShowWedgesPanel(false);
  };

  const deleteWedge = (wedgeId: string) => {
    setSavedWedges((prev) => prev.filter((w) => w.id !== wedgeId));
  };

  // Find similar projects to the selected one
  const findSimilar = async (project: Project) => {
    if (!embeddingsData || !data) return;

    const embeddingsMap = new Map(
      embeddingsData.embeddings.map((e) => [`${e.source}:${e.id}`, e.vec])
    );

    const key = `${project.source}:${project.id}`;
    const vec = embeddingsMap.get(key);
    if (!vec) {
      console.warn('No embedding found for', key);
      return;
    }

    // Find similar projects
    const similar = findTopSimilar(
      vec,
      data.projects.filter((p) => p.id !== project.id),
      (p) => {
        const pKey = `${p.source}:${p.id}`;
        return embeddingsMap.get(pKey);
      },
      10
    );

    setSimilarProjects(similar.map((s) => s.item));
    setShowSimilarProjects(true);
  };

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading projects...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top Bar */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-4 py-3">
          <div className="flex items-center gap-4">
            {/* Logo + hamburger */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setLeftRailOpen(!leftRailOpen)}
                className="lg:hidden text-gray-600 hover:text-gray-900"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <h1 className="text-xl font-bold text-gray-900">oss-scout</h1>
            </div>

            {/* Search */}
            <div className="flex-1 min-w-[200px] flex items-center gap-2">
              <input
                type="text"
                placeholder={semanticSearchEnabled ? "Semantic search (e.g. 'voice cloning for anime')..." : "Search projects..."}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={semanticLoading}
              />
              {embeddingsData && (
                <button
                  onClick={() => setSemanticSearchEnabled(!semanticSearchEnabled)}
                  className={`px-2 py-1.5 text-xs font-medium rounded transition-colors ${
                    semanticSearchEnabled
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                  title={semanticSearchEnabled ? 'Using semantic search' : 'Use semantic search'}
                >
                  {semanticSearchEnabled ? '🧠' : '🔤'}
                </button>
              )}
            </div>

            {/* Lens dropdown */}
            <select
              value={activeLens}
              onChange={(e) => applyLens(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm font-medium focus:ring-2 focus:ring-blue-500"
            >
              {DISCOVERY_LENSES.map((lens) => (
                <option key={lens.id} value={lens.id}>
                  {lens.label}
                </option>
              ))}
            </select>

            {/* Sort dropdown */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="health">Health</option>
              <option value="popularity">Popularity</option>
              <option value="people">People</option>
              <option value="momentum">Momentum</option>
              <option value="newest">Newest</option>
            </select>

            {/* Graph link */}
            <a
              href="/graph"
              className="px-3 py-1.5 bg-black text-white rounded text-sm font-medium hover:bg-gray-800 transition-colors"
            >
              Graph
            </a>

            {/* Saved Wedges */}
            <button
              onClick={() => setShowWedgesPanel(!showWedgesPanel)}
              className="relative px-3 py-1.5 border border-gray-300 rounded text-sm font-medium hover:bg-gray-50 transition-colors"
            >
              Wedges
              {savedWedges.some((w) => (w.newMatchCount ?? 0) > 0) && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                  {savedWedges.reduce((sum, w) => sum + (w.newMatchCount ?? 0), 0)}
                </span>
              )}
            </button>

            {/* Save Current View */}
            <button
              onClick={() => setShowSaveWedgeModal(true)}
              className="px-3 py-1.5 border border-blue-500 text-blue-600 rounded text-sm font-medium hover:bg-blue-50 transition-colors"
              title="Save current filter state"
            >
              Save
            </button>

            {/* Metadata */}
            <div className="hidden md:block text-xs text-gray-500">
              {filteredProjects.length} / {data.count}
            </div>
          </div>
        </div>

      </header>

      {/* Main content - 3 column layout */}
      <div className="flex max-w-[1600px] mx-auto">
        {/* Left Rail - Filters */}
        <aside
          className={`${
            leftRailOpen ? 'translate-x-0' : '-translate-x-full'
          } fixed lg:sticky lg:translate-x-0 top-[57px] left-0 w-64 h-[calc(100vh-57px)] bg-white border-r border-gray-200 p-4 overflow-y-auto transition-transform z-40 lg:z-0`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm text-gray-900">Filters</h3>
              <button
                onClick={resetFilters}
                className="text-xs text-blue-600 hover:text-blue-800 underline"
              >
                Reset
              </button>
            </div>

            {/* Source */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Source</label>
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value as any)}
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
              >
                <option value="all">All</option>
                <option value="github">GitHub</option>
                <option value="huggingface">Hugging Face</option>
              </select>
            </div>

            {/* Modality */}
            {availableTags.modality.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Modality</label>
                <div className="space-y-1">
                  {availableTags.modality.slice(0, 6).map(({ tag, count }) => (
                    <label key={tag} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={tagFilters.includes(tag)}
                        onChange={() => toggleTag(tag)}
                        className="rounded border-gray-300"
                      />
                      <span className="text-gray-700">{tag}</span>
                      <span className="ml-auto text-xs text-gray-500">({count})</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Task */}
            {availableTags.task.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Task</label>
                <div className="space-y-1">
                  {availableTags.task.slice(0, 6).map(({ tag, count }) => (
                    <label key={tag} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={tagFilters.includes(tag)}
                        onChange={() => toggleTag(tag)}
                        className="rounded border-gray-300"
                      />
                      <span className="text-gray-700">{tag}</span>
                      <span className="ml-auto text-xs text-gray-500">({count})</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Ecosystem */}
            {availableTags.ecosystem.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Ecosystem</label>
                <div className="space-y-1">
                  {availableTags.ecosystem.slice(0, 6).map(({ tag, count }) => (
                    <label key={tag} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={tagFilters.includes(tag)}
                        onChange={() => toggleTag(tag)}
                        className="rounded border-gray-300"
                      />
                      <span className="text-gray-700">{tag}</span>
                      <span className="ml-auto text-xs text-gray-500">({count})</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Health */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Health</label>
              <select
                value={healthFilter}
                onChange={(e) => setHealthFilter(e.target.value as any)}
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
              >
                <option value="all">All</option>
                <option value="hot">Alive</option>
                <option value="steady">Steady</option>
                <option value="decaying">Decaying</option>
              </select>
            </div>

            {/* Updated within */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Updated within: {maxDaysOld}d
              </label>
              <input
                type="range"
                min="1"
                max="180"
                value={maxDaysOld}
                onChange={(e) => setMaxDaysOld(Number(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Min stars */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Min stars/downloads: {minStars}
              </label>
              <input
                type="range"
                min="0"
                max="10000"
                step="100"
                value={minStars}
                onChange={(e) => setMinStars(Number(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Min contributors */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Min contributors: {minContributors}
              </label>
              <input
                type="range"
                min="0"
                max="20"
                value={minContributors}
                onChange={(e) => setMinContributors(Number(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Contributor filter banner */}
            {contributorFilter && (
              <div className="p-2 bg-blue-50 border border-blue-200 rounded text-xs">
                <div className="font-medium text-blue-900 mb-1">
                  By: {contributorFilter}
                </div>
                <button
                  onClick={() => setContributorFilter(null)}
                  className="text-blue-600 hover:text-blue-800 underline"
                >
                  Clear
                </button>
              </div>
            )}
          </div>
        </aside>

        {/* Overlay for mobile */}
        {leftRailOpen && (
          <div
            className="fixed inset-0 bg-black bg-opacity-25 z-30 lg:hidden"
            onClick={() => setLeftRailOpen(false)}
          />
        )}

        {/* Center Feed */}
        <main className="flex-1 min-w-0 p-4 lg:px-6">
          {/* Lens description */}
          {activeLens !== 'all' && (
            <div className="mb-4 p-3 bg-white border border-gray-200 rounded text-sm text-gray-700 italic">
              {DISCOVERY_LENSES.find((l) => l.id === activeLens)?.description}
            </div>
          )}

          {/* Cards */}
          <div className="space-y-3">
            {filteredProjects.length === 0 ? (
              <div className="text-center text-gray-500 py-12 bg-white border border-gray-200 rounded">
                No projects match your filters
              </div>
            ) : (
              filteredProjects.map((project) => (
                <div
                  key={project.id}
                  onClick={() => setSelectedProject(project)}
                  className={`bg-white border rounded p-4 cursor-pointer transition-all hover:shadow-sm ${
                    selectedProject?.id === project.id
                      ? 'ring-2 ring-black'
                      : 'border-gray-200 hover:border-gray-400'
                  }`}
                >
                  {/* Title + badges */}
                  <div className="mb-2">
                    <h3 className="font-bold text-gray-900 mb-1">
                      {project.full_name || project.name}
                    </h3>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-medium">
                        {project.source === 'github' ? 'GitHub' : 'HF'}
                      </span>
                      {project.health?.health_label && (
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            project.health.health_label === 'alive'
                              ? 'bg-green-100 text-green-700'
                              : project.health.health_label === 'steady'
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {project.health.health_label}
                        </span>
                      )}
                      {project.momentum?.momentum_label === 'rising' && (
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                          ⬆️ rising
                        </span>
                      )}
                      {getLicenseLabel(project) && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                          📄 {getLicenseLabel(project)}
                        </span>
                      )}
                      {(project.tags ?? []).slice(0, 2).map((tag) => (
                        <span key={tag} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Why interesting */}
                  <p className="text-sm text-gray-600 mb-2 italic">
                    {computeWhyInteresting(project)}
                  </p>

                  {/* Metrics */}
                  <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
                    {project.stars !== undefined && <span>⭐ {project.stars.toLocaleString()}</span>}
                    {project.likes !== undefined && <span>❤️ {project.likes.toLocaleString()}</span>}
                    {project.downloads !== undefined && <span>⬇️ {project.downloads.toLocaleString()}</span>}
                    {project.contributors && <span>👥 {project.contributors.length}</span>}
                    <span>📅 {project.days_since_update}d</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </main>

        {/* Right Panel - Details */}
        {selectedProject && (
          <aside className="hidden xl:block w-80 sticky top-[57px] h-[calc(100vh-57px)] bg-white border-l border-gray-200 p-4 overflow-y-auto">
            <div className="space-y-4">
              {/* Title + link */}
              <div>
                <h2 className="font-bold text-gray-900 mb-1">{selectedProject.name}</h2>
                <p className="text-xs text-gray-600 mb-3">{selectedProject.full_name}</p>
                <div className="flex flex-wrap gap-2">
                  <a
                    href={selectedProject.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block px-3 py-1 bg-black text-white rounded text-xs font-medium hover:bg-gray-800"
                  >
                    Open {selectedProject.source === 'github' ? 'Repo' : 'Model'} →
                  </a>
                  {selectedProject.source === 'github' && (
                    <a
                      href={`/graph?project=${encodeURIComponent(selectedProject.full_name)}`}
                      className="inline-block px-3 py-1 bg-white border border-gray-300 text-gray-700 rounded text-xs font-medium hover:bg-gray-50"
                    >
                      Graph
                    </a>
                  )}
                  {embeddingsData && (
                    <button
                      onClick={() => findSimilar(selectedProject)}
                      className="inline-block px-3 py-1 bg-purple-600 text-white rounded text-xs font-medium hover:bg-purple-700"
                    >
                      🧠 Find Similar
                    </button>
                  )}
                </div>
              </div>

              {/* Description */}
              <p className="text-sm text-gray-700">{selectedProject.description}</p>

              {/* Scores */}
              <div className="space-y-2 text-xs">
                <div>
                  <div className="flex justify-between mb-1">
                    <span>Health</span>
                    <span className="font-medium">{selectedProject.health_score.toFixed(0)}</span>
                  </div>
                  <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${
                        selectedProject.health_score >= 70 ? 'bg-green-500' :
                        selectedProject.health_score >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${selectedProject.health_score}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span>Popularity</span>
                    <span className="font-medium">{selectedProject.popularity_score.toFixed(0)}</span>
                  </div>
                  <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-orange-500"
                      style={{ width: `${selectedProject.popularity_score}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between mb-1">
                    <span>People</span>
                    <span className="font-medium">{selectedProject.people_score.toFixed(0)}</span>
                  </div>
                  <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: `${selectedProject.people_score}%` }}
                    />
                  </div>
                </div>
                {selectedProject.momentum && (
                  <div>
                    <div className="flex justify-between mb-1">
                      <span>Momentum</span>
                      <span className="font-medium">{selectedProject.momentum.momentum_score.toFixed(1)}</span>
                    </div>
                    <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-600"
                        style={{ width: `${Math.min(100, selectedProject.momentum.momentum_score * 10)}%` }}
                      />
                    </div>
                    {(selectedProject.momentum.stars_delta > 0 || selectedProject.momentum.downloads_delta > 0 || selectedProject.momentum.likes_delta > 0) && (
                      <div className="mt-1 text-[10px] text-gray-500">
                        {selectedProject.momentum.stars_delta > 0 && `+${selectedProject.momentum.stars_delta} ⭐ `}
                        {selectedProject.momentum.downloads_delta > 0 && `+${selectedProject.momentum.downloads_delta.toLocaleString()} ⬇️ `}
                        {selectedProject.momentum.likes_delta > 0 && `+${selectedProject.momentum.likes_delta} ❤️`}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* HF Metadata */}
              {selectedProject.hf && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-900 mb-2">HuggingFace Info</h3>
                  <div className="space-y-1 text-xs text-gray-600">
                    {selectedProject.hf.library && (
                      <div className="flex justify-between">
                        <span>Library:</span>
                        <span className="font-medium">{selectedProject.hf.library}</span>
                      </div>
                    )}
                    {selectedProject.hf.pipeline_tag && (
                      <div className="flex justify-between">
                        <span>Pipeline:</span>
                        <span className="font-medium">{selectedProject.hf.pipeline_tag}</span>
                      </div>
                    )}
                    {selectedProject.hf.license && (
                      <div className="flex justify-between">
                        <span>License:</span>
                        <span className="font-medium">{selectedProject.hf.license}</span>
                      </div>
                    )}
                    {selectedProject.hf.base_model && (
                      <div className="flex justify-between">
                        <span>Base Model:</span>
                        <span className="font-medium text-[10px]">{selectedProject.hf.base_model}</span>
                      </div>
                    )}
                    {selectedProject.hf.datasets && selectedProject.hf.datasets.length > 0 && (
                      <div>
                        <span>Datasets:</span>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {selectedProject.hf.datasets.map((ds) => (
                            <span key={ds} className="px-1.5 py-0.5 bg-gray-100 rounded text-[10px]">
                              {ds}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {selectedProject.hf.paper && (
                      <div className="mt-2">
                        <a
                          href={selectedProject.hf.paper}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 underline"
                        >
                          📄 Paper
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Health v2 Metrics (for GitHub) */}
              {selectedProject.health && (selectedProject.health.pr_merge_latency_days !== null || selectedProject.health.issue_close_latency_days !== null || selectedProject.growth_rate_weekly !== undefined) && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-900 mb-2">Health v2 Metrics</h3>
                  <div className="space-y-1 text-xs text-gray-600">
                    {selectedProject.health.pr_merge_latency_days !== null && (
                      <div className="flex justify-between">
                        <span>PR Merge Latency:</span>
                        <span className={`font-medium ${
                          selectedProject.health.pr_merge_latency_days < 7 ? 'text-green-600' :
                          selectedProject.health.pr_merge_latency_days < 30 ? 'text-yellow-600' :
                          'text-red-600'
                        }`}>
                          {selectedProject.health.pr_merge_latency_days}d
                        </span>
                      </div>
                    )}
                    {selectedProject.health.issue_close_latency_days !== null && (
                      <div className="flex justify-between">
                        <span>Issue Close Latency:</span>
                        <span className={`font-medium ${
                          selectedProject.health.issue_close_latency_days < 14 ? 'text-green-600' :
                          selectedProject.health.issue_close_latency_days < 60 ? 'text-yellow-600' :
                          'text-red-600'
                        }`}>
                          {selectedProject.health.issue_close_latency_days}d
                        </span>
                      </div>
                    )}
                    {selectedProject.growth_rate_weekly !== undefined && selectedProject.growth_rate_weekly !== 0 && (
                      <div className="flex justify-between">
                        <span>Growth Rate:</span>
                        <span className="font-medium text-blue-600">
                          {selectedProject.growth_rate_weekly > 0 ? '+' : ''}{selectedProject.growth_rate_weekly.toFixed(1)}/week
                        </span>
                      </div>
                    )}
                    <div className="mt-2 pt-2 border-t border-gray-200 text-[10px] text-gray-500">
                      Responsiveness-focused scoring for investor trust
                    </div>
                  </div>
                </div>
              )}

              {/* Tags */}
              {(selectedProject.tags ?? []).length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-900 mb-2">Tags</h3>
                  <div className="flex flex-wrap gap-1">
                    {selectedProject.tags!.map((tag) => (
                      <span key={tag} className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Contributors */}
              {selectedProject.contributors && selectedProject.contributors.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-900 mb-2">Contributors</h3>
                  <div className="space-y-2">
                    {selectedProject.contributors.slice(0, 5).map((c) => (
                      <button
                        key={c.login}
                        onClick={() => {
                          setContributorFilter(c.login);
                          setSourceFilter('github');
                        }}
                        className="w-full flex items-center gap-2 p-1 hover:bg-gray-50 rounded text-left"
                      >
                        <img src={c.avatar_url} alt={c.login} className="w-6 h-6 rounded-full" />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-gray-900 truncate">{c.login}</div>
                          <div className="text-[10px] text-gray-500">{c.contributions} commits</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Similar projects (semantic) */}
              {showSimilarProjects && similarProjects.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-xs font-semibold text-gray-900">🧠 Similar Projects</h3>
                    <button
                      onClick={() => setShowSimilarProjects(false)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <div className="space-y-2">
                    {similarProjects.map((similar) => (
                      <button
                        key={similar.id}
                        onClick={() => {
                          setSelectedProject(similar);
                          setShowSimilarProjects(false);
                        }}
                        className="w-full p-2 border border-purple-200 rounded hover:border-purple-400 transition-colors text-left"
                      >
                        <div className="text-xs font-medium text-gray-900 truncate mb-1">
                          {similar.name}
                        </div>
                        <div className="flex gap-1 flex-wrap">
                          {(similar.tags ?? []).slice(0, 3).map((tag) => (
                            <span key={tag} className="px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-[10px]">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Related projects */}
              {!showSimilarProjects && relatedProjects.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-900 mb-2">Related</h3>
                  <div className="space-y-2">
                    {relatedProjects.map((related) => (
                      <button
                        key={related.id}
                        onClick={() => setSelectedProject(related)}
                        className="w-full p-2 border border-gray-200 rounded hover:border-gray-400 transition-colors text-left"
                      >
                        <div className="text-xs font-medium text-gray-900 truncate mb-1">
                          {related.name}
                        </div>
                        <div className="flex gap-1 flex-wrap">
                          {(related.tags ?? []).slice(0, 3).map((tag) => (
                            <span key={tag} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-[10px]">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* Save Wedge Modal */}
      {showSaveWedgeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96 max-w-[90vw]">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Save Current View</h2>
            <p className="text-sm text-gray-600 mb-4">
              Give this wedge a memorable name. You'll be able to quickly return to this exact filter/sort combination.
            </p>
            <input
              type="text"
              placeholder="e.g., Rising ComfyUI Nodes"
              value={newWedgeName}
              onChange={(e) => setNewWedgeName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && saveCurrentWedge()}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-4"
              autoFocus
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => {
                  setShowSaveWedgeModal(false);
                  setNewWedgeName('');
                }}
                className="px-4 py-2 border border-gray-300 rounded text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={saveCurrentWedge}
                disabled={!newWedgeName.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Wedges Panel */}
      {showWedgesPanel && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-[600px] max-w-[90vw] max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900">Saved Wedges</h2>
              <button
                onClick={() => setShowWedgesPanel(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {savedWedges.length === 0 ? (
              <div className="text-center py-8 text-gray-500 text-sm">
                <p className="mb-2">No saved wedges yet.</p>
                <p>Click "Save" in the header to save your current filter state.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {savedWedges.map((wedge) => (
                  <div
                    key={wedge.id}
                    className="border border-gray-200 rounded-lg p-4 hover:border-gray-400 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-gray-900">{wedge.name}</h3>
                          {(wedge.newMatchCount ?? 0) > 0 && (
                            <span className="px-2 py-0.5 bg-red-500 text-white text-xs font-bold rounded-full">
                              {wedge.newMatchCount} new
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          Created {new Date(wedge.createdAt).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        onClick={() => deleteWedge(wedge.id)}
                        className="text-red-600 hover:text-red-800 text-xs font-medium ml-2"
                        title="Delete wedge"
                      >
                        Delete
                      </button>
                    </div>

                    {/* Show active filters */}
                    <div className="flex flex-wrap gap-1 mb-3">
                      {wedge.state.activeLens !== 'all' && (
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">
                          Lens: {DISCOVERY_LENSES.find((l) => l.id === wedge.state.activeLens)?.label}
                        </span>
                      )}
                      {wedge.state.sourceFilter !== 'all' && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">
                          {wedge.state.sourceFilter}
                        </span>
                      )}
                      {wedge.state.healthFilter !== 'all' && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">
                          {wedge.state.healthFilter}
                        </span>
                      )}
                      {wedge.state.tagFilters.length > 0 && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">
                          {wedge.state.tagFilters.length} tags
                        </span>
                      )}
                      {wedge.state.searchQuery && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">
                          search: "{wedge.state.searchQuery}"
                        </span>
                      )}
                    </div>

                    <button
                      onClick={() => loadWedge(wedge)}
                      className="w-full px-3 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors"
                    >
                      Load This Wedge
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
