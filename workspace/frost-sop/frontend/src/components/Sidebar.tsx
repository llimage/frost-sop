"use client";

import { useQuery } from "@tanstack/react-query";
import { useStore } from "@/lib/store";
import { getProjects } from "@/lib/api";

export default function Sidebar() {
  const { currentProjectId, setProject } = useStore();

  const { data: projects, isLoading, error } = useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
  });

  return (
    <aside className="w-56 shrink-0 border-r border-[#E2E8F0] bg-white overflow-y-auto hidden lg:block">
      <div className="p-4">
        {/* Section header */}
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
            项目列表
          </h2>
          <button
            className="text-[#64748B] hover:text-[#3B82F6] transition-colors"
            title="新建项目"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>

        {/* Project list */}
        {isLoading && (
          <div className="text-sm text-[#64748B] py-4 text-center">加载中...</div>
        )}
        {error && (
          <div className="text-sm text-red-500 py-4 text-center">加载失败</div>
        )}
        {projects && (
          <ul className="space-y-1">
            {Array.isArray(projects) && projects.map((project: any) => {
              const isActive = currentProjectId === project.id;
              return (
                <li key={project.id}>
                  <button
                    onClick={() => setProject(project.id)}
                    className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700 font-medium"
                        : "text-[#0F172A] hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="truncate">{project.name}</span>
                      <span
                        className={`w-2 h-2 rounded-full shrink-0 ${
                          project.status === "active"
                            ? "bg-[#22C55E]"
                            : project.status === "paused"
                            ? "bg-[#F59E0B]"
                            : "bg-[#64748B]"
                        }`}
                      />
                    </div>
                    {project.task_count !== undefined && (
                      <div className="text-xs text-[#64748B] mt-0.5">
                        {project.task_count} 个任务
                      </div>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {projects && (!Array.isArray(projects) || projects.length === 0) && (
          <div className="text-sm text-[#64748B] py-4 text-center">暂无项目</div>
        )}
      </div>

      {/* Quick stats */}
      <div className="border-t border-[#E2E8F0] p-4">
        <h2 className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-3">
          快速概览
        </h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-[#64748B]">活跃项目</span>
            <span className="font-medium text-[#0F172A]">
              {projects ? projects.filter((p: any) => p.status === "active").length : "-"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#64748B]">本月任务</span>
            <span className="font-medium text-[#0F172A]">
              {projects
                ? projects.reduce((sum: number, p: any) => sum + (p.task_count || 0), 0)
                : "-"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#64748B]">系统状态</span>
            <span className="font-medium text-[#22C55E]">正常</span>
          </div>
        </div>
      </div>

      {/* Panel 演示链接 */}
      <div className="border-t border-[#E2E8F0] p-4">
        <a
          href="/panels"
          className="flex items-center gap-2 text-sm text-[#64748B] hover:text-[#3B82F6] transition-colors"
        >
          🔮 V5.0 Panel 演示
        </a>
      </div>
    </aside>
  );
}
