"use client";

import { useQuery } from "@tanstack/react-query";
import { getCosts } from "@/lib/api";
import { CostDashboard } from "@/components/CostBar";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

export default function CostsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["costs"],
    queryFn: getCosts,
  });

  const total = data?.monthly_total || data?.total_cost || 0;
  const budget = data?.monthly_budget || data?.budget || 300;
  const breakdown = data?.model_breakdown || data?.breakdown || [];
  const history = data?.daily_costs || data?.history || [];

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-[#0F172A]">成本仪表盘</h1>
        <p className="text-sm text-[#64748B] mt-1">API 调用成本追踪与分析</p>
      </div>

      {isLoading && (
        <div className="text-sm text-[#64748B] py-8 text-center">
          加载成本数据...
        </div>
      )}

      {/* Budget Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">预算概览</CardTitle>
        </CardHeader>
        <CardContent>
          <CostDashboard />
        </CardContent>
      </Card>

      {/* Daily/History Breakdown */}
      {history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">每日消耗</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {history.map((item: any, i: number) => (
                <div key={i}>
                  <div className="flex justify-between text-sm py-2">
                    <span className="text-[#0F172A]">{item.date || `Day ${i + 1}`}</span>
                    <span className="font-medium">¥{(item.cost || 0).toFixed(4)}</span>
                  </div>
                  {i < history.length - 1 && <Separator />}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* All-time Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">历史统计</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            {[
              {
                label: "本月总消耗",
                value: `¥${total.toFixed(4)}`,
                color: "text-[#3B82F6]",
              },
              {
                label: "预算余额",
                value: `¥${Math.max(budget - total, 0).toFixed(2)}`,
                color: "text-[#22C55E]",
              },
              {
                label: "预算使用率",
                value: `${Math.min((total / budget) * 100, 100).toFixed(1)}%`,
                color: total > budget * 0.8 ? "text-[#F59E0B]" : "text-[#3B82F6]",
              },
              {
                label: "模型数",
                value: `${breakdown.length}`,
                color: "text-[#64748B]",
              },
            ].map((stat) => (
              <div key={stat.label}>
                <div className="text-xs text-[#64748B] uppercase tracking-wider mb-1">
                  {stat.label}
                </div>
                <div className={`text-xl font-bold ${stat.color}`}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
