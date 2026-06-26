"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSchedules, createSchedule } from "@/lib/api";
import { useStore } from "@/lib/store";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function SchedulePage() {
  const { data: schedules, isLoading, refetch } = useQuery({
    queryKey: ["schedules"],
    queryFn: getSchedules,
  });

  const [form, setForm] = useState({ title: "", start_time: "", end_time: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { addLog } = useStore();

  const handleSubmit = async () => {
    if (!form.title.trim()) return;
    setIsSubmitting(true);
    try {
      await createSchedule({
        title: form.title,
        start_time: form.start_time || new Date().toISOString(),
        end_time: form.end_time || new Date().toISOString(),
      });
      addLog(`📅 日程已创建: ${form.title}`);
      setForm({ title: "", start_time: "", end_time: "" });
      refetch();
    } catch (e: any) {
      addLog(`❌ 创建日程失败: ${e.message || e}`);
    }
    setIsSubmitting(false);
  };

  // Fallback mock data
  const displaySchedules =
    schedules && Array.isArray(schedules) && schedules.length > 0
      ? schedules
      : [
          { id: "1", title: "F15 前端重构启动", start_time: "2026-06-25T09:00", end_time: "2026-06-25T18:00" },
          { id: "2", title: "周度回顾会议", start_time: "2026-06-26T14:00", end_time: "2026-06-26T15:00" },
          { id: "3", title: "成本审查", start_time: "2026-06-27T10:00", end_time: "2026-06-27T11:00" },
        ];

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">日程管理</h1>
          <p className="text-sm text-[#64748B] mt-1">管理你的项目和任务日程</p>
        </div>
      </div>

      {/* New Schedule Form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">新增日程</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-3">
            <Input
              placeholder="日程标题"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="flex-1"
            />
            <div className="flex gap-2">
              <Input
                type="datetime-local"
                value={form.start_time}
                onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                className="w-auto text-sm"
              />
              <Input
                type="datetime-local"
                value={form.end_time}
                onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                className="w-auto text-sm"
              />
            </div>
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting || !form.title.trim()}
              className="shrink-0"
            >
              {isSubmitting ? "创建中..." : "创建"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Schedule List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            日程列表
            {displaySchedules && (
              <Badge variant="secondary" className="ml-2 text-xs">
                {displaySchedules.length} 项
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="text-sm text-[#64748B] py-4 text-center">
              加载日程...
            </div>
          )}
          {displaySchedules.length === 0 ? (
            <div className="text-sm text-[#64748B] py-8 text-center">
              暂无日程，请创建新日程
            </div>
          ) : (
            <div className="space-y-1">
              {displaySchedules.map((item: any, i: number) => {
                const startDate = item.start_time
                  ? new Date(item.start_time)
                  : null;
                const endDate = item.end_time
                  ? new Date(item.end_time)
                  : null;
                return (
                  <div key={item.id || i}>
                    <div className="flex items-center justify-between py-3 px-3 rounded-md hover:bg-gray-50">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600 font-semibold text-sm shrink-0">
                          {startDate
                            ? startDate.getDate()
                            : "?"}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-[#0F172A]">
                            {item.title}
                          </div>
                          <div className="text-xs text-[#64748B]">
                            {startDate
                              ? startDate.toLocaleString("zh-CN", {
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : "未指定"}
                            {endDate && (
                              <>
                                {" — "}
                                {endDate.toLocaleString("zh-CN", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {startDate && startDate > new Date()
                          ? "即将"
                          : "已过"}
                      </Badge>
                    </div>
                    {i < displaySchedules.length - 1 && <Separator />}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
