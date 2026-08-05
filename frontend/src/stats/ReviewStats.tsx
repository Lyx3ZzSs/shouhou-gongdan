import { useEffect, useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, TrendingUp, Clock, CheckCircle2, AlertCircle, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Line, Column, Pie } from '@antv/g2plot';
import type { StatsOverview, TrendPoint, ReviewerStat, DurationBucket, StatusBucket, FieldCorrection, EfficiencyPoint } from './types';
import {
  fetchStatsOverview,
  fetchByReviewer,
  fetchTrends,
  fetchDurationDistribution,
  fetchStatusDistribution,
  fetchFieldCorrections,
  fetchEfficiency,
} from '../api/stats';
import { fadeInUp, staggerContainer, staggerItem } from '@/lib/animations';

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
  icon: Icon, label, value, color, accent,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  color: string;
  accent: string;
}) {
  return (
    <motion.div
      className="flex items-center gap-3 rounded-2xl border border-border/30 bg-card/60 backdrop-blur-sm shadow-glass-sm p-4 hover:shadow-glass-md hover:scale-[1.02] transition-all duration-300"
      variants={staggerItem}
    >
      <div className={`flex h-10 w-10 items-center justify-center rounded-2xl ${color} shadow-sm`}>
        <Icon className="h-5 w-5 text-white" />
      </div>
      <div>
        <div className="text-xs text-muted-foreground tracking-wide">{label}</div>
        <div className={`text-xl font-bold tracking-tight ${accent}`}>{value}</div>
      </div>
    </motion.div>
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

    chartRef.current?.destroy();
    chartRef.current = null;

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
  const [corrections, setCorrections] = useState<FieldCorrection[]>([]);
  const [efficiency, setEfficiency] = useState<EfficiencyPoint[]>([]);

  const trendRef = useRef<HTMLDivElement>(null);
  const reviewerRef = useRef<HTMLDivElement>(null);
  const durationRef = useRef<HTMLDivElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);
  const effRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([
      fetchStatsOverview(),
      fetchTrends(30),
      fetchByReviewer(),
      fetchDurationDistribution(),
      fetchStatusDistribution(),
      fetchFieldCorrections(15),
      fetchEfficiency(12),
    ]).then(([ov, tr, rv, dr, st, fc, eff]) => {
      setOverview(ov);
      setTrends(tr);
      setReviewers(rv);
      setDurations(dr);
      setStatuses(st);
      setCorrections(fc);
      setEfficiency(eff);
    }).catch(console.error);
  }, []);

  // 效率趋势折线数据：一次通过率 + 同步接受率（同为百分比，可同轴）
  const effLineData = efficiency.flatMap((p) => [
    { week: p.week, metric: '一次通过率', value: p.one_pass_rate ?? 0 },
    { week: p.week, metric: '同步接受率', value: p.sync_acceptance_rate ?? 0 },
  ]);
  const latestEff = efficiency[efficiency.length - 1];
  const maxCorrection = Math.max(1, ...corrections.map((c) => c.correction_count));

  // 效率趋势折线图
  useChart(effRef, Line, effLineData, (data) => ({
    data,
    xField: 'week',
    yField: 'value',
    seriesField: 'metric',
    smooth: true,
    height: 280,
    color: ['#22C55E', '#3B82F6'],
    yAxis: { title: { text: '%', style: { fill: '#94a3b8' } }, label: { style: { fill: '#94a3b8' } } },
    xAxis: { label: { formatter: (v: string) => v.slice(5), style: { fill: '#94a3b8' } } },
    legend: { position: 'top', itemName: { style: { fill: '#64748b' } } },
    lineStyle: { lineWidth: 2 },
  }));

  // 每日趋势折线图
  useChart(trendRef, Line, trends, (data) => ({
    data,
    xField: 'date',
    yField: 'reviewed_count',
    smooth: true,
    height: 280,
    color: '#3B82F6',
    lineStyle: { lineWidth: 2 },
    area: { style: { fill: 'l(270) 0:#3B82F620 1:#3B82F605' } },
    xAxis: { label: { formatter: (v: string) => v.slice(5), style: { fill: '#94a3b8' } } },
    yAxis: { title: { text: '审核数量', style: { fill: '#94a3b8' } }, label: { style: { fill: '#94a3b8' } } },
    tooltip: { showCrosshairs: true },
  }));

  // 审核人员柱状图
  useChart(reviewerRef, Column, reviewers, (data) => ({
    data,
    xField: 'reviewer_name',
    yField: 'total_reviewed',
    height: 260,
    color: '#6366F1',
    columnStyle: { radius: [6, 6, 0, 0] },
    xAxis: { label: { autoRotate: false, style: { fill: '#94a3b8' } } },
    yAxis: { title: { text: '审核数量', style: { fill: '#94a3b8' } }, label: { style: { fill: '#94a3b8' } } },
  }));

  // 耗时分布柱状图
  useChart(durationRef, Column, durations, (data) => ({
    data,
    xField: 'range',
    yField: 'count',
    height: 260,
    color: '#F59E0B',
    columnStyle: { radius: [6, 6, 0, 0] },
    xAxis: { label: { autoRotate: false, style: { fill: '#94a3b8' } } },
    yAxis: { title: { text: '工单数', style: { fill: '#94a3b8' } }, label: { style: { fill: '#94a3b8' } } },
  }));

  // 状态分布饼图
  useChart(statusRef, Pie, statuses, (data) => ({
    data,
    angleField: 'count',
    colorField: 'status',
    height: 260,
    radius: 0.8,
    color: ['#3B82F6', '#22C55E', '#F59E0B', '#EF4444', '#94A3B8'],
    label: { type: 'outer' as const, style: { fill: '#64748b' } },
    interactions: [{ type: 'element-active' as const }],
  }));

  return (
    <div className="flex h-screen flex-col bg-gradient-to-b from-app via-background to-app">
      {/* 顶部导航 */}
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border/40 bg-background/80 backdrop-blur-xl px-4">
        <Button variant="ghost" size="sm" onClick={onBack} className="rounded-xl">
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回工作台
        </Button>
        <h1 className="text-lg font-semibold tracking-tight">审核统计</h1>
      </header>

      {/* 可滚动内容 */}
      <main className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          {/* 统计卡片行 */}
          {overview && (
            <motion.div
              className="grid grid-cols-2 gap-4 md:grid-cols-4"
              variants={staggerContainer}
              initial="hidden"
              animate="visible"
            >
              <StatCard
                icon={TrendingUp} label="今日审核" color="bg-blue-500" accent="text-blue-600"
                value={String(overview.today_reviewed)}
              />
              <StatCard
                icon={Clock} label="平均耗时" color="bg-amber-500" accent="text-amber-600"
                value={fmtDuration(overview.avg_duration_seconds)}
              />
              <StatCard
                icon={CheckCircle2} label="一次通过率" color="bg-green-500" accent="text-green-600"
                value={fmtRate(overview.one_pass_rate)}
              />
              <StatCard
                icon={AlertCircle} label="待审核" color="bg-orange-500" accent="text-orange-600"
                value={String(overview.pending_count)}
              />
            </motion.div>
          )}

          {/* 每日趋势 */}
          <motion.section
            className="rounded-2xl border border-border/30 bg-card/60 backdrop-blur-sm shadow-glass-sm p-5"
            variants={fadeInUp}
            initial="hidden"
            animate="visible"
          >
            <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground">每日审核趋势（近30天）</h2>
            <div ref={trendRef} style={{ minHeight: 280 }} />
          </motion.section>

          {/* 双列图表 */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <motion.section
              className="rounded-2xl border border-border/30 bg-card/60 backdrop-blur-sm shadow-glass-sm p-5"
              variants={fadeInUp}
              initial="hidden"
              animate="visible"
            >
              <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground">审核人员排名</h2>
              <div ref={reviewerRef} style={{ minHeight: 260 }} />
            </motion.section>
            <motion.section
              className="rounded-2xl border border-border/30 bg-card/60 backdrop-blur-sm shadow-glass-sm p-5"
              variants={fadeInUp}
              initial="hidden"
              animate="visible"
            >
              <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground">审核耗时分布</h2>
              <div ref={durationRef} style={{ minHeight: 260 }} />
            </motion.section>
          </div>

          {/* 状态分布 */}
          <motion.section
            className="rounded-2xl border border-border/30 bg-card/60 backdrop-blur-sm shadow-glass-sm p-5"
            variants={fadeInUp}
            initial="hidden"
            animate="visible"
          >
            <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground">工单状态分布</h2>
            <div ref={statusRef} style={{ minHeight: 260 }} />
          </motion.section>

          {/* 售后效率趋势（审核质量对售后工单的影响） */}
          <motion.section
            className="rounded-2xl border border-border/30 bg-card/60 backdrop-blur-sm shadow-glass-sm p-5"
            variants={fadeInUp}
            initial="hidden"
            animate="visible"
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold tracking-wide text-muted-foreground">售后效率趋势（按周）</h2>
              {latestEff && (
                <div className="flex flex-wrap gap-1.5 text-xs">
                  <span className="rounded-lg bg-muted/60 px-2 py-0.5 text-muted-foreground">
                    平均返工 <b className="text-foreground">{latestEff.avg_reject_count ?? '--'}</b> 次
                  </span>
                  <span className="rounded-lg bg-muted/60 px-2 py-0.5 text-muted-foreground">
                    平均修正 <b className="text-foreground">{latestEff.avg_corrections ?? '--'}</b> 字段
                  </span>
                  <span className="rounded-lg bg-muted/60 px-2 py-0.5 text-muted-foreground">
                    本周确认 <b className="text-foreground">{latestEff.confirmed_count}</b> 单
                  </span>
                </div>
              )}
            </div>
            {effLineData.length === 0 ? (
              <p className="py-8 text-center text-xs text-muted-foreground">
                暂无已确认工单数据。审核确认工单后此处将按周展示一次通过率与同步接受率趋势。
              </p>
            ) : (
              <>
                <div ref={effRef} style={{ minHeight: 280 }} />
                <p className="mt-1 text-[11px] text-muted-foreground/70">
                  一次通过率 = 无驳回记录即通过 ÷ 全部通过；同步接受率依赖销售易同步启用，未启用时恒为 0。
                </p>
              </>
            )}
          </motion.section>

          {/* 错误字段 Top（审核员最常纠正的字段） */}
          <motion.section
            className="rounded-2xl border border-border/30 bg-card/60 backdrop-blur-sm shadow-glass-sm p-5"
            variants={fadeInUp}
            initial="hidden"
            animate="visible"
          >
            <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold tracking-wide text-muted-foreground">
              <Wrench className="h-3.5 w-3.5" />
              错误字段 Top（最常被修正）
            </h2>
            {corrections.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">暂无修正记录。</p>
            ) : (
              <ul className="space-y-2">
                {corrections.map((c) => (
                  <li key={c.field_path} className="flex items-center gap-3">
                    <span className="w-40 shrink-0 truncate text-xs text-muted-foreground" title={c.field_label}>
                      {c.field_label}
                    </span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted/50">
                      <motion.div
                        className="h-full rounded-full bg-amber-500/80"
                        initial={{ width: 0 }}
                        animate={{ width: `${(c.correction_count / maxCorrection) * 100}%` }}
                        transition={{ duration: 0.6, ease: 'easeOut' }}
                      />
                    </div>
                    <span className="w-10 shrink-0 text-right text-xs font-medium text-foreground">
                      {c.correction_count}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </motion.section>
        </div>
      </main>
    </div>
  );
}
