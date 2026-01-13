'use client';

import 'vis-network/styles/vis-network.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Network } from 'vis-network';

type Node = {
  id: string;
  kind: 'person' | 'project';
  label: string;
  url: string;
  score?: number;
  topics?: string[];
  use_cases?: string[];
  avatar_url?: string;
  project_count?: number;
  total_score?: number;
  stars?: number;
  full_name?: string;
};

type Link = {
  source: string;
  target: string;
  weight: number;
  contributions?: number;
};

type Payload = {
  nodes: Node[];
  links: Link[];
  person_count: number;
  project_count: number;
};

export default function GraphPage() {
  const ref = useRef<HTMLDivElement | null>(null);
  const netRef = useRef<any>(null);
  const [data, setData] = useState<Payload | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [useCaseFilter, setUseCaseFilter] = useState<string[]>([]);
  const [minProjectCount, setMinProjectCount] = useState(1);
  const [highlightedProject, setHighlightedProject] = useState<string | null>(null);

  useEffect(() => {
    fetch('/data/graph.json')
      .then((r) => r.json())
      .then((j) => setData(j))
      .catch((err) => {
        console.error('Failed to load graph:', err);
        setData(null);
      });

    // Check for project highlight from URL
    const params = new URLSearchParams(window.location.search);
    const project = params.get('project');
    if (project) {
      setHighlightedProject(project);
    }
  }, []);

  // Available use cases
  const allUseCases = useMemo(() => {
    if (!data) return [];
    const cases = new Set<string>();
    data.nodes
      .filter((n) => n.kind === 'project')
      .forEach((p) => p.use_cases?.forEach((uc) => cases.add(uc)));
    return Array.from(cases).sort();
  }, [data]);

  // Filtered nodes and links
  const filteredData = useMemo(() => {
    if (!data) return null;

    let nodes = data.nodes;
    let links = data.links;

    // Filter by use case
    if (useCaseFilter.length > 0) {
      const validProjectIds = new Set(
        nodes
          .filter(
            (n) =>
              n.kind === 'project' &&
              n.use_cases?.some((uc) => useCaseFilter.includes(uc))
          )
          .map((n) => n.id)
      );

      // Keep projects matching filter + their contributors
      const validPersonIds = new Set(
        links
          .filter((l) => validProjectIds.has(l.target))
          .map((l) => l.source)
      );

      nodes = nodes.filter(
        (n) =>
          (n.kind === 'project' && validProjectIds.has(n.id)) ||
          (n.kind === 'person' && validPersonIds.has(n.id))
      );

      links = links.filter(
        (l) => validProjectIds.has(l.target) && validPersonIds.has(l.source)
      );
    }

    // Filter by minimum project count
    if (minProjectCount > 1) {
      const personProjectCounts = new Map<string, number>();
      links.forEach((l) => {
        const count = personProjectCounts.get(l.source) || 0;
        personProjectCounts.set(l.source, count + 1);
      });

      const validPersonIds = new Set(
        Array.from(personProjectCounts.entries())
          .filter(([_, count]) => count >= minProjectCount)
          .map(([id, _]) => id)
      );

      nodes = nodes.filter(
        (n) =>
          n.kind === 'project' ||
          (n.kind === 'person' && validPersonIds.has(n.id))
      );

      links = links.filter((l) => validPersonIds.has(l.source));
    }

    return { nodes, links };
  }, [data, useCaseFilter, minProjectCount]);

  useEffect(() => {
    if (!filteredData || !ref.current) return;

    // vis expects {id, label, ...} and {from, to}
    const nodes = filteredData.nodes.map((n) => {
      const isHighlighted =
        highlightedProject &&
        n.kind === 'project' &&
        n.full_name === highlightedProject;

      return {
        id: n.id,
        label: n.label,
        title: `${n.label}\n${n.url}`,
        value:
          n.kind === 'project'
            ? Math.max(5, (n.score || 1) * 0.5)
            : Math.max(3, (n.project_count || 1) * 2),
        shape: n.kind === 'project' ? 'box' : 'dot',
        color:
          isHighlighted
            ? { background: '#f59e0b', border: '#d97706' }
            : n.kind === 'project'
            ? { background: '#3b82f6', border: '#1e40af' }
            : { background: '#10b981', border: '#059669' },
        font: { color: '#ffffff' },
        borderWidth: isHighlighted ? 4 : 1,
      };
    });

    const edges = filteredData.links.map((e) => ({
      from: e.source,
      to: e.target,
      value: Math.min(5, Math.log(e.weight + 1)),
      color: { color: '#d1d5db', opacity: 0.5 },
    }));

    const network = new Network(
      ref.current,
      { nodes, edges } as any,
      {
        interaction: {
          hover: true,
          navigationButtons: true,
          keyboard: true,
          zoomView: true,
        },
        physics: {
          enabled: true,
          stabilization: { iterations: 100 },
          barnesHut: {
            gravitationalConstant: -8000,
            springConstant: 0.04,
            springLength: 95,
          },
        },
        nodes: {
          font: { size: 14 },
        },
      }
    );

    network.on('click', (params: any) => {
      const nodeId = params.nodes?.[0];
      if (!nodeId) {
        setSelectedNode(null);
        return;
      }
      const node = filteredData.nodes.find((n) => n.id === nodeId);
      if (node) {
        setSelectedNode(node);
      }
    });

    network.on('doubleClick', (params: any) => {
      const nodeId = params.nodes?.[0];
      if (!nodeId) return;
      const node = filteredData.nodes.find((n) => n.id === nodeId);
      if (!node) return;

      if (node.kind === 'person') {
        // Navigate to feed filtered by this contributor
        window.location.href = `/?contributor=${encodeURIComponent(node.label)}`;
      } else if (node.kind === 'project' && node.url) {
        // Open project in new tab
        window.open(node.url, '_blank');
      }
    });

    netRef.current = network;
    return () => network.destroy();
  }, [filteredData]);

  const toggleUseCase = (useCase: string) => {
    setUseCaseFilter((prev) =>
      prev.includes(useCase)
        ? prev.filter((uc) => uc !== useCase)
        : [...prev, useCase]
    );
  };

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading graph...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <a
                href="/"
                className="text-blue-600 hover:text-blue-800 font-medium"
              >
                ← Feed
              </a>
              <h1 className="text-2xl font-bold text-gray-900">
                Contributor Graph
              </h1>
            </div>
            <div className="text-sm text-gray-600">
              {filteredData?.nodes.filter((n) => n.kind === 'person').length || 0}{' '}
              contributors ·{' '}
              {filteredData?.nodes.filter((n) => n.kind === 'project').length ||
                0}{' '}
              projects
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-col gap-3">
            {/* Use case filters */}
            {allUseCases.length > 0 && (
              <div className="flex flex-wrap gap-2 items-center">
                <span className="text-sm font-medium text-gray-700">
                  Filter:
                </span>
                {allUseCases.map((useCase) => (
                  <button
                    key={useCase}
                    onClick={() => toggleUseCase(useCase)}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                      useCaseFilter.includes(useCase)
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    {useCase}
                  </button>
                ))}
                {useCaseFilter.length > 0 && (
                  <button
                    onClick={() => setUseCaseFilter([])}
                    className="text-sm text-gray-600 hover:text-gray-900 underline"
                  >
                    Clear
                  </button>
                )}
              </div>
            )}

            {/* Min project count */}
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-gray-700">
                Min projects per contributor:
              </label>
              <input
                type="range"
                min="1"
                max="10"
                value={minProjectCount}
                onChange={(e) => setMinProjectCount(Number(e.target.value))}
                className="w-32"
              />
              <span className="text-sm text-gray-600">{minProjectCount}</span>
            </div>

            <div className="text-xs text-gray-500">
              💡 Click to select · Double-click contributor → filter feed · Double-click project → open · Drag to move · Scroll to zoom
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Graph */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div ref={ref} className="h-[80vh] w-full bg-gray-50" />
            </div>
          </div>

          {/* Info panel */}
          <div className="lg:col-span-1">
            <div className="sticky top-24">
              {selectedNode ? (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        selectedNode.kind === 'project'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-green-100 text-green-700'
                      }`}
                    >
                      {selectedNode.kind === 'project'
                        ? 'Project'
                        : 'Contributor'}
                    </span>
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      ✕
                    </button>
                  </div>

                  <h3 className="font-semibold text-gray-900 mb-2">
                    {selectedNode.label}
                  </h3>

                  {selectedNode.kind === 'project' && (
                    <>
                      <p className="text-sm text-gray-600 mb-3">
                        {selectedNode.full_name}
                      </p>
                      <div className="space-y-2 mb-4">
                        <div className="text-sm">
                          <span className="text-gray-600">Score:</span>{' '}
                          <span className="font-medium text-blue-600">
                            {selectedNode.score}
                          </span>
                        </div>
                        {selectedNode.stars && (
                          <div className="text-sm">
                            <span className="text-gray-600">Stars:</span>{' '}
                            <span className="font-medium">
                              {selectedNode.stars.toLocaleString()}
                            </span>
                          </div>
                        )}
                      </div>
                      {selectedNode.use_cases &&
                        selectedNode.use_cases.length > 0 && (
                          <div className="mb-4">
                            <div className="text-xs text-gray-600 mb-1">
                              Use cases:
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {selectedNode.use_cases.map((uc) => (
                                <span
                                  key={uc}
                                  className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs"
                                >
                                  {uc}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                    </>
                  )}

                  {selectedNode.kind === 'person' && (
                    <>
                      {selectedNode.avatar_url && (
                        <img
                          src={selectedNode.avatar_url}
                          alt={selectedNode.label}
                          className="w-16 h-16 rounded-full mb-3"
                        />
                      )}
                      <div className="space-y-2 mb-4">
                        <div className="text-sm">
                          <span className="text-gray-600">Projects:</span>{' '}
                          <span className="font-medium">
                            {selectedNode.project_count}
                          </span>
                        </div>
                        <div className="text-sm">
                          <span className="text-gray-600">Total score:</span>{' '}
                          <span className="font-medium text-green-600">
                            {selectedNode.total_score?.toFixed(1)}
                          </span>
                        </div>
                      </div>
                    </>
                  )}

                  <div className="space-y-2">
                    <a
                      href={selectedNode.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full text-center bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                    >
                      Open on GitHub
                    </a>
                    {selectedNode.kind === 'person' && (
                      <a
                        href={`/?contributor=${encodeURIComponent(selectedNode.label)}`}
                        className="block w-full text-center bg-green-600 text-white py-2 px-4 rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                      >
                        📊 View Projects in Feed
                      </a>
                    )}
                  </div>
                </div>
              ) : (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="text-sm text-gray-600 space-y-2">
                    <p className="font-medium text-gray-900 mb-3">Legend</p>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded bg-blue-500"></div>
                      <span>Projects (boxes)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-green-500"></div>
                      <span>Contributors (circles)</span>
                    </div>
                    <p className="mt-4 text-xs text-gray-500">
                      Node size = importance (stars/projects)
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

