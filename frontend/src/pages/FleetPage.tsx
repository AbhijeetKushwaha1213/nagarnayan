/**
 * Nagar Nayan — Fleet & Physical Sensors Infrastructure
 *
 * Real API-driven management of registered transit fleet buses, mounted camera sensors,
 * and associated RTSP streaming metadata from Phases 2-3 backend APIs.
 */

import { useEffect, useState } from 'react';
import { api } from '@/services/apiClient';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/Page';
import { getIcon } from '@/components/ui/icons';
import type { Bus, Camera, Stream } from '@/types/backend';

type ActiveTab = 'buses' | 'cameras' | 'streams';

export function FleetPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('buses');
  const [buses, setBuses] = useState<Bus[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [streams, setStreams] = useState<Stream[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFleetData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [busesRes, camerasRes, streamsRes] = await Promise.allSettled([
        api.getBuses(),
        api.getCameras(),
        api.getStreams(),
      ]);

      setBuses(busesRes.status === 'fulfilled' ? busesRes.value : []);
      setCameras(camerasRes.status === 'fulfilled' ? camerasRes.value : []);
      setStreams(streamsRes.status === 'fulfilled' ? streamsRes.value : []);

      if (
        busesRes.status === 'rejected' &&
        camerasRes.status === 'rejected' &&
        streamsRes.status === 'rejected'
      ) {
        setError('Failed to reach backend infrastructure APIs. Ensure backend is running.');
      }
    } catch (err: any) {
      setError(err.message || 'Error loading fleet infrastructure');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFleetData();
  }, []);

  const BusIcon = getIcon('bus');
  const VideoIcon = getIcon('video');
  const SignalIcon = getIcon('signal');

  return (
    <PageContainer className="flex flex-col gap-4">
      <Panel className="p-4">
        <PanelHeader
          title="Transit Fleet & Sensing Infrastructure"
          subtitle="Physical mobile sensing hardware: public buses, mounted camera units, and RTSP stream metadata"
          icon={<BusIcon size={16} />}
        />

        {/* Tab Selection */}
        <div className="mt-4 flex items-center gap-2 border-b border-border-subtle pb-3">
          <button
            type="button"
            onClick={() => setActiveTab('buses')}
            className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-[12px] font-medium transition-colors ${
              activeTab === 'buses'
                ? 'bg-brand-50 text-brand-700 font-semibold'
                : 'text-ink-600 hover:bg-surface-muted'
            }`}
          >
            <BusIcon size={14} />
            <span>Buses ({buses.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('cameras')}
            className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-[12px] font-medium transition-colors ${
              activeTab === 'cameras'
                ? 'bg-brand-50 text-brand-700 font-semibold'
                : 'text-ink-600 hover:bg-surface-muted'
            }`}
          >
            <VideoIcon size={14} />
            <span>Cameras ({cameras.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('streams')}
            className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-[12px] font-medium transition-colors ${
              activeTab === 'streams'
                ? 'bg-brand-50 text-brand-700 font-semibold'
                : 'text-ink-600 hover:bg-surface-muted'
            }`}
          >
            <SignalIcon size={14} />
            <span>Streams ({streams.length})</span>
          </button>

          <button
            type="button"
            onClick={fetchFleetData}
            className="ml-auto rounded border border-border-subtle bg-surface px-3 py-1 text-[12px] text-ink-700 hover:bg-surface-muted"
          >
            Refresh
          </button>
        </div>

        {/* Error Notification */}
        {error ? (
          <div className="mt-4 flex items-center justify-between rounded bg-critical-soft p-3 text-[12px] text-critical">
            <span>{error}</span>
            <button
              type="button"
              onClick={fetchFleetData}
              className="font-semibold underline hover:no-underline"
            >
              Try Again
            </button>
          </div>
        ) : null}

        {/* Tab 1: Buses */}
        {activeTab === 'buses' ? (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead>
                <tr className="border-b border-border-subtle text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  <th className="pb-2.5">Bus Number</th>
                  <th className="pb-2.5">Route ID</th>
                  <th className="pb-2.5">Status</th>
                  <th className="pb-2.5">Bus ID (UUID)</th>
                  <th className="pb-2.5">Registered At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle text-ink-700">
                {isLoading ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i} className="py-3">
                      <td className="py-3"><Skeleton className="h-4 w-28" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-20" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-16" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-32" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-24" /></td>
                    </tr>
                  ))
                ) : buses.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-ink-400">
                      No buses currently registered in the database.
                    </td>
                  </tr>
                ) : (
                  buses.map((bus) => (
                    <tr key={bus.id} className="hover:bg-surface-muted transition-colors">
                      <td className="py-3 font-semibold text-ink-900">{bus.bus_number}</td>
                      <td className="py-3 font-mono text-[11px]">{bus.route_id || '—'}</td>
                      <td className="py-3">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                            bus.status === 'active'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {bus.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 font-mono text-[11px] text-ink-500">{bus.id}</td>
                      <td className="py-3 font-mono text-[11px] text-ink-500">
                        {new Date(bus.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}

        {/* Tab 2: Cameras */}
        {activeTab === 'cameras' ? (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead>
                <tr className="border-b border-border-subtle text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  <th className="pb-2.5">Camera Type</th>
                  <th className="pb-2.5">Parent Bus ID</th>
                  <th className="pb-2.5">Status</th>
                  <th className="pb-2.5">Camera ID</th>
                  <th className="pb-2.5">Installed At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle text-ink-700">
                {isLoading ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i} className="py-3">
                      <td className="py-3"><Skeleton className="h-4 w-20" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-32" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-16" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-32" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-24" /></td>
                    </tr>
                  ))
                ) : cameras.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-ink-400">
                      No cameras currently registered in the database.
                    </td>
                  </tr>
                ) : (
                  cameras.map((camera) => (
                    <tr key={camera.id} className="hover:bg-surface-muted transition-colors">
                      <td className="py-3 font-semibold text-ink-900 capitalize">
                        {camera.camera_type} Camera
                      </td>
                      <td className="py-3 font-mono text-[11px] text-ink-500">{camera.bus_id}</td>
                      <td className="py-3">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                            camera.status === 'active'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                        >
                          {camera.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 font-mono text-[11px] text-ink-500">{camera.id}</td>
                      <td className="py-3 font-mono text-[11px] text-ink-500">
                        {new Date(camera.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}

        {/* Tab 3: Streams */}
        {activeTab === 'streams' ? (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead>
                <tr className="border-b border-border-subtle text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  <th className="pb-2.5">RTSP Stream URL</th>
                  <th className="pb-2.5">Protocol</th>
                  <th className="pb-2.5">Camera ID</th>
                  <th className="pb-2.5">Status</th>
                  <th className="pb-2.5">Stream ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle text-ink-700">
                {isLoading ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i} className="py-3">
                      <td className="py-3"><Skeleton className="h-4 w-48" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-16" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-32" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-16" /></td>
                      <td className="py-3"><Skeleton className="h-4 w-32" /></td>
                    </tr>
                  ))
                ) : streams.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-ink-400">
                      No video streams currently registered in the database.
                    </td>
                  </tr>
                ) : (
                  streams.map((stream) => (
                    <tr key={stream.id} className="hover:bg-surface-muted transition-colors">
                      <td className="py-3 font-mono text-[11px] text-brand-700">
                        {stream.stream_url}
                      </td>
                      <td className="py-3 font-mono text-[11px] uppercase">{stream.protocol}</td>
                      <td className="py-3 font-mono text-[11px] text-ink-500">{stream.camera_id}</td>
                      <td className="py-3">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                            stream.status === 'active'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {stream.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 font-mono text-[11px] text-ink-500">{stream.id}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>
    </PageContainer>
  );
}
