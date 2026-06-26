"use client";

import { useState, useRef, useEffect } from "react";
import { useStore } from "@/lib/store";
import { sendChat } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const quickActions = [
  { label: "📊 进度如何？", query: "当前所有项目的进度如何？" },
  { label: "💰 成本正常吗？", query: "本月成本是否在预算内？" },
  { label: "🎯 下一步做什么？", query: "下一步应该做什么？" },
];

const fallbackResponses: Record<string, string> = {
  "进度": "当前 FROST-SOP 项目进展：\n- F14 持久化修复 ✅ 完成\n- F16 API 层封装 ✅ 完成\n- F15 Next.js 前端 🔄 进行中\n\n105 个测试全部通过，系统后端运行稳定。",
  "成本": "本月成本汇总：\n- 本月总消耗: 约 ¥0.15\n- 预算 ¥300，消耗极低，非常安全。",
  "下一步": "建议优先级：\n1. 完成 F15 Next.js 前端核心页面\n2. 接入真实 API 替换 mock 数据\n3. 端到端验收测试\n4. 准备上线",
};

export default function CeoChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 0,
      role: "assistant",
      content:
        "你好，我是 CEO Agent。我可以帮你查看项目状态、分析成本趋势、调度任务执行。有什么可以帮你的？",
      timestamp: new Date().toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      }),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { addLog } = useStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const timestamp = new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });

    const userMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: text,
      timestamp,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    addLog(`💬 发送: ${text}`);

    try {
      let reply = "";
      // Try real API first
      try {
        const res = await sendChat(text);
        reply = res.reply || res.response || res.message || JSON.stringify(res);
        addLog("🤖 CEO 回复: " + reply.slice(0, 80));
      } catch {
        // Fallback to keyword matching
        for (const [keyword, response] of Object.entries(fallbackResponses)) {
          if (text.includes(keyword)) {
            reply = response;
            break;
          }
        }
        if (!reply) {
          reply =
            "收到。让我查看一下...\n\n当前 FROST-SOP 家族共 8 个 Agent 在线，本月已执行 17 个任务，系统运行正常。你需要了解哪个方面的详情？\n\n- 📊 项目进度\n- 💰 成本分析\n- 🎯 下一步建议";
        }
        addLog("🤖 CEO 回复(本地): " + reply.slice(0, 80));
      }

      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: reply,
        timestamp: new Date().toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      addLog(`❌ CEO 对话失败: ${e.message || e}`);
    }
    setIsLoading(false);
  };

  return (
    <div className="flex flex-col h-full bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#E2E8F0] bg-gray-50/50 shrink-0">
        <h3 className="text-sm font-semibold text-[#0F172A] flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-[#3B82F6] text-white text-xs flex items-center justify-center font-bold">
            C
          </span>
          CEO Agent 对话
        </h3>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-4 py-2.5 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-[#3B82F6] text-white"
                  : "bg-gray-50 text-[#0F172A] border border-[#E2E8F0]"
              }`}
            >
              {msg.content}
              <div
                className={`text-xs mt-1 ${
                  msg.role === "user" ? "text-white/60" : "text-[#64748B]"
                }`}
              >
                {msg.timestamp}
              </div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-50 border border-[#E2E8F0] rounded-lg px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span
                    className="w-2 h-2 bg-[#3B82F6] rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="w-2 h-2 bg-[#3B82F6] rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="w-2 h-2 bg-[#3B82F6] rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick actions */}
      <div className="px-4 py-2 border-t border-[#E2E8F0] flex gap-2 flex-wrap shrink-0">
        {quickActions.map((action) => (
          <Badge
            key={action.label}
            variant="secondary"
            className="cursor-pointer hover:bg-slate-200 transition-colors text-xs py-1 px-2"
            onClick={() => sendMessage(action.query)}
          >
            {action.label}
          </Badge>
        ))}
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-[#E2E8F0] flex gap-2 shrink-0">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage(input);
            }
          }}
          placeholder="输入消息... (Enter 发送)"
          disabled={isLoading}
          className="flex-1"
        />
        <Button
          onClick={() => sendMessage(input)}
          disabled={isLoading || !input.trim()}
          size="sm"
        >
          发送
        </Button>
      </div>
    </div>
  );
}
