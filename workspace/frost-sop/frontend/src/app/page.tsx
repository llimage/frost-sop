"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useStore } from "@/lib/store";
import { getAgents, getTasks, createTask } from "@/lib/api";
import { AgentGrid } from "@/components/AgentCard";
import LogTerminal from "@/components/LogTerminal";
import CeoChat from "@/components/CeoChat";
import { CostDashboard } from "@/components/CostBar";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

const quickCommands = [
  { label: "📊 进度如何？", query: "当前所有项目的进度如何？" },
  { label: "💰 成本正常吗？", query: "本月成本是否在预算内？" },
  { label: "🎯 下一步做什么？", query: "下一步应该做什么？" },
];

export default function Dashboard() {
  const { addLog } = useStore();
  const [taskInput, setTaskInput] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Fetch agents from API
  const { data: apiAgents } = useQuery({
    queryKey: ["agents"],
    queryFn: getAgents,
  });

  // Fetch tasks
  const { data: tasks } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => getTasks(10),
  });

  // Build agent list from API or fallback
  const agents = (apiAgents && Array.isArray(apiAgents) ? apiAgents : []).map(
    (a: any, i: number) => ({
      id: a.id || a.name || `agent-${i}`,
      name: a.name || "Unknown",
      role: a.role || a.agent_type || "agent",
      icon: ["👑", "📋", "🏗️", "💻", "🔍", "🎯", "🦉", "🔗"][i % 8],
      status: a.status || (i < 6 ? "active" : "idle"),
      model: a.model || "deepseek-chat",
      generation: a.generation ?? 1,
      lastActive: a.last_heartbeat || "刚刚",
      costThisMonth: a.cost_this_month || 0,
    })
  );

  const statCards = [
    {
      label: "活跃项目",
      value: tasks ? new Set(tasks.map((t: any) => t.project_id)).size : "2",
      icon: "📁",
      color: "text-blue-600",
    },
    {
      label: "在线 Agent",
      value: agents.filter((a: any) => a.status === "active").length || 8,
      icon: "🤖",
      color: "text-green-600",
    },
    {
      label: "本月任务",
      value: tasks?.length || 17,
      icon: "✅",
      color: "text-blue-600",
    },
    {
      label: "本月成本",
      value: "¥0.15",
      icon: "💰",
      color: "text-amber-600",
    },
  ];

  const handleCreateTask = async () => {
    if (!taskInput.trim() || isCreating) return;
    setIsCreating(true);
    addLog(`🚀 创建任务: ${taskInput}`);
    try {
      const result = await createTask(taskInput, "DEV-001", "default");
      addLog(`✅ 任务已创建: ${result.task_id || "OK"}`);
      setTaskInput("");
    } catch (e: any) {
      addLog(`❌ 创建任务失败: ${e.message || e}`);
    }
    setIsCreating(false);
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">指挥官驾驶舱</h1>
          <p className="text-sm text-[#64748B] mt-1">
            S-O-P AI 家族指挥平台 v1.1.0
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-2">
            <Input
              placeholder="输入任务描述..."
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreateTask();
              }}
              disabled={isCreating}
              className="w-48 lg:w-64 text-sm"
            />
            <Button
              onClick={handleCreateTask}
              disabled={isCreating || !taskInput.trim()}
              size="sm"
            >
              {isCreating ? "执行中..." : "🚀 执行"}
            </Button>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#64748B] uppercase tracking-wider">
                  {stat.label}
                </span>
                <span className="text-lg">{stat.icon}</span>
              </div>
              <div className={`text-2xl font-bold mt-2 ${stat.color}`}>
                {stat.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick commands */}
      <div className="flex gap-2 flex-wrap">
        {quickCommands.map((cmd) => (
          <Badge
            key={cmd.label}
            variant="secondary"
            className="cursor-pointer hover:bg-slate-200 transition-colors text-xs py-1.5 px-3"
          >
            {cmd.label}
          </Badge>
        ))}
      </div>

      {/* Main content: left 7 / right 3 */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left column */}
        <div className="xl:col-span-2 space-y-6">
          {/* Agent Grid */}
          <section>
            <h2 className="text-lg font-semibold text-[#0F172A] mb-3 flex items-center gap-2">
              <span>🤖</span> AI Agent 团队
              <Badge variant="secondary" className="ml-2 text-xs font-normal">
                {agents.length} 个 Agent
              </Badge>
            </h2>
            <AgentGrid agents={agents} />
          </section>

          {/* Log Terminal */}
          <section>
            <h2 className="text-lg font-semibold text-[#0F172A] mb-3 flex items-center gap-2">
              <span>📝</span> 实时日志
            </h2>
            <div className="h-72">
              <LogTerminal />
            </div>
          </section>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* CEO Chat */}
          <section className="h-[420px]">
            <CeoChat />
          </section>

          {/* Cost dashboard */}
          <section>
            <h2 className="text-lg font-semibold text-[#0F172A] mb-3 flex items-center gap-2">
              <span>💰</span> 成本面板
            </h2>
            <Card>
              <CardContent className="p-4">
                <CostDashboard />
              </CardContent>
            </Card>
          </section>

          {/* Quick links */}
          <section>
            <Card>
              <CardContent className="p-4 text-sm space-y-2">
                <h3 className="font-semibold text-[#0F172A] mb-2">
                  📌 快捷操作
                </h3>
                <button className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-50 transition-colors text-[#0F172A]">
                  📋 查看最新产出文档
                </button>
                <button className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-50 transition-colors text-[#0F172A]">
                  🔍 检查成本异常
                </button>
                <button className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-50 transition-colors text-[#0F172A]">
                  📊 生成周报
                </button>
              </CardContent>
            </Card>
          </section>
        </div>
      </div>
    </div>
  );
}
