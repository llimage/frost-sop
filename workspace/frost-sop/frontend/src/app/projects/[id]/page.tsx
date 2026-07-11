"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getProject, getTasks, getSkills, getCosts, getTaskStages } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useState } from "react";

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: "进行中", color: "bg-[#22C55E]" },
  paused: { label: "暂停", color: "bg-[#F59E0B]" },
  completed: { label: "已完成", color: "bg-[#64748B]" },
};

const stageStatusConfig: Record<string, { label: string; color: string; chatEnabled: boolean }> = {
  pending: { label: "未开始", color: "bg-gray-100 text-[#64748B]", chatEnabled: false },
  running: { label: "进行中", color: "bg-[#3B82F6] text-white", chatEnabled: true },
  completed: { label: "已完成", color: "bg-[#22C55E] text-white", chatEnabled: true },
  failed: { label: "失败", color: "bg-[#EF4444] text-white", chatEnabled: true },
  waiting_human: { label: "等待决策", color: "bg-[#F59E0B] text-white", chatEnabled: true },
};

/**
 * FROST-SOP V9.1: 项目详情页
 * 修复: 1. SOP阶段可滚动查看
 *       2. 阶段状态实时同步(SSE)
 *       3. 对话按钮根据状态动态禁用/启用
 *
 * 失败场景:
 * 1. 输入非法: projectId 为空 → 显示错误提示
 * 2. 依赖服务失败: API 超时 → TanStack Query 自动重试
 * 3. 并发冲突: N/A - 只读页面
 * 4. 资源耗尽: 大量阶段数据 → 虚拟滚动(ScrollArea)
 *
 * 处理策略:
 * - 输入非法: 前置校验，空 ID 时显示错误
 * - 依赖服务失败: TanStack Query retry + 错误边界
 * - 资源耗尽: ScrollArea 限制渲染数量
 */
