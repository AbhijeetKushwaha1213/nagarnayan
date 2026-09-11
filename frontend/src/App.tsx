import { Route, Routes } from 'react-router-dom';
import { RealtimeProvider } from '@/context/RealtimeContext';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Dashboard } from '@/pages/Dashboard';
import { EventsPage } from '@/pages/EventsPage';
import { Alerts } from '@/pages/Alerts';
import { FleetPage } from '@/pages/FleetPage';
import { LiveMap } from '@/pages/LiveMap';
import { RoadIntelligence } from '@/pages/RoadIntelligence';
import { TrafficIntelligence } from '@/pages/TrafficIntelligence';
import { Infrastructure } from '@/pages/Infrastructure';
import { SafetyIncidents } from '@/pages/SafetyIncidents';
import { FleetCoverage } from '@/pages/FleetCoverage';
import { Analytics } from '@/pages/Analytics';
import { Settings } from '@/pages/Settings';

export default function App() {
  return (
    <RealtimeProvider>
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="fleet" element={<FleetPage />} />
          <Route path="map" element={<LiveMap />} />
          <Route path="road" element={<RoadIntelligence />} />
          <Route path="traffic" element={<TrafficIntelligence />} />
          <Route path="infrastructure" element={<Infrastructure />} />
          <Route path="safety" element={<SafetyIncidents />} />
          <Route path="fleet-coverage" element={<FleetCoverage />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Dashboard />} />
        </Route>
      </Routes>
    </RealtimeProvider>
  );
}
