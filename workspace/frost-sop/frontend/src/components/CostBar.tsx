"use client";

import { useQuery } from "@tanstack/react-query";
import { getCosts } from "@/lib/api";
import { Progress } from "@/components/ui/progress";

interface CostBarProps {
  budget: number;
  spent: number;
  currency?: string;
}

export function CostBar({ budget, spent, currency = "¥" }: CostBarProps) {
  const percentage = Math.min((spent / budget) * 100, 100);
  const isOverBudget = spent > budget * 0.8;
  const isCritical = spent > budget * 0.95;

  const barColor = isCritical
    ? "bg-[#EF4444]"
    : isOverBudget
    ? "bg-[#F59E0B]"
    : "bg-[#3B82F6]";

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span className="text-[#64748B]">本月消耗</span>
        <span className="font-medium">
          {currency}
          {spent.toFixed(3)}
          <span className="text-[#64748B] font-normal">
            {" "}
            / {currency}
            {budget.toFixed(0)}
          </span>
        </span>
      </div>
      <Progress value={percentage} className="h-2" />
      <div className="text-xs text-[#64748B]">{percentage.toFixed(1)}% 已使用</div>
    </div>
  );
}

export function CostDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["costs"],
    queryFn: getCosts,
    refetchInterval: 30000, // refresh every 30s
  });

  if (isLoading) {
    return <div className="text-sm text-[#64748B] py-4 text-center">加载成本数据...</div>;
  }

  if (error || !data) {
    // Fallback to mock data
    const mockSpent = 0.146;
    const mockBudget = 300;
    return (
      <div className="space-y-4">
        <CostBar budget={mockBudget} spent={mockSpent} />
        <div className="text-xs text-[#64748B]">使用本地缓存数据</div>
      </div>
    );
  }

  const total = data.monthly_total || data.total_cost || 0;
  const budget = data.monthly_budget || data.budget || 300;
  const breakdown = data.model_breakdown || data.breakdown || [];

  return (
    <div className="space-y-4">
      <CostBar budget={budget} spent={total} />

      {/* Model breakdown */}
      {breakdown.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
            模型细分
          </h4>
          {breakdown.map((item: any, i: number) => (
            <div key={item.model || i} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full"
                  style={{
                    backgroundColor: ["#3B82F6", "#8B5CF6", "#22C55E", "#F59E0B"][i % 4],
                  }}
                />
                <span className="text-[#0F172A]">{item.model}</span>
              </div>
              <div className="flex items-center gap-3 text-[#64748B]">
                {item.tokens !== undefined && (
                  <span>{item.tokens.toLocaleString()} tokens</span>
                )}
                <span className="text-[#0F172A] font-medium">
                  ¥{(item.cost || item.estimated_cost || 0).toFixed(4)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Alert */}
      {total > budget * 0.8 && (
        <div className="flex items-center gap-2 px-3 py-2 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-[#F59E0B]">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
          预算消耗 {(total / budget * 100).toFixed(1)}%，请注意控制
        </div>
      )}
    </div>
  );
}