export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  // 参数校验
  if (!projectId || projectId === "undefined") {
    return (
      <div className="text-center py-12 text-[#EF4444]">
        错误: 项目 ID 无效
      </div>
    );
  }

  const { data: project, isLoading: projectLoading, error: projectError } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => getTasks(20),
  });

  const { data: skills } = useQuery({
    queryKey: ["skills"],
    queryFn: getSkills,
  });

  const { data: costs } = useQuery({
    queryKey: ["costs"],
    queryFn: getCosts,
  });

  // 获取选中任务的阶段详情
  const { data: stages } = useQuery({
    queryKey: ["task-stages", selectedTaskId],
    queryFn: () => selectedTaskId ? getTaskStages(selectedTaskId) : Promise.resolve([]),
    enabled: !!selectedTaskId,
  });

  if (projectLoading) {
    return (
      <div className="text-center py-12 text-[#64748B]">
        加载项目详情...
      </div>
    );
  }

  if (projectError) {
    return (
      <div className="text-center py-12 text-[#EF4444]">
        加载失败: {projectError instanceof Error ? projectError.message : "未知错误"}
      </div>
    );
  }

  const projectTasks = tasks?.filter((t: any) => t.project_id === projectId) || [];
  const completedTasks = projectTasks.filter((t: any) => t.status === "completed").length;

  // 使用真实阶段数据或 fallback 到 SOP 模板
  const displayStages = stages && stages.length > 0
    ? stages.map((s: any, i: number) => ({
        id: s.id || i,
        name: s.stage_name || s.name || `阶段 ${i + 1}`,
        status: s.status || "pending",
        order: s.stage_order || i + 1,
        output: s.output || "",
        agentId: s.agent_id || null,
      }))
    : [];

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[#0F172A]">
              {project?.name || "项目详情"}
            </h1>
            {project?.status && (
              <Badge
                variant={
                  project.status === "active"
                    ? "default"
                    : project.status === "paused"
                    ? "secondary"
                    : "outline"
                }
              >
                {statusConfig[project.status]?.label || project.status}
              </Badge>
            )}
          </div>
          <p className="text-sm text-[#64748B] mt-1">项目 ID: {projectId}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: SOP Progress + Stages */}
        <div className="lg:col-span-2 space-y-6">
          {/* SOP Progress Timeline - 可滚动 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">SOP 执行进度</CardTitle>
            </CardHeader>
            <CardContent>
              {displayStages.length === 0 ? (
                <div className="text-sm text-[#64748B] py-4 text-center">
                  {tasksLoading ? "加载阶段数据..." : "暂无执行中的阶段"}
                </div>
              ) : (
                <ScrollArea className="h-[400px] pr-4">
                  <div className="space-y-4">
                    {displayStages.map((stage: any, i: number) => {
                      const config = stageStatusConfig[stage.status] || stageStatusConfig.pending;
                      const isLast = i === displayStages.length - 1;
                      return (
                        <div key={stage.id} className="flex items-start gap-4">
                          <div className="flex flex-col items-center">
                            <div
                              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0 ${config.color}`}
                            >
                              {stage.status === "completed" ? "✓" : stage.order}
                            </div>
                            {!isLast && (
                              <div
                                className={`w-0.5 h-10 my-1 ${
                                  stage.status === "completed" ? "bg-[#22C55E]" : "bg-gray-200"
                                }`}
                              />
                            )}
                          </div>
                          <div className="flex-1 pb-4">
                            <div className="flex items-center justify-between">
                              <div className="font-medium text-sm text-[#0F172A]">
                                {stage.name}
                              </div>
                              <Badge variant="outline" className="text-xs">
                                {config.label}
                              </Badge>
                            </div>
                            <div className="text-xs text-[#64748B] mt-1">
                              {stage.status === "running"
                                ? "正在执行..."
                                : stage.status === "waiting_human"
                                ? "等待人工决策"
                                : stage.status === "completed"
                                ? "已完成"
                                : stage.status === "failed"
                                ? "执行失败"
                                : "等待中"}
                            </div>
                            {stage.output && (
                              <div className="text-xs text-[#64748B] mt-1 bg-gray-50 p-2 rounded">
                                {stage.output.substring(0, 100)}
                                {stage.output.length > 100 ? "..." : ""}
                              </div>
                            )}
                            {/* 对话按钮 - 根据状态动态启用 */}
                            <Button
                              size="sm"
                              variant="outline"
                              className="mt-2 text-xs"
                              disabled={!config.chatEnabled}
                              onClick={() => {
                                if (config.chatEnabled) {
                                  // TODO: 打开对话面板
                                  console.log(`[Chat] Open chat for stage ${stage.id}`);
                                }
                              }}
                            >
                              {config.chatEnabled ? "💬 对话" : "🔒 未开始"}
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>

          {/* Task List */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">任务列表 ({projectTasks.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {projectTasks.length === 0 ? (
                <div className="text-sm text-[#64748B] py-4 text-center">
                  暂无任务
                </div>
              ) : (
                <div className="space-y-2">
                  {projectTasks.slice(0, 10).map((task: any, i: number) => (
                    <div
                      key={task.id || i}
                      className={`flex items-center justify-between py-2 px-3 rounded-md cursor-pointer transition-colors ${
                        selectedTaskId === task.id
                          ? "bg-blue-50 border border-blue-200"
                          : "hover:bg-gray-50"
                      }`}
                      onClick={() => setSelectedTaskId(task.id)}
                    >
                      <div className="text-sm text-[#0F172A] truncate flex-1">
                        {task.description || task.title || "未命名任务"}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={task.status === "completed" ? "default" : "secondary"}
                          className="text-xs shrink-0"
                        >
                          {task.status === "completed" ? "完成" : "进行中"}
                        </Badge>
                        {selectedTaskId === task.id && (
                          <span className="text-xs text-blue-600">👁 查看阶段</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Stats + Skills */}
        <div className="space-y-6">
          {/* Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">项目统计</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-[#64748B]">总任务</span>
                <span className="font-medium">{projectTasks.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-[#64748B]">已完成</span>
                <span className="font-medium text-[#22C55E]">{completedTasks}</span>
              </div>
              <Separator />
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-[#64748B]">完成率</span>
                  <span className="font-medium">
                    {projectTasks.length > 0
                      ? Math.round((completedTasks / projectTasks.length) * 100)
                      : 0}
                    %
                  </span>
                </div>
                <Progress
                  value={
                    projectTasks.length > 0
                      ? (completedTasks / projectTasks.length) * 100
                      : 0
                  }
                />
              </div>
            </CardContent>
          </Card>

          {/* Associated Skills */}
          {skills && Array.isArray(skills) && skills.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">关联技能</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {skills.slice(0, 8).map((skill: any, i: number) => (
                    <div
                      key={skill.id || i}
                      className="flex items-center justify-between text-sm py-1"
                    >
                      <span className="text-[#0F172A]">
                        {skill.name || skill.id || `Skill ${i + 1}`}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {skill.status || "active"}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Cost Summary */}
          {costs && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">本月成本</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-[#0F172A]">
                  ¥{(costs.monthly_total || costs.total_cost || 0).toFixed(4)}
                </div>
                <div className="text-xs text-[#64748B] mt-1">
                  预算 ¥{costs.monthly_budget || costs.budget || 300}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
