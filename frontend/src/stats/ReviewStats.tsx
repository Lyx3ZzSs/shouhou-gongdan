import { useEffect, useState, useRef } from 'react';
import { ArrowLeft, TrendingUp, Clock, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Line, Column, Pie } from '@antv/g2plot';
import type { StatsOverview, TrendPoint, ReviewerStat, DurationBucket, StatusBucket } from './types';
import {
  fetchStatsOverview,
  fetchByReviewer,
  fetchTrends,
  fetchDurationDistribution,
  fetchStatusDistribution,
} from '../api/stats';

// ── 格式化工具 ──
function fmtDuration(s: number | null): string {
  if (s == null) return '--';
  if (s < 60) return `${s}秒`;
  if (s < 3600) return `${Math.round(s / 60)}分钟`;
  return `${(s / 3600).toFixed(1)}小时`;
}
function fmtRate(r: number | null): string {
  return r != null ? `${r}%` : '--';
}

// ── 统计卡片 ──
function StatCard({
  icon: Icon, label, value, color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${color}`}>
        <Icon className="h-5 w-5 text-white" />
      </div>
      <div>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-xl font-semibold">{value}</div>
      </div>
    </div>
  );
}

// ── 图表容器 Hook ──
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function useChart(
  containerRef: React.RefObject<HTMLDivElement | null>,
  ChartClass: new (container: HTMLElement, config: any) => any,
  data: any[],
  getConfig: (data: any[]) => any,
) {
  const chartRef = useRef<any>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !el.isConnected || data.length === 0) return;

    // 销毁旧图表
    chartRef.current?.destroy();
    chartRef.current = null;

    // requestAnimationFrame 确保容器在 DOM 中完全就绪且已布局
    const raf = requestAnimationFrame(() => {
      try {
        const chart = new ChartClass(el, getConfig(data));
        chart.render();
        chartRef.current = chart;
      } catch (err) {
        console.error('图表创建失败:', err);
      }
    });

    return () => {
      cancelAnimationFrame(raf);
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [containerRef, data]);
}

// ── 主组件 ──
interface Props { onBack: () => void }

export function ReviewStats({ onBack }: Props) {
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [reviewers, setReviewers] = useState<ReviewerStat[]>([]);
  const [durations, setDurations] = useState<DurationBucket[]>([]);
  const [statuses, setStatuses] = useState<StatusBucket[]>([]);

  const trendRef = useRef<HTMLDivElement>(null);
  const reviewerRef = useRef<HTMLDivElement>(null);
  const durationRef = useRef<HTMLDivElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([
      fetchStatsOverview(),
      fetchTrends(30),
      fetchByReviewer(),
      fetchDurationDistribution(),
      fetchStatusDistribution(),
    ]).then(([ov, tr, rv, dr, st]) => {
      setOverview(ov);
      setTrends(tr);
      setReviewers(rv);
      setDurations(dr);
      setStatuses(st);
    }).catch(console.error);
  }, []);

  // 每日趋势折线图
  useChart(trendRef, Line, trends, (data) => ({
    data,
    xField: 'date',
    yField: 'reviewed_count',
    smooth: true,
    height: 280,
    xAxis: { label: { formatter: (v: string) => v.slice(5) } },
    yAxis: { title: { text: '审核数量' } },
    tooltip: { showCrosshairs: true },
  }));

  // 审核人员柱状图
  useChart(reviewerRef, Column, reviewers, (data) => ({
    data,
    xField: 'reviewer_name',
    yField: 'total_reviewed',
    height: 260,
    xAxis: { label: { autoRotate: false } },
    yAxis: { title: { text: '审核数量' } },
  }));

  // 耗时分布柱状图
  useChart(durationRef, Column, durations, (data) => ({
    data,
    xField: 'range',
    yField: 'count',
    height: 260,
    xAxis: { label: { autoRotate: false } },
    yAxis: { title: { text: '工单数' } },
  }));

  // 状态分布饼图
  useChart(statusRef, Pie, statuses, (data) => ({
    data,
    angleField: 'count',
    colorField: 'status',
    height: 260,
    radius: 0.8,
    label: { type: 'outer' as const },
    interactions: [{ type: 'element-active' as const }],
  }));

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* 顶部导航 */}
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border px-4">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回工作台
        </Button>
        <h1 className="text-lg font-semibold">审核统计</h1>
      </header>

      {/* 可滚动内容 */}
      <main className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          {/* 统计卡片行 */}
          {overview && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard
                icon={TrendingUp} label="今日审核" color="bg-blue-500"
                value={String(overview.today_reviewed)}
              />
              <StatCard
                icon={Clock} label="平均耗时" color="bg-amber-500"
                value={fmtDuration(overview.avg_duration_seconds)}
              />
              <StatCard
                icon={CheckCircle2} label="通过率" color="bg-green-500"
                value={fmtRate(overview.approval_rate)}
              />
              <StatCard
                icon={AlertCircle} label="待审核" color="bg-orange-500"
                value={String(overview.pending_count)}
              />
            </div>
          )}

          {/* 每日趋势 - 全宽 */}
          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-medium">每日审核趋势（近30天）</h2>
            <div ref={trendRef} style={{ minHeight: 280 }} />
          </section>

          {/* 双列图表 */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-3 text-sm font-medium">审核人员排名</h2>
              <div ref={reviewerRef} style={{ minHeight: 260 }} />
            </section>
            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-3 text-sm font-medium">审核耗时分布</h2>
              <div ref={durationRef} style={{ minHeight: 260 }} />
            </section>
          </div>

          {/* 状态分布 */}
          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-medium">工单状态分布</h2>
            <div ref={statusRef} style={{ minHeight: 260 }} />
          </section>
        </div>
      </main>
    </div>
  );
}
