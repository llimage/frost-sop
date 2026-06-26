"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface AgentInfo {
  id: string;
  name: string;
  role: string;
  icon: string;
  status: "active" | "idle" | "offline";
  model: string;
  generation: number | string;
  lastActive: string;
  costThisMonth: number;
}

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  idle: "secondary",
  offline: "outline",
};

const statusLabel: Record<string, string> = {
  active: "运行中",
  idle: "待命中",
  offline: "离线",
};

export default function AgentCard({
  agent,
  onExpand,
}: {
  agent: AgentInfo;
  onExpand?: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card
      className="hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => {
        setExpanded(!expanded);
        onExpand?.(agent.id);
      }}
    >
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <span className="text-2xl">{agent.icon}</span>
            <div>
              <div className="font-medium text-sm text-[#0F172A]">{agent.name}</div>
              <div className="text-xs text-[#64748B]">{agent.role}</div>
            </div>
          </div>
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              agent.status === "active"
                ? "bg-[#22C55E]"
                : agent.status === "idle"
                ? "bg-[#F59E0B]"
                : "bg-gray-300"
            }`}
            title={agent.status}
          />
        </div>

        {/* Quick info */}
        <div className="flex items-center gap-2 text-xs text-[#64748B] mb-2 flex-wrap">
          <Badge variant="outline" className="text-xs font-normal">
            {agent.model}
          </Badge>
          <Badge variant="secondary" className="text-xs font-normal">
            Gen {agent.generation}
          </Badge>
          <Badge
            variant={statusVariant[agent.status] || "outline"}
            className="text-xs font-normal"
          >
            {statusLabel[agent.status] || agent.status}
          </Badge>
          <span className="text-[#0F172A] font-medium">
            ¥{agent.costThisMonth.toFixed(3)}
          </span>
        </div>

        {/* Expanded detail */}
        {expanded && (
          <div className="mt-3 pt-3 border-t border-[#E2E8F0] space-y-2 text-xs text-[#64748B]">
            <div className="flex justify-between">
              <span>最近活跃</span>
              <span className="text-[#0F172A]">{agent.lastActive}</span>
            </div>
            <div className="flex justify-between">
              <span>本月调用</span>
              <span className="text-[#0F172A]">
                {Math.floor(Math.random() * 50) + 10} 次
              </span>
            </div>
            <div className="flex justify-between">
              <span>成功率</span>
              <span className="text-[#22C55E]">
                {(90 + Math.random() * 10).toFixed(1)}%
              </span>
            </div>
            <button
              className="w-full mt-2 px-3 py-1.5 bg-blue-50 text-blue-700 rounded text-xs font-medium hover:bg-blue-100 transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                onExpand?.(agent.id);
              }}
            >
              查看详情 →
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function AgentGrid({
  agents,
  onAgentExpand,
}: {
  agents: AgentInfo[];
  onAgentExpand?: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} onExpand={onAgentExpand} />
      ))}
    </div>
  );
}
