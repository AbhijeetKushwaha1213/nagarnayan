import { Route, Routes } from 'react-router-dom';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { CommandCenter } from '@/pages/CommandCenter';
import { LiveMap } from '@/pages/LiveMap';
import { RoadIntelligence } from '@/pages/RoadIntelligence';
import { TrafficIntelligence } from '@/pages/TrafficIntelligence';
import { Infrastructure } from '@/pages/Infrastructure';
import { SafetyIncidents } from '@/pages/SafetyIncidents';
import { FleetCoverage } from '@/pages/FleetCoverage';
import { Analytics } from '@/pages/Analytics';
import { Alerts } from '@/pages/Alerts';
import { Settings } from '@/pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<CommandCenter />} />
        <Route path="map" element={<LiveMap />} />
        <Route path="road" element={<RoadIntelligence />} />
        <Route path="traffic" element={<TrafficIntelligence />} />
        <Route path="infrastructure" element={<Infrastructure />} />
        <Route path="safety" element={<SafetyIncidents />} />
        <Route path="fleet" element={<FleetCoverage />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<CommandCenter />} />
      </Route>
    </Routes>
  );
}
