"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getProject, getTasks, getSkills, getCosts } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: "进行中", color: "bg-[#22C55E]" },
  paused: { label: "暂停", color: "bg-[#F59E0B]" },
  completed: { label: "已完成", color: "bg-[#64748B]" },
};

const sopStages = ["需求分析", "架构设计", "代码实现", "测试验证", "部署交付"];

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: tasks } = useQuery({
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

  if (isLoading) {
    return (
      <div className="text-center py-12 text-[#64748B]">
        加载项目详情...
      </div>
    );
  }

  const projectTasks = tasks?.filter((t: any) => t.project_id === projectId) || [];
  const completedTasks = projectTasks.filter((t: any) => t.status === "completed").length;

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
        {/* Left: SOP Progress + Outputs */}
        <div className="lg:col-span-2 space-y-6">
          {/* SOP Progress Timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">SOP 进度时间线</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {sopStages.map((stage, i) => {
                const isCompleted = i < Math.ceil(completedTasks * 5 / Math.max(projectTasks.length, 1));
                const isCurrent = i === Math.ceil(completedTasks * 5 / Math.max(projectTasks.length, 1));
                return (
                  <div key={stage} className="flex items-start gap-4">
                    <div className="flex flex-col items-center">
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium shrink-0 ${
                          isCompleted
                            ? "bg-[#22C55E] text-white"
                            : isCurrent
                            ? "bg-[#3B82F6] text-white"
                            : "bg-gray-100 text-[#64748B]"
                        }`}
                      >
                        {isCompleted ? "✓" : i + 1}
                      </div>
                      {i < sopStages.length - 1 && (
                        <div
                          className={`w-0.5 h-8 my-1 ${
                            isCompleted ? "bg-[#22C55E]" : "bg-gray-200"
                          }`}
                        />
                      )}
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="font-medium text-sm text-[#0F172A]">{stage}</div>
                      <div className="text-xs text-[#64748B]">
                        {isCompleted
                          ? "已完成"
                          : isCurrent
                          ? "进行中..."
                          : "等待中"}
                      </div>
                    </div>
                  </div>
                );
              })}
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
                      className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-gray-50"
                    >
                      <div className="text-sm text-[#0F172A] truncate flex-1">
                        {task.description || task.title || "未命名任务"}
                      </div>
                      <Badge
                        variant={task.status === "completed" ? "default" : "secondary"}
                        className="text-xs shrink-0 ml-2"
                      >
                        {task.status === "completed" ? "完成" : "进行中"}
                      </Badge>
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
