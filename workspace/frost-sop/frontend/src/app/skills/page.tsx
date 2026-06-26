"use client";

import { useQuery } from "@tanstack/react-query";
import { getSkills } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function SkillsPage() {
  const { data: skills, isLoading } = useQuery({
    queryKey: ["skills"],
    queryFn: getSkills,
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-[#0F172A]">技能库</h1>
        <p className="text-sm text-[#64748B] mt-1">
          FROST-SOP 家族技能基因库
        </p>
      </div>

      {isLoading && (
        <div className="text-sm text-[#64748B] py-8 text-center">
          加载技能库...
        </div>
      )}

      {skills && Array.isArray(skills) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {skills.map((skill: any, i: number) => (
            <Card key={skill.id || i}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-medium text-sm text-[#0F172A]">
                      {skill.name || skill.id || `Skill ${i + 1}`}
                    </div>
                    {skill.description && (
                      <div className="text-xs text-[#64748B] mt-1 line-clamp-2">
                        {skill.description}
                      </div>
                    )}
                  </div>
                  <Badge
                    variant={
                      skill.status === "active" ? "default" : "secondary"
                    }
                    className="text-xs shrink-0"
                  >
                    {skill.status || "active"}
                  </Badge>
                </div>
                <div className="flex items-center gap-3 mt-3 text-xs text-[#64748B]">
                  {skill.version && <span>v{skill.version}</span>}
                  {skill.task_type && (
                    <Badge variant="outline" className="text-xs">
                      {skill.task_type}
                    </Badge>
                  )}
                  {skill.success_rate !== undefined && (
                    <span>成功率: {skill.success_rate}%</span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {(!skills || (Array.isArray(skills) && skills.length === 0)) && !isLoading && (
        <Card>
          <CardContent className="p-8 text-center text-sm text-[#64748B]">
            暂无技能数据，连接后端后将自动加载
          </CardContent>
        </Card>
      )}
    </div>
  );
}
