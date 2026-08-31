import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TrafficPoint, TrendPoint, VehicleClassBreakdown } from '@/types/domain';

const AXIS = { fontSize: 11, fill: '#94a3b8' };
const GRID = '#e2e8f0';

const tooltipStyle = {
  background: '#0f1729',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 8,
  fontSize: 12,
  color: '#e2e8f0',
};

export function TrafficDensityChart({ data }: { data: TrafficPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
        <defs>
          <linearGradient id="trafficFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2563eb" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#2563eb" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="time" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} interval={1} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: '#94a3b8', strokeDasharray: '3 3' }} />
        <Area
          type="monotone"
          dataKey="density"
          name="Density index"
          stroke="#2563eb"
          strokeWidth={2}
          fill="url(#trafficFill)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

const VEHICLE_COLORS = ['#2563eb', '#06b6d4', '#7c3aed', '#d97706'];

export function VehicleMixChart({ data }: { data: VehicleClassBreakdown }) {
  const rows = [
    { name: 'Cars', value: data.cars },
    { name: 'Motorcycles', value: data.motorcycles },
    { name: 'Buses', value: data.buses },
    { name: 'Trucks', value: data.trucks },
  ];
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={rows}
          dataKey="value"
          nameKey="name"
          innerRadius="58%"
          outerRadius="82%"
          paddingAngle={2}
          stroke="none"
        >
          {rows.map((_, i) => (
            <Cell key={i} fill={VEHICLE_COLORS[i]} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} />
        <Legend
          verticalAlign="middle"
          align="right"
          layout="vertical"
          iconType="circle"
          wrapperStyle={{ fontSize: 12 }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function TrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} interval={2} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="traffic" name="Traffic" stroke="#2563eb" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="potholes" name="Road" stroke="#ea580c" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="infrastructure" name="Infra" stroke="#d97706" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="safety" name="Safety" stroke="#7c3aed" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CategoryBarChart({
  data,
}: {
  data: { name: string; value: number; color: string }[];
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(148,163,184,0.1)' }} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
