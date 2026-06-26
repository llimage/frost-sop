"use client";

import { useEffect, useRef } from "react";
import { useStore } from "@/lib/store";
import { ScrollArea } from "@/components/ui/scroll-area";

const levelIcons: Record<string, string> = {
  info: "ℹ️",
  warn: "⚠️",
  error: "❌",
  success: "✅",
};

const levelColors: Record<string, string> = {
  info: "text-slate-400",
  warn: "text-yellow-400",
  error: "text-red-400",
  success: "text-green-400",
};

export default function LogTerminal({ title = "实时日志" }: { title?: string }) {
  const { logs, clearLogs } = useStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="bg-[#0F172A] text-slate-300 rounded-lg overflow-hidden border border-gray-700 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800/50 border-b border-gray-700 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-[#22C55E]" />
          <span className="text-xs text-gray-400 font-medium tracking-wide">
            {title}
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>{logs.length} 条</span>
          <button
            className="hover:text-gray-300 transition-colors"
            onClick={clearLogs}
            title="清空日志"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Logs */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-1 font-mono text-xs leading-relaxed">
          {logs.length === 0 && (
            <div className="text-gray-600 text-center py-8">
              暂无日志，执行任务后将自动显示
            </div>
          )}
          {logs.map((log, i) => {
            // Parse level from log format: [HH:MM:SS] message
            const isError = log.includes("❌") || log.includes("失败");
            const isSuccess = log.includes("✅") || log.includes("完成") || log.includes("成功");
            const isWarn = log.includes("⚠️");

            let level: string;
            if (isError) level = "error";
            else if (isWarn) level = "warn";
            else if (isSuccess) level = "success";
            else level = "info";

            return (
              <div key={i} className="flex gap-2 hover:bg-white/5 px-1 rounded py-0.5">
                <span className={levelColors[level] || "text-slate-400"}>
                  {levelIcons[level] || "•"}
                </span>
                <span className="text-slate-300 break-all">{log}</span>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
    </div>
  );
}
